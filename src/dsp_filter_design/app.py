import os
import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import dsp_filter_design.dsp_utils as dsp
import numpy as np

# --- Constants ---
LIGO_PURPLE = "#593196"
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

        # ROC Toggle
        html.Label("Highlight Region (Stability)"),
        dbc.RadioItems(
            id="roc-radio",
            options=[
                {"label": "Causal", "value": "causal"},
                {"label": "Anti-Causal", "value": "anticausal"},
                {"label": "Off", "value": "off"}
            ],
            value="causal",
            inline=True,
            className="mb-3"
        ),

        # Buttons
        dbc.Row([
            dbc.Col(dbc.Button("Add Pole", id="btn-add-p", outline=True, color="danger",
                               size="sm", className="w-100"), width=6),
            dbc.Col(dbc.Button("Rem Pole", id="btn-rem-p", outline=True, color="danger",
                               size="sm", className="w-100"), width=6),
        ], className="mb-2"),
        dbc.Row([
            dbc.Col(
                dbc.Button("Add Zero", id="btn-add-z", outline=True, color="primary",
                           size="sm", className="w-100"), width=6),
            dbc.Col(
                dbc.Button("Rem Zero", id="btn-rem-z", outline=True, color="primary",
                           size="sm", className="w-100"), width=6),
        ], className="mb-2"),

        dbc.Button("Reset All", id="btn-reset", outline=True, color="secondary",
                   size="sm", className="w-100"),

    ])
], className="h-100 shadow-sm")

