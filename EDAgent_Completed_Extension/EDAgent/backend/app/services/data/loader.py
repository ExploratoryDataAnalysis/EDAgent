"""
Typed DataFrame loader with an LRU cache.

The profiler works on strings. Analyses need real numbers/dates, so this module converts
each column to a proper dtype *in memory only* (the uploaded file is never modified) using
the column types/roles the profiler already inferred. Cells that cannot be converted become
missing and are counted, so every analysis can report exactly what it excluded and why.
"""

import hashlib
import json
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.core.config import settings
from app.services.data.reader import read_table_as_strings
from app.services.profiler.profiler_engine import ProfilerEngine

# Matches 1,234 / 1,234,567.89 style thousands separators only (so "1,2" stays text).
_THOUSANDS = re.compile(r"^[+-]?\d{1,3}(,\d{3})+(\.\d+)?$")
_CURRENCY = re.compile(r"^[\s$€£₹¥]+|[\s%]+$")
_TRUE = {"true", "t", "yes", "y", "1"}
_FALSE = {"false", "f", "no", "n", "0"}


@dataclass
class ColumnInfo:
    """What the analysis layer knows about one column."""
    name: str
    role: str            # identifier | measure | category | datetime | boolean | text | unknown
    kind: str            # numeric | datetime | boolean | string  (the dtype it was converted to)
    inferred_type: str
    distinct_count: int = 0
    missing_count: int = 0
    unparseable_count: int = 0   # non-missing cells that could not be converted to `kind`
    infinite_count: int = 0

    @property
    def is_numeric(self) -> bool:
        return self.kind == "numeric"


@dataclass
class LoadedDataset:
    df: pd.DataFrame
    columns: Dict[str, ColumnInfo]
    fingerprint: str
    warnings: List[str] = field(default_factory=list)

    @property
    def n_rows(self) -> int:
        return int(len(self.df))

    def numeric_columns(self, include_identifiers: bool = False) -> List[str]:
        return [
            c for c, i in self.columns.items()
            if i.is_numeric and (include_identifiers or i.role not in ("identifier", "category"))
        ]


def _kind_for(role: str, inferred: str) -> str:
    """Decides which dtype a column is converted to, from the profiler's role + type."""
    if role == "datetime" or inferred == "datetime":
        return "datetime"
    if role == "boolean" or inferred == "boolean":
        return "boolean"
    if inferred in ("integer", "float") and role in ("measure", "category", "identifier", "unknown"):
        return "numeric"
    return "string"


def _to_numeric(series: pd.Series) -> tuple[pd.Series, int, int]:
    """Converts a string series to float; returns (values, unparseable_count, infinite_count)."""
    s = series.astype(object)
    present = s.notna()
    cleaned = s.where(~present, s.map(lambda v: _clean_number(v) if isinstance(v, str) else v))
    values = pd.to_numeric(cleaned, errors="coerce")
    infinite = int(np.isinf(values.to_numpy(dtype=float, na_value=np.nan)).sum())
    values = values.replace([np.inf, -np.inf], np.nan)
    unparseable = int((present & values.isna()).sum()) - infinite
    return values.astype(float), max(unparseable, 0), infinite


def _clean_number(v: str) -> str:
    v = _CURRENCY.sub("", v.strip())
    if _THOUSANDS.match(v):
        v = v.replace(",", "")
    return v


def _to_datetime(series: pd.Series) -> tuple[pd.Series, int]:
    present = series.notna()
    try:
        # format="mixed" lets pandas parse each cell on its own; utc=True normalises any
        # timezone offsets so the column has a single consistent (naive-UTC) basis.
        parsed = pd.to_datetime(series, errors="coerce", format="mixed", utc=True)
    except (ValueError, TypeError):
        parsed = pd.to_datetime(series, errors="coerce", utc=True)
    parsed = parsed.dt.tz_convert(None)
    return parsed, int((present & parsed.isna()).sum())


