"""Run the unchanged v6 notebook in an isolated repository-shaped directory."""
import argparse
import hashlib
import shutil
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parent.parent
SOURCE_NAME = "2c13021f-74a9-4289-a1e5-fe0472c89881.csv"
EXPECTED_SHA256 = "c58a3901ee9aa845f5b33a9a3e930a2b95027367e5b2fef0225d4539db884511"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id", help="new directory name under .repro")
    args = parser.parse_args()
    if Path(args.run_id).name != args.run_id or args.run_id in {".", ".."}:
        parser.error("run_id must be a single directory name")
    run = ROOT / ".repro" / args.run_id
    source = ROOT / "data" / "raw" / SOURCE_NAME
    if digest(source) != EXPECTED_SHA256:
        raise ValueError("Input SHA-256 differs from the frozen manifest; run stopped")
    if (run / "analysis").exists():
        raise FileExistsError(f"Run already exists: {run}")
    boundary = run / "data/reference/municipal_boundaries/cb_2024_us_county_500k.zip"
    if not boundary.is_file():
        raise FileNotFoundError(f"Place the Census boundary archive at {boundary}")
    (run / "analysis").mkdir(parents=True)
    (run / "data/raw").mkdir(parents=True)
    shutil.copy2(source, run / "data/raw" / SOURCE_NAME)
    notebook_path = run / "analysis/EDA_v6.ipynb"
    shutil.copy2(ROOT / "analysis/EDA_v6.ipynb", notebook_path)
    notebook = nbformat.read(notebook_path, as_version=4)
    def report_cell(cell, cell_index, **kwargs):
        if cell.cell_type == "code":
            print(f"Finished cell {cell_index}", flush=True)

    client = NotebookClient(notebook, timeout=None, kernel_name="v6-repro",
                            resources={"metadata": {"path": str(run)}},
                            on_cell_complete=report_cell)
    try:
        client.execute()
    finally:
        # Keep partial execution evidence if a cell fails.
        nbformat.write(notebook, run / "analysis/EDA_v6_executed.ipynb")
    print(f"Completed; isolated outputs: {run / 'analysis/outputs'}")


if __name__ == "__main__":
    main()
