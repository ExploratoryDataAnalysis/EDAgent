"""
Time-based operations: trends by day/week/month/quarter/year, seasonality components and
date distributions.
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from app.services.analysis import charts
from app.services.analysis.common import (
    AnalysisError, Ctx, OpOutput, coerce_warnings, fmt, make_table, missing_note, table_from_rows,
)

_FREQ = {"day": "D", "week": "W", "month": "M", "quarter": "Q", "year": "Y"}
_FREQ_NEW = {"D": "D", "W": "W", "M": "M", "Q": "Q", "Y": "Y"}


def _periods(ts: pd.Series, interval: str) -> pd.Series:
    """Floors timestamps to the start of their period (ISO weeks start on Monday)."""
    f = _FREQ[interval]
    return ts.dt.to_period("W-SUN" if f == "W" else f).dt.start_time


def _period_labels(starts: pd.Series, interval: str) -> List[str]:
    fmt_map = {"day": "%Y-%m-%d", "week": "%Y-%m-%d", "month": "%Y-%m", "quarter": None, "year": "%Y"}
    if interval == "quarter":
        return [f"{t.year}-Q{(t.month - 1) // 3 + 1}" for t in starts]
    return [t.strftime(fmt_map[interval]) for t in starts]


_COMPONENTS = {
    "month_of_year": (lambda s: s.dt.month, "month of year"),
    "day_of_week": (lambda s: s.dt.dayofweek, "day of week"),
    "hour_of_day": (lambda s: s.dt.hour, "hour of day"),
    "quarter_of_year": (lambda s: s.dt.quarter, "quarter of year"),
}
_DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def time_trend(ctx: Ctx) -> OpOutput:
    p = ctx.plan
    dc, measure = p.date_column, p.column
    agg = "count" if not measure else p.aggregation
    if agg not in ("sum", "mean", "median", "count", "min", "max", "std"):
        raise AnalysisError(f"Aggregation '{agg}' is not supported for time trends.")
    d = ctx.df[[dc] + ([measure] if measure else [])]
    n_bad_dates = int(d[dc].isna().sum())
    d = d.dropna(subset=[dc])
    if d.empty:
        raise AnalysisError(f"Column '{dc}' has no valid dates.")
    out = OpOutput(columns_used=[dc] + ([measure] if measure else []), records_used=len(d))
    out.warnings += coerce_warnings(ctx, [dc] + ([measure] if measure else []))
    component = ctx.param("component")

    # --- seasonality: aggregate by a calendar component instead of a continuous timeline
    if component:
        if component not in _COMPONENTS:
            raise AnalysisError(f"component must be one of {', '.join(_COMPONENTS)}.")
        fn, label = _COMPONENTS[component]
        key = fn(d[dc])
        series = d[measure].groupby(key).agg(agg) if measure else key.groupby(key).size()
        counts = key.groupby(key).size()
        names = (_DOW if component == "day_of_week" else _MON if component == "month_of_year" else None)
        xs = [names[int(k) - (0 if component == "day_of_week" else 1)] if names else str(int(k)) for k in series.index]
        tbl = pd.DataFrame({label: xs, "value": series.values, "rows": counts.reindex(series.index).values})
        out.tables.append(make_table("seasonality", tbl, ctx.row_cap))
        out.charts.append(charts.bar("seasonality", f"{agg} of {measure or 'rows'} by {label}", xs, series.tolist(), label, f"{agg} {measure or 'count'}"))
        peak = int(np.nanargmax(series.values))
        out.metrics = {"component": component, "peak": xs[peak], "peak_value": float(series.values[peak]), "aggregation": agg}
        out.summary = f"By {label}, the highest {agg} of {measure or 'rows'} is {xs[peak]} ({fmt(series.values[peak])})."
        out.warnings.append("Seasonality patterns are descriptive; confirm with enough years/cycles of data before concluding a seasonal effect.")
        out.methodology = f"Rows are grouped by {label} (ignoring the year) and {agg} is computed."
        out.missing_value_handling = "Rows with an unparseable/missing date are excluded." if n_bad_dates else "No missing dates."
        out.exclusions = missing_note(ctx, [dc], len(d))
        out.code = f"s = df.groupby(df[{dc!r}].dt.{ {'month_of_year':'month','day_of_week':'dayofweek','hour_of_day':'hour','quarter_of_year':'quarter'}[component]})" + (f"[{measure!r}].{agg}()" if measure else ".size()")
        return out

    # --- continuous trend
    interval = p.interval
    d = d.assign(_period=_periods(d[dc], interval))
    grp = d.groupby("_period")
    series = grp[measure].agg(agg) if measure else grp.size()
    rows_per = grp.size()
    full_idx = pd.date_range(series.index.min(), series.index.max(), freq={"D": "D", "W": "W-MON", "M": "MS", "Q": "QS", "Y": "YS"}[_FREQ[interval]])
    series = series.reindex(full_idx)
    rows_per = rows_per.reindex(full_idx)
    empty = int(series.isna().sum())
    if len(series) > 5000:
        raise AnalysisError(f"This would create {len(series):,} {interval} buckets; choose a coarser interval.")
    if len(series) < 2:
        out.warnings.append("Only one time bucket exists in the data; a trend cannot be shown.")

    compare = ctx.param("compare_with", "none")
    prev = None
    if compare in ("previous_period", "previous_year"):
        if compare == "previous_period":
            prev = series.shift(1)
            prev_label = f"previous {interval}"
        else:
            offset = pd.DateOffset(weeks=52) if interval == "week" else pd.DateOffset(years=1)
            shifted = series.copy()
            shifted.index = shifted.index + offset
            prev = shifted.reindex(series.index)
            prev_label = "previous year"
        if prev.notna().sum() == 0:
            out.warnings.append(f"No overlapping '{prev_label}' data exists, so no comparison could be drawn (the data span is too short).")

    labels = _period_labels(series.index.to_series(), interval)
    table = pd.DataFrame({"period": labels, "value": series.values, "rows": rows_per.fillna(0).astype(int).values})
    if prev is not None:
        table["previous"] = prev.values
        table["change"] = table["value"] - table["previous"]
        with np.errstate(divide="ignore", invalid="ignore"):
            table["pct_change"] = np.where(table["previous"].astype(float) != 0, table["change"] / table["previous"].astype(float) * 100, np.nan)
    out.tables.append(make_table("trend", table, ctx.row_cap))
    traces = [{"name": f"{agg} of {measure}" if measure else "row count", "x": labels, "y": series.tolist()}]
    if prev is not None:
        traces.append({"name": prev_label, "x": labels, "y": prev.tolist(), "dash": "dot"})
    out.charts.append(charts.line("trend", f"{agg} of {measure or 'rows'} per {interval}", traces, interval, f"{agg} {measure or 'count'}"))
    valid = series.dropna()
    first, last = (float(valid.iloc[0]), float(valid.iloc[-1])) if len(valid) else (np.nan, np.nan)
    pk = valid.idxmax() if len(valid) else None
    out.metrics = {"interval": interval, "periods": int(len(series)), "empty_periods": empty, "first": first, "last": last,
                   "peak_period": labels[list(series.index).index(pk)] if pk is not None else None, "peak_value": float(valid.max()) if len(valid) else None,
                   "aggregation": agg, "compare_with": compare}
    if prev is not None and prev.notna().any():
        both = pd.DataFrame({"a": series, "b": prev}).dropna()
        tot_a, tot_b = float(both["a"].sum()), float(both["b"].sum())
        out.metrics["comparison_total_current"] = tot_a
        out.metrics["comparison_total_previous"] = tot_b
        out.metrics["comparison_pct_change"] = float((tot_a - tot_b) / tot_b * 100) if tot_b else None
    out.summary = (f"{agg.title()} of {measure or 'rows'} per {interval} over {len(series)} periods ({labels[0]} to {labels[-1]}); "
                   f"first {fmt(first)}, last {fmt(last)}, peak {fmt(out.metrics['peak_value'])} in {out.metrics['peak_period']}.")
    if "comparison_pct_change" in out.metrics and out.metrics["comparison_pct_change"] is not None:
        out.summary += f" Versus {prev_label} (matching periods): {out.metrics['comparison_pct_change']:+.1f}%."
    if empty:
        out.warnings.append(f"{empty} {interval}(s) in the range have no data; they appear as gaps rather than zeros.")
    if n_bad_dates:
        out.warnings.append(f"{n_bad_dates} row(s) with a missing/unparseable date were excluded.")
    out.exclusions = missing_note(ctx, [dc] + ([measure] if measure else []), len(d))
    out.methodology = (f"Rows are bucketed by {interval} of '{dc}' (weeks start Monday) and {agg} is computed per bucket. Empty buckets inside the range are shown as gaps. "
                       "Dates with timezone offsets are converted to UTC.")
    out.missing_value_handling = "Rows without a valid date are excluded; missing measure values are ignored by the aggregation."
    out.code = (f"d = df.dropna(subset=[{dc!r}])\n"
                f"trend = d.groupby(d[{dc!r}].dt.to_period({_FREQ[interval]!r}))" + (f"[{measure!r}].{agg}()" if measure else ".size()"))
    return out


def date_distribution(ctx: Ctx) -> OpOutput:
    p = ctx.plan
    dc = p.date_column
    d = ctx.df[dc].dropna()
    if d.empty:
        raise AnalysisError(f"Column '{dc}' has no valid dates.")
    interval = p.interval
    starts = _periods(d, interval)
    counts = starts.value_counts().sort_index()
    labels = _period_labels(counts.index.to_series(), interval)
    out = OpOutput(columns_used=[dc], records_used=len(d))
    out.tables.append(table_from_rows("date_counts", ["period", "count"], [{"period": l, "count": int(c)} for l, c in zip(labels, counts.values)], ctx.row_cap))
    out.charts.append(charts.bar("date_distribution", f"Records per {interval} ({dc})", labels, counts.tolist(), interval, "Records"))
    dow = d.dt.dayofweek.value_counts().reindex(range(7), fill_value=0)
    out.charts.append(charts.bar("weekday", f"Records by weekday ({dc})", _DOW, dow.tolist(), "weekday", "Records"))
    span = (d.max() - d.min()).days
    out.metrics = {"min": d.min(), "max": d.max(), "span_days": int(span), "periods": int(len(counts)), "busiest_period": labels[int(np.argmax(counts.values))]}
    has_time = bool((d.dt.hour != 0).any() or (d.dt.minute != 0).any())
    if has_time:
        hrs = d.dt.hour.value_counts().reindex(range(24), fill_value=0)
        out.charts.append(charts.bar("hour", f"Records by hour of day ({dc})", [str(h) for h in range(24)], hrs.tolist(), "hour", "Records"))
    out.summary = f"'{dc}' spans {span} day(s) ({d.min().date()} to {d.max().date()}) across {len(counts)} {interval} bucket(s); busiest: {out.metrics['busiest_period']}."
    miss = int(ctx.df[dc].isna().sum())
    if miss:
        out.warnings.append(f"{miss} row(s) with a missing/unparseable date are excluded.")
    out.exclusions = missing_note(ctx, [dc], len(d))
    out.warnings += coerce_warnings(ctx, [dc])
    out.methodology = f"Counts of valid dates per {interval}; weekday (and hour, when times exist) patterns shown separately."
    out.missing_value_handling = "Rows with missing/unparseable dates are excluded."
    out.code = f"counts = df[{dc!r}].dropna().dt.to_period({_FREQ[interval]!r}).value_counts().sort_index()"
    return out
