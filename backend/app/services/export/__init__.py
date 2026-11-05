"""
Report and Export Service Package
"""

from typing import Dict, Any, List


class ExportService:
    """Manages report composition, CSV/XLSX bundles, and export artifacts."""

    @staticmethod
    def format_export_filename(dataset_name: str, export_type: str, extension: str) -> str:
        import re
        from datetime import datetime

        clean_name = re.sub(r"[^\w\-]", "_", dataset_name)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"{clean_name}_{export_type}_{timestamp}.{extension}"
