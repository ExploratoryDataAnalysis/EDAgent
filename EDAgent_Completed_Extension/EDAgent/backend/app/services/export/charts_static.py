"""
Static chart rendering (PNG / SVG) from the same Plotly figure JSON the browser draws.

Plotly's own image export needs a headless Chrome, which is not available everywhere, so the
exports use matplotlib: it is installed with the backend, deterministic and fast. Only the
trace types the analysis engine emits are supported (bar, scatter, heatmap, box, violin); an
unknown trace is skipped and reported in the returned notes rather than crashing an export.
"""

import io
import textwrap
from typing import Any, Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")  # no display server on the backend
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

FIG_SIZE = (8.4, 4.8)
_FONT = "DejaVu Sans"
plt.rcParams.update({"font.family": _FONT, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.25})


def _title(layout: Dict[str, Any]) -> str:
    t = layout.get("title")
    return (t.get("text") if isinstance(t, dict) else t) or ""


def _axis_title(layout: Dict[str, Any], axis: str) -> str:
    t = (layout.get(axis) or {}).get("title")
    return (t.get("text") if isinstance(t, dict) else t) or ""


def _color(trace: Dict[str, Any], default: str = "#2563EB") -> str:
    marker = trace.get("marker") or {}
    c = marker.get("color")
    return c if isinstance(c, str) else default


def _wrap(labels: List[Any], width: int = 14) -> List[str]:
    return ["\n".join(textwrap.wrap(str(l), width)) or str(l) for l in labels]


