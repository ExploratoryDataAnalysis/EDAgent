"""
Visualization Service
Generates Plotly JSON specifications for interactive frontend rendering and export.
"""

from typing import Dict, Any, List, Optional


class VisualizationService:
    """Creates structured Plotly chart specifications."""

    @staticmethod
    def create_histogram_spec(
        x_data: List[Any],
        title: str,
        x_label: str,
        nbins: Optional[int] = None
    ) -> Dict[str, Any]:
        return {
            "data": [
                {
                    "type": "histogram",
                    "x": x_data,
                    "nbinsx": nbins or 30,
                    "marker": {"color": "#3B82F6", "line": {"color": "#1D4ED8", "width": 1}},
                }
            ],
            "layout": {
                "title": title,
                "xaxis": {"title": x_label},
                "yaxis": {"title": "Count / Frequency"},
                "template": "plotly_white",
                "autosize": True,
            },
        }

    @staticmethod
    def create_bar_spec(
        categories: List[str],
        values: List[float],
        title: str,
        x_label: str,
        y_label: str
    ) -> Dict[str, Any]:
        return {
            "data": [
                {
                    "type": "bar",
                    "x": categories,
                    "y": values,
                    "marker": {"color": "#6366F1"},
                }
            ],
            "layout": {
                "title": title,
                "xaxis": {"title": x_label},
                "yaxis": {"title": y_label},
                "template": "plotly_white",
                "autosize": True,
            },
        }