def _to_boolean(series: pd.Series) -> tuple[pd.Series, int]:
    lowered = series.astype(object).map(lambda v: v.strip().lower() if isinstance(v, str) else v)
    mapped = lowered.map(lambda v: True if v in _TRUE else (False if v in _FALSE else np.nan))
    present = series.notna()
    return mapped.astype("boolean"), int((present & mapped.isna()).sum())


def build_typed_frame(headers: List[str], rows: List[List[str]], profile_columns: List[Dict[str, Any]]) -> tuple[pd.DataFrame, Dict[str, ColumnInfo]]:
    """Builds the typed DataFrame + per-column info from raw string rows and a profile."""
    raw = pd.DataFrame(rows, columns=headers, dtype=object)
    prof_by_name = {c["name"]: c for c in profile_columns}
    data: Dict[str, pd.Series] = {}
    infos: Dict[str, ColumnInfo] = {}

    for name in headers:
        col = raw[name]
        # Missing placeholders (NA, null, "-", ...) become real missing values, matching the profiler.
        col = col.where(~col.map(ProfilerEngine._is_missing_or_placeholder), np.nan)
        pc = prof_by_name.get(name, {})
        role = str(pc.get("semantic_role", "unknown"))
        inferred = str(pc.get("inferred_type", "string"))
        kind = _kind_for(role, inferred)
        unparseable = infinite = 0

        if kind == "numeric":
            col, unparseable, infinite = _to_numeric(col)
        elif kind == "datetime":
            col, unparseable = _to_datetime(col)
        elif kind == "boolean":
            col, unparseable = _to_boolean(col)

        data[name] = col
        infos[name] = ColumnInfo(
            name=name, role=role, kind=kind, inferred_type=inferred,
            distinct_count=int(col.nunique(dropna=True)), missing_count=int(col.isna().sum()),
            unparseable_count=unparseable, infinite_count=infinite,
        )
    return pd.DataFrame(data), infos


# --- cache -----------------------------------------------------------------

_cache: "OrderedDict[str, LoadedDataset]" = OrderedDict()
_cache_lock = threading.Lock()


def _cache_key(dataset_id: str, fingerprint: str) -> str:
    return f"{dataset_id}:{fingerprint}"


def dataset_fingerprint(checksum: str, parse_options: Optional[Dict[str, Any]]) -> str:
    """Identity of 'this file parsed this way'. Used for caching and stamped on reports."""
    blob = json.dumps({"sha": checksum, "opts": parse_options or {}}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def invalidate_dataset(dataset_id: str) -> None:
    """Drops cached frames for a dataset (called on re-parse, sheet change or delete)."""
    with _cache_lock:
        for k in [k for k in _cache if k.startswith(f"{dataset_id}:")]:
            _cache.pop(k, None)


def load_dataset(
    dataset_id: str,
    file_path: str,
    file_format: str,
    checksum: str,
    parse_options: Optional[Dict[str, Any]],
    profile_columns: List[Dict[str, Any]],
    *,
    use_cache: bool = True,
) -> LoadedDataset:
    """Loads (or returns the cached) typed DataFrame for a dataset."""
    fp = dataset_fingerprint(checksum, parse_options)
    key = _cache_key(dataset_id, fp)
    if use_cache:
        with _cache_lock:
            if key in _cache:
                _cache.move_to_end(key)
                return _cache[key]

    opts = parse_options or {}
    headers, rows, warnings = read_table_as_strings(
        file_path, file_format, sheet_name=opts.get("sheet"), delimiter=opts.get("delimiter"), encoding=opts.get("encoding")
    )
    df, infos = build_typed_frame(headers, rows, profile_columns)
    loaded = LoadedDataset(df=df, columns=infos, fingerprint=fp, warnings=warnings)

    if use_cache:
        with _cache_lock:
            _cache[key] = loaded
            while len(_cache) > max(1, settings.DATAFRAME_CACHE_ENTRIES):
                _cache.popitem(last=False)
    return loaded
