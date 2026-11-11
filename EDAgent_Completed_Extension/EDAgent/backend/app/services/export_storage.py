"""
Where generated files (reports, bundles) live on disk.

Paths stored in the database are relative to EXPORTS_STORAGE_PATH and resolved through
`export_path`, which refuses anything that would escape that folder.
"""

import os
import time
from typing import Optional

from app.core.config import settings


def export_root() -> str:
    root = os.path.abspath(settings.EXPORTS_STORAGE_PATH)
    os.makedirs(root, exist_ok=True)
    return root


def export_path(rel: str) -> str:
    root = export_root()
    full = os.path.abspath(os.path.join(root, rel))
    if os.path.commonpath([full, root]) != root:
        raise ValueError("Invalid export path")
    return full


def remove_export_file(rel: Optional[str]) -> None:
    if not rel:
        return
    try:
        path = export_path(rel)
        if os.path.isfile(path):
            os.remove(path)
    except (ValueError, OSError):
        pass


def purge_old_exports() -> int:
    """Deletes generated files older than EXPORT_RETENTION_HOURS. Returns how many were removed."""
    root = export_root()
    cutoff = time.time() - settings.EXPORT_RETENTION_HOURS * 3600
    removed = 0
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            # The tracked placeholder keeps an empty export directory in the repository.
            if f == ".gitkeep":
                continue
            p = os.path.join(dirpath, f)
            try:
                if os.path.getmtime(p) < cutoff:
                    os.remove(p)
                    removed += 1
            except OSError:
                continue
    return removed
