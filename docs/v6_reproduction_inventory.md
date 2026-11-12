# v6 reproduction inventory

## Identity and status

- Attempt/run ID (inventory label): `v6-repro-20261112b`. The notebook itself does
  not write a run ID; this label identifies the isolated directory and was not
  added to its manifest. Executed 2026-11-12; fresh manifest generated at
  `2026-11-12T02:47:13.569275+00:00`. This is an unreviewed reproduction,
  **NOT_APPROVED_FOR_PRODUCTION**, not a replacement or release. Human review
  and model promotion remain pending. No reviewer has signed off.
- Frozen manifest: [`analysis/outputs/run_manifest.json`](../analysis/outputs/run_manifest.json),
  generated `2026-11-11T03:13:38.038283+00:00`; its output files remain intact.
- Notebook: `analysis/EDA_v6.ipynb`, version `6.1-targeted-corrections`, Git
  base commit `2da0abb426577f6967779af84d35f1e4bcb748cc`, Git blob
  `960c1ae2aa406b2e6834fd724e37d5f5c383ca6a`, file SHA-256
  `bdb7101c9fc017a68690506fd8cfdec579623b028563f287202ed54e6e324064`.
  The runner copied this unchanged notebook to the staging directory.
- Input: WPRDC [cumulative resource 2c13021f-74a9-4289-a1e5-fe0472c89881](https://data.wprdc.org/dataset/allegheny-county-crash-data/resource/2c13021f-74a9-4289-a1e5-fe0472c89881),
  publisher metadata last modified 2025-06-30. Official [CKAN dump](https://data.wprdc.org/datastore/dump/2c13021f-74a9-4289-a1e5-fe0472c89881),
  local `data/raw/2c13021f-74a9-4289-a1e5-fe0472c89881.csv`, SHA-256
  `c58a3901ee9aa845f5b33a9a3e930a2b95027367e5b2fef0225d4539db884511`,
  116,560,683 bytes. See [source decisions](sources_and_decisions.md), including
  the boundary reference and the publisher's alternative download failure.
- Environment: Windows, Python 3.13.7; the frozen manifest states Python
  3.13.18. All ten package versions recorded in that manifest matched. The
  installed dependency snapshot is [requirements-v6-repro.txt](../analysis/requirements-v6-repro.txt);
  `pip check` passed. The original manifest does not record a complete lock,
  platform or native library builds, so those cannot be established as equal.
  The [README](../analysis/README.md#reproduction) gives the download, checksum,
  environment, kernel and execution commands. The environment was originally
  installed with the ten manifest pins plus nbclient and ipykernel; the resulting
  freeze was checked with `pip install --no-index -r analysis/requirements-v6-repro.txt`.
- The first staging attempt `v6-repro-20261112` stalled at kernel startup in the
  sandbox before executing a cell and was interrupted. The completed attempt
  used local kernel access outside that sandbox. The runner exited 0; after the
  last cell, joblib's background resource tracker printed a `KeyError` for a
  temporary memmap cleanup registration. The saved notebook has 44 executed code
  cells and no error outputs. The cleanup message remains unresolved.

## Reconciliation

- Input: 248,810 records, 191 columns, 248,810 unique crash IDs and every year
  2004–2024. The 21 yearly rows and all columns in `severity_by_year.csv` match
  the frozen values exactly after CSV parsing. Total known severity is 205,544;
  43,266 records have unknown/excluded severity. The full-period table counts
  1,396 fatal and 7,052 serious/fatal records; interpret the latter across the
  2016 severity-standard change with care.
- The 2016–2021 training interval has 71,704 source records, 58,660 known
  severity records and 2,384 serious/fatal records. The 2022–2024 test interval
  has 32,186 source records, 27,697 known severity records and 1,231 serious/fatal
  records (4.444524677762934%). The years were previously examined and are not
  fresh external validation.
- 238,556 state-route coordinate candidates were screened against the county
  polygon; 275 were outside, leaving 238,281 unique crash records. All 38,332
  grid rows match the frozen parsed table, and their counts sum to 238,281.
  Candidate police/state pairs: 238,517; 2,146 exceed 500 m. Police encoding
  remains unverified and no official pair-agreement claim is made.
- All 15 CSVs have the same shape and column order as frozen. Parsed strings,
  integers, missing values and floating values were compared row by row with
  `rtol=1e-10`, `atol=1e-12`, equal missing values; none fell outside tolerance.
  Eleven become byte-identical after CRLF-to-LF normalization. Four additionally
  differ in floating-point text/values: association raw p and FDR q differ by
  at most `1.05e-53` and `2.09e-53`; one logistic Brier score differs by
  `1.632e-12`; candidate distance summary and 87 disagreement distances differ
  by at most `7.276e-12` metres. The four-model comparison retains the same
  test denominator, prevalence, ranking and AP values; best AP is
  `0.15478649768236308`. These small differences are observed, but their exact
  computational cause has not been established.
- All five joblib hashes differ. Matching tabular metrics do not establish
  identical model internals or predictions. Python, platform and unrecorded
  native/transitive dependencies differ or are unknown; serialization may also
  vary, but no cause has been verified. Treat these model-hash differences as
  unresolved, and do not load or promote either set based on this comparison.
  The manifest differs in generation/source-check timestamps and Python version;
  its other parsed fields match. The frozen boundary archive hash was not
  recorded, so byte identity of that reference cannot be verified.

## SHA-256 inventory

The two columns are byte hashes of the frozen files and the staged run,
respectively. `intervention_evidence/.gitkeep` is a repository placeholder, not
an output. The CSVs differ in line endings (frozen LF, run CRLF); the four
additional numerical differences are identified above. Models are review-only.

| Relative path under `analysis/outputs` | Frozen SHA-256 | Run SHA-256 |
| --- | --- | --- |
| `eda_summary/association_pooling_audit.csv` | `df0484a730cb970619c81fd10f3b31a1ee2cd5514968899f61862e0109a46546` | `3c8f7dbf41c0abc90b0e94f6b57a7d8f349eaaec790ae413a8588f42a15ba5fc` |
| `eda_summary/association_tests.csv` | `f4e4022025ddf787fa939887893263a84f5c14103f9b1f32f4c52bc85d34424c` | `d49c829f907a9e562c0f6ff8cfc32c811e5624bc42fefef21db20c782c9dc0fc` |
| `eda_summary/findings_review.csv` | `dc4bbb1bf5f0f4841570a1192ba8669aa52486082a687c528dcd90c33d9a6960` | `c5fcb0f1e6b4ef3a5867c35a7f7956cf55c7a95f3c440b1dd4fb9e72ad4b4c10` |
| `eda_summary/injury_reconciliation.csv` | `eea397540b1da57baec0b7de6a4f6f341525dd8765b7efe93730224c35a005bb` | `48495403df5100febb2619dfcc3f0495524f5e00f71697c3ea6540f6bfd11bd4` |
| `eda_summary/severity_by_year.csv` | `71203c297fcdd845a7e995a910d8f1934999ec141f7913a6da2ed0074e3a3e3f` | `425f651092fa58977a2dae111d34fad38be9829dcebea20b13b0c0a719619dc2` |
| `eda_summary/source_missingness.csv` | `32a0e799028d77c24858f453619d7fd1d8a3cbc88dc3cd22510ab859bc4b067a` | `ae2e4a2fe7c57ac6247f4cd42d09967c2e4bcdb47c99ca2e55f7b4ac45544da0` |
| `eda_summary/variable_roles.csv` | `da21344714aee9a03a5bca6f2302454479c515b953270d69bcf7024074167de0` | `a9cbb3ee8ad4c20949440db29c9a88eef58c8f35bbb56baf354494a04482de47` |
| `model_artifacts/histgradientboosting_plus_collision_review.joblib` | `2194e7e79843a9e7dcdcf7234ac8325140c2e07997c52ca536ec70bbf3f85a42` | `8a4a23f4c37edeee056791223a11a4a27c74b6b46fccb80818c5947463ed47e9` |
| `model_artifacts/logistic_regression_plus_collision_review.joblib` | `fed91142f368b3e97ef3e93872eaffc41de4bdcca52aed4b00865d73f317f45e` | `8bb3ad5e5a85614e138cdcdafe2700f5d8b54bb5cb1ff1f8bcc5165a3db09bb3` |
| `model_artifacts/logistic_regression_temporally_calibrated_review.joblib` | `c89d113639c689cf032758b2dd1899ef87359a338c6c158c9dd6308b9bde9f21` | `4557e1c5f8924400ce602601dbce4b4ec81e51a73d85aa7a80c8320cddd0dbfd` |
| `model_artifacts/random_forest_plus_collision_review.joblib` | `14fe6f79a9b080c2cdfd1536109da0abc817ee6b4c49a58afdaed45398ece7bf` | `4ad9469489cdf90a08d365d96447cdca7ace9cac9f66169688d0455897f7a670` |
| `model_artifacts/random_forest_without_collision_review.joblib` | `e521353dae5c41a12300a92008e3b9c96bbdcb37fe55b58f9f3ba8a1215b09d6` | `105691043b4ff9e4cf16485d20dd2f852cb23cf3bb1ee3f8eadc4db8a05c71b1` |
| `model_metrics/severity_ap_temporal_intervals.csv` | `04d6446571a3d9282d77d125c1b5b421642f0695a5c83fafd1ef25f4de5ec8f7` | `264046da195ebbfebd6dd58a741ffbc3d6909c0dc40cd46e4351b6315013d244` |
| `model_metrics/severity_model_comparison.csv` | `de54733c03599971cf6cdae07e79c41969a0ea66516b1e006e12f133799d4cbc` | `4bc2f0a77b30fac97356ae62c4b76f86d38978c2ff9042b418b38e5afd295573` |
| `run_manifest.json` | `8bdedd5347e0942f49eae2465c7e7f261260476a7fead09b3315dfa67747400f` | `e7c94c41ba60c8c8e0fe049a7ea157c452ddd29c98adc182e0f3e2fa29ba37a4` |
| `spatial/candidate_coordinate_comparison_summary.csv` | `1aac1de7fe33e28bb3b74c722b7547cd1211e6415091b21d8638b548c4016e97` | `60b6ce18e874b60a9950225fcc49b35e6e7898549992aefd90382660b8106647` |
| `spatial/candidate_coordinate_disagreements_review.csv` | `6454a9ae11f8c5821d26c72f07d4f5456ab1e16bb49fa9d7c1441103e95f0cd1` | `1eb3720d53c5173c8bd04f7882119443ffbc433cd5495ca75feb33463dd0a568` |
| `spatial/coordinate_coverage_by_year.csv` | `40683f291098c9d2f5218c51fbcb746b68b0d2a834653da64fb47c574dbddff4` | `d4efcdef9916183ce172af451fd7622b1e90466dec9af96f0143a8618f509641` |
| `spatial/county_points_review.csv` | `d100fdbba6e09c30927fc016c8cbe076cf58e9593a7cf598e5e0fcc8e79c9f42` | `6e88ba681ea7266fb35ac54f428382135d8e6b2bd74e93c0f536a4b14b483561` |
| `spatial/historical_grid_screening.csv` | `5ce12d5e3dfe616a48a77aaac0214a47af4f9d063f9aadcd4038eadf5ff490d5` | `7b39712029b029692431df20b58bab4a574956417120426afe217228df2d5f5a` |
| `spatial/police_coordinate_encoding_audit.csv` | `d74959b3f28434b8be7c731247a1f325646552d32528e50ede8b334b4893f06f` | `4f2398d9fb959b8b855ded7c5b191d7e2b36febc82783c09bc99043d91cd6b30` |
