"""
Automatic Dataset Profiler Engine
Pure deterministic statistical calculation engine.
Follows Section 5.2 and Appendix A of the EDAgent specification.
Zero LLM dependencies.
"""

import csv
import math
import os
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple, Set

import numpy as np
import scipy.stats as stats
from dateutil import parser as date_parser

from app.schemas.profiler import (
    ProfilerResultResponse,
    DatasetOverview,
    ColumnProfile,
    NumericSummary,
    CategoricalSummary,
    DateSummary,
    MissingnessReport,
    DuplicatesReport,
    QualityWarning,
    SemanticRoleEnum,
    SeverityEnum,
    DistributionAnalysis,
    NumericHistogram,
    HistogramBin,
    NumericBoxplot,
    CategoricalFrequencyChart,
    CategoricalFrequencyItem,
    DateDistributionChart,
    DateDistributionItem,
    TimeDistributionChart,
    RelationshipAnalysis,
    CorrelationMatrix,
    CategoricalAssociation,
    SuggestedAnalysis,
)


class ProfilerEngine:
    """Deterministic EDA profiler for tabular datasets."""

    # Regex patterns for common date/datetime formats
    DATE_PATTERNS = [
        re.compile(r"^\d{4}-\d{2}-\d{2}$"),
        re.compile(r"^\d{4}/\d{2}/\d{2}$"),
        re.compile(r"^\d{2}/\d{2}/\d{4}$"),
        re.compile(r"^\d{2}-\d{2}-\d{4}$"),
        re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}"),
        re.compile(r"^\d{4}/\d{2}/\d{2}[ T]\d{2}:\d{2}:\d{2}"),
        re.compile(r"^\d{2}/\d{2}/\d{4}[ T]\d{2}:\d{2}:\d{2}"),
    ]

    # Common string missing/null placeholder values
    MISSING_PLACEHOLDERS = {
        "", "na", "n/a", "null", "none", "nan", "nil", "missing", "undefined", "?", "-", ".", "void"
    }

    # Numeric placeholder values
    NUMERIC_PLACEHOLDERS = {999, -999, 9999, -9999, 99999, -99999}

    # Date placeholder values
    DATE_PLACEHOLDERS = {"0000-00-00", "1970-01-01", "1900-01-01", "0001-01-01"}

    # Role keyword patterns
    ID_PATTERN = re.compile(
        r"(^|_)(id|uuid|guid|pk|ssn|key|identifier|student_id|employee_id|customer_id|user_id|order_id|station_id)($|_)",
        re.IGNORECASE,
    )
    ID_KEYWORDS = {
        "id", "uuid", "guid", "key", "code", "pk", "ssn", "identifier",
        "student_id", "employee_id", "customer_id", "user_id", "order_id",
        "account_id", "account_no", "account_number", "phone", "phone_number", "station_id"
    }
    POSTAL_KEYWORDS = {"zip", "zipcode", "zip_code", "postal", "postal_code", "postcode", "pincode", "pin_code"}
    SEVERITY_KEYWORDS = {
        "severity", "status_code", "priority", "rating_code", "grade",
        "tier", "stage", "severity_code", "level_code", "risk_level"
    }
    BOOLEAN_KEYWORDS = {"is_", "has_", "flag", "active", "enabled", "in_stock", "can_", "should_"}
    TEXT_KEYWORDS = {
        "notes", "description", "comment", "comments", "review", "reviews",
        "feedback", "summary", "text", "message", "bio", "details", "body", "transcript"
    }
    MEASURE_KEYWORDS = {
        "price", "salary", "income", "revenue", "cost", "expenses", "profit",
        "age", "score", "gpa", "temperature", "weight", "height", "distance",
        "duration", "amount", "balance", "rate", "quantity", "sales", "volume",
        "speed", "latitude", "longitude", "pct", "percentage"
    }

    @classmethod
    def _is_identifier_name(cls, name: str) -> bool:
        """Accurately checks if a column name matches ID patterns using word/boundary matching."""
        n = name.lower().strip()
        if n in cls.ID_KEYWORDS:
            return True
        return bool(cls.ID_PATTERN.search(n))

    @classmethod
    def profile_csv_file(cls, file_path: str, delimiter: str = ",") -> Dict[str, Any]:
        """Backward-compatible entry point for profiling a CSV file."""
        return cls.profile_dataset(file_path=file_path, format_str="csv", delimiter=delimiter)

    @classmethod
    def profile_dataset(
        cls,
        file_path: str,
        format_str: str = "csv",
        sheet_name: Optional[str] = None,
        delimiter: Optional[str] = None,
        encoding: Optional[str] = None,
        parsing_warnings: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Profiles a dataset file (CSV, TSV, or XLSX) on disk."""
        start_time = time.time()
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        dataset_name = os.path.basename(file_path)
        warnings: List[str] = list(parsing_warnings or [])

        fmt = format_str.lower().lstrip(".")
        warnings: List[str] = list(parsing_warnings or [])

        # For larger files (>200 KB) in CSV/TSV format, use fast vectorized pandas profiling
        # to process 250k+ rows in seconds instead of hanging the HTTP worker thread.
        if file_size > 200_000 and fmt in ("csv", "tsv"):
            try:
                return cls._profile_dataset_fast(
                    file_path=file_path,
                    fmt=fmt,
                    sheet_name=sheet_name,
                    delimiter=delimiter,
                    encoding=encoding,
                    parsing_warnings=warnings,
                    file_size_bytes=file_size,
                    dataset_name=dataset_name,
                    start_time=start_time,
                )
            except Exception as e:
                import logging
                logging.getLogger("edagent.profiler").warning(f"Fast profiling failed, falling back to legacy path: {e}")

        headers: List[str] = []
        rows: List[List[Any]] = []

        # Read through the shared reader so headers/rows are identical to what the analysis
        # engine later loads (sanitised duplicate headers, padded ragged rows, same encoding).
        from app.services.data.reader import read_table_as_strings

        try:
            headers, rows, read_warnings = read_table_as_strings(
                file_path, fmt, sheet_name=sheet_name, delimiter=delimiter, encoding=encoding
            )
            warnings.extend(w for w in read_warnings if w not in warnings)
        except Exception as e:  # unreadable file -> an empty profile that explains why
            warnings.append(f"File read error: {e}")

        load_time = round(time.time() - start_time, 4)

        return cls.profile_data(
            headers=headers,
            rows=rows,
            file_size_bytes=file_size,
            dataset_name=dataset_name,
            selected_sheet=sheet_name if fmt == "xlsx" else None,
            load_time_seconds=load_time,
            parsing_warnings=warnings,
        )

    @classmethod
    def _profile_dataset_fast(
        cls,
        file_path: str,
        fmt: str,
        sheet_name: Optional[str],
        delimiter: Optional[str],
        encoding: Optional[str],
        parsing_warnings: List[str],
        file_size_bytes: int,
        dataset_name: str,
        start_time: float,
    ) -> Dict[str, Any]:
        """Vectorized fast profiling using pandas and numpy for large files (>200 KB)."""
        import pandas as pd
        import numpy as np
        from app.services.ingestion.validator import IngestionValidator
        from app.services.ingestion.parser import IngestionService
        from app.services.data.reader import IngestionService_format

        enc = encoding or IngestionValidator.detect_encoding(file_path)
        delim = delimiter or ("\t" if fmt == "tsv" else IngestionService._detect_delimiter(file_path, IngestionService_format(fmt), enc))

        df = pd.read_csv(file_path, delimiter=delim, encoding=enc, low_memory=False)
        load_time = round(time.time() - start_time, 4)

        raw_headers = [str(c).strip() for c in df.columns]
        headers, hw = IngestionService._sanitize_headers(raw_headers)
        df.columns = headers
        warnings = list(parsing_warnings) + list(hw)

        total_rows = len(df)
        total_cols = len(df.columns)

        # 1. Exact Duplicate Analysis
        exact_dup_count = int(df.duplicated().sum())
        dup_pct = round((exact_dup_count / max(1, total_rows)) * 100, 2)
        dup_samples = []
        if exact_dup_count > 0:
            dup_df = df[df.duplicated(keep=False)].head(5)
            dup_samples = [{"row": {col: str(v) if pd.notna(v) else "" for col, v in r.items()}, "occurrences": 2} for _, r in dup_df.iterrows()]

        # 2. Missingness Analysis
        missing_counts = df.isna().sum()
        total_cells = total_rows * total_cols
        total_missing = int(missing_counts.sum())
        missing_pct = round((total_missing / max(1, total_cells)) * 100, 2)
        per_col_missing = {col: round(float(missing_counts[col]) / max(1, total_rows) * 100, 2) for col in headers}
        cols_with_missing = [c for c, m in per_col_missing.items() if m > 0]
        missing_chart = [{"column": col, "missing_count": int(missing_counts[col]), "missing_percentage": per_col_missing[col]} for col in headers]

        # 3. Column Profiles
        col_profiles = []
        quality_warnings = []
        candidate_keys = []
        numeric_measures = {}
        categorical_series = {}

        sample_size = min(total_rows, 25000)
        sample_df = df.sample(n=sample_size, random_state=42) if total_rows > sample_size else df

        for h in headers:
            s_full = df[h]
            s_samp = sample_df[h]
            miss_count = int(missing_counts[h])
            miss_pct = per_col_missing[h]
            non_null = total_rows - miss_count
            distinct_count = int(s_full.nunique(dropna=True))
            is_unique = (distinct_count == total_rows and miss_count == 0)
            if is_unique:
                candidate_keys.append(h)

            dtype_str = str(s_full.dtype)
            is_num = pd.api.types.is_numeric_dtype(s_full) and not pd.api.types.is_bool_dtype(s_full)
            is_id = cls._is_identifier_name(h)

            numeric_sum = None
            categorical_sum = None
            date_sum = None
            sample_vals = [str(x) if pd.notna(x) else "" for x in s_full.dropna().head(5).tolist()]

            if is_num and not (is_id and distinct_count > 100):
                role = SemanticRoleEnum.MEASURE.value
                inferred = "integer" if "int" in dtype_str else "float"
                s_clean = s_full.dropna()
                if len(s_clean) > 0:
                    q25, q50, q75 = s_clean.quantile([0.25, 0.5, 0.75])
                    iqr = float(q75 - q25)
                    numeric_sum = {
                        "count": non_null,
                        "mean": round(float(s_clean.mean()), 4),
                        "std": round(float(s_clean.std()), 4) if len(s_clean) > 1 else 0.0,
                        "min": float(s_clean.min()),
                        "q25": float(q25),
                        "median": float(q50),
                        "q75": float(q75),
                        "max": float(s_clean.max()),
                        "iqr": iqr,
                        "zeros_count": int((s_clean == 0).sum()),
                        "zeros_percentage": round(float((s_clean == 0).sum()) / max(1, total_rows) * 100, 2),
                        "infinite_count": int(np.isinf(s_clean).sum()) if hasattr(s_clean, "values") else 0,
                        "nan_count": miss_count,
                    }
                    numeric_measures[h] = s_samp.dropna().astype(float).tolist()
            elif is_id or is_unique:
                role = SemanticRoleEnum.IDENTIFIER.value
                inferred = "string"
            elif distinct_count <= 2 and non_null > 0:
                role = SemanticRoleEnum.BOOLEAN.value
                inferred = "boolean"
                vc = s_full.value_counts(dropna=True).head(5)
                categorical_sum = {
                    "unique_count": distinct_count,
                    "top_values": [{"value": str(k), "count": int(v), "percentage": round(100.0 * v / max(1, non_null), 2)} for k, v in vc.items()],
                    "is_high_cardinality": False,
                }
            elif distinct_count <= 50 or (distinct_count <= 500 and distinct_count / max(1, non_null) < 0.1):
                role = SemanticRoleEnum.CATEGORY.value
                inferred = "string"
                vc = s_full.value_counts(dropna=True).head(10)
                categorical_sum = {
                    "unique_count": distinct_count,
                    "most_frequent_value": str(vc.index[0]) if len(vc) > 0 else None,
                    "most_frequent_count": int(vc.iloc[0]) if len(vc) > 0 else 0,
                    "most_frequent_percentage": round(100.0 * float(vc.iloc[0]) / max(1, non_null), 2) if len(vc) > 0 else 0,
                    "top_values": [{"value": str(k), "count": int(v), "percentage": round(100.0 * v / max(1, non_null), 2)} for k, v in vc.items()],
                    "is_high_cardinality": distinct_count > 100,
                }
                categorical_series[h] = s_samp.dropna().astype(str).tolist()
            else:
                role = SemanticRoleEnum.TEXT.value
                inferred = "string"

            if miss_pct > 50:
                quality_warnings.append({
                    "column": h,
                    "check_type": "high_missingness",
                    "severity": SeverityEnum.HIGH.value if miss_pct > 80 else SeverityEnum.MEDIUM.value,
                    "message": f"Column '{h}' has {miss_pct}% missing values.",
                    "affected_count": miss_count,
                })

            col_profiles.append({
                "name": h,
                "storage_dtype": dtype_str,
                "inferred_type": inferred,
                "semantic_role": role,
                "role_confidence": 0.95,
                "role_uncertainty_reason": None,
                "non_null_count": non_null,
                "missing_count": miss_count,
                "missing_percentage": miss_pct,
                "distinct_count": distinct_count,
                "is_unique": is_unique,
                "numeric_summary": numeric_sum,
                "categorical_summary": categorical_sum,
                "date_summary": date_sum,
                "sample_values": sample_vals,
            })

        # 4. Distributions
        histograms = []
        boxplots = []
        for h, vals in list(numeric_measures.items())[:25]:
            arr = np.array(vals)
            if len(arr) > 0 and np.isfinite(arr).any():
                clean_arr = arr[np.isfinite(arr)]
                counts, bin_edges = np.histogram(clean_arr, bins=10)
                bins = []
                for i in range(len(counts)):
                    bins.append({
                        "bin_start": float(bin_edges[i]),
                        "bin_end": float(bin_edges[i+1]),
                        "count": int(counts[i]),
                        "percentage": round(float(counts[i]) / max(1, len(clean_arr)) * 100, 2),
                    })
                histograms.append({"column": h, "bins": bins, "bin_count": len(bins)})

                q25, q50, q75 = np.percentile(clean_arr, [25, 50, 75])
                iqr = float(q75 - q25)
                lower_fence = q25 - 1.5 * iqr
                upper_fence = q75 + 1.5 * iqr
                outliers_mask = (clean_arr < lower_fence) | (clean_arr > upper_fence)
                outliers = int(outliers_mask.sum())
                boxplots.append({
                    "column": h,
                    "min": round(float(clean_arr.min()), 4),
                    "q25": round(float(q25), 4),
                    "median": round(float(q50), 4),
                    "q75": round(float(q75), 4),
                    "max": round(float(clean_arr.max()), 4),
                    "iqr": round(float(iqr), 4),
                    "lower_fence": round(float(lower_fence), 4),
                    "upper_fence": round(float(upper_fence), 4),
                    "outlier_count": outliers,
                    "outliers_sample": [round(float(x), 4) for x in clean_arr[outliers_mask][:10]],
                })

        cat_charts = []
        for h, vals in list(categorical_series.items())[:25]:
            vc = pd.Series(vals).value_counts().head(10)
            items = [{"category": str(k), "count": int(v), "percentage": round(100.0 * v / max(1, len(vals)), 2)} for k, v in vc.items()]
            cat_charts.append({"column": h, "frequencies": items, "distinct_categories_count": len(vc)})

        distributions = {
            "histograms": histograms,
            "boxplots": boxplots,
            "categorical_frequencies": cat_charts,
            "date_distributions": [],
            "time_distributions": [],
        }

        # 5. Relationships
        num_cols = [h for h in headers if h in numeric_measures][:30]
        matrix = {}
        if len(num_cols) >= 2:
            sub = sample_df[num_cols].apply(pd.to_numeric, errors="coerce")
            corr = sub.corr(method="pearson").fillna(0).round(4)
            for c1 in num_cols:
                matrix[c1] = {}
                for c2 in num_cols:
                    matrix[c1][c2] = float(corr.loc[c1, c2])

        relationships = {
            "pearson": {"matrix": matrix, "columns": num_cols},
            "spearman": None,
            "categorical_associations": [],
        }

        # 6. Recommendations
        missing_report = {
            "total_cells": total_cells,
            "missing_cells": total_missing,
            "overall_missing_percentage": missing_pct,
            "per_column": per_col_missing,
            "columns_with_missing": cols_with_missing,
            "missingness_chart_data": missing_chart,
            "missingness_patterns": [],
        }
        suggested_analyses, suggested_questions = cls._generate_recommendations(
            column_profiles=col_profiles,
            distributions=distributions,
            relationships=relationships,
            missing_report=missing_report,
        )

        duplicates_report = {
            "exact_duplicate_rows_count": exact_dup_count,
            "exact_duplicate_percentage": dup_pct,
            "candidate_duplicate_keys": candidate_keys,
            "duplicate_rows_sample": dup_samples,
        }

        prof_duration = round(time.time() - start_time, 4)

        return {
            "overview": {
                "dataset_name": dataset_name,
                "total_rows": total_rows,
                "total_columns": total_cols,
                "file_size_bytes": file_size_bytes,
                "memory_estimate_bytes": int(df.memory_usage(deep=False).sum()),
                "selected_sheet": sheet_name if fmt == "xlsx" else None,
                "load_time_seconds": load_time,
                "profiling_duration_seconds": prof_duration,
                "parsing_warnings": warnings,
            },
            "columns": col_profiles,
            "missingness": missing_report,
            "duplicates": duplicates_report,
            "distributions": distributions,
            "quality_warnings": quality_warnings,
            "relationships": relationships,
            "suggested_analyses": suggested_analyses,
            "suggested_questions": suggested_questions,
            "correlation_matrix": matrix if matrix else None,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def profile_data(
        cls,
        headers: List[str],
        rows: List[List[Any]],
        file_size_bytes: int = 0,
        dataset_name: str = "dataset",
        selected_sheet: Optional[str] = None,
        load_time_seconds: float = 0.0,
        parsing_warnings: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Pure deterministic EDA profiling calculation on tabular data.
        Zero LLM dependencies.
        """
        prof_start_time = time.time()
        total_rows = len(rows)
        total_cols = len(headers)
        warnings: List[str] = list(parsing_warnings or [])

        # Sanitize empty / headerless datasets
        if total_cols == 0:
            prof_duration = round(time.time() - prof_start_time, 4)
            return cls._empty_profile_payload(
                dataset_name=dataset_name,
                file_size_bytes=file_size_bytes,
                load_time_seconds=load_time_seconds,
                profiling_duration_seconds=prof_duration,
                parsing_warnings=warnings + ["Dataset contains no columns."],
            )

        # Pad or truncate rows to total_cols
        padded_rows: List[List[str]] = []
        for r in rows:
            str_r = [str(c).strip() if c is not None else "" for c in r]
            if len(str_r) < total_cols:
                str_r.extend([""] * (total_cols - len(str_r)))
            elif len(str_r) > total_cols:
                str_r = str_r[:total_cols]
            padded_rows.append(str_r)

        # 1. Exact Duplicate Analysis & Candidate Keys
        exact_duplicate_count, dup_pct, dup_sample = cls._analyze_duplicates(padded_rows, headers)

        # 2. Extract column-wise data arrays
        col_data: Dict[str, List[str]] = {h: [] for h in headers}
        for r in padded_rows:
            for idx, h in enumerate(headers):
                col_data[h].append(r[idx])

        # 3. Missingness Analysis
        total_cells = total_rows * total_cols
        missing_report = cls._analyze_missingness(col_data, total_rows, total_cols)

        # 4. Column Inventory, Role Inference, Descriptive Stats, & Column Quality Checks
        quality_warnings: List[Dict[str, Any]] = []
        column_profiles: List[Dict[str, Any]] = []
        parsed_dates_by_col: Dict[str, List[datetime]] = {}
        numeric_measures_by_col: Dict[str, List[float]] = {}
        categorical_series_by_col: Dict[str, List[str]] = {}

        candidate_keys: List[str] = []

        for h in headers:
            values = col_data[h]
            profile, c_warnings, parsed_dts, clean_nums, clean_cats = cls._profile_single_column(
                h, values, total_rows
            )
            column_profiles.append(profile)
            quality_warnings.extend(c_warnings)

            if parsed_dts:
                parsed_dates_by_col[h] = parsed_dts
            if clean_nums is not None and profile["semantic_role"] == SemanticRoleEnum.MEASURE.value:
                numeric_measures_by_col[h] = clean_nums
            if clean_cats is not None and profile["semantic_role"] in (
                SemanticRoleEnum.CATEGORY.value,
                SemanticRoleEnum.BOOLEAN.value,
            ):
                categorical_series_by_col[h] = clean_cats

            # Identify candidate primary keys (non-null and 100% unique)
            if profile["is_unique"] and profile["missing_count"] == 0:
                candidate_keys.append(h)
            elif (
                cls._is_identifier_name(h)
                and profile["distinct_count"] < total_rows
                and profile["distinct_count"] > 1
            ):
                # ID-like column that unexpectedly has duplicate keys
                dup_key_warning = {
                    "column": h,
                    "check_type": "candidate_duplicate_keys",
                    "severity": SeverityEnum.LOW.value,
                    "message": f"Column '{h}' matches key naming conventions but contains duplicate values.",
                    "affected_count": total_rows - profile["distinct_count"],
                }
                quality_warnings.append(dup_key_warning)

        # 5. Distribution Analysis (Histograms, Boxplots, Frequencies, Date distributions)
        distributions = cls._compute_distributions(
            column_profiles=column_profiles,
            numeric_measures=numeric_measures_by_col,
            categorical_series=categorical_series_by_col,
            parsed_dates=parsed_dates_by_col,
        )

        # 6. Relationships (Pearson, Spearman, Categorical Cramér's V)
        relationships = cls._compute_relationships(
            headers=headers,
            column_profiles=column_profiles,
            padded_rows=padded_rows,
            numeric_measures_by_col=numeric_measures_by_col,
            categorical_series_by_col=categorical_series_by_col,
        )

        # 7. Deterministic Recommendations
        suggested_analyses, suggested_questions = cls._generate_recommendations(
            column_profiles=column_profiles,
            distributions=distributions,
            relationships=relationships,
            missing_report=missing_report,
        )

        # Memory footprint calculation
        memory_footprint_bytes = cls._estimate_memory_footprint(col_data, total_rows)

        prof_duration = round(time.time() - prof_start_time, 4)

        # Assemble Duplicates Report
        duplicates_report = {
            "exact_duplicate_rows_count": exact_duplicate_count,
            "exact_duplicate_percentage": dup_pct,
            "candidate_duplicate_keys": candidate_keys,
            "duplicate_rows_sample": dup_sample,
        }

        # Format legacy correlation matrix for backward compatibility
        legacy_corr_matrix: Optional[Dict[str, Dict[str, Optional[float]]]] = None
        if relationships.get("pearson") and relationships["pearson"].get("matrix"):
            legacy_corr_matrix = relationships["pearson"]["matrix"]

        return {
            "overview": {
                "dataset_name": dataset_name,
                "total_rows": total_rows,
                "total_columns": total_cols,
                "file_size_bytes": file_size_bytes,
                "memory_estimate_bytes": memory_footprint_bytes,
                "selected_sheet": selected_sheet,
                "load_time_seconds": load_time_seconds,
                "profiling_duration_seconds": prof_duration,
                "parsing_warnings": warnings,
            },
            "columns": column_profiles,
            "missingness": missing_report,
            "duplicates": duplicates_report,
            "distributions": distributions,
            "quality_warnings": quality_warnings,
            "relationships": relationships,
            "suggested_analyses": suggested_analyses,
            "suggested_questions": suggested_questions,
            "correlation_matrix": legacy_corr_matrix,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

    # =========================================================================
    # Internal Computational Modules
    # =========================================================================

    @classmethod
    def _analyze_duplicates(
        cls, rows: List[List[str]], headers: List[str]
    ) -> Tuple[int, float, List[Dict[str, Any]]]:
        """Detects exact duplicate rows without classifying repeated IDs as duplicates."""
        total_rows = len(rows)
        if total_rows == 0:
            return 0, 0.0, []

        row_counts = Counter(tuple(r) for r in rows)
        exact_duplicate_count = sum(count - 1 for count in row_counts.values() if count > 1)
        duplicate_percentage = round((exact_duplicate_count / total_rows) * 100, 2)

        duplicate_samples: List[Dict[str, Any]] = []
        for r_tuple, count in row_counts.items():
            if count > 1:
                row_dict = {headers[i]: r_tuple[i] for i in range(min(len(headers), len(r_tuple)))}
                duplicate_samples.append({"row": row_dict, "occurrences": count})
                if len(duplicate_samples) >= 5:
                    break

        return exact_duplicate_count, duplicate_percentage, duplicate_samples

    @classmethod
    def _analyze_missingness(
        cls, col_data: Dict[str, List[str]], total_rows: int, total_cols: int
    ) -> Dict[str, Any]:
        """Calculates dataset and column missingness, chart data, and missing patterns."""
        total_cells = total_rows * total_cols
        total_missing = 0
        per_col_pct: Dict[str, float] = {}
        cols_with_missing: List[str] = []
        chart_data: List[Dict[str, Any]] = []

        if total_rows == 0:
            return {
                "total_cells": 0,
                "missing_cells": 0,
                "overall_missing_percentage": 0.0,
                "per_column": {h: 0.0 for h in col_data},
                "columns_with_missing": [],
                "missingness_chart_data": [],
                "missingness_patterns": [],
            }

        # Track missingness per row for pattern identification
        row_missing_masks: List[Tuple[str, ...]] = []
        row_count = total_rows

        for r_idx in range(row_count):
            missing_in_row = [
                h for h in col_data if cls._is_missing_or_placeholder(col_data[h][r_idx])
            ]
            if missing_in_row:
                row_missing_masks.append(tuple(sorted(missing_in_row)))

        for h, values in col_data.items():
            missing_count = sum(1 for v in values if cls._is_missing_or_placeholder(v))
            total_missing += missing_count
            pct = round((missing_count / total_rows) * 100, 2)
            per_col_pct[h] = pct

            if missing_count > 0:
                cols_with_missing.append(h)

            chart_data.append({
                "column": h,
                "missing_count": missing_count,
                "missing_percentage": pct,
                "present_count": total_rows - missing_count,
            })

        chart_data.sort(key=lambda x: x["missing_percentage"], reverse=True)

        overall_missing_pct = round((total_missing / total_cells) * 100, 2) if total_cells > 0 else 0.0

        # Pattern co-occurrence
        pattern_counts = Counter(row_missing_masks)
        patterns_list = [
            {"missing_columns": list(cols), "row_count": count, "percentage": round((count / total_rows) * 100, 2)}
            for cols, count in pattern_counts.most_common(5)
        ]

        return {
            "total_cells": total_cells,
            "missing_cells": total_missing,
            "overall_missing_percentage": overall_missing_pct,
            "per_column": per_col_pct,
            "columns_with_missing": cols_with_missing,
            "missingness_chart_data": chart_data,
            "missingness_patterns": patterns_list,
        }

    @classmethod
    def _is_missing_or_placeholder(cls, val: Any) -> bool:
        """Determines if a cell is empty or represents a missing placeholder."""
        if val is None:
            return True
        if isinstance(val, float) and math.isnan(val):
            return True
        s = str(val).strip().lower()
        return s in cls.MISSING_PLACEHOLDERS

    @classmethod
    def _profile_single_column(
        cls,
        col_name: str,
        values: List[str],
        total_rows: int,
    ) -> Tuple[
        Dict[str, Any],
        List[Dict[str, Any]],
        Optional[List[datetime]],
        Optional[List[float]],
        Optional[List[str]],
    ]:
        """Profiles a single column: type inference, semantic role, descriptive stats, and quality warnings."""
        quality_warnings: List[Dict[str, Any]] = []
        non_empty = [v for v in values if not cls._is_missing_or_placeholder(v)]
        missing_count = total_rows - len(non_empty)
        missing_percentage = round((missing_count / total_rows) * 100, 2) if total_rows > 0 else 0.0

        distinct_values = set(non_empty)
        distinct_count = len(distinct_values)
        is_unique = distinct_count == total_rows and total_rows > 0

        # Safe sample values (sanitizing CSV injection prefixes and truncating length)
        sample_values = [cls._sanitize_sample_value(v) for v in non_empty[:5]]

        # Quality Check: High Missingness
        if missing_percentage > 40.0:
            severity = SeverityEnum.HIGH.value if missing_percentage > 80.0 else SeverityEnum.MEDIUM.value
            quality_warnings.append({
                "column": col_name,
                "check_type": "high_missingness",
                "severity": severity,
                "message": f"Column '{col_name}' has {missing_percentage}% missing values.",
                "affected_count": missing_count,
            })

        # Quality Check: Constant or Near-Constant Column
        if distinct_count == 1 and total_rows > 0:
            quality_warnings.append({
                "column": col_name,
                "check_type": "constant",
                "severity": SeverityEnum.HIGH.value,
                "message": f"Column '{col_name}' is constant with a single value.",
                "affected_count": total_rows,
            })
        elif distinct_count == 2 and total_rows > 50:
            quality_warnings.append({
                "column": col_name,
                "check_type": "near_constant",
                "severity": SeverityEnum.LOW.value,
                "message": f"Column '{col_name}' has only 2 distinct values across {total_rows} rows.",
                "affected_count": None,
            })
        elif total_rows >= 20 and distinct_count > 1 and non_empty:
            top_val, top_cnt = Counter(non_empty).most_common(1)[0]
            top_ratio = top_cnt / len(non_empty)
            if top_ratio >= 0.95:
                quality_warnings.append({
                    "column": col_name,
                    "check_type": "near_constant",
                    "severity": SeverityEnum.LOW.value,
                    "message": f"Column '{col_name}' is near-constant: value '{top_val}' accounts for {round(top_ratio * 100, 2)}% of records.",
                    "affected_count": top_cnt,
                })

        # Quality Check: Suspicious placeholder strings
        suspicious_matches = [
            v for v in values if v.strip().lower() in {"?", "-", "n/a", "null", "none", "unknown", "void"}
        ]
        if suspicious_matches:
            quality_warnings.append({
                "column": col_name,
                "check_type": "suspicious_values",
                "severity": SeverityEnum.LOW.value,
                "message": f"Column '{col_name}' contains {len(suspicious_matches)} placeholder value(s) (e.g. '{suspicious_matches[0]}').",
                "affected_count": len(suspicious_matches),
            })

        # 1. Evaluate Date/Time
        parsed_dates, invalid_date_count, tz_warnings = cls._evaluate_dates(col_name, non_empty)
        parse_success_rate = (
            round((len(parsed_dates) / len(non_empty)) * 100, 2) if non_empty else 0.0
        )

        name_lower = col_name.lower().strip()

        # Date Summary
        date_summary: Optional[Dict[str, Any]] = None
        if parsed_dates and (
            parse_success_rate >= 70.0
            or any(k in name_lower for k in ("date", "time", "created_at", "updated_at", "timestamp", "dob"))
        ):
            sorted_dates = sorted(parsed_dates)
            min_date_str = sorted_dates[0].isoformat()
            max_date_str = sorted_dates[-1].isoformat()
            date_range_days = (sorted_dates[-1] - sorted_dates[0]).days

            date_summary = {
                "parse_success_rate": parse_success_rate,
                "min_date": min_date_str,
                "max_date": max_date_str,
                "invalid_date_count": invalid_date_count,
                "date_range_days": date_range_days,
                "timezone_warnings": tz_warnings,
            }

            if invalid_date_count > 0:
                quality_warnings.append({
                    "column": col_name,
                    "check_type": "invalid_dates",
                    "severity": SeverityEnum.MEDIUM.value,
                    "message": f"Column '{col_name}' contains {invalid_date_count} unparseable date values.",
                    "affected_count": invalid_date_count,
                })

            for tzw in tz_warnings:
                quality_warnings.append({
                    "column": col_name,
                    "check_type": "invalid_dates",
                    "severity": SeverityEnum.LOW.value,
                    "message": tzw,
                    "affected_count": None,
                })

            profile = {
                "name": col_name,
                "storage_dtype": "datetime",
                "inferred_type": "datetime",
                "semantic_role": SemanticRoleEnum.DATETIME.value,
                "role_confidence": round(min(0.99, max(0.70, parse_success_rate / 100.0)), 2),
                "role_uncertainty_reason": None,
                "non_null_count": len(non_empty),
                "missing_count": missing_count,
                "missing_percentage": missing_percentage,
                "distinct_count": distinct_count,
                "is_unique": is_unique,
                "numeric_summary": None,
                "categorical_summary": None,
                "date_summary": date_summary,
                "sample_values": sample_values,
            }
            return profile, quality_warnings, parsed_dates, None, None

        # 2. Evaluate Boolean
        lowered_distinct = {v.lower() for v in distinct_values}
        is_boolean = False
        if lowered_distinct.issubset({"true", "false", "t", "f", "yes", "no", "y", "n"}):
            is_boolean = True
        elif lowered_distinct.issubset({"0", "1"}) and any(
            name_lower.startswith(pref) for pref in ("is_", "has_", "flag_", "can_", "in_")
        ):
            is_boolean = True

        if is_boolean:
            cat_summary = cls._compute_categorical_summary(non_empty, distinct_count)
            profile = {
                "name": col_name,
                "storage_dtype": "boolean",
                "inferred_type": "boolean",
                "semantic_role": SemanticRoleEnum.BOOLEAN.value,
                "role_confidence": 0.98,
                "role_uncertainty_reason": None,
                "non_null_count": len(non_empty),
                "missing_count": missing_count,
                "missing_percentage": missing_percentage,
                "distinct_count": distinct_count,
                "is_unique": is_unique,
                "numeric_summary": None,
                "categorical_summary": cat_summary,
                "date_summary": None,
                "sample_values": sample_values,
            }
            return profile, quality_warnings, None, None, non_empty

        # 3. Evaluate Numeric
        numeric_vals, inf_count, nan_count, non_num_count = cls._extract_numeric_values(non_empty)
        is_all_numeric = (len(numeric_vals) + inf_count + nan_count == len(non_empty)) and len(non_empty) > 0

        # Mixed types warning
        if len(numeric_vals) > 0 and non_num_count > 0:
            quality_warnings.append({
                "column": col_name,
                "check_type": "mixed_types",
                "severity": SeverityEnum.MEDIUM.value,
                "message": f"Column '{col_name}' contains mixed data types ({len(numeric_vals)} numeric, {non_num_count} string/text).",
                "affected_count": non_num_count,
            })

        if inf_count > 0:
            quality_warnings.append({
                "column": col_name,
                "check_type": "infinite_values",
                "severity": SeverityEnum.HIGH.value,
                "message": f"Column '{col_name}' contains {inf_count} infinite numeric value(s).",
                "affected_count": inf_count,
            })

        if is_all_numeric and numeric_vals:
            # Check integer vs float storage dtype
            is_all_ints = all(x.is_integer() for x in numeric_vals)
            storage_dtype = "integer" if is_all_ints else "float"

            num_summary = cls._compute_numeric_summary(
                numeric_vals, inf_count=inf_count, nan_count=missing_count + nan_count
            )

            # Check domain-specific out-of-range checks
            cls._check_out_of_range(col_name, name_lower, numeric_vals, quality_warnings)

            # Role: Postal / Zip Code check
            if any(k in name_lower for k in cls.POSTAL_KEYWORDS):
                cat_summary = cls._compute_categorical_summary(non_empty, distinct_count)
                profile = {
                    "name": col_name,
                    "storage_dtype": storage_dtype,
                    "inferred_type": storage_dtype,
                    "semantic_role": SemanticRoleEnum.CATEGORY.value,
                    "role_confidence": 0.95,
                    "role_uncertainty_reason": "Postal/ZIP codes are geographic discrete categories rather than measurable quantities.",
                    "non_null_count": len(non_empty),
                    "missing_count": missing_count,
                    "missing_percentage": missing_percentage,
                    "distinct_count": distinct_count,
                    "is_unique": is_unique,
                    "numeric_summary": num_summary,
                    "categorical_summary": cat_summary,
                    "date_summary": None,
                    "sample_values": sample_values,
                }
                return profile, quality_warnings, None, None, non_empty

            # Role: Severity / Status / Rating code check
            if any(k in name_lower for k in cls.SEVERITY_KEYWORDS) and (
                distinct_count <= 15 or distinct_count / len(non_empty) <= 0.1
            ):
                cat_summary = cls._compute_categorical_summary(non_empty, distinct_count)
                profile = {
                    "name": col_name,
                    "storage_dtype": storage_dtype,
                    "inferred_type": storage_dtype,
                    "semantic_role": SemanticRoleEnum.CATEGORY.value,
                    "role_confidence": 0.92,
                    "role_uncertainty_reason": f"Column '{col_name}' represents discrete category/severity codes.",
                    "non_null_count": len(non_empty),
                    "missing_count": missing_count,
                    "missing_percentage": missing_percentage,
                    "distinct_count": distinct_count,
                    "is_unique": is_unique,
                    "numeric_summary": num_summary,
                    "categorical_summary": cat_summary,
                    "date_summary": None,
                    "sample_values": sample_values,
                }
                return profile, quality_warnings, None, None, non_empty

            # Role: Identifier check
            is_id_name = cls._is_identifier_name(name_lower)
            is_perfect_sequence = (
                is_all_ints
                and distinct_count == total_rows
                and total_rows > 5
                and (max(numeric_vals) - min(numeric_vals) == total_rows - 1)
            )

            # A column of all-distinct *decimals* (e.g. salary 52340.17) is a continuous measurement,
            # not an identifier; only unique whole numbers without a measure-like name are treated as IDs.
            is_measure_name = any(k in name_lower for k in cls.MEASURE_KEYWORDS)
            is_unique_int_id = is_unique and total_rows > 10 and is_all_ints and not is_measure_name
            if is_id_name or is_unique_int_id or is_perfect_sequence:
                quality_warnings.append({
                    "column": col_name,
                    "check_type": "possible_id",
                    "severity": SeverityEnum.LOW.value,
                    "message": f"Column '{col_name}' is numeric but behaves like an identifier. Exclude from correlation analysis by default.",
                    "affected_count": None,
                })
                profile = {
                    "name": col_name,
                    "storage_dtype": storage_dtype,
                    "inferred_type": storage_dtype,
                    "semantic_role": SemanticRoleEnum.IDENTIFIER.value,
                    "role_confidence": 0.95 if is_id_name else 0.85,
                    "role_uncertainty_reason": "High uniqueness or ID-matching name indicates entity identifier.",
                    "non_null_count": len(non_empty),
                    "missing_count": missing_count,
                    "missing_percentage": missing_percentage,
                    "distinct_count": distinct_count,
                    "is_unique": is_unique,
                    "numeric_summary": num_summary,
                    "categorical_summary": None,
                    "date_summary": None,
                    "sample_values": sample_values,
                }
                return profile, quality_warnings, None, None, None

            # Encoded categorical numbers (e.g., status 0, 1, 2 with small cardinality)
            if distinct_count <= 5 and total_rows > 20:
                cat_summary = cls._compute_categorical_summary(non_empty, distinct_count)
                profile = {
                    "name": col_name,
                    "storage_dtype": storage_dtype,
                    "inferred_type": storage_dtype,
                    "semantic_role": SemanticRoleEnum.CATEGORY.value,
                    "role_confidence": 0.88,
                    "role_uncertainty_reason": f"Small distinct count ({distinct_count}) indicates numeric encoded categories.",
                    "non_null_count": len(non_empty),
                    "missing_count": missing_count,
                    "missing_percentage": missing_percentage,
                    "distinct_count": distinct_count,
                    "is_unique": is_unique,
                    "numeric_summary": num_summary,
                    "categorical_summary": cat_summary,
                    "date_summary": None,
                    "sample_values": sample_values,
                }
                return profile, quality_warnings, None, None, non_empty

            # Default: Numeric Measure
            profile = {
                "name": col_name,
                "storage_dtype": storage_dtype,
                "inferred_type": storage_dtype,
                "semantic_role": SemanticRoleEnum.MEASURE.value,
                "role_confidence": 0.95,
                "role_uncertainty_reason": None,
                "non_null_count": len(non_empty),
                "missing_count": missing_count,
                "missing_percentage": missing_percentage,
                "distinct_count": distinct_count,
                "is_unique": is_unique,
                "numeric_summary": num_summary,
                "categorical_summary": None,
                "date_summary": None,
                "sample_values": sample_values,
            }
            return profile, quality_warnings, None, numeric_vals, None

        # 4. Text / Categorical / Identifier Evaluation (String Data)
        cat_summary = cls._compute_categorical_summary(non_empty, distinct_count)

        # Check extreme class imbalance
        if cat_summary["top_values"] and len(non_empty) >= 50:
            top_pct = cat_summary["top_values"][0]["percentage"]
            if top_pct >= 99.0 and distinct_count > 1:
                quality_warnings.append({
                    "column": col_name,
                    "check_type": "unusual_distribution",
                    "severity": SeverityEnum.LOW.value,
                    "message": f"Column '{col_name}' exhibits severe class imbalance: '{cat_summary['top_values'][0]['value']}' represents {top_pct}% of records.",
                    "affected_count": cat_summary["top_values"][0]["count"],
                })

        # Check Identifier
        if (
            cls._is_identifier_name(name_lower)
            and (distinct_count / max(len(non_empty), 1) >= 0.7 or is_unique)
        ):
            profile = {
                "name": col_name,
                "storage_dtype": "string",
                "inferred_type": "string",
                "semantic_role": SemanticRoleEnum.IDENTIFIER.value,
                "role_confidence": 0.95,
                "role_uncertainty_reason": "High uniqueness and ID naming pattern.",
                "non_null_count": len(non_empty),
                "missing_count": missing_count,
                "missing_percentage": missing_percentage,
                "distinct_count": distinct_count,
                "is_unique": is_unique,
                "numeric_summary": None,
                "categorical_summary": cat_summary,
                "date_summary": None,
                "sample_values": sample_values,
            }
            return profile, quality_warnings, None, None, None

        # Check Free-Text
        avg_str_len = (
            sum(len(s) for s in non_empty) / max(len(non_empty), 1) if non_empty else 0
        )
        has_text_keywords = any(k in name_lower for k in cls.TEXT_KEYWORDS)
        if (
            (avg_str_len > 35 and distinct_count / max(len(non_empty), 1) > 0.4)
            or has_text_keywords
            or any(len(s) > 80 and " " in s for s in non_empty[:10])
        ):
            profile = {
                "name": col_name,
                "storage_dtype": "string",
                "inferred_type": "string",
                "semantic_role": SemanticRoleEnum.TEXT.value,
                "role_confidence": 0.92,
                "role_uncertainty_reason": "Long string lengths and unstructured text characteristics.",
                "non_null_count": len(non_empty),
                "missing_count": missing_count,
                "missing_percentage": missing_percentage,
                "distinct_count": distinct_count,
                "is_unique": is_unique,
                "numeric_summary": None,
                "categorical_summary": cat_summary,
                "date_summary": None,
                "sample_values": sample_values,
            }
            return profile, quality_warnings, None, None, None

        # Default: Categorical
        profile = {
            "name": col_name,
            "storage_dtype": "string",
            "inferred_type": "string",
            "semantic_role": SemanticRoleEnum.CATEGORY.value,
            "role_confidence": 0.90,
            "role_uncertainty_reason": None,
            "non_null_count": len(non_empty),
            "missing_count": missing_count,
            "missing_percentage": missing_percentage,
            "distinct_count": distinct_count,
            "is_unique": is_unique,
            "numeric_summary": None,
            "categorical_summary": cat_summary,
            "date_summary": None,
            "sample_values": sample_values,
        }
        return profile, quality_warnings, None, None, non_empty

    # =========================================================================
    # Helpers for Statistics & Type Evaluation
    # =========================================================================

    @classmethod
    def _evaluate_dates(
        cls, col_name: str, values: List[str]
    ) -> Tuple[List[datetime], int, List[str]]:
        """Attempts to parse dates and detects timezone characteristics."""
        parsed_dates: List[datetime] = []
        invalid_count = 0
        tz_offsets: Set[Optional[Any]] = set()
        has_aware = False
        has_naive = False

        sample_subset = values[:100] if len(values) > 100 else values

        # Quick pre-filter: check if sample matches date patterns
        matching_sample = sum(
            1 for v in sample_subset if any(p.match(v) for p in cls.DATE_PATTERNS)
        )
        if matching_sample / max(len(sample_subset), 1) < 0.3 and not any(
            k in col_name.lower() for k in ("date", "time", "timestamp", "dob")
        ):
            return [], 0, []

        for v in values:
            if v in cls.DATE_PLACEHOLDERS:
                invalid_count += 1
                continue
            try:
                # Use dateutil parser with fuzzy=False for strict verification
                dt = date_parser.parse(v, fuzzy=False)
                parsed_dates.append(dt)
                if dt.tzinfo is not None:
                    has_aware = True
                    tz_offsets.add(dt.utcoffset())
                else:
                    has_naive = True
            except (ValueError, TypeError, OverflowError):
                invalid_count += 1

        tz_warnings: List[str] = []
        if has_aware and has_naive:
            tz_warnings.append(
                f"Column '{col_name}' contains a mix of timezone-aware and timezone-naive timestamps."
            )
        if len(tz_offsets) > 1:
            tz_warnings.append(
                f"Column '{col_name}' contains timestamps with multiple differing timezone offsets."
            )

        return parsed_dates, invalid_count, tz_warnings

    @classmethod
    def _extract_numeric_values(
        cls, values: List[str]
    ) -> Tuple[List[float], int, int, int]:
        """Separates finite numbers from infinities, NaNs, and strings."""
        numeric_vals: List[float] = []
        inf_count = 0
        nan_count = 0
        non_num_count = 0

        for v in values:
            s = v.strip().lower()
            if s in ("inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"):
                inf_count += 1
            elif s in ("nan", "+nan", "-nan"):
                nan_count += 1
            else:
                try:
                    num = float(s)
                    if math.isinf(num):
                        inf_count += 1
                    elif math.isnan(num):
                        nan_count += 1
                    else:
                        numeric_vals.append(num)
                except ValueError:
                    non_num_count += 1

        return numeric_vals, inf_count, nan_count, non_num_count

    @classmethod
    def _compute_numeric_summary(
        cls,
        numeric_vals: List[float],
        inf_count: int = 0,
        nan_count: int = 0,
    ) -> Dict[str, Any]:
        """Calculates robust descriptive statistics for numeric measurements."""
        n = len(numeric_vals)
        if n == 0:
            return {
                "count": 0,
                "mean": None,
                "std": None,
                "min": None,
                "q25": None,
                "median": None,
                "q75": None,
                "max": None,
                "iqr": None,
                "skewness": None,
                "kurtosis": None,
                "zeros_count": 0,
                "zeros_percentage": 0.0,
                "infinite_count": inf_count,
                "nan_count": nan_count,
            }

        arr = np.array(numeric_vals, dtype=np.float64)
        mean_val = float(np.mean(arr))
        std_val = float(np.std(arr, ddof=1)) if n > 1 else 0.0
        min_val = float(np.min(arr))
        max_val = float(np.max(arr))

        q25 = float(np.percentile(arr, 25))
        median_val = float(np.percentile(arr, 50))
        q75 = float(np.percentile(arr, 75))
        iqr = float(q75 - q25)

        # Skewness & Kurtosis
        skew_val = 0.0
        kurt_val = 0.0
        if n >= 3 and std_val > 0:
            try:
                skew_val = float(stats.skew(arr, bias=False))
            except Exception:
                skew_val = 0.0
        if n >= 4 and std_val > 0:
            try:
                kurt_val = float(stats.kurtosis(arr, bias=False))
            except Exception:
                kurt_val = 0.0

        zeros_cnt = int(np.sum(arr == 0))
        zeros_pct = round((zeros_cnt / n) * 100, 2)

        return {
            "count": n,
            "mean": round(mean_val, 4),
            "std": round(std_val, 4),
            "min": round(min_val, 4),
            "q25": round(q25, 4),
            "median": round(median_val, 4),
            "q75": round(q75, 4),
            "max": round(max_val, 4),
            "iqr": round(iqr, 4),
            "skewness": round(skew_val, 4),
            "kurtosis": round(kurt_val, 4),
            "zeros_count": zeros_cnt,
            "zeros_percentage": zeros_pct,
            "infinite_count": inf_count,
            "nan_count": nan_count,
        }

    @classmethod
    def _compute_categorical_summary(
        cls, values: List[str], distinct_count: int
    ) -> Dict[str, Any]:
        """Calculates categorical frequency distribution."""
        n = len(values)
        if n == 0:
            return {
                "unique_count": 0,
                "most_frequent_value": None,
                "most_frequent_count": None,
                "most_frequent_percentage": None,
                "top_values": [],
                "is_high_cardinality": False,
            }

        counts = Counter(values)
        most_common = counts.most_common(10)
        mode_val, mode_cnt = most_common[0]

        top_values = [
            {
                "value": str(k),
                "count": int(v),
                "percentage": round((v / n) * 100, 2),
            }
            for k, v in most_common
        ]

        is_high_card = distinct_count > 50 or (distinct_count / n > 0.5 and n > 20)

        return {
            "unique_count": distinct_count,
            "most_frequent_value": str(mode_val),
            "most_frequent_count": int(mode_cnt),
            "most_frequent_percentage": round((mode_cnt / n) * 100, 2),
            "top_values": top_values,
            "is_high_cardinality": is_high_card,
        }

    @classmethod
    def _check_out_of_range(
        cls,
        col_name: str,
        name_lower: str,
        numeric_vals: List[float],
        quality_warnings: List[Dict[str, Any]],
    ) -> None:
        """Domain heuristics for out-of-range checks without assuming they are incorrect."""
        # Age check
        if "age" in name_lower:
            invalid_age = [x for x in numeric_vals if x < 0 or x > 130]
            if invalid_age:
                quality_warnings.append({
                    "column": col_name,
                    "check_type": "possible_out_of_range",
                    "severity": SeverityEnum.LOW.value,
                    "message": f"Column '{col_name}' contains {len(invalid_age)} value(s) outside expected human age range (0-130).",
                    "affected_count": len(invalid_age),
                })
        # Monetary / Quantity negative checks
        elif any(k in name_lower for k in ("price", "salary", "income", "revenue", "cost", "quantity")):
            negatives = [x for x in numeric_vals if x < 0]
            if negatives:
                quality_warnings.append({
                    "column": col_name,
                    "check_type": "possible_out_of_range",
                    "severity": SeverityEnum.LOW.value,
                    "message": f"Column '{col_name}' contains {len(negatives)} negative value(s). Verify if negative quantities represent valid adjustments or refunds.",
                    "affected_count": len(negatives),
                })
        # Percentage checks
        elif any(k in name_lower for k in ("percent", "pct", "percentage")):
            out_of_bound = [x for x in numeric_vals if x < 0 or x > 100]
            if out_of_bound:
                quality_warnings.append({
                    "column": col_name,
                    "check_type": "possible_out_of_range",
                    "severity": SeverityEnum.LOW.value,
                    "message": f"Column '{col_name}' contains {len(out_of_bound)} value(s) outside 0-100% range.",
                    "affected_count": len(out_of_bound),
                })

    @classmethod
    def _sanitize_sample_value(cls, val: Any) -> Any:
        """Sanitizes sample values against formula injection and truncates length."""
        s = str(val).strip()
        if len(s) > 100:
            s = s[:97] + "..."
        # Formula injection mitigation
        if s.startswith(("=", "+", "-", "@")):
            s = "'" + s
        return s

    @classmethod
    def _estimate_memory_footprint(
        cls, col_data: Dict[str, List[str]], total_rows: int
    ) -> int:
        """Approximates columnar memory footprint in bytes."""
        if total_rows == 0:
            return 0
        total_bytes = 0
        for _, vals in col_data.items():
            col_bytes = sum(len(s.encode("utf-8")) + 48 for s in vals)  # string overhead
            total_bytes += col_bytes
        # Add list container overhead
        total_bytes += total_rows * 64
        return total_bytes

    # =========================================================================
    # Distribution Computations
    # =========================================================================

    @classmethod
    def _compute_distributions(
        cls,
        column_profiles: List[Dict[str, Any]],
        numeric_measures: Dict[str, List[float]],
        categorical_series: Dict[str, List[str]],
        parsed_dates: Dict[str, List[datetime]],
    ) -> Dict[str, Any]:
        """Generates histograms, boxplots, category frequency charts, and date/time distributions."""
        histograms: List[Dict[str, Any]] = []
        boxplots: List[Dict[str, Any]] = []
        cat_frequencies: List[Dict[str, Any]] = []
        date_distributions: List[Dict[str, Any]] = []
        time_distributions: List[Dict[str, Any]] = []

        # 1. Numeric Histograms & Boxplots
        for col_name, vals in numeric_measures.items():
            if not vals:
                continue
            arr = np.array(vals, dtype=np.float64)
            n = len(arr)
            min_v = float(np.min(arr))
            max_v = float(np.max(arr))

            # Boxplot calculation
            q25 = float(np.percentile(arr, 25))
            median_v = float(np.percentile(arr, 50))
            q75 = float(np.percentile(arr, 75))
            iqr = q75 - q25
            lower_fence = q25 - 1.5 * iqr
            upper_fence = q75 + 1.5 * iqr

            outliers = [float(x) for x in arr if x < lower_fence or x > upper_fence]
            boxplots.append({
                "column": col_name,
                "min": round(min_v, 4),
                "q25": round(q25, 4),
                "median": round(median_v, 4),
                "q75": round(q75, 4),
                "max": round(max_v, 4),
                "iqr": round(iqr, 4),
                "lower_fence": round(lower_fence, 4),
                "upper_fence": round(upper_fence, 4),
                "outlier_count": len(outliers),
                "outliers_sample": [round(x, 4) for x in outliers[:10]],
            })

            # Histogram calculation with sensible binning
            if min_v == max_v:
                bins = [{
                    "bin_start": round(min_v, 4),
                    "bin_end": round(max_v, 4),
                    "count": n,
                    "percentage": 100.0,
                }]
            else:
                # Sturges' rule clamped to [5, 15]
                k = max(5, min(15, int(math.ceil(math.log2(n) + 1))))
                counts, bin_edges = np.histogram(arr, bins=k)
                bins = []
                for b_idx in range(len(counts)):
                    cnt = int(counts[b_idx])
                    pct = round((cnt / n) * 100, 2)
                    bins.append({
                        "bin_start": round(float(bin_edges[b_idx]), 4),
                        "bin_end": round(float(bin_edges[b_idx + 1]), 4),
                        "count": cnt,
                        "percentage": pct,
                    })

            histograms.append({
                "column": col_name,
                "bins": bins,
            })

        # 2. Categorical Frequency Charts (capped to top 10 + Other)
        for col_name, vals in categorical_series.items():
            if not vals:
                continue
            counts = Counter(vals)
            total_n = len(vals)
            most_common = counts.most_common(10)
            categories = [
                {
                    "value": str(k),
                    "count": int(v),
                    "percentage": round((v / total_n) * 100, 2),
                }
                for k, v in most_common
            ]
            top_sum = sum(item["count"] for item in categories)
            other_cnt = total_n - top_sum
            other_pct = round((other_cnt / total_n) * 100, 2)

            cat_frequencies.append({
                "column": col_name,
                "categories": categories,
                "other_count": other_cnt,
                "other_percentage": other_pct,
            })

        # 3. Date & Time Distributions
        for col_name, dts in parsed_dates.items():
            if not dts:
                continue
            sorted_dts = sorted(dts)
            span_days = (sorted_dts[-1] - sorted_dts[0]).days

            # Choose grouping unit
            if span_days > 730:
                unit = "year"
                fmt = "%Y"
            elif span_days > 60:
                unit = "month"
                fmt = "%Y-%m"
            else:
                unit = "day"
                fmt = "%Y-%m-%d"

            period_counts = Counter(d.strftime(fmt) for d in sorted_dts)
            buckets = [
                {"period": period, "count": count}
                for period, count in sorted(period_counts.items())
            ]
            date_distributions.append({
                "column": col_name,
                "unit": unit,
                "buckets": buckets,
            })

            # Time of day / Day of week
            dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            dow_counts = Counter(d.strftime("%A") for d in dts)
            dow_dict = {day: dow_counts.get(day, 0) for day in dow_order}

            has_time = any(d.hour != 0 or d.minute != 0 or d.second != 0 for d in dts)
            hod_dict: Dict[str, int] = {}
            if has_time:
                hod_counts = Counter(d.hour for d in dts)
                hod_dict = {str(h): hod_counts.get(h, 0) for h in range(24)}

            time_distributions.append({
                "column": col_name,
                "day_of_week": dow_dict,
                "hour_of_day": hod_dict,
            })

        return {
            "histograms": histograms,
            "boxplots": boxplots,
            "categorical_frequencies": cat_frequencies,
            "date_distributions": date_distributions,
            "time_distributions": time_distributions,
        }

    # =========================================================================
    # Relationships Computations (Pearson, Spearman, Cramér's V)
    # =========================================================================

    @classmethod
    def _compute_relationships(
        cls,
        headers: List[str],
        column_profiles: List[Dict[str, Any]],
        padded_rows: List[List[str]],
        numeric_measures_by_col: Dict[str, List[float]],
        categorical_series_by_col: Dict[str, List[str]],
    ) -> Dict[str, Any]:
        """Calculates Pearson/Spearman correlations and categorical Cramér's V."""
        warnings: List[str] = []
        excluded_columns: List[str] = []

        measure_cols = list(numeric_measures_by_col.keys())
        all_cols_set = set(headers)

        for p in column_profiles:
            c_name = p["name"]
            if c_name not in measure_cols:
                excluded_columns.append(c_name)
                warnings.append(
                    f"Column '{c_name}' excluded from numeric correlation analysis (role: {p['semantic_role']})."
                )

        # Check measure columns variance
        valid_measures: List[str] = []
        col_to_idx = {h: i for i, h in enumerate(headers)}

        for col in measure_cols:
            vals = numeric_measures_by_col[col]
            if len(vals) < 3:
                warnings.append(
                    f"Column '{col}' has fewer than 3 valid observations; excluded from correlation."
                )
            elif float(np.std(vals)) == 0.0:
                warnings.append(
                    f"Column '{col}' has zero variance (constant values); excluded from correlation."
                )
            else:
                valid_measures.append(col)

        pearson_matrix: Dict[str, Dict[str, Optional[float]]] = {}
        spearman_matrix: Dict[str, Dict[str, Optional[float]]] = {}

        for col1 in valid_measures:
            pearson_matrix[col1] = {}
            spearman_matrix[col1] = {}
            for col2 in valid_measures:
                if col1 == col2:
                    pearson_matrix[col1][col2] = 1.0
                    spearman_matrix[col1][col2] = 1.0
                    continue

                idx1, idx2 = col_to_idx[col1], col_to_idx[col2]
                paired_x: List[float] = []
                paired_y: List[float] = []

                for r in padded_rows:
                    v1_str, v2_str = r[idx1], r[idx2]
                    if not cls._is_missing_or_placeholder(v1_str) and not cls._is_missing_or_placeholder(v2_str):
                        try:
                            x = float(v1_str)
                            y = float(v2_str)
                            if math.isfinite(x) and math.isfinite(y):
                                paired_x.append(x)
                                paired_y.append(y)
                        except ValueError:
                            pass

                if len(paired_x) < 3:
                    warnings.append(
                        f"Insufficient overlapping observations between '{col1}' and '{col2}' (count={len(paired_x)} < 3)."
                    )
                    pearson_matrix[col1][col2] = None
                    spearman_matrix[col1][col2] = None
                    continue

                arr_x = np.array(paired_x, dtype=np.float64)
                arr_y = np.array(paired_y, dtype=np.float64)

                if np.std(arr_x) == 0.0 or np.std(arr_y) == 0.0:
                    pearson_matrix[col1][col2] = None
                    spearman_matrix[col1][col2] = None
                    continue

                try:
                    p_res = stats.pearsonr(arr_x, arr_y)
                    r_val = float(p_res.statistic) if hasattr(p_res, "statistic") else float(p_res[0])
                    pearson_matrix[col1][col2] = round(r_val, 4) if not math.isnan(r_val) else None
                except Exception:
                    pearson_matrix[col1][col2] = None

                try:
                    s_res = stats.spearmanr(arr_x, arr_y)
                    rho_val = float(s_res.statistic) if hasattr(s_res, "statistic") else float(s_res[0])
                    spearman_matrix[col1][col2] = round(rho_val, 4) if not math.isnan(rho_val) else None
                except Exception:
                    spearman_matrix[col1][col2] = None

        # Categorical comparisons via Cramér's V
        categorical_associations: List[Dict[str, Any]] = []
        cat_cols = list(categorical_series_by_col.keys())[:5]  # Limit to top 5 categorical columns

        for i in range(len(cat_cols)):
            for j in range(i + 1, len(cat_cols)):
                c1, c2 = cat_cols[i], cat_cols[j]
                idx1, idx2 = col_to_idx[c1], col_to_idx[c2]

                paired_pairs = []
                for r in padded_rows:
                    v1_str, v2_str = r[idx1], r[idx2]
                    if not cls._is_missing_or_placeholder(v1_str) and not cls._is_missing_or_placeholder(v2_str):
                        paired_pairs.append((v1_str, v2_str))

                if len(paired_pairs) >= 10:
                    pair_counts = Counter(paired_pairs)
                    cats_x = sorted(list({p[0] for p in paired_pairs}))
                    cats_y = sorted(list({p[1] for p in paired_pairs}))

                    if len(cats_x) >= 2 and len(cats_y) >= 2:
                        contingency = np.zeros((len(cats_x), len(cats_y)), dtype=np.int64)
                        for r_idx, cx in enumerate(cats_x):
                            for c_idx, cy in enumerate(cats_y):
                                contingency[r_idx, c_idx] = pair_counts.get((cx, cy), 0)

                        try:
                            chi2, p_val, _, _ = stats.chi2_contingency(contingency)
                            n_obs = len(paired_pairs)
                            min_dim = min(len(cats_x) - 1, len(cats_y) - 1)
                            if min_dim >= 1 and n_obs > 0:
                                cramers_v = math.sqrt(chi2 / (n_obs * min_dim))
                                cramers_v = min(1.0, max(0.0, float(cramers_v)))
                                categorical_associations.append({
                                    "column_x": c1,
                                    "column_y": c2,
                                    "cramers_v": round(cramers_v, 4),
                                    "chi2": round(float(chi2), 2),
                                    "p_value": round(float(p_val), 4),
                                })
                        except Exception:
                            pass

        return {
            "pearson": {
                "columns": valid_measures,
                "matrix": pearson_matrix,
            }
            if valid_measures
            else None,
            "spearman": {
                "columns": valid_measures,
                "matrix": spearman_matrix,
            }
            if valid_measures
            else None,
            "categorical_associations": categorical_associations,
            "warnings": warnings,
            "excluded_columns": excluded_columns,
        }

    # =========================================================================
    # Recommendation Generation
    # =========================================================================

    @classmethod
    def _generate_recommendations(
        cls,
        column_profiles: List[Dict[str, Any]],
        distributions: Dict[str, Any],
        relationships: Dict[str, Any],
        missing_report: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Generates deterministic suggested analyses and human-readable questions."""
        suggestions: List[Dict[str, Any]] = []
        questions: List[str] = []

        measures = [c["name"] for c in column_profiles if c["semantic_role"] == SemanticRoleEnum.MEASURE.value]
        categories = [
            c["name"]
            for c in column_profiles
            if c["semantic_role"] in (SemanticRoleEnum.CATEGORY.value, SemanticRoleEnum.BOOLEAN.value)
            and 2 <= c["distinct_count"] <= 20
        ]
        dates = [c["name"] for c in column_profiles if c["semantic_role"] == SemanticRoleEnum.DATETIME.value]

        # 1. Group-by comparison: Measure x Category
        if measures and categories:
            m = measures[0]
            cat = categories[0]
            suggestions.append({
                "title": f"Compare average {m} across {cat} groups",
                "description": f"Calculate summary aggregations and visualize the distribution of {m} segmented by {cat}.",
                "operation": "group_by",
                "columns": [m, cat],
                "rationale": f"Continuous measure '{m}' can reveal key subgroup disparities when sliced across categorical dimension '{cat}'.",
            })
            questions.append(f"How does {m} compare across different {cat} groups?")

        # 2. Time-series trend: Measure x Date
        if measures and dates:
            m = measures[0]
            d = dates[0]
            suggestions.append({
                "title": f"Explore monthly {m} trend over {d}",
                "description": f"Plot time-series trajectory of {m} against {d} to detect seasonality or long-term growth trends.",
                "operation": "trend",
                "columns": [m, d],
                "rationale": f"Chronological column '{d}' enables temporal exploration of quantitative measure '{m}'.",
            })
            questions.append(f"What is the trend of {m} over {d}?")

        # 3. Outlier investigation
        boxplots = distributions.get("boxplots", [])
        outlier_boxplots = [b for b in boxplots if b["outlier_count"] > 0]
        if outlier_boxplots:
            target_b = outlier_boxplots[0]
            col_target = target_b["column"]
            suggestions.append({
                "title": f"Investigate statistical outliers in {col_target}",
                "description": f"Analyze {target_b['outlier_count']} outlier observation(s) falling outside 1.5x IQR fences [{target_b['lower_fence']}, {target_b['upper_fence']}].",
                "operation": "outlier",
                "columns": [col_target],
                "rationale": f"Identified {target_b['outlier_count']} potential outlier points that may warrant domain verification or robust filtering.",
            })
            questions.append(f"What is the distribution and outlier range of {col_target}?")
        elif measures:
            questions.append(f"What is the distribution and outlier range of {measures[0]}?")

        # 4. Correlation exploration
        pearson_info = relationships.get("pearson")
        if pearson_info and pearson_info.get("matrix"):
            matrix = pearson_info["matrix"]
            best_pair = None
            max_r = 0.0
            for c1, row_map in matrix.items():
                for c2, r_val in row_map.items():
                    if c1 < c2 and r_val is not None:
                        if abs(r_val) > max_r:
                            max_r = abs(r_val)
                            best_pair = (c1, c2, r_val)

            if best_pair and max_r >= 0.35:
                c1, c2, r_val = best_pair
                suggestions.append({
                    "title": f"Examine linear relationship between {c1} and {c2}",
                    "description": f"Significant linear correlation detected (r = {r_val}). Fit a scatter plot and regression line.",
                    "operation": "correlation",
                    "columns": [c1, c2],
                    "rationale": f"Pearson correlation coefficient of {r_val} indicates strong mutual linear association.",
                })
                questions.append(f"What is the correlation between {c1} and {c2}?")
            elif len(measures) >= 2:
                questions.append(f"What is the correlation between {measures[0]} and {measures[1]}?")
        elif len(measures) >= 2:
            questions.append(f"What is the correlation between {measures[0]} and {measures[1]}?")

        # 5. Missingness investigation
        cols_missing = missing_report.get("columns_with_missing", [])
        if cols_missing:
            col_m = cols_missing[0]
            pct = missing_report["per_column"].get(col_m, 0.0)
            if pct > 15.0:
                suggestions.append({
                    "title": f"Investigate missingness patterns in {col_m}",
                    "description": f"Column '{col_m}' has {pct}% missing cells. Examine whether data is Missing Completely at Random (MCAR).",
                    "operation": "missingness",
                    "columns": [col_m],
                    "rationale": f"High missingness ({pct}%) may skew downstream statistics if not accounted for.",
                })

        return suggestions[:5], questions[:5]

    @classmethod
    def _empty_profile_payload(
        cls,
        dataset_name: str,
        file_size_bytes: int,
        load_time_seconds: float,
        profiling_duration_seconds: float,
        parsing_warnings: List[str],
    ) -> Dict[str, Any]:
        """Returns structured profiler contract for an empty or invalid dataset."""
        return {
            "overview": {
                "dataset_name": dataset_name,
                "total_rows": 0,
                "total_columns": 0,
                "file_size_bytes": file_size_bytes,
                "memory_estimate_bytes": 0,
                "selected_sheet": None,
                "load_time_seconds": load_time_seconds,
                "profiling_duration_seconds": profiling_duration_seconds,
                "parsing_warnings": parsing_warnings,
            },
            "columns": [],
            "missingness": {
                "total_cells": 0,
                "missing_cells": 0,
                "overall_missing_percentage": 0.0,
                "per_column": {},
                "columns_with_missing": [],
                "missingness_chart_data": [],
                "missingness_patterns": [],
            },
            "duplicates": {
                "exact_duplicate_rows_count": 0,
                "exact_duplicate_percentage": 0.0,
                "candidate_duplicate_keys": [],
                "duplicate_rows_sample": [],
            },
            "distributions": {
                "histograms": [],
                "boxplots": [],
                "categorical_frequencies": [],
                "date_distributions": [],
                "time_distributions": [],
            },
            "quality_warnings": [
                {
                    "column": None,
                    "check_type": "empty_dataset",
                    "severity": SeverityEnum.HIGH.value,
                    "message": "Dataset contains 0 data rows.",
                    "affected_count": 0,
                }
            ],
            "relationships": {
                "pearson": None,
                "spearman": None,
                "categorical_associations": [],
                "warnings": ["Dataset contains no data rows; relationships cannot be computed."],
                "excluded_columns": [],
            },
            "suggested_analyses": [],
            "suggested_questions": [],
            "correlation_matrix": None,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }
