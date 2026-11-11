# EDA v6 research baseline

`EDA_v6.ipynb` is the sole canonical research notebook for the 2004-2024
Allegheny County crash-data baseline. It includes exploratory analysis,
statistical tests, geographic screening, and conditional model training and
evaluation.

## Inputs

The notebook expects the source dataset named
`2c13021f-74a9-4289-a1e5-fe0472c89881.csv` in `data/raw/` when run from this
repository. The data source, SHA-256 checksum, row count, environment, and
review gates are recorded in `outputs/run_manifest.json`.

The raw dataset is not included in this repository. Obtain it through the
recorded source URL and verify its checksum before running the notebook.

## Outputs and review status

`outputs/` is the frozen extract from the accepted v6 run:

- `eda_summary/` contains baseline tables and the findings ledger.
- `spatial/` contains review-only geographic diagnostics and screening data.
- `model_metrics/` contains temporal evaluation metrics.
- `model_artifacts/` contains five review-only `.joblib` pipelines.

All model artefacts and outputs are `NOT_APPROVED_FOR_PRODUCTION`. The
application must verify the run metadata, integrity, and approval status before
using an artefact.

## Reproduction

Run the notebook from the repository root or `analysis/` with Python and the
package versions recorded in `outputs/run_manifest.json`. Preserve the single
notebook path and write any refreshed results to a new reviewed release before
replacing this frozen extract.
