import os
import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import dsp_filter_design.dsp_utils as dsp
import numpy as np

# --- Constants ---
LIGO_PURPLE = "#593196"
# "editable": True is CRITICAL for dragging shapes
CONFIG_PLOT = {"displayModeBar": False, "responsive": True, "editable": True}

# --- App Initialization ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.LUX])
app.title = "DSP Explorer"
server = app.server

# --- Layout Components ---
control_panel = dbc.Card([
    dbc.CardHeader("Filter Design Parameters"),
    dbc.CardBody([
        dbc.Row([
            dbc.Col([
                html.Label("Domain"),
                dbc.RadioItems(
                    id="domain-radio",
                    options=[{"label": "Analog (s)", "value": "analog"},
                             {"label": "Digital (z)", "value": "digital"}],
                    value="analog",
                    inputClassName="btn-check",
                    labelClassName="btn btn-outline-primary btn-sm",
                    labelCheckedClassName="active"
                ),
            ], width=12, className="mb-3"),

            dbc.Col([
                html.Label("Family"),
                dcc.Dropdown(
                    id="family-dd",
                    options=["Butterworth", "Chebyshev I", "Chebyshev II", "Elliptic",
                             "Bessel", "Custom"],
                    value="Butterworth", clearable=False
                )
            ], width=6),
            dbc.Col([
                html.Label("Type"),
                dcc.Dropdown(
                    id="type-dd",
                    options=[
                        {"label": "Lowpass", "value": "low"},
                        {"label": "Highpass", "value": "high"},
                        {"label": "Bandpass", "value": "bandpass"},
                        {"label": "Bandstop", "value": "bandstop"}
                    ],
                    value="low", clearable=False
                )
            ], width=6),
        ], className="mb-2"),

        dbc.Row([
            dbc.Col([
                html.Label("Order"),
                dbc.Input(id="order-in", type="number", value=4, min=1, step=1)
            ], width=4),
            dbc.Col([
                html.Label("Cutoff 1"),
                dbc.Input(id="cut1-in", type="number", value=1.0, step=0.1)
            ], width=4),
            dbc.Col([
                html.Label("Cutoff 2"),
                dbc.Input(id="cut2-in", type="number", value=2.0, step=0.1,
                          disabled=True)
            ], width=4),
        ], className="mb-3"),

        html.Hr(),
        dbc.ButtonGroup([
            dbc.Button("Add Pole", id="btn-add-p", outline=True, color="danger",
                       size="sm"),
            dbc.Button("Add Zero", id="btn-add-z", outline=True, color="primary",
                       size="sm"),
            dbc.Button("Reset", id="btn-reset", outline=True, color="secondary",
                       size="sm"),
        ], className="w-100")
    ])
], className="h-100 shadow-sm")

plots_col = html.Div([
    dbc.Row([
        # Only pz-plot needs to be editable for dragging
        dbc.Col(dcc.Graph(id="pz-plot", config=CONFIG_PLOT, style={"height": "400px"}),
                md=6),
        dbc.Col(dcc.Graph(id="bode-plot", config={"displayModeBar": False},
                          style={"height": "400px"}), md=6),
    ]),
    dbc.Row([
        dbc.Col(dcc.Graph(id="impulse-plot", config={"displayModeBar": False},
                          style={"height": "250px"}), width=12)
    ])
])

app.layout = dbc.Container([
    dbc.NavbarSimple(brand="Digital Signal Processing Explorer", brand_href="#",
                     color="dark", dark=True, className="mb-4"),
    dbc.Row([
        dbc.Col(control_panel, md=3),
        dbc.Col(plots_col, md=9)
    ]),
    dcc.Store(id="filter-state", data={"poles": [], "zeros": [], "gain": 1.0})
], fluid=True, className="p-0")


# --- Callbacks ---
@app.callback(
    Output("cut2-in", "disabled"),
    Input("type-dd", "value")
)
def toggle_cutoff2(ftype):
    return ftype not in ["bandpass", "bandstop"]


