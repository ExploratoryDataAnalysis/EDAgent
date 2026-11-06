"""
Builds the dataset context shown to the LLM.

Only schema-level facts and small, sanitised samples go into a prompt: column names, roles,
types, missingness, numeric ranges and a few top category labels. Raw rows are never sent.
Every string that came from the dataset passes through `sanitize_prompt_data` and is placed
inside a clearly delimited, explicitly-untrusted block (prompt-injection hygiene).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from app.core.security import sanitize_prompt_data


@dataclass
class DatasetContext:
    text: str
    # What the model sees -> the real column name. The model may echo a sanitised name, and the
    # plan is mapped back before validation so odd names (quotes, '<', very long) still work.
    name_map: Dict[str, str] = field(default_factory=dict)
    column_names: List[str] = field(default_factory=list)


def _fmt(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)


def build_context(dataset_name: str, profile: Dict[str, Any], max_chars: int) -> DatasetContext:
    cols = profile.get("columns", [])
    overview = profile.get("overview", {})
    name_map: Dict[str, str] = {}

    def line(c: Dict[str, Any], detail: int) -> str:
        shown = sanitize_prompt_data(c["name"], 80)
        name_map[shown] = c["name"]
        parts = [f'"{shown}"', f"role={c.get('semantic_role')}", f"type={c.get('inferred_type')}", f"missing={c.get('missing_percentage', 0)}%", f"distinct={c.get('distinct_count')}"]
        ns = c.get("numeric_summary")
        if ns and detail >= 1:
            parts.append(f"min={_fmt(ns.get('min'))} median={_fmt(ns.get('median'))} max={_fmt(ns.get('max'))}")
        ds = c.get("date_summary")
        if ds and detail >= 1:
            parts.append(f"dates {ds.get('min_date')} to {ds.get('max_date')}")
        cs = c.get("categorical_summary")
        if cs and detail >= 2 and not cs.get("is_high_cardinality"):
            vals = ", ".join(sanitize_prompt_data(str(t.get("value")), 40) for t in (cs.get("top_values") or [])[:8])
            if vals:
                parts.append(f"values: [{vals}]")
        return "- " + "; ".join(parts)

    for detail in (2, 1, 0):  # shrink the detail level until it fits the budget
        name_map.clear()
        lines = [line(c, detail) for c in cols]
        body = "\n".join(lines)
        header = f'Dataset "{sanitize_prompt_data(dataset_name, 80)}": {overview.get("total_rows")} rows, {overview.get("total_columns")} columns.'
        text = f"{header}\nColumns:\n{body}"
        if len(text) <= max_chars:
            break
    if len(text) > max_chars:
        keep = max(1, int(len(lines) * max_chars / max(len(text), 1)))
        text = f"{header}\nColumns (first {keep} of {len(lines)} shown; the dataset is wide):\n" + "\n".join(lines[:keep])
    return DatasetContext(text=text, name_map=dict(name_map), column_names=[c["name"] for c in cols])
