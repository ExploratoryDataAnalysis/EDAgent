"""
Plotly figure builders.

Each function returns a plain JSON figure ({"data": [...], "layout": {...}}) that the React
front-end renders with Plotly and that the export service re-draws as PNG/SVG. Only the small
set of trace types used here (bar, scatter, heatmap, box, violin) is supported by the static
renderer, so new chart kinds should be added in both places.
"""

from typing import Any, Dict, List, Optional, Sequence

from app.schemas.analysis import ResultChart
from app.services.analysis.common import jsonable

PALETTE = ["#2563EB", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#06B6D4", "#EC4899", "#84CC16", "#F97316", "#64748B"]


def _layout(title: str, xlabel: str = "", ylabel: str = "", **extra: Any) -> Dict[str, Any]:
    layout: Dict[str, Any] = {
        "title": {"text": title, "font": {"size": 15}},
        "template": "plotly_white",
        "autosize": True,
        "margin": {"l": 60, "r": 24, "t": 56, "b": 60},
        "xaxis": {"title": {"text": xlabel}, "automargin": True},
        "yaxis": {"title": {"text": ylabel}, "automargin": True},
        "legend": {"orientation": "h", "y": -0.2},
        "hovermode": "closest",
    }
    layout.update(extra)
    return layout


def chart(chart_id: str, kind: str, title: str, data: List[Dict[str, Any]], layout: Dict[str, Any]) -> ResultChart:
    return ResultChart(id=chart_id, title=title, kind=kind, spec=jsonable({"data": data, "layout": layout}))


def bar(chart_id: str, title: str, x: Sequence[Any], y: Sequence[Any], xlabel: str, ylabel: str,
        horizontal: bool = False, error: Optional[Sequence[float]] = None, text: Optional[Sequence[str]] = None,
        color: str = PALETTE[0]) -> ResultChart:
    trace: Dict[str, Any] = {"type": "bar", "marker": {"color": color}, "hovertemplate": "%{x}: %{y}<extra></extra>"}
    if horizontal:
        trace.update({"x": list(y), "y": list(x), "orientation": "h", "hovertemplate": "%{y}: %{x}<extra></extra>"})
    else:
        trace.update({"x": [str(v) for v in x], "y": list(y)})
    if error is not None:
        trace["error_y" if not horizontal else "error_x"] = {"type": "data", "array": list(error), "visible": True}
    if text is not None:
        trace["text"] = list(text)
        trace["textposition"] = "auto"
    layout = _layout(title, ylabel if horizontal else xlabel, xlabel if horizontal else ylabel)
    if horizontal:
        layout["yaxis"]["autorange"] = "reversed"
    return chart(chart_id, "bar", title, [trace], layout)


def grouped_bar(chart_id: str, title: str, categories: Sequence[Any], series: Dict[str, Sequence[float]],
                xlabel: str, ylabel: str, stacked: bool = False) -> ResultChart:
    data = [
        {"type": "bar", "name": str(name), "x": [str(c) for c in categories], "y": list(vals),
         "marker": {"color": PALETTE[i % len(PALETTE)]}}
        for i, (name, vals) in enumerate(series.items())
    ]
    return chart(chart_id, "bar", title, data, _layout(title, xlabel, ylabel, barmode="stack" if stacked else "group"))


def histogram_bars(chart_id: str, title: str, edges: Sequence[float], counts: Sequence[int], xlabel: str,
                   mean: Optional[float] = None, median: Optional[float] = None) -> ResultChart:
    """Draws a histogram from precomputed bins (exact counts, tiny payload, no raw data sent)."""
    centers = [(edges[i] + edges[i + 1]) / 2 for i in range(len(counts))]
    widths = [edges[i + 1] - edges[i] for i in range(len(counts))]
    hover = [f"[{edges[i]:.4g}, {edges[i + 1]:.4g})<br>count: {counts[i]}" for i in range(len(counts))]
    trace = {"type": "bar", "x": centers, "y": list(counts), "width": widths, "marker": {"color": PALETTE[0], "line": {"color": "#1E3A8A", "width": 0.5}},
             "text": hover, "hoverinfo": "text"}
    shapes, annotations = [], []
    for val, name, colour in ((mean, "mean", "#EF4444"), (median, "median", "#10B981")):
        if val is not None:
            shapes.append({"type": "line", "x0": val, "x1": val, "y0": 0, "y1": 1, "yref": "paper", "line": {"color": colour, "dash": "dash", "width": 2}})
            annotations.append({"x": val, "y": 1.02 if name == "mean" else 1.09, "yref": "paper", "text": f"{name} {val:.4g}", "showarrow": False, "font": {"color": colour, "size": 11}})
    return chart(chart_id, "histogram", title, [trace], _layout(title, xlabel, "Count", bargap=0.02, shapes=shapes, annotations=annotations))


def line(chart_id: str, title: str, series: List[Dict[str, Any]], xlabel: str, ylabel: str) -> ResultChart:
    data = [
        {"type": "scatter", "mode": "lines+markers", "name": s["name"], "x": s["x"], "y": s["y"],
         "line": {"color": PALETTE[i % len(PALETTE)], "dash": s.get("dash", "solid")}, "connectgaps": False}
        for i, s in enumerate(series)
    ]
    return chart(chart_id, "line", title, data, _layout(title, xlabel, ylabel, hovermode="x unified"))


def scatter(chart_id: str, title: str, groups: List[Dict[str, Any]], xlabel: str, ylabel: str,
            line_trace: Optional[Dict[str, Any]] = None, equal_scale: bool = False) -> ResultChart:
    data = [
        {"type": "scatter", "mode": "markers", "name": g["name"], "x": g["x"], "y": g["y"],
         "marker": {"color": g.get("color", PALETTE[i % len(PALETTE)]), "size": g.get("size", 6), "opacity": 0.7},
         "text": g.get("text")}
        for i, g in enumerate(groups)
    ]
    if line_trace:
        data.append({"type": "scatter", "mode": "lines", "name": line_trace.get("name", "trend"), "x": line_trace["x"], "y": line_trace["y"],
                     "line": {"color": "#111827", "dash": "dash", "width": 2}})
    layout = _layout(title, xlabel, ylabel)
    if equal_scale:
        layout["yaxis"]["scaleanchor"] = "x"
    return chart(chart_id, "scatter", title, data, layout)


def heatmap(chart_id: str, title: str, z: List[List[Optional[float]]], x: Sequence[str], y: Sequence[str],
            zmin: Optional[float] = None, zmax: Optional[float] = None, diverging: bool = True,
            fmt_text: bool = True, xlabel: str = "", ylabel: str = "") -> ResultChart:
    trace: Dict[str, Any] = {
        "type": "heatmap", "z": z, "x": list(x), "y": list(y),
        "colorscale": "RdBu" if diverging else "Blues", "reversescale": diverging,
        "hovertemplate": "%{y} × %{x}: %{z}<extra></extra>",
    }
    if zmin is not None:
        trace["zmin"], trace["zmax"] = zmin, zmax
    if fmt_text:
        trace["text"] = [[("" if v is None else f"{v:.2f}") for v in row] for row in z]
        trace["texttemplate"] = "%{text}"
    layout = _layout(title, xlabel, ylabel, margin={"l": 110, "r": 24, "t": 56, "b": 110})
    layout["yaxis"]["autorange"] = "reversed"
    return chart(chart_id, "heatmap", title, [trace], layout)


def boxes(chart_id: str, title: str, groups: List[Dict[str, Any]], xlabel: str, ylabel: str) -> ResultChart:
    """Box plot from precomputed quartiles/fences plus explicit outlier markers."""
    boxes_trace = {
        "type": "box", "name": "distribution",
        "x": [g["name"] for g in groups], "q1": [g["q1"] for g in groups], "median": [g["median"] for g in groups],
        "q3": [g["q3"] for g in groups], "lowerfence": [g["lower"] for g in groups], "upperfence": [g["upper"] for g in groups],
        "mean": [g.get("mean") for g in groups], "boxmean": True, "marker": {"color": PALETTE[0]},
    }
    ox, oy = [], []
    for g in groups:
        for v in g.get("outliers", []):
            ox.append(g["name"])
            oy.append(v)
    data: List[Dict[str, Any]] = [boxes_trace]
    if oy:
        data.append({"type": "scatter", "mode": "markers", "name": "outliers (1.5×IQR)", "x": ox, "y": oy,
                     "marker": {"color": "#EF4444", "size": 6, "symbol": "circle-open"}})
    return chart(chart_id, "box", title, data, _layout(title, xlabel, ylabel))


def violins(chart_id: str, title: str, groups: List[Dict[str, Any]], xlabel: str, ylabel: str) -> ResultChart:
    data = [
        {"type": "violin", "name": g["name"], "y": g["values"], "box": {"visible": True}, "meanline": {"visible": True},
         "line": {"color": PALETTE[i % len(PALETTE)]}, "points": False}
        for i, g in enumerate(groups)
    ]
    return chart(chart_id, "violin", title, data, _layout(title, xlabel, ylabel, showlegend=False))
