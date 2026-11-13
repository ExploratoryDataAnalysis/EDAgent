# EDA v6 research baseline

`EDA_v6.ipynb` is the sole canonical research notebook for the 2004-2024
Allegheny County crash-data baseline. It includes exploratory analysis,
statistical tests, geographic diagnostics, and retrospective model training and
evaluation. [Project Plan v3](../docs/EDAgent_Project_Plan_v3.pdf) governs release use; site-level screening and frequency modelling are outside its scope.

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

The following PowerShell workflow uses the exact source, checks its hash, and
runs the unchanged notebook in a separate repository-shaped directory. It uses
the package versions from the manifest plus the full dependency snapshot from
the 2026-11-12 attempt. That attempt used Windows and Python 3.13.7; the frozen
manifest reports Python 3.13.18. See the [inventory](../docs/v6_reproduction_inventory.md)
for results and limitations. Run from the repository root with Python 3.13 and
network access. The kernel needs local loopback access. Pick a new run ID each
time; never point the run at the frozen output directory.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r analysis/requirements-v6-repro.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ipykernel install --prefix .venv --name v6-repro
New-Item -ItemType Directory -Force data/raw | Out-Null
curl.exe -L --fail 'https://data.wprdc.org/datastore/dump/2c13021f-74a9-4289-a1e5-fe0472c89881' -o data/raw/2c13021f-74a9-4289-a1e5-fe0472c89881.csv
if ($LASTEXITCODE -ne 0) { throw 'Crash data download failed' }
$inputHash = (Get-FileHash data/raw/2c13021f-74a9-4289-a1e5-fe0472c89881.csv -Algorithm SHA256).Hash
if ($inputHash -ne 'c58a3901ee9aa845f5b33a9a3e930a2b95027367e5b2fef0225d4539db884511') { throw 'Crash input checksum mismatch' }
$runId = 'v6-repro-NEW'
$boundaryDir = ".repro/$runId/data/reference/municipal_boundaries"
New-Item -ItemType Directory -Force $boundaryDir | Out-Null
curl.exe -L --fail 'https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip' -o "$boundaryDir/cb_2024_us_county_500k.zip"
if ($LASTEXITCODE -ne 0) { throw 'Boundary download failed' }
Get-FileHash "$boundaryDir/cb_2024_us_county_500k.zip" -Algorithm SHA256
.\.venv\Scripts\python.exe analysis/run_v6_repro.py $runId
```

The runner refuses a mismatched input or an existing run's `analysis` directory.
It copies the source and notebook into the run directory, executes from a clean
kernel, and saves the executed notebook there, including partial evidence on
failure. Outputs and raw inputs are ignored by Git. The boundary hash must be
recorded with each run: the original manifest did not include it. Do not replace
the frozen extract until a refreshed release is reviewed.
