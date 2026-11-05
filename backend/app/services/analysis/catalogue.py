"""
Controlled Analysis Tool Catalogue
Provides safe, deterministic, parameter-validated analytical routines.
"""

from typing import Dict, Any, List
from app.schemas.analysis import AnalysisOperationEnum, StructuredAnalysisPlan


class ToolCatalogue:
    """Registry and metadata for approved analysis operations."""

    OPERATIONS_METADATA = {
        AnalysisOperationEnum.HISTOGRAM: {
            "name": "histogram",
            "description": "Calculates frequency distribution bins and generates a histogram plot.",
            "required_parameters": ["column"],
            "optional_parameters": ["bins", "filter_expression"],
            "supported_roles": ["measure"],
        },
        AnalysisOperationEnum.BOXPLOT: {
            "name": "boxplot",
            "description": "Calculates quartiles, median, whiskers, and outlier points for numeric columns.",
            "required_parameters": ["column"],
            "optional_parameters": ["group_by_column", "filter_expression"],
            "supported_roles": ["measure"],
        },
        AnalysisOperationEnum.CORRELATION: {
            "name": "correlation",
            "description": "Calculates Pearson/Spearman correlation between two or more numeric columns.",
            "required_parameters": ["target_columns"],
            "optional_parameters": ["method"],
            "supported_roles": ["measure"],
        },
        AnalysisOperationEnum.GROUP_BY: {
            "name": "group_by",
            "description": "Aggregates a metric column across categorical groups.",
            "required_parameters": ["column", "group_by_column", "aggregation"],
            "optional_parameters": ["filter_expression"],
            "supported_roles": ["measure", "category"],
        },
        AnalysisOperationEnum.OUTLIER_IQR: {
            "name": "outlier_iqr",
            "description": "Identifies outlier records using 1.5 * IQR fences.",
            "required_parameters": ["column"],
            "optional_parameters": ["filter_expression"],
            "supported_roles": ["measure"],
        },
        AnalysisOperationEnum.CROSSTAB: {
            "name": "crosstab",
            "description": "Computes contingency frequency table between two categorical columns.",
            "required_parameters": ["target_columns"],
            "optional_parameters": ["normalize"],
            "supported_roles": ["category"],
        },
        AnalysisOperationEnum.TIME_TREND: {
            "name": "time_trend",
            "description": "Aggregates a numeric measure over temporal intervals (day/week/month).",
            "required_parameters": ["column", "group_by_column"],
            "optional_parameters": ["interval", "aggregation"],
            "supported_roles": ["measure", "datetime"],
        },
    }

    @classmethod
    def get_tool_definitions_for_llm(cls) -> List[Dict[str, Any]]:
        """Returns JSON Schema tool definitions for LLM function calling."""
        tools = []
        for op, meta in cls.OPERATIONS_METADATA.items():
            tools.append({
                "type": "function",
                "function": {
                    "name": meta["name"],
                    "description": meta["description"],
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "column": {"type": "string", "description": "Target primary column name"},
                            "target_columns": {"type": "array", "items": {"type": "string"}, "description": "List of columns for bivariate/multivariate analysis"},
                            "group_by_column": {"type": "string", "description": "Categorical column to group by"},
                            "aggregation": {"type": "string", "enum": ["mean", "sum", "count", "median", "min", "max"]},
                            "filter_expression": {"type": "string", "description": "Optional SQL-like filter, e.g. status == 'Active'"},
                        },
                        "required": meta["required_parameters"],
                    },
                },
            })
        return tools

    @classmethod
    def validate_plan_against_schema(
        cls, plan: StructuredAnalysisPlan, available_columns: Dict[str, str]
    ) -> List[str]:
        """Validates that requested plan references valid columns and suitable roles."""
        errors: List[str] = []
        meta = cls.OPERATIONS_METADATA.get(plan.operation)
        if not meta:
            errors.append(f"Operation '{plan.operation}' is not supported in the approved tool catalogue.")
            return errors

        # Validate column existence
        if plan.column and plan.column not in available_columns:
            errors.append(f"Column '{plan.column}' does not exist in dataset schema.")
        if plan.target_columns:
            for col in plan.target_columns:
                if col not in available_columns:
                    errors.append(f"Column '{col}' does not exist in dataset schema.")
        if plan.group_by_column and plan.group_by_column not in available_columns:
            errors.append(f"Group column '{plan.group_by_column}' does not exist in dataset schema.")

        return errors
