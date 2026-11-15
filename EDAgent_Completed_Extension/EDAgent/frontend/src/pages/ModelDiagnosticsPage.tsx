import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  loadModelsData,
  confirmModelsRelease,
  modelsDownloadUrl,
  modelsAssetUrl,
  type ModelsData,
  type ModelComparison,
  type FeatureAblation,
  type ThresholdPerformance,
  type CalibrationDiagnostics,
} from '../services/modelsService';
import { useReleaseRequest } from '../components/layout/ReleaseStatus';

const card = 'min-w-0 border border-stone-300 bg-[#fffcf4] p-4 sm:p-6 shadow-sm';
const formatCount = new Intl.NumberFormat('en-US');

export function ModelDiagnosticsPage() {
  const { state, retry } = useReleaseRequest(loadModelsData, confirmModelsRelease);

  return (
    <article className="public-document space-y-8">
      <header className="public-hero public-measure">
        <p className="public-kicker">Allegheny County, Pennsylvania · 2016–2024 Retrospective Research</p>
        <h1 className="text-3xl font-serif font-bold text-stone-900 tracking-tight sm:text-4xl">
          Retrospective Crash Severity Model Diagnostics
        </h1>
        <p className="public-lede text-lg text-stone-700 leading-relaxed mt-2">
          Evaluation of retrospective severity classification models conditioned strictly on already
          reported crashes with known outcomes. This research does not forecast crash occurrence or evaluate live site risk.
        </p>
        <div className="public-actions flex flex-wrap gap-4 mt-4">
          <Link to="/road-safety" className="text-sm font-medium text-emerald-800 underline hover:text-emerald-950">
            Road Safety Overview
          </Link>
          <Link to="/road-safety/map" className="text-sm font-medium text-emerald-800 underline hover:text-emerald-950">
            County crash grid
          </Link>
          <Link to="/road-safety/evidence" className="text-sm font-medium text-emerald-800 underline hover:text-emerald-950">
            Severity & measurement
          </Link>
          <Link to="/methods" className="text-sm font-medium text-emerald-800 underline hover:text-emerald-950">
            Methodology & codebook
          </Link>
        </div>
      </header>

      {state.kind === 'loading' && (
        <section className={card} aria-label="Loading models release">
          <h2 className="text-lg font-serif font-bold text-stone-900">Verifying scientific release gate…</h2>
          <p className="text-sm text-stone-600 mt-1">
            Evaluating cryptographic manifest checksums and authorization ledger status.
          </p>
        </section>
      )}

      {(state.kind === 'unavailable' || state.kind === 'error') && (
        <section className="border-l-4 border-amber-600 bg-amber-50 p-6 space-y-4" aria-label="Gate Status Notice">
          <div className="flex items-start justify-between gap-4">
            <div>
              <span className="inline-block text-xs font-semibold uppercase tracking-wider text-amber-800 bg-amber-200/60 px-2 py-0.5 rounded">
                Gated Derivative · Pending Independent Approval
              </span>
              <h2 className="text-xl font-serif font-bold text-stone-900 mt-2">
                Retrospective Model Diagnostics are Offline
              </h2>
            </div>
            <button
              onClick={retry}
              className="px-3 py-1.5 text-xs font-semibold bg-stone-900 text-stone-50 rounded hover:bg-stone-800"
            >
              Recheck Gate
            </button>
          </div>
          <p className="text-sm text-stone-700 leading-relaxed">
            In accordance with Project Plan v4 (Phase 12) and Plan v3 scientific boundaries, statistical severity models
            remain strictly offline until the exact candidate derivative (version <code>v3-d5-1</code>) receives explicit,
            cryptographically signed scientific approval from the independent Road Safety Review Committee.
          </p>
          <div className="text-xs text-stone-600 bg-amber-100/50 p-3 rounded font-mono space-y-1">
            <div>DERIVATIVE STATUS: REVIEW_CANDIDATE (PENDING_INDEPENDENT_REVIEW)</div>
            <div>PRIMARY_SITE_ASSIGNMENTS_ACCEPTED: 0</div>
            <div>LIVE_INFERENCE_PERMITTED: FALSE</div>
            <div>SITE_PREDICTIONS_PERMITTED: FALSE</div>
          </div>
          <p className="text-xs text-stone-600">
            Readers seeking verified empirical findings should consult the approved{' '}
            <Link to="/road-safety" className="underline font-medium text-emerald-800">
              Historical Descriptive Overview
            </Link>{' '}
            or the{' '}
            <Link to="/methods" className="underline font-medium text-emerald-800">
              Scientific Methodology Documentation
            </Link>.
          </p>
        </section>
      )}

      {state.kind === 'ready' && <ApprovedModelDiagnostics data={state.data} />}
    </article>
  );
}