plots_col = html.Div([
    dbc.Row([
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

# 1. Update Input Defaults based on Domain
@app.callback(
    Output("cut1-in", "value"),
    Output("cut2-in", "disabled"),
    Input("domain-radio", "value"),
    Input("type-dd", "value"),
    State("cut1-in", "value")
)
def update_defaults(domain, ftype, current_c1):
    ctx = callback_context
    trigger = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else "init"

    # Enable/Disable 2nd cutoff
    c2_disabled = ftype not in ["bandpass", "bandstop"]

    # Smart Default for Cutoff 1
    new_c1 = current_c1
    if trigger == "domain-radio":
        if domain == "digital":
            # Switch to normalized freq (0.25 is a nice visual default)
            new_c1 = 0.25
        else:
            # Switch to rad/s
            new_c1 = 1.0

    return new_c1, c2_disabled


# 2. Main Logic: Update Filter State
@app.callback(
    Output("filter-state", "data"),
    Input("family-dd", "value"), Input("type-dd", "value"),
    Input("order-in", "value"),
    Input("cut1-in", "value"), Input("cut2-in", "value"),
    Input("btn-add-p", "n_clicks"), Input("btn-add-z", "n_clicks"),
    Input("btn-rem-p", "n_clicks"), Input("btn-rem-z", "n_clicks"),
    Input("btn-reset", "n_clicks"),
    Input("pz-plot", "relayoutData"),
    State("domain-radio", "value"),
    State("filter-state", "data")
)
def update_filter_state(fam, ftype, order, c1, c2,
                        add_p, add_z, rem_p, rem_z, btn_rst,
                        relayout, domain, current_data):
    ctx = callback_context
    trigger = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else "init"

    poles = [complex(p[0], p[1]) for p in current_data.get("poles", [])]
    zeros = [complex(z[0], z[1]) for z in current_data.get("zeros", [])]
    gain = current_data.get("gain", 1.0)

    # Design Triggers
    design_triggers = ["family-dd", "type-dd", "order-in", "cut1-in", "cut2-in",
                       "btn-reset"]

    if trigger in design_triggers or trigger == "init":
        if fam != "Custom":
            z, p, k = dsp.design_filter(fam, ftype, order, domain, c1, c2)
            zeros, poles, gain = list(z), list(p), float(k)
        elif trigger == "btn-reset":
            zeros, poles, gain = [], [], 1.0

    # Manual Add
    if trigger == "btn-add-p":
        poles.append(complex(-0.5, 0.5) if domain == "analog" else complex(0.5, 0.5))
    if trigger == "btn-add-z":
        zeros.append(complex(0, 0.5) if domain == "analog" else complex(0, 0.5))

    # Manual Remove
    if trigger == "btn-rem-p" and poles:
        poles.pop()
    if trigger == "btn-rem-z" and zeros:
        zeros.pop()

    # Dragging
    if trigger == "pz-plot" and relayout:
        offset = 1 if domain == "digital" else 0
        n_zeros = len(zeros)

        for key, val in relayout.items():
            if "shapes[" in key:
                try:
                    shape_idx = int(key.split("[")[1].split("]")[0])
                    attr = key.split(".")[-1]
                    logic_idx = shape_idx - offset
                    radius = 0.05

                    if 0 <= logic_idx < n_zeros:
                        curr_z = zeros[logic_idx]
                        if attr == "x0":
                            zeros[logic_idx] = complex(val + radius, curr_z.imag)
                        elif attr == "x1":
                            zeros[logic_idx] = complex(val - radius, curr_z.imag)
                        elif attr == "y0":
                            zeros[logic_idx] = complex(curr_z.real, val + radius)
                        elif attr == "y1":
                            zeros[logic_idx] = complex(curr_z.real, val - radius)

                    elif logic_idx >= n_zeros:
                        p_idx = logic_idx - n_zeros
                        if p_idx < len(poles):
                            curr_p = poles[p_idx]
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


# 3. Update Plots
@app.callback(
    Output("pz-plot", "figure"), Output("bode-plot", "figure"),
    Output("impulse-plot", "figure"),
    Input("filter-state", "data"), Input("domain-radio", "value"),
    Input("roc-radio", "value")
)
def update_plots(data, domain, roc_mode):
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

    # -- P/Z Map --
    shapes = []

    # 1. Background Regions (Stability/Causality)
    if roc_mode != "off":
        if domain == "analog":
            if roc_mode == "causal":
                # Green Left Half Plane
                shapes.append({
                    "type": "rect", "x0": -100, "x1": 0, "y0": -100, "y1": 100,
                    "fillcolor": "rgba(0, 255, 0, 0.1)", "line": {"width": 0},
                    "layer": "below", "editable": False
                })
            else:
                # Red Right Half Plane
                shapes.append({
                    "type": "rect", "x0": 0, "x1": 100, "y0": -100, "y1": 100,
                    "fillcolor": "rgba(255, 0, 0, 0.1)", "line": {"width": 0},
                    "layer": "below", "editable": False
                })
        else:  # Digital
            if roc_mode == "causal":
                # Green Inside Unit Circle
                shapes.append({
                    "type": "circle", "x0": -1, "x1": 1, "y0": -1, "y1": 1,
                    "fillcolor": "rgba(0, 255, 0, 0.1)", "line": {"width": 0},
                    "layer": "below", "editable": False
                })
            else:
                # Red Outside Unit Circle (Donut)
                # Outer Box (CCW) + Inner Circle (CW) = Hole
                path_str = "M -100 -100 L 100 -100 L 100 100 L -100 100 Z M 1 0 A 1 1 0 0 1 -1 0 A 1 1 0 0 1 1 0 Z"
                shapes.append({
                    "type": "path", "path": path_str,
                    "fillcolor": "rgba(255, 0, 0, 0.1)", "line": {"width": 0},
                    "layer": "below", "editable": False
                })

    # 2. Reference Lines
    if domain == "digital":
        shapes.append({
            "type": "circle", "x0": -1, "x1": 1, "y0": -1, "y1": 1,
            "line": {"dash": "dot", "color": "gray"}, "editable": False
        })
    else:
        shapes.append({
            "type": "line", "x0": 0, "x1": 0, "y0": -100, "y1": 100,
            "line": {"color": "gray", "width": 1}, "editable": False
        })

    # 3. Zeros (Blue)
    radius = 0.05
    for z in zeros:
        shapes.append({
            "type": "circle",
            "x0": z.real - radius, "x1": z.real + radius,
            "y0": z.imag - radius, "y1": z.imag + radius,
            "line": {"color": "blue", "width": 2},
            "fillcolor": "rgba(0, 0, 255, 0.1)"
        })

    # 4. Poles (Red)
    for p in poles:
        shapes.append({
            "type": "circle",
            "x0": p.real - radius, "x1": p.real + radius,
            "y0": p.imag - radius, "y1": p.imag + radius,
            "line": {"color": "red", "width": 2},
            "fillcolor": "rgba(255, 0, 0, 0.1)"
        })

    pz_fig = {
        "data": [{"x": [-2, 2], "y": [-2, 2], "mode": "markers", "opacity": 0}],
        "layout": {
            "title": "Pole-Zero Map",
            "xaxis": {"range": [-2, 2], "title": "Real", "zeroline": False},
            "yaxis": {"range": [-2, 2], "scaleanchor": "x", "scaleratio": 1,
                      "title": "Imaginary", "zeroline": False},
            "shapes": shapes,
            "margin": {"l": 40, "r": 40, "t": 40, "b": 40},
            "dragmode": "select"
        }
    }

    # -- Impulse --
    if y is None:
        imp_fig = {
            "data": [],
            "layout": {
                "title": "Impulse Response",
                "margin": {"l": 40, "r": 20, "t": 40, "b": 40},
                "xaxis": {"visible": False}, "yaxis": {"visible": False},
                "annotations": [{
                    "text": "IMPROPER TRANSFER FUNCTION<br>(Zeros > Poles)<br>Cannot compute impulse.",
                    "xref": "paper", "yref": "paper", "showarrow": False,
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
