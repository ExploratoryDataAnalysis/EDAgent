"""
Baseline Dataset Profiler Engine
Pure deterministic statistical calculation engine.
Follows Appendix A and Section 5.2 of the project specification.
"""

import csv
import math
import re
from collections import Counter
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

from app.schemas.profiler import (
    ProfilerResultResponse,
    DatasetOverview,
    ColumnProfile,
    NumericSummary,
    CategoricalSummary,
    MissingnessReport,
    DuplicatesReport,
    QualityWarning,
    SemanticRoleEnum,
    SeverityEnum,
)


class ProfilerEngine:
    """Deterministic EDA profiler for tabular data."""

    DATE_PATTERNS = [
        r"^\d{4}-\d{2}-\d{2}$",
        r"^\d{4}/\d{2}/\d{2}$",
        r"^\d{2}/\d{2}/\d{4}$",
        r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}",
    ]

    @classmethod
    def profile_csv_file(cls, file_path: str, delimiter: str = ",") -> Dict[str, Any]:
        """Runs a complete baseline profile on a CSV file."""
        import os
        import time

        start_time = time.time()
        file_size = os.path.getsize(file_path)

        rows: List[List[str]] = []
        headers: List[str] = []

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f, delimiter=delimiter)
            try:
                headers = next(reader)
            except StopIteration:
                pass
            for row in reader:
                if row:
                    rows.append(row)

        total_rows = len(rows)
        total_cols = len(headers)
        load_time = round(time.time() - start_time, 4)

        if total_rows == 0 or total_cols == 0:
            return {
                "overview": {
                    "dataset_name": os.path.basename(file_path),
                    "total_rows": 0,
                    "total_columns": 0,
                    "file_size_bytes": file_size,
                    "memory_estimate_bytes": 0,
                    "load_time_seconds": load_time,
                    "parsing_warnings": ["Dataset contains no data rows."],
                },
                "columns": [],
                "missingness": {
                    "total_cells": 0,
                    "missing_cells": 0,
                    "overall_missing_percentage": 0.0,
                    "per_column": {},
                    "columns_with_missing": [],
                },
                "duplicates": {
                    "exact_duplicate_rows_count": 0,
                    "exact_duplicate_percentage": 0.0,
                    "candidate_duplicate_keys": [],
                },
                "quality_warnings": [],
                "suggested_questions": [],
                "computed_at": datetime.now(timezone.utc).isoformat(),
            }

        # 1. Duplicates Analysis
        row_tuples = [tuple(r) for r in rows]
        exact_duplicate_count = total_rows - len(set(row_tuples))
        duplicate_percentage = round((exact_duplicate_count / total_rows) * 100, 2)

        # 2. Per-Column Analysis
        column_data: Dict[str, List[str]] = {h: [] for h in headers}
        for r in rows:
            for i, h in enumerate(headers):
                val = r[i].strip() if i < len(r) else ""
                column_data[h].append(val)

        total_cells = total_rows * total_cols
        total_missing_cells = 0
        per_column_missing: Dict[str, float] = {}
        columns_with_missing: List[str] = []
        quality_warnings: List[Dict[str, Any]] = []
        column_profiles: List[Dict[str, Any]] = []
        candidate_keys: List[str] = []

        for h in headers:
            values = column_data[h]
            non_empty_values = [v for v in values if v != ""]
            missing_count = len(values) - len(non_empty_values)
            missing_percentage = round((missing_count / total_rows) * 100, 2)
            total_missing_cells += missing_count

            per_column_missing[h] = missing_percentage
            if missing_count > 0:
                columns_with_missing.append(h)

            distinct_values = set(non_empty_values)
            distinct_count = len(distinct_values)
            is_unique = distinct_count == total_rows and total_rows > 0

            # Quality Check: High Missingness
            if missing_percentage > 40.0:
                quality_warnings.append({
                    "column": h,
                    "check_type": "high_missingness",
                    "severity": "medium",
                    "message": f"Column '{h}' has {missing_percentage}% missing values.",
                    "affected_count": missing_count,
                })

            # Quality Check: Constant or Near-Constant Column
            if distinct_count == 1:
                quality_warnings.append({
                    "column": h,
                    "check_type": "constant",
                    "severity": "high",
                    "message": f"Column '{h}' is constant with a single value.",
                    "affected_count": total_rows,
                })
            elif distinct_count == 2 and total_rows > 50:
                quality_warnings.append({
                    "column": h,
                    "check_type": "near_constant",
                    "severity": "low",
                    "message": f"Column '{h}' has only 2 distinct values across {total_rows} rows.",
                    "affected_count": None,
                })

            # Check candidate key (non-null unique column)
            if is_unique and missing_count == 0:
                candidate_keys.append(h)

            # Type and Role Inference
            role, inferred_type, num_summary, cat_summary = cls._infer_role_and_stats(
                h, non_empty_values, total_rows, distinct_count
            )

            # Quality Check: Potential ID used as metric
            if role == SemanticRoleEnum.IDENTIFIER and inferred_type in ("integer", "float"):
                quality_warnings.append({
                    "column": h,
                    "check_type": "possible_id",
                    "severity": "low",
                    "message": f"Column '{h}' is numeric but behaves like an identifier. Exclude from correlation analysis by default.",
                    "affected_count": None,
                })

            column_profiles.append({
                "name": h,
                "storage_dtype": inferred_type,
                "inferred_type": inferred_type,
                "semantic_role": role,
                "role_confidence": 0.95,
                "non_null_count": len(non_empty_values),
                "missing_count": missing_count,
                "missing_percentage": missing_percentage,
                "distinct_count": distinct_count,
                "is_unique": is_unique,
                "numeric_summary": num_summary,
                "categorical_summary": cat_summary,
                "sample_values": non_empty_values[:5],
            })

        # Suggested Questions based on roles
        suggested_questions = cls._generate_suggested_questions(column_profiles)

        return {
            "overview": {
                "dataset_name": os.path.basename(file_path),
                "total_rows": total_rows,
                "total_columns": total_cols,
                "file_size_bytes": file_size,
                "memory_estimate_bytes": file_size * 3,
                "load_time_seconds": load_time,
                "parsing_warnings": [],
            },
            "columns": column_profiles,
            "missingness": {
                "total_cells": total_cells,
                "missing_cells": total_missing_cells,
                "overall_missing_percentage": round((total_missing_cells / total_cells) * 100, 2) if total_cells > 0 else 0.0,
                "per_column": per_column_missing,
                "columns_with_missing": columns_with_missing,
            },
            "duplicates": {
                "exact_duplicate_rows_count": exact_duplicate_count,
                "exact_duplicate_percentage": duplicate_percentage,
                "candidate_duplicate_keys": candidate_keys,
            },
            "quality_warnings": quality_warnings,
            "suggested_questions": suggested_questions,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def _infer_role_and_stats(
        cls,
        name: str,
        values: List[str],
        total_rows: int,
        distinct_count: int
    ) -> Tuple[SemanticRoleEnum, str, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        if not values:
            return SemanticRoleEnum.UNKNOWN, "string", None, None

        # Check numeric
        numeric_vals = []
        is_all_numeric = True
        for v in values:
            try:
                numeric_vals.append(float(v))
            except ValueError:
                is_all_numeric = False
                break

        name_lower = name.lower()

        # Check Date/Time
        is_date = False
        if not is_all_numeric:
            date_matches = 0
            for v in values[:30]:
                if any(re.match(pat, v) for pat in cls.DATE_PATTERNS):
                    date_matches += 1
            if date_matches / max(len(values[:30]), 1) > 0.7:
                is_date = True

        if is_date or "date" in name_lower or "time" in name_lower:
            return SemanticRoleEnum.DATETIME, "datetime", None, None

        # If Numeric
        if is_all_numeric and len(numeric_vals) > 0:
            # Check if likely ID
            if (
                ("id" in name_lower or "code" in name_lower or "zip" in name_lower)
                or (distinct_count == total_rows and total_rows > 10)
            ):
                return SemanticRoleEnum.IDENTIFIER, "integer", None, None

            # Calculate robust statistics
            sorted_vals = sorted(numeric_vals)
            n = len(sorted_vals)
            mean_val = sum(sorted_vals) / n
            variance = sum((x - mean_val) ** 2 for x in sorted_vals) / (n - 1) if n > 1 else 0.0
            std_val = math.sqrt(variance)
            min_val = sorted_vals[0]
            max_val = sorted_vals[-1]
            q25 = sorted_vals[int(n * 0.25)]
            median_val = sorted_vals[int(n * 0.50)]
            q75 = sorted_vals[int(n * 0.75)]

            num_summary = {
                "count": n,
                "mean": round(mean_val, 4),
                "std": round(std_val, 4),
                "min": round(min_val, 4),
                "q25": round(q25, 4),
                "median": round(median_val, 4),
                "q75": round(q75, 4),
                "max": round(max_val, 4),
                "zeros_count": sum(1 for x in sorted_vals if x == 0),
            }

            if distinct_count <= 5 and n > 20:
                # Encoded categorical numbers (e.g., status 0, 1, 2)
                counts = Counter(values)
                top_values = [
                    {"value": k, "count": v, "percentage": round((v / n) * 100, 2)}
                    for k, v in counts.most_common(5)
                ]
                return (
                    SemanticRoleEnum.CATEGORY,
                    "integer",
                    num_summary,
                    {"unique_count": distinct_count, "top_values": top_values, "is_high_cardinality": False},
                )

            return SemanticRoleEnum.MEASURE, "float", num_summary, None

        # Categorical or Text
        counts = Counter(values)
        top_values = [
            {"value": k, "count": v, "percentage": round((v / len(values)) * 100, 2)}
            for k, v in counts.most_common(10)
        ]
        is_high_card = distinct_count > 50

        cat_summary = {
            "unique_count": distinct_count,
            "top_values": top_values,
            "is_high_cardinality": is_high_card,
        }

        distinct_values = set(values)
        # Boolean detection
        lowered_distinct = {v.lower() for v in distinct_values}
        if lowered_distinct in ({"true", "false"}, {"yes", "no"}, {"0", "1"}, {"t", "f"}):
            return SemanticRoleEnum.BOOLEAN, "boolean", None, cat_summary

        if (
            ("id" in name_lower or "uuid" in name_lower or "guid" in name_lower or "key" in name_lower)
            and distinct_count / max(total_rows, 1) > 0.8
        ):
            return SemanticRoleEnum.IDENTIFIER, "string", None, None

        if distinct_count > total_rows * 0.7 and any(len(v) > 50 for v in values[:10]):
            return SemanticRoleEnum.TEXT, "string", None, cat_summary

        return SemanticRoleEnum.CATEGORY, "string", None, cat_summary

    @classmethod
    def _generate_suggested_questions(cls, column_profiles: List[Dict[str, Any]]) -> List[str]:
        questions: List[str] = []
        measures = [c["name"] for c in column_profiles if c["semantic_role"] == SemanticRoleEnum.MEASURE]
        categories = [c["name"] for c in column_profiles if c["semantic_role"] == SemanticRoleEnum.CATEGORY]
        dates = [c["name"] for c in column_profiles if c["semantic_role"] == SemanticRoleEnum.DATETIME]

        if measures:
            questions.append(f"What is the distribution and outlier range of {measures[0]}?")
        if len(measures) >= 2:
            questions.append(f"What is the correlation between {measures[0]} and {measures[1]}?")
        if measures and categories:
            questions.append(f"How does {measures[0]} compare across different {categories[0]} groups?")
        if measures and dates:
            questions.append(f"What is the trend of {measures[0]} over {dates[0]}?")
        return questions[:4]