@app.callback(
    Output("filter-state", "data"),
    Input("family-dd", "value"), Input("type-dd", "value"),
    Input("order-in", "value"), Input("domain-radio", "value"),
    Input("cut1-in", "value"), Input("cut2-in", "value"),
    Input("btn-add-p", "n_clicks"), Input("btn-add-z", "n_clicks"),
    Input("btn-reset", "n_clicks"),
    Input("pz-plot", "relayoutData"),
    State("filter-state", "data")
)
def update_filter_state(fam, ftype, order, domain, c1, c2, btn_p, btn_z, btn_rst,
                        relayout, current_data):
    ctx = callback_context
    trigger = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else "init"

    poles = [complex(p[0], p[1]) for p in current_data.get("poles", [])]
    zeros = [complex(z[0], z[1]) for z in current_data.get("zeros", [])]
    gain = current_data.get("gain", 1.0)

    # 1. Parameter Change -> Re-design
    design_triggers = ["family-dd", "type-dd", "order-in", "domain-radio", "cut1-in",
                       "cut2-in", "btn-reset"]
    if trigger in design_triggers or trigger == "init":
        if fam != "Custom":
            z, p, k = dsp.design_filter(fam, ftype, order, domain, c1, c2)
            zeros, poles, gain = list(z), list(p), float(k)
        elif trigger == "btn-reset":
            zeros, poles, gain = [], [], 1.0

    # 2. Add Pole/Zero (Manual)
    if trigger == "btn-add-p":
        poles.append(complex(-0.5, 0.5) if domain == "analog" else complex(0.5, 0.5))
    if trigger == "btn-add-z":
        zeros.append(complex(0, 0.5) if domain == "analog" else complex(0, 0.5))

    # 3. Dragging on Plot (Relayout)
    # The crucial part: Logic to update coordinates based on shape drag
    if trigger == "pz-plot" and relayout:
        # relayoutData contains keys like 'shapes[2].x0'
        # shapes[0] is Unit Circle (if digital), then Zeros, then Poles

        # Determine index offset
        offset = 1 if domain == "digital" else 0
        n_zeros = len(zeros)

        for key, val in relayout.items():
            if "shapes[" in key:
                # Extract shape index
                try:
                    shape_idx = int(key.split("[")[1].split("]")[0])
                    attr = key.split(".")[-1]  # x0, x1, y0, y1

                    # Calculate Logic Index
                    logic_idx = shape_idx - offset

                    # Is it a Zero? (0 to n_zeros - 1)
                    if 0 <= logic_idx < n_zeros:
                        curr_z = zeros[logic_idx]
                        radius = 0.05
                        if attr == "x0":
                            zeros[logic_idx] = complex(val + radius, curr_z.imag)
                        elif attr == "x1":
                            zeros[logic_idx] = complex(val - radius, curr_z.imag)
                        elif attr == "y0":
                            zeros[logic_idx] = complex(curr_z.real, val + radius)
                        elif attr == "y1":
                            zeros[logic_idx] = complex(curr_z.real, val - radius)

                    # Is it a Pole? (n_zeros to n_zeros + n_poles - 1)
                    elif logic_idx >= n_zeros:
                        p_idx = logic_idx - n_zeros
                        if p_idx < len(poles):
                            curr_p = poles[p_idx]
                            radius = 0.05
                            if attr == "x0":
                                poles[p_idx] = complex(val + radius, curr_p.imag)
                            elif attr == "x1":
                                poles[p_idx] = complex(val - radius, curr_p.imag)
                            elif attr == "y0":
                                poles[p_idx] = complex(curr_p.real, val + radius)
                            elif attr == "y1":
                                poles[p_idx] = complex(curr_p.real, val - radius)

                except Exception as e:
                    print(f"Drag parse error: {e}")

    return dsp.sanitize_json({
        "poles": [[p.real, p.imag] for p in poles],
        "zeros": [[z.real, z.imag] for z in zeros],
        "gain": gain
    })


@app.callback(
    Output("pz-plot", "figure"), Output("bode-plot", "figure"),
    Output("impulse-plot", "figure"),
    Input("filter-state", "data"), Input("domain-radio", "value")
)
def update_plots(data, domain):
    poles = dsp.to_complex_array(data["poles"])
    zeros = dsp.to_complex_array(data["zeros"])
    gain = data["gain"]

    w, mag, phase, t, y = dsp.compute_responses(zeros, poles, gain, domain)

    # -- Bode --
    bode_fig = {
        "data": [
            {"x": w, "y": mag, "name": "Mag", "line": {"color": LIGO_PURPLE}},
            {"x": w, "y": phase, "name": "Phase", "yaxis": "y2",
             "line": {"color": "orange", "dash": "dot"}}
        ],
        "layout": {
            "title": "Bode Plot",
            "xaxis": {"type": "log" if domain == "analog" else "linear",
                      "title": "Frequency"},
            "yaxis": {"title": "Magnitude (dB)"},
            "yaxis2": {"title": "Phase (deg)", "overlaying": "y", "side": "right"},
            "margin": {"l": 50, "r": 50, "t": 40, "b": 40}
        }
    }

    # -- P/Z Map (Using Shapes for Draggability) --
    shapes = []

    # 1. Unit Circle (if Digital) - locked
    if domain == "digital":
        shapes.append({
            "type": "circle", "x0": -1, "x1": 1, "y0": -1, "y1": 1,
            "line": {"dash": "dot", "color": "gray"}, "editable": False
        })

    # 2. Zeros (Blue Circles)
    radius = 0.05
    for z in zeros:
        shapes.append({
            "type": "circle",
            "x0": z.real - radius, "x1": z.real + radius,
            "y0": z.imag - radius, "y1": z.imag + radius,
            "line": {"color": "blue", "width": 2},
            "fillcolor": "rgba(0, 0, 255, 0.1)"
        })

    # 3. Poles (Red Circles)
    for p in poles:
        shapes.append({
            "type": "circle",
            "x0": p.real - radius, "x1": p.real + radius,
            "y0": p.imag - radius, "y1": p.imag + radius,
            "line": {"color": "red", "width": 2},
            "fillcolor": "rgba(255, 0, 0, 0.1)"
        })

    pz_fig = {
        "data": [
            # Dummy trace to set axis range, otherwise shapes might not define range
            # well
            {"x": [-2, 2], "y": [-2, 2], "mode": "markers", "opacity": 0}
        ],
        "layout": {
            "title": "Pole-Zero Map (Drag Shapes)",
            "xaxis": {"range": [-2, 2], "title": "Real"},
            "yaxis": {"range": [-2, 2], "scaleanchor": "x", "scaleratio": 1,
                      "title": "Imaginary"},
            "shapes": shapes,
            "margin": {"l": 40, "r": 40, "t": 40, "b": 40},
            "dragmode": "select"  # Helps prevent zooming when trying to drag
        }
    }

    # -- Impulse --
    if y is None:
        # ERROR STATE: Display Warning
        imp_fig = {
            "data": [],
            "layout": {
                "title": "Impulse Response",
                "margin": {"l": 40, "r": 20, "t": 40, "b": 40},
                "xaxis": {"visible": False},
                "yaxis": {"visible": False},
                "annotations": [{
                    "text": "IMPROPER TRANSFER FUNCTION<br>(Zeros > Poles)<br>Cannot "
                            "compute impulse.",
                    "xref": "paper", "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 14, "color": "red"}
                }]
            }
        }
    else:
        imp_fig = {
            "data": [
                {"x": t, "y": y, "type": "bar" if domain == "digital" else "scatter",
                 "marker": {"color": "#333"}}],
            "layout": {"title": "Impulse Response",
                       "margin": {"l": 40, "r": 20, "t": 40, "b": 40}}
        }

    return pz_fig, bode_fig, imp_fig


def main():
    debug_mode = os.environ.get("DASH_DEBUG", "True") == "True"
    app.run(debug=debug_mode)


if __name__ == "__main__":
    main()
