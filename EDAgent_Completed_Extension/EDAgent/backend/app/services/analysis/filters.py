"""
Structured filter engine.

Filters arrive as data (`FilterGroup` of `FilterCondition`s), never as strings that get
evaluated, so there is no expression-injection surface. Each condition is translated to a
vectorised pandas boolean mask. Semantics follow SQL: a comparison against a missing value is
"unknown" and therefore excluded (use is_null / not_null to select missing rows explicitly).
"""

from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from app.schemas.analysis import FilterCondition, FilterGroup, FilterOperatorEnum as Op
from app.services.data.loader import ColumnInfo

MAX_CONDITIONS = 25
MAX_DEPTH = 3


def count_conditions(group: FilterGroup, depth: int = 1) -> Tuple[int, int]:
    """Returns (total_conditions, max_depth) so validation can bound filter complexity."""
    total, deepest = 0, depth
    for c in group.conditions:
        if isinstance(c, FilterGroup):
            t, d = count_conditions(c, depth + 1)
            total += t
            deepest = max(deepest, d)
        else:
            total += 1
    return total, deepest


def _coerce(value: Any, info: ColumnInfo) -> Any:
    """Converts a filter value to the column's dtype or raises ValueError with a clear message."""
    if info.kind == "numeric":
        if isinstance(value, bool):
            raise ValueError("expected a number")
        return float(str(value).replace(",", "")) if isinstance(value, str) else float(value)
    if info.kind == "datetime":
        ts = pd.to_datetime(value, errors="raise")
        return ts.tz_convert(None) if getattr(ts, "tzinfo", None) else ts
    if info.kind == "boolean":
        if isinstance(value, bool):
            return value
        s = str(value).strip().lower()
        if s in ("true", "yes", "1", "t", "y"):
            return True
        if s in ("false", "no", "0", "f", "n"):
            return False
        raise ValueError("expected true/false")
    return str(value)


def validate_condition(cond: FilterCondition, columns: Dict[str, ColumnInfo]) -> List[str]:
    errors: List[str] = []
    info = columns.get(cond.column)
    if info is None:
        return [f"Filter column '{cond.column}' does not exist."]
    op = cond.operator
    if op in (Op.IS_NULL, Op.NOT_NULL):
        return errors
    if cond.value is None:
        return [f"Filter on '{cond.column}' with operator '{op.value}' needs a value."]
    if op in (Op.CONTAINS, Op.NOT_CONTAINS, Op.STARTS_WITH) and info.kind != "string":
        return [f"Operator '{op.value}' only applies to text columns, but '{cond.column}' is {info.kind}."]
    if op in (Op.GT, Op.GTE, Op.LT, Op.LTE, Op.BETWEEN) and info.kind in ("boolean",):
        return [f"Operator '{op.value}' is not meaningful for boolean column '{cond.column}'."]
    if op in (Op.GT, Op.GTE, Op.LT, Op.LTE, Op.BETWEEN) and info.kind == "string" and info.role not in ("category", "text", "unknown"):
        pass
    try:
        if op in (Op.IN, Op.NOT_IN):
            if not isinstance(cond.value, list) or not cond.value:
                return [f"Operator '{op.value}' on '{cond.column}' needs a non-empty list."]
            for v in cond.value:
                _coerce(v, info)
        elif op == Op.BETWEEN:
            if not isinstance(cond.value, list) or len(cond.value) != 2:
                return [f"Operator 'between' on '{cond.column}' needs [low, high]."]
            lo, hi = (_coerce(v, info) for v in cond.value)
            if lo > hi:
                errors.append(f"'between' on '{cond.column}': low value is greater than high value.")
        else:
            _coerce(cond.value, info)
    except (ValueError, TypeError) as e:
        errors.append(f"Filter value for '{cond.column}' is not valid for a {info.kind} column ({e}).")
    return errors


def validate_filters(group: FilterGroup, columns: Dict[str, ColumnInfo]) -> List[str]:
    total, depth = count_conditions(group)
    errors: List[str] = []
    if total > MAX_CONDITIONS:
        errors.append(f"Too many filter conditions ({total}); the limit is {MAX_CONDITIONS}.")
    if depth > MAX_DEPTH:
        errors.append(f"Filter groups are nested too deeply (max {MAX_DEPTH}).")
    if errors:
        return errors
    for c in group.conditions:
        errors.extend(validate_filters(c, columns) if isinstance(c, FilterGroup) else validate_condition(c, columns))
    return errors