function ApprovedModelDiagnostics({ data }: { data: ModelsData }) {
  const { provenance, comparisons, ablation, thresholds, calibration } = data;
  const manifestSha = provenance.bundle.manifest_sha256;

  return (
    <div className="space-y-12">
      {/* SECTION 1: Research Question & Conditioning Statement */}
      <section className="space-y-4" aria-labelledby="sec-question">
        <div className="border-l-4 border-emerald-700 bg-emerald-50/50 p-4 sm:p-5 space-y-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-emerald-800">
            Core Scientific Definition & Boundary
          </span>
          <h2 id="sec-question" className="text-xl font-serif font-bold text-stone-900">
            1. Target Definition & Conditioning Statement
          </h2>
          <p className="text-sm text-stone-700 leading-relaxed">
            All models evaluate the conditional probability of serious or fatal injury (<em>Y</em><sub>severe</sub> = 1)
            <strong> conditioned strictly on a police-reported crash having already occurred with a known injury outcome</strong>:
          </p>
          <div className="bg-white/80 border border-emerald-200 p-3 rounded text-sm font-mono text-emerald-950">
            P(Severe Injury | Crash Reported ∧ Severity Known)
          </div>
          <p className="text-xs text-stone-600 leading-relaxed">
            <strong>Critical distinction:</strong> This model does NOT predict crash frequency, spatial crash occurrence,
            or traffic exposure risk. It evaluates retrospective injury severity conditional on impact.
          </p>
        </div>
      </section>

      {/* SECTION 2: Population, Reporting Era & Exclusions */}
      <section className="space-y-4" aria-labelledby="sec-population">
        <h2 id="sec-population" className="text-2xl font-serif font-bold text-stone-900">
          2. Population, Reporting Era & Exclusions
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className={card}>
            <p className="text-xs font-medium text-stone-500 uppercase">Training Cohort (2016–2021)</p>
            <p className="text-2xl font-serif font-bold text-stone-900 mt-1">58,660</p>
            <p className="text-xs text-stone-600 mt-1">
              Known-severity crashes · 2,384 severe positives (4.06% prevalence)
            </p>
          </div>
          <div className={card}>
            <p className="text-xs font-medium text-stone-500 uppercase">Test Holdout (2022–2024)</p>
            <p className="text-2xl font-serif font-bold text-stone-900 mt-1">27,697</p>
            <p className="text-xs text-stone-600 mt-1">
              Chronological holdout · 1,231 severe positives (4.44% prevalence)
            </p>
          </div>
          <div className={card}>
            <p className="text-xs font-medium text-stone-500 uppercase">Unknown Severity Excluded</p>
            <p className="text-2xl font-serif font-bold text-amber-800 mt-1">43,266</p>
            <p className="text-xs text-stone-600 mt-1">
              17.39% of 2004–2024 extract · Listwise deletion (never imputed as non-severe)
            </p>
          </div>
        </div>
        <p className="text-sm text-stone-700 leading-relaxed">
          The 2016 partition respects Pennsylvania&apos;s transition to the federal MMUCC 4th Edition standard. Prior to 2016,
          major injury definitions varied across 130 municipal departments and are not clinically comparable.
          The 2022–2024 test cohort represents a retrospective chronological holdout; note that these years were inspected
          during exploratory research (v5/v6) and do not constitute a prospective clinical trial.
        </p>
      </section>

      {/* SECTION 3: Model Comparison Matrix */}
      <section className="space-y-4" aria-labelledby="sec-models">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <h2 id="sec-models" className="text-2xl font-serif font-bold text-stone-900">
              3. Model Performance on Chronological Holdout (2022–2024)
            </h2>
            <p className="text-sm text-stone-600">
              Evaluated on N = 27,697 reported crashes (1,231 severe, 4.44% prevalence). Chance AP = 0.0444; Chance ROC = 0.5000.
            </p>
          </div>
          <a
            href={modelsDownloadUrl('model_comparisons', manifestSha)}
            className="text-xs font-semibold text-emerald-800 underline hover:text-emerald-950"
            download
          >
            Download CSV
          </a>
        </div>

        <div className="overflow-x-auto border border-stone-300">
          <table className="w-full text-left text-sm border-collapse bg-white">
            <thead className="bg-stone-100 text-stone-800 font-semibold border-b border-stone-300">
              <tr>
                <th className="p-3">Model Architecture</th>
                <th className="p-3">Feature Set</th>
                <th className="p-3 text-right">Average Precision</th>
                <th className="p-3 text-right">95% Temporal CI</th>
                <th className="p-3 text-right">ROC-AUC</th>
                <th className="p-3 text-right">Bal. Acc (0.50)</th>
                <th className="p-3 text-right">Brier Score</th>
                <th className="p-3">Calibration State</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-200">
              <tr className="bg-stone-50/50 text-stone-500 font-mono text-xs">
                <td className="p-3 italic">Chance / Base Rate Baseline</td>
                <td className="p-3">—</td>
                <td className="p-3 text-right">0.0444</td>
                <td className="p-3 text-right">—</td>
                <td className="p-3 text-right">0.5000</td>
                <td className="p-3 text-right">0.5000</td>
                <td className="p-3 text-right">0.0425</td>
                <td className="p-3">Constant Base Rate</td>
              </tr>
              {comparisons.map((m) => (
                <tr key={m.model_id} className="hover:bg-amber-50/30">
                  <td className="p-3 font-medium text-stone-900">{m.model_name}</td>
                  <td className="p-3 text-xs text-stone-600">
                    {m.includes_collision_type ? (
                      <span className="text-amber-800 font-medium">Post-crash collision + env</span>
                    ) : (
                      <span className="text-stone-700">Pre-crash env only</span>
                    )}
                  </td>
                  <td className="p-3 text-right font-mono font-semibold text-stone-900">
                    {m.average_precision.toFixed(4)}
                  </td>
                  <td className="p-3 text-right font-mono text-xs text-stone-600">
                    [{m.ap_interval_lower_95.toFixed(4)}, {m.ap_interval_upper_95.toFixed(4)}]
                  </td>
                  <td className="p-3 text-right font-mono">{m.roc_auc.toFixed(4)}</td>
                  <td className="p-3 text-right font-mono">{m.balanced_accuracy_0_50.toFixed(4)}</td>
                  <td className="p-3 text-right font-mono">
                    <span className={m.brier_score > 0.10 ? 'text-rose-700 font-semibold' : 'text-emerald-800 font-semibold'}>
                      {m.brier_score.toFixed(4)}
                    </span>
                  </td>
                  <td className="p-3 text-xs text-stone-600">{m.calibration_state}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-stone-600">
          * Note: Uncalibrated classifiers exhibit Brier scores (&gt; 0.17) far worse than a naive constant prediction (0.0425).
          Only temporally calibrated logistic regression achieves true probabilistic calibration (0.0416).
        </p>
      </section>

      {/* SECTION 4: Feature Timing & Collision-Type Ablation */}
      <section className="space-y-4" aria-labelledby="sec-ablation">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <h2 id="sec-ablation" className="text-2xl font-serif font-bold text-stone-900">
              4. Feature Timing & Collision-Type Ablation
            </h2>
            <p className="text-sm text-stone-600">
              Categorical associations on 2016–2023 known crashes (N = 77,476) and impact of removing in-incident attributes.
            </p>
          </div>
          <a
            href={modelsDownloadUrl('feature_ablation', manifestSha)}
            className="text-xs font-semibold text-emerald-800 underline hover:text-emerald-950"
            download
          >
            Download CSV
          </a>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="border border-stone-300 bg-white p-4 space-y-3">
            <h3 className="text-base font-serif font-bold text-stone-900">
              Statistical Association with Severity (Cramér&apos;s V)
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="bg-stone-100 text-stone-700 font-semibold border-b">
                  <tr>
                    <th className="p-2">Feature</th>
                    <th className="p-2">Observation Timing</th>
                    <th className="p-2 text-right">Cramér&apos;s V</th>
                    <th className="p-2 text-right">Chi-Square (df)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-200">
                  {ablation.map((a) => (
                    <tr key={a.feature_id} className={a.is_post_crash ? 'bg-amber-50/50 font-medium' : ''}>
                      <td className="p-2">{a.feature_name}</td>
                      <td className="p-2">
                        <span className={`px-1.5 py-0.5 rounded text-[11px] ${a.is_post_crash ? 'bg-amber-200 text-amber-900' : 'bg-stone-200 text-stone-800'}`}>
                          {a.timing_category}
                        </span>
                      </td>
                      <td className="p-2 text-right font-mono font-bold">{a.cramers_v.toFixed(4)}</td>
                      <td className="p-2 text-right font-mono text-stone-600">
                        {a.chi2_statistic.toFixed(1)} ({a.degrees_of_freedom})
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-stone-600">
              All association tests significant at FDR-adjusted Benjamini-Hochberg q &lt; 10⁻⁵.
            </p>
          </div>

          <div className={card + ' space-y-3'}>
            <h3 className="text-base font-serif font-bold text-stone-900">
              The Kinematic Timing Finding
            </h3>
            <p className="text-sm text-stone-700 leading-relaxed">
              <strong>Collision Type</strong> (head-on, angle, rear-end, pedestrian) is observed <em>during or after</em> the crash.
              It is an indicator of impact mechanics, not an antecedent pre-crash road condition.
            </p>
            <div className="border border-stone-300 bg-white p-3 space-y-2">
              <div className="flex justify-between items-center text-xs">
                <span>Random Forest <strong>with</strong> collision type:</span>
                <span className="font-mono font-bold text-stone-900">AP = 0.1420</span>
              </div>
              <div className="w-full bg-stone-200 h-2 rounded">
                <div className="bg-emerald-700 h-2 rounded" style={{ width: '100%' }}></div>
              </div>
              <div className="flex justify-between items-center text-xs">
                <span>Random Forest <strong>without</strong> collision type:</span>
                <span className="font-mono font-bold text-amber-800">AP = 0.0517</span>
              </div>
              <div className="w-full bg-stone-200 h-2 rounded">
                <div className="bg-amber-600 h-2 rounded" style={{ width: '36.4%' }}></div>
              </div>
              <div className="flex justify-between items-center text-xs text-stone-500">
                <span>Chance baseline (test prevalence):</span>
                <span className="font-mono">AP = 0.0444</span>
              </div>
            </div>
            <p className="text-xs text-stone-600">
              Removing collision type eliminates 92.5% of the model&apos;s lift above chance. Environmental, lighting,
              and roadway geometry alone cannot reliably forecast whether an occurring crash will be fatal or serious.
            </p>
          </div>
        </div>
      </section>

      {/* SECTION 5: Probability Calibration Contrast */}
      <section className="space-y-4" aria-labelledby="sec-calibration">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <h2 id="sec-calibration" className="text-2xl font-serif font-bold text-stone-900">
              5. Probability Calibration & Decision Thresholds
            </h2>
            <p className="text-sm text-stone-600">
              Demonstrating the necessity of Platt scaling to prevent severely distorted probability claims.
            </p>
          </div>
          <div className="flex gap-4">
            <a
              href={modelsDownloadUrl('calibration_diagnostics', manifestSha)}
              className="text-xs font-semibold text-emerald-800 underline hover:text-emerald-950"
              download
            >
              Calibration CSV
            </a>
            <a
              href={modelsDownloadUrl('threshold_performance', manifestSha)}
              className="text-xs font-semibold text-emerald-800 underline hover:text-emerald-950"
              download
            >
              Thresholds CSV
            </a>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="border border-stone-300 bg-white p-4 space-y-3">
            <h3 className="text-base font-serif font-bold text-stone-900">
              Brier Score Calibration Contrast
            </h3>
            <p className="text-xs text-stone-700">
              Lower Brier score indicates superior probability accuracy. Baseline = 0.0425.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="bg-stone-100 text-stone-700 font-semibold border-b">
                  <tr>
                    <th className="p-2">Model</th>
                    <th className="p-2 text-right">Brier Score</th>
                    <th className="p-2 text-right">Baseline (0.0426)</th>
                    <th className="p-2">Method</th>
                    <th className="p-2">State</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-200">
                  {calibration.map((c) => (
                    <tr key={c.model_id}>
                      <td className="p-2 font-medium">{c.model_name}</td>
                      <td className="p-2 text-right font-mono font-bold">
                        <span className={c.beats_constant_baseline ? 'text-emerald-800' : 'text-rose-700'}>
                          {c.brier_score.toFixed(4)}
                        </span>
                      </td>
                      <td className="p-2 text-right font-mono text-stone-600">
                        {c.brier_constant_baseline.toFixed(4)}
                      </td>
                      <td className="p-2 text-[11px] text-stone-600">{c.calibration_method}</td>
                      <td className="p-2 text-[11px]">
                        <span className={`px-1 py-0.5 rounded ${c.beats_constant_baseline ? 'bg-emerald-100 text-emerald-900' : 'bg-stone-200 text-stone-800'}`}>
                          {c.calibration_state}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-stone-600">
              Uncalibrated logistic regression scores (Brier = 0.2132) represent arbitrary decision margins, not event probabilities.
              Temporally folded Platt scaling improves probability estimation by 80.5%, beating the constant baseline.
            </p>
          </div>

          <div className="border border-stone-300 bg-white p-4 space-y-3">
            <h3 className="text-base font-serif font-bold text-stone-900">
              Confusion Matrix at 0.50 Threshold (2022–2024 Test Cohort)
            </h3>
            <p className="text-xs text-stone-700">
              N = 27,697 total test crashes · Actual Positives = 1,231 · Actual Negatives = 26,466
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="bg-stone-100 text-stone-700 font-semibold border-b">
                  <tr>
                    <th className="p-2">Model</th>
                    <th className="p-2 text-right">TP</th>
                    <th className="p-2 text-right">FP</th>
                    <th className="p-2 text-right">FN</th>
                    <th className="p-2 text-right">TN</th>
                    <th className="p-2 text-right">Sensitivity</th>
                    <th className="p-2 text-right">Specificity</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-200">
                  {thresholds.map((t) => (
                    <tr key={t.model_id}>
                      <td className="p-2 font-medium">{t.model_name}</td>
                      <td className="p-2 text-right font-mono">{formatCount.format(t.true_positives)}</td>
                      <td className="p-2 text-right font-mono">{formatCount.format(t.false_positives)}</td>
                      <td className="p-2 text-right font-mono">{formatCount.format(t.false_negatives)}</td>
                      <td className="p-2 text-right font-mono">{formatCount.format(t.true_negatives)}</td>
                      <td className="p-2 text-right font-mono">{(t.sensitivity_recall * 100).toFixed(1)}%</td>
                      <td className="p-2 text-right font-mono">{(t.specificity * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-stone-600">
              At a fixed 0.50 cutoff, calibrated probabilities on a 4.4% prevalence dataset classify all events as negative (0% sensitivity).
              Decision thresholds must be calibrated to specific operational resource constraints.
            </p>
          </div>
        </div>
      </section>

      {/* SECTION 6: Scientific Limitations & Concrete Prohibitions */}
      <section className="space-y-4" aria-labelledby="sec-limitations">
        <h2 id="sec-limitations" className="text-2xl font-serif font-bold text-stone-900">
          6. Scientific Limitations & Prohibited Uses
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="border-l-4 border-rose-600 bg-rose-50/60 p-4 space-y-2">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-rose-900">
              Strictly Prohibited Claims & Applications
            </h3>
            <ul className="text-xs text-rose-950 space-y-1.5 list-disc pl-4">
              <li><strong>NO Live Crash Forecasting:</strong> Models do not forecast where or when crashes will occur.</li>
              <li><strong>NO Site-Level Risk Scores:</strong> Severity models cannot be mapped to intersections or road segments.</li>
              <li><strong>NO Intersection Rankings:</strong> Ranking corridors based on severity classifier weights is scientifically invalid.</li>
              <li><strong>NO Treatment Selection:</strong> Feature coefficients reflect physical kinematics, not countermeasure effectiveness.</li>
              <li><strong>NO Live Case Scoring:</strong> Serving scores for individual ongoing incidents is strictly barred.</li>
            </ul>
          </div>

          <div className="border-l-4 border-stone-600 bg-stone-100/70 p-4 space-y-2">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-stone-900">
              Documented Methodological Constraints
            </h3>
            <ul className="text-xs text-stone-800 space-y-1.5 list-disc pl-4">
              <li><strong>Severe Class Imbalance:</strong> True prevalence is ~4.4%; metrics must be compared against chance AP (0.0444).</li>
              <li><strong>Reporting Erase Break:</strong> Pre-2016 classifications cannot be combined with post-2016 MMUCC standards.</li>
              <li><strong>Uncalibrated Score Distortion:</strong> Raw tree votes and logits cannot be interpreted as probabilities.</li>
              <li><strong>Exploratory Inspection:</strong> Test cohort (2022–2024) was inspected during iterative notebook development.</li>
            </ul>
          </div>
        </div>
      </section>

      {/* SECTION 7: Provenance, Verification & Data Downloads */}
      <section className="space-y-4" aria-labelledby="sec-provenance">
        <div className={card + ' space-y-4'}>
          <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-stone-200 pb-3">
            <div>
              <h2 id="sec-provenance" className="text-xl font-serif font-bold text-stone-900">
                7. Provenance, Cryptographic Verification & Downloads
              </h2>
              <p className="text-xs text-stone-600">
                Immutable SHA-256 identities guaranteeing exact reproduction from frozen research inputs.
              </p>
            </div>
            <span className="text-xs font-mono bg-emerald-100 text-emerald-900 px-2 py-1 rounded">
              Status: {provenance.bundle.approval_state}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono text-stone-700">
            <div>
              <p className="font-semibold text-stone-900">Derivative Kind & Version:</p>
              <p>{provenance.bundle.kind} · {provenance.bundle.version} (Schema v{provenance.schema_version})</p>
            </div>
            <div>
              <p className="font-semibold text-stone-900">Run ID & Primary Assignment Count:</p>
              <p>{provenance.run_id} · PRIMARY_SITE_ASSIGNMENTS = {provenance.scope.PRIMARY_SITE_ASSIGNMENTS_ACCEPTED}</p>
            </div>
            <div className="md:col-span-2 break-all">
              <p className="font-semibold text-stone-900">Manifest SHA-256 Digest:</p>
              <p className="bg-stone-100 p-2 rounded">{provenance.bundle.manifest_sha256}</p>
            </div>
          </div>

          <div className="space-y-2 pt-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-stone-500">
              Download Verified Derivative Artifacts
            </h3>
            <div className="flex flex-wrap gap-3">
              <a
                href={modelsDownloadUrl('model_comparisons', manifestSha)}
                className="px-3 py-1.5 bg-stone-900 text-stone-50 text-xs rounded hover:bg-stone-800"
                download
              >
                Model Comparisons (CSV)
              </a>
              <a
                href={modelsDownloadUrl('feature_ablation', manifestSha)}
                className="px-3 py-1.5 bg-stone-900 text-stone-50 text-xs rounded hover:bg-stone-800"
                download
              >
                Feature Timing & Ablation (CSV)
              </a>
              <a
                href={modelsDownloadUrl('threshold_performance', manifestSha)}
                className="px-3 py-1.5 bg-stone-900 text-stone-50 text-xs rounded hover:bg-stone-800"
                download
              >
                Threshold Performance (CSV)
              </a>
              <a
                href={modelsDownloadUrl('calibration_diagnostics', manifestSha)}
                className="px-3 py-1.5 bg-stone-900 text-stone-50 text-xs rounded hover:bg-stone-800"
                download
              >
                Calibration Diagnostics (CSV)
              </a>
              <a
                href={modelsAssetUrl('models_data_dictionary.md', manifestSha)}
                className="px-3 py-1.5 bg-stone-200 text-stone-900 text-xs rounded hover:bg-stone-300"
                download
              >
                Data Dictionary (Markdown)
              </a>
              <a
                href={modelsAssetUrl('manifest.json', manifestSha)}
                className="px-3 py-1.5 bg-stone-200 text-stone-900 text-xs rounded hover:bg-stone-300"
                download
              >
                Release Manifest (JSON)
              </a>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