def render_figure(spec: Dict[str, Any]) -> Tuple[plt.Figure, List[str]]:
    """Draws a figure spec; returns (figure, notes about anything that could not be drawn)."""
    data = spec.get("data", [])
    layout = spec.get("layout", {})
    notes: List[str] = []
    fig, ax = plt.subplots(figsize=FIG_SIZE)
    stacked = layout.get("barmode") == "stack"
    bar_traces = [t for t in data if t.get("type") == "bar"]
    bar_index = 0
    categorical_x: List[str] = []
    horizontal = False
    box_names: List[str] = []
    string_x_labels: List[str] = []

    for tr in data:
        kind = tr.get("type")
        if kind == "bar":
            horizontal = tr.get("orientation") == "h"
            xs, ys = tr.get("x", []), tr.get("y", [])
            cat_axis = ys if horizontal else xs
            val_axis = xs if horizontal else ys
            numeric_cat = all(isinstance(v, (int, float)) for v in cat_axis) and tr.get("width") is not None
            pos = np.array(cat_axis, dtype=float) if numeric_cat else np.arange(len(cat_axis))
            if not numeric_cat and not categorical_x:
                categorical_x = [str(v) for v in cat_axis]
            n = max(len(bar_traces), 1)
            if numeric_cat:
                widths = tr.get("width") or 1
                ax.bar(pos, val_axis, width=widths, color=_color(tr), edgecolor="#1E3A8A", linewidth=0.4)
            elif horizontal:
                ax.barh(pos, val_axis, color=_color(tr, "#2563EB"), height=0.7)
            elif stacked:
                bottom = np.zeros(len(pos)) if bar_index == 0 else getattr(ax, "_edagent_bottom", np.zeros(len(pos)))
                ax.bar(pos, val_axis, bottom=bottom, color=_color(tr), label=tr.get("name"))
                ax._edagent_bottom = bottom + np.nan_to_num(np.array(val_axis, dtype=float))  # type: ignore[attr-defined]
            else:
                width = 0.8 / n
                offs = (bar_index - (n - 1) / 2) * width
                err = (tr.get("error_y") or {}).get("array")
                ax.bar(pos + offs, val_axis, width=width, color=_color(tr), label=tr.get("name"), yerr=err, capsize=3 if err else 0)
            bar_index += 1
        elif kind == "scatter":
            mode = tr.get("mode", "markers")
            x, y = tr.get("x", []), tr.get("y", [])
            if x and isinstance(x[0], str):
                # String x values (dates/categories). Reuse the box positions when drawing box outliers,
                # otherwise place points in order and remember labels for thinned tick marks.
                if box_names:
                    x = [box_names.index(v) + 1 if v in box_names else np.nan for v in x]
                else:
                    if not string_x_labels:
                        string_x_labels.extend(str(v) for v in x)
                    lookup = {v: i for i, v in enumerate(string_x_labels)}
                    x = [lookup.get(str(v), np.nan) for v in x]
            if "lines" in mode and "markers" not in mode:
                ax.plot(x, y, color=(tr.get("line") or {}).get("color", "#111827"), linestyle="--" if (tr.get("line") or {}).get("dash") == "dash" else "-", label=tr.get("name"), linewidth=2)
            elif "lines" in mode:
                ax.plot(x, y, marker="o", markersize=3.5, color=(tr.get("line") or {}).get("color", "#2563EB"), linestyle="--" if (tr.get("line") or {}).get("dash") == "dash" else "-", label=tr.get("name"))
            else:
                ax.scatter(x, y, s=((tr.get("marker") or {}).get("size") or 6) * 3.2, alpha=0.7, color=_color(tr), label=tr.get("name"), linewidths=0)
        elif kind == "heatmap":
            z = np.array([[np.nan if v is None else v for v in row] for row in tr["z"]], dtype=float)
            ax.grid(False)
            cmap = "RdBu_r" if tr.get("reversescale") else "Blues"
            im = ax.imshow(z, cmap=cmap, vmin=tr.get("zmin"), vmax=tr.get("zmax"), aspect="auto")
            ax.set_xticks(range(len(tr["x"])))
            ax.set_xticklabels(_wrap(tr["x"], 12), rotation=45, ha="right")
            ax.set_yticks(range(len(tr["y"])))
            ax.set_yticklabels(_wrap(tr["y"], 16))
            fig.colorbar(im, ax=ax, fraction=0.04)
            if z.size <= 144:  # annotate cells only when they stay legible
                for i in range(z.shape[0]):
                    for j in range(z.shape[1]):
                        if not np.isnan(z[i, j]):
                            rgba = im.cmap(im.norm(z[i, j]))
                            lum = 0.299 * rgba[0] + 0.587 * rgba[1] + 0.114 * rgba[2]
                            ax.text(j, i, f"{z[i, j]:.2f}", ha="center", va="center", fontsize=7, color="#111827" if lum > 0.55 else "white")
            ax.spines[:].set_visible(False)
        elif kind == "box":
            stats = []
            for i, name in enumerate(tr.get("x", [])):
                stats.append({"label": str(name), "q1": tr["q1"][i], "med": tr["median"][i], "q3": tr["q3"][i], "whislo": tr["lowerfence"][i], "whishi": tr["upperfence"][i], "fliers": []})
            ax.bxp(stats, showfliers=False, patch_artist=True, boxprops={"facecolor": "#BFDBFE", "edgecolor": "#1E40AF"}, medianprops={"color": "#1E3A8A", "linewidth": 2})
            means = tr.get("mean") or []
            if any(m is not None for m in means):
                ax.scatter(range(1, len(means) + 1), [np.nan if m is None else m for m in means], marker="D", color="#EF4444", s=22, zorder=3, label="mean")
            categorical_x = []
            box_names.extend(str(n) for n in tr.get("x", []))
        elif kind == "violin":
            vals = tr.get("y", [])
            pos = len(ax.collections) + 1
            parts = ax.violinplot([vals], positions=[len(getattr(ax, "_edagent_violins", [])) + 1], showmeans=True, showmedians=True)
            ax._edagent_violins = getattr(ax, "_edagent_violins", []) + [tr.get("name", "")]  # type: ignore[attr-defined]
            for b in parts["bodies"]:
                b.set_facecolor((tr.get("line") or {}).get("color", "#2563EB"))
                b.set_alpha(0.6)
        else:
            notes.append(f"trace type '{kind}' is not drawn in static exports")

    if getattr(ax, "_edagent_violins", None):
        names = ax._edagent_violins  # type: ignore[attr-defined]
        ax.set_xticks(range(1, len(names) + 1))
        ax.set_xticklabels(_wrap(names, 12))
    if categorical_x and not horizontal and data and data[0].get("type") == "bar" and data[0].get("width") is None:
        ax.set_xticks(range(len(categorical_x)))
        ax.set_xticklabels(_wrap(categorical_x, 12), rotation=0 if len(categorical_x) <= 6 else 45, ha="center" if len(categorical_x) <= 6 else "right")
    if string_x_labels:
        step = max(1, len(string_x_labels) // 10)
        idx = list(range(0, len(string_x_labels), step))
        ax.set_xticks(idx)
        ax.set_xticklabels([string_x_labels[i] for i in idx], rotation=45, ha="right")
    if horizontal:
        ys = data[0].get("y", [])
        ax.set_yticks(range(len(ys)))
        ax.set_yticklabels(_wrap(ys, 24))
        ax.invert_yaxis()

    for shape in layout.get("shapes", []) or []:  # vertical reference lines (mean / median on histograms)
        if shape.get("type") == "line" and shape.get("x0") == shape.get("x1"):
            ax.axvline(shape["x0"], color=(shape.get("line") or {}).get("color", "#EF4444"), linestyle="--", linewidth=1.6)
    for ann in layout.get("annotations", []) or []:
        if ann.get("yref") == "paper" and ann.get("x") is not None and isinstance(ann["x"], (int, float)):
            ax.annotate(ann.get("text", ""), (ann["x"], min(max(ann.get("y", 1.0), 1.0), 1.12) - 0.0), xycoords=("data", "axes fraction"), fontsize=8, color=(ann.get("font") or {}).get("color", "#111827"), ha="left", va="bottom")

    ax.set_title(_title(layout), fontsize=12, loc="left")
    if not any(t.get("type") == "heatmap" for t in data):
        ax.set_xlabel(_axis_title(layout, "xaxis"))
        ax.set_ylabel(_axis_title(layout, "yaxis"))
    handles, labels = ax.get_legend_handles_labels()
    if labels and len(labels) > 1:
        ax.legend(fontsize=8, frameon=False, loc="best")
    fig.tight_layout()
    return fig, notes


def render_bytes(spec: Dict[str, Any], fmt: str = "png", dpi: int = 160) -> bytes:
    fig, _ = render_figure(spec)
    buf = io.BytesIO()
    try:
        fig.savefig(buf, format=fmt, dpi=dpi, bbox_inches="tight", facecolor="white")
    finally:
        plt.close(fig)
    return buf.getvalue()
