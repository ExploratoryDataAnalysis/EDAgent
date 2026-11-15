# Retrospective Severity Models Aggregate Data Dictionary

## Schema Version: 1.0.0 (Derivative Release v3-d5-1)

This release presents retrospective model performance metrics conditioned on reported crashes with known outcomes (2016–2024). It does NOT predict live crash occurrence.

### Tables:
1. `model_comparisons`: Evaluation metrics on 2022–2024 test holdout (N = 27,697).
2. `feature_ablation`: Association strengths and pre-crash vs post-crash timing comparison.
3. `threshold_performance`: Confusion matrix counts at 0.50 decision threshold.
4. `calibration_diagnostics`: Brier scores and calibration methods.