def _condition_mask(df: pd.DataFrame, cond: FilterCondition, info: ColumnInfo) -> pd.Series:
    s = df[cond.column]
    op = cond.operator
    if op == Op.IS_NULL:
        return s.isna()
    if op == Op.NOT_NULL:
        return s.notna()
    if op in (Op.IN, Op.NOT_IN):
        vals = [_coerce(v, info) for v in cond.value]
        m = s.isin(vals)
        return m if op == Op.IN else (~m & s.notna())
    if op == Op.BETWEEN:
        lo, hi = (_coerce(v, info) for v in cond.value)
        return (s >= lo) & (s <= hi)
    if op in (Op.CONTAINS, Op.NOT_CONTAINS, Op.STARTS_WITH):
        text = str(cond.value)
        st = s.astype(object).where(s.notna(), None)
        if op == Op.STARTS_WITH:
            m = st.map(lambda v: isinstance(v, str) and v.lower().startswith(text.lower()))
        else:
            m = st.map(lambda v: isinstance(v, str) and text.lower() in v.lower())
        m = m.astype(bool)
        return m if op != Op.NOT_CONTAINS else (~m & s.notna())
    val = _coerce(cond.value, info)
    if info.kind == "string":
        # Text equality is case-sensitive and exact; compare as strings only.
        s = s.astype(object)
    ops = {Op.EQ: s == val, Op.NE: s != val, Op.GT: s > val, Op.GTE: s >= val, Op.LT: s < val, Op.LTE: s <= val}
    m = ops[op]
    return m.fillna(False).astype(bool) & s.notna()  # unknown (missing) never matches


def build_mask(df: pd.DataFrame, group: FilterGroup, columns: Dict[str, ColumnInfo]) -> pd.Series:
    """Combines all conditions with the group's AND/OR logic into one boolean mask."""
    masks: List[pd.Series] = []
    for c in group.conditions:
        if isinstance(c, FilterGroup):
            masks.append(build_mask(df, c, columns))
        else:
            masks.append(_condition_mask(df, c, columns[c.column]))
    if not masks:
        return pd.Series(True, index=df.index)
    out = masks[0]
    for m in masks[1:]:
        out = (out & m) if group.logic == "and" else (out | m)
    return out


def describe_filters(group: FilterGroup) -> str:
    """Human-readable form, shown in the UI and written into methodology/reports."""
    parts: List[str] = []
    for c in group.conditions:
        if isinstance(c, FilterGroup):
            parts.append(f"({describe_filters(c)})")
        else:
            v = "" if c.value is None else f" {c.value!r}"
            parts.append(f"{c.column} {c.operator.value}{v}")
    return f" {group.logic.upper()} ".join(parts)


def filter_code(group: FilterGroup, var: str = "df") -> str:
    """Equivalent pandas code so the filter step is reproducible outside EDAgent."""
    def one(c: FilterCondition) -> str:
        col, o, v = f"{var}[{c.column!r}]", c.operator, c.value
        if o == Op.IN:
            return f"{col}.isin({v!r})"
        if o == Op.NOT_IN:
            return f"(~{col}.isin({v!r}) & {col}.notna())"
        if o == Op.BETWEEN:
            lo, hi = (v if isinstance(v, list) and len(v) == 2 else (None, None))
            return f"{col}.between({lo!r}, {hi!r})"
        if o == Op.CONTAINS:
            return f"{col}.str.contains({str(v)!r}, case=False, na=False, regex=False)"
        if o == Op.NOT_CONTAINS:
            return f"(~{col}.str.contains({str(v)!r}, case=False, na=True, regex=False))"
        if o == Op.STARTS_WITH:
            return f"{col}.str.lower().str.startswith({str(v).lower()!r}, na=False)"
        if o == Op.IS_NULL:
            return f"{col}.isna()"
        if o == Op.NOT_NULL:
            return f"{col}.notna()"
        symbol = {Op.EQ: "==", Op.NE: "!=", Op.GT: ">", Op.GTE: ">=", Op.LT: "<", Op.LTE: "<="}[o]
        return f"({col} {symbol} {v!r})"

    def expr(g: FilterGroup) -> str:
        items = [f"({expr(c)})" if isinstance(c, FilterGroup) else one(c) for c in g.conditions]
        return (" & " if g.logic == "and" else " | ").join(items) if items else "True"

    return f"{var} = {var}[{expr(group)}]"
