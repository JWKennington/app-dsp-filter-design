import os
import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import dsp_filter_design.dsp_utils as dsp
import numpy as np

# --- Constants ---
# --- Constants ---
LSC_BLUE = "#003262"  # Professional LSC Blue

CONFIG_PLOT = {
    "displayModeBar": False,
    "editable": True,  # Must be True for dragging shapes
    "edits": {
        "annotationPosition": False,
        "annotationTail": False,
        "annotationText": False,
        "axisTitleText": False,
        "colorbarPosition": False,
        "colorbarTitleText": False,
        "legendPosition": False,
        "legendText": False,
        "shapePosition": True,  # Allow dragging!
        "titleText": False      # Prevent title editing
    },
    "modeBarButtonsToRemove": ["toImage", "sendDataToCloud", "pan2d", "select2d", "lasso2d", "zoomIn2d", "zoomOut2d", "autoScale2d", "resetScale2d"]
}

# --- App Initialization ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.LUX])
app.title = "DSP Explorer"
server = app.server

# --- Layout Components ---
header = dbc.Navbar(
    dbc.Container(
        [
            html.A(
                dbc.Row(
                    [
                        dbc.Col(html.Img(src="/assets/lsc-logo-small.png", height="40px")),
                        dbc.Col(dbc.NavbarBrand("DSP Filter Design Explorer", className="ms-2")),
                    ],
                    align="center",
                    className="g-0",
                ),
                href="#",
                style={"textDecoration": "none"},
            ),
        ]
    ),
    color=LSC_BLUE,

    dark=True,
    className="mb-4",
)

explainer = dbc.Accordion(
    [
        dbc.AccordionItem(
            [
                html.P("This application serves as a pedagogical tool for exploring digital filter design principles."),
                html.P("Key Features:"),
                html.Ul([
                    html.Li("Visualize poles and zeros in both Analog (s-plane) and Digital (z-plane) domains."),
                    html.Li("Design common filters (Butterworth, Chebyshev, etc.) and observe their frequency and impulse responses."),
                    html.Li("Understand stability and causality regions (ROC) with interactive highlighting."),
                    html.Li("Compare 'Causal' vs 'Anti-Causal' system behaviors.")
                ]),
                html.P("Use the control panel on the left to configure your filter, and drag poles/zeros on the chart to fine-tune your design."),
            ],
            title="About this App (How to Use)",
        ),
    ],
    start_collapsed=True,
    className="mb-4",
)

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
        dbc.Col(dbc.Card([
            dbc.CardHeader("Pole-Zero Map", className="p-1 text-center"),
            dbc.CardBody(dcc.Graph(id="pz-plot", config=CONFIG_PLOT), className="p-0")
        ]), md=6),
        dbc.Col(dbc.Card([
            dbc.CardHeader("Bode Plot", className="p-1 text-center"),
            dbc.CardBody(dcc.Graph(id="bode-plot", config=CONFIG_PLOT), className="p-0")
        ]), md=6),
    ], className="mb-2 g-2"),
    dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardHeader("Impulse Response", className="p-1 text-center"),
            dbc.CardBody(dcc.Graph(id="impulse-plot", config=CONFIG_PLOT), className="p-0")
        ]), width=12)
    ], className="g-2")
])




footer = html.Footer(
    dbc.Container(
        [
            html.Hr(),
            html.P("© 2026 James Kennington. All Rights Reserved.", className="text-center text-muted"),
        ],
        fluid=True,
    ),
    className="mt-5"
)

app.layout = dbc.Container([
    header,
    explainer,
    dbc.Row([
        dbc.Col(control_panel, md=3),
        dbc.Col(plots_col, md=9)
    ]),
    footer,
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

    c2_disabled = ftype not in ["bandpass", "bandstop"]

    new_c1 = current_c1
    if trigger == "domain-radio":
        if domain == "digital":
            # Switch to normalized freq
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
    State("roc-radio", "value"), # Added for shape offset calculation
    State("filter-state", "data")
)
def update_filter_state(fam, ftype, order, c1, c2,
                        add_p, add_z, rem_p, rem_z, btn_rst,
                        relayout, domain, roc_mode, current_data):
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
        # Calculate Offset for Background Shapes
        # 1. Stability Region (if enabled) -> 1 shape
        # 2. Reference Line -> 1 shape
        # offset = (1 if roc_mode != "off" else 0) + 1
        offset = 1 + (1 if roc_mode != "off" else 0)
        
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


# 3a. Update Response Plots (Bode + Impulse)
# Depends on: Filter State, Domain
@app.callback(
    Output("bode-plot", "figure"), Output("impulse-plot", "figure"),
    Input("filter-state", "data"), Input("domain-radio", "value")
)
def update_response_plots(data, domain):
    poles = dsp.to_complex_array(data["poles"])
    zeros = dsp.to_complex_array(data["zeros"])
    gain = data["gain"]

    w, mag, phase, t, y = dsp.compute_responses(zeros, poles, gain, domain)

    # -- Bode --
    bode_fig = {
        "data": [
            {"x": w, "y": mag, "name": "Mag", "line": {"color": LSC_BLUE}},

            {"x": w, "y": phase, "name": "Phase", "yaxis": "y2",
             "line": {"color": "orange", "dash": "dot"}}
        ],
        "layout": {
            "title": "Bode Plot",
            "height": 300,
            "font": {"color": "black"},
            "xaxis": {"type": "log" if domain == "analog" else "linear",
                      "title": {"text": "Frequency"}, "automargin": True},
            "yaxis": {"title": {"text": "Magnitude (dB)"}, "automargin": True},
            "yaxis2": {"title": {"text": "Phase (deg)"}, "overlaying": "y", "side": "right", "automargin": True},
            "margin": {"l": 50, "r": 50, "t": 30, "b": 30},
            "legend": {"x": 1, "y": 1}
        }
    }

    # -- Impulse --
    if y is None:
        imp_fig = {
            "data": [],
            "layout": {
                "title": "Impulse Response",
                "height": 250,
                "margin": {"l": 40, "r": 20, "t": 40, "b": 40},
                "xaxis": {"visible": False}, "yaxis": {"visible": False},
                "annotations": [{
                    "text": "IMPROPER TRANSFER FUNCTION<br>(Zeros > Poles)<br>Cannot "
                            "compute impulse.",
                    "xref": "paper", "yref": "paper", "showarrow": False,
                    "font": {"size": 14, "color": "red"}
                }]
            }
        }
    else:
        # Determine range for better visualization
        t_min = np.min(t) if len(t) > 0 else 0.0
        t_max = np.max(t) if len(t) > 0 else 1.0
        
        # Add padding
        pad = (t_max - t_min) * 0.05
        x_range = [t_min - pad, t_max + pad]

        imp_fig = {
            "data": [
                {"x": t, "y": y, "type": "bar" if domain == "digital" else "scatter",
                 "marker": {"color": "#333"}}],
            "layout": {
                "title": "Impulse Response",
                "height": 250,
                "font": {"color": "black"},
                "margin": {"l": 60, "r": 20, "t": 30, "b": 40},
                "xaxis": {
                    "title": {"text": "Time (s)" if domain == "analog" else "Samples"},
                    "range": x_range,
                    "automargin": True
                },
                "yaxis": {"title": {"text": "Amplitude"}, "automargin": True},
                "shapes": [
                    {
                        "type": "line",
                        "x0": 0, "x1": 0,
                        "y0": 0, "y1": 1,
                        "xref": "x", "yref": "paper",
                        "line": {"color": "gray", "width": 1.5, "dash": "dash"}
                    }
                ]
            }
        }

    return bode_fig, imp_fig


# 3b. Update P/Z Map
# Depends on: Filter State, Domain, ROC Toggle
@app.callback(
    Output("pz-plot", "figure"),
    Input("filter-state", "data"), Input("domain-radio", "value"),
    Input("roc-radio", "value")
)
def update_pz_map(data, domain, roc_mode):
    poles = dsp.to_complex_array(data["poles"])
    zeros = dsp.to_complex_array(data["zeros"])
    
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
                # Red Outside Unit Circle (Donut Hole)
                # Method: Polygon Approximation + Bridge Path
                # SVG Arcs can be flaky with winding rules in some renderers.
                # A robust solution is to approximate the circle with a polygon (e.g. 64 sides)
                # and use the same bridge topology.
                #
                # Path: Outer Box (CCW) -> Bridge In -> Inner Circle (CW Polygon) -> Bridge Out -> Close

                # 1. Outer Box (CCW)
                # (-20,-20) -> (20,-20) -> (20,20) -> (-20,20) -> (-20,-20)
                outer = "M -20 -20 L 20 -20 L 20 20 L -20 20 L -20 -20"

                # 2. Bridge In: From (-20, -20) to Top of Circle (0, 1)
                bridge_in = "L 0 1"

                # 3. Inner Circle Polygon (CW)
                # Start at (0, 1), go CW to (0, 1)
                # 64 segments = sufficient resolution for visual circle
                angles = np.linspace(np.pi/2, -3*np.pi/2, 65) # 65 points for 64 segments (start==end)
                circle_pts = []
                for theta in angles[1:]: # Skip first point (0,1) as bridge_in lands there
                    x = np.cos(theta)
                    y = np.sin(theta)
                    circle_pts.append(f"L {x:.5f} {y:.5f}")
                
                inner_poly = " ".join(circle_pts)

                # 4. Bridge Out: From Top of Circle (0, 1) back to start (-20, -20)
                bridge_out = "L -20 -20"

                path_str = f"{outer} {bridge_in} {inner_poly} {bridge_out} Z"

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
            "height": 300,
            "font": {"color": "black"},
            "xaxis": {"range": [-2, 2], "title": {"text": "Real"}, "zeroline": False},
            "yaxis": {"range": [-2, 2], "scaleanchor": "x", "scaleratio": 1,
                      "title": {"text": "Imaginary"}, "zeroline": False},
            "shapes": shapes,
            "margin": {"l": 40, "r": 40, "t": 30, "b": 30},
            "dragmode": "select"
        }
    }

    return pz_fig


def main():
    debug_mode = os.environ.get("DASH_DEBUG", "False") == "True"
    app.run(debug=debug_mode, port=8050)


if __name__ == "__main__":
    main()
