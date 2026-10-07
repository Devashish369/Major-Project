/**
 * pages/BenchmarksPage.jsx – Model Benchmarks page (spec §9, M8).
 *
 * Clearly labelled per spec:
 *   - "benchmark on public NASA93 data (93 projects)"
 *   - "risk training data is simulated"
 *
 * Sections:
 *   1. NASA93 Effort Benchmark – GradientBoosting regressor on real COCOMO data
 *   2. Risk Delay Classifier   – classifier trained on SIMULATED snapshots
 *   3. Task Estimator          – TF-IDF+Ridge on 16 public Jira CSV datasets
 */
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft, FlaskConical, Database, AlertTriangle, CheckCircle2,
  BarChart3, Cpu, TrendingUp, Activity,
} from 'lucide-react';
import { getBenchmarks } from '../api/benchmarks';

// ── Helpers ───────────────────────────────────────────────────────────────────

function MetricCard({ label, value, sub, color = 'indigo' }) {
  const colors = {
    indigo: 'bg-indigo-500/10 border-indigo-500/20 text-indigo-400',
    green:  'bg-green-500/10  border-green-500/20  text-green-400',
    amber:  'bg-amber-500/10  border-amber-500/20  text-amber-400',
    rose:   'bg-rose-500/10   border-rose-500/20   text-rose-400',
  };
  return (
    <div className={`rounded-xl border p-4 ${colors[color]}`}>
      <p className="text-xs font-medium uppercase tracking-wide opacity-70">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
      {sub && <p className="text-xs opacity-60 mt-0.5">{sub}</p>}
    </div>
  );
}

function SectionHeader({ icon: Icon, title, badge, badgeColor = 'amber' }) {
  const badgeColors = {
    amber: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
    blue:  'bg-blue-500/20  text-blue-300  border-blue-500/30',
    green: 'bg-green-500/20 text-green-300 border-green-500/30',
  };
  return (
    <div className="flex items-center gap-3 mb-5">
      <div className="p-2.5 rounded-xl bg-slate-700/50 border border-slate-600">
        <Icon className="h-5 w-5 text-slate-300" />
      </div>
      <div className="flex-1">
        <h2 className="text-base font-semibold text-white">{title}</h2>
      </div>
      {badge && (
        <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${badgeColors[badgeColor]}`}>
          {badge}
        </span>
      )}
    </div>
  );
}

function FeatureBar({ name, importance }) {
  const pct = Math.round(importance * 100);
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-slate-400 w-32 truncate font-mono">{name}</span>
      <div className="flex-1 h-2 rounded-full bg-slate-700">
        <div
          className="h-2 rounded-full bg-indigo-500 transition-all"
          style={{ width: `${Math.max(2, pct)}%` }}
        />
      </div>
      <span className="text-xs text-slate-500 w-10 text-right">{pct}%</span>
    </div>
  );
}

function ConfusionMatrix({ cm }) {
  if (!cm || cm.length < 2) return null;
  const [[tn, fp], [fn, tp]] = cm;
  const cells = [
    { label: 'True Negative',  val: tn, color: 'text-green-400' },
    { label: 'False Positive', val: fp, color: 'text-rose-400' },
    { label: 'False Negative', val: fn, color: 'text-rose-400' },
    { label: 'True Positive',  val: tp, color: 'text-green-400' },
  ];
  return (
    <div>
      <p className="text-xs text-slate-500 mb-2">Confusion matrix (rows=actual, cols=predicted)</p>
      <div className="grid grid-cols-2 gap-1 w-48">
        {cells.map(({ label, val, color }) => (
          <div key={label}
            className="rounded-lg bg-slate-700/50 p-2 text-center border border-slate-600">
            <p className={`text-lg font-bold ${color}`}>{val}</p>
            <p className="text-[10px] text-slate-500">{label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function BenchmarksPage() {
  const navigate = useNavigate();
  const { data, isLoading, isError } = useQuery({
    queryKey: ['benchmarks'],
    queryFn: getBenchmarks,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-96 text-slate-400">
        <Cpu className="h-5 w-5 animate-spin mr-2" />
        Loading benchmark data…
      </div>
    );
  }

  if (isError) {
    return (
      <div className="max-w-2xl mx-auto mt-12 rounded-xl bg-rose-500/10 border border-rose-500/30 p-6 text-center text-rose-400">
        <AlertTriangle className="h-6 w-6 mx-auto mb-2" />
        <p className="font-semibold">Benchmarks unavailable</p>
        <p className="text-sm mt-1 text-rose-300">
          Run <code className="font-mono bg-rose-500/10 px-1 rounded">python -m ml.train_effort</code> and{' '}
          <code className="font-mono bg-rose-500/10 px-1 rounded">python -m ml.train_risk</code> first.
        </p>
      </div>
    );
  }

  const effort = data?.effort ?? {};
  const risk   = data?.risk   ?? {};
  const sortedEffortFeatures = (effort.feature_importances_sorted || []).slice(0, 8);
  const sortedRiskFeatures   = (risk.feature_importances_sorted   || []).slice(0, 8);

  return (
    <div className="max-w-5xl mx-auto space-y-8 pb-16">

      {/* ── Page header ──────────────────────────────────────────────────── */}
      <div className="pt-2">
        <button
          onClick={() => navigate('/dashboard')}
          className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-white mb-4 transition"
        >
          <ArrowLeft className="h-4 w-4" /> Back to dashboard
        </button>
        <div className="flex items-center gap-3 mb-1">
          <FlaskConical className="h-6 w-6 text-indigo-400" />
          <h1 className="text-xl font-bold text-white">Model Benchmarks</h1>
        </div>
        <p className="text-sm text-slate-400">
          Performance metrics for the ML models powering IntelliPM's AI features.
        </p>
      </div>

      {/* ── 1. NASA93 Effort Benchmark ──────────────────────────────────── */}
      <section className="rounded-2xl border border-slate-700 bg-slate-800 p-6">
        <SectionHeader
          icon={Database}
          title="Effort Estimator – NASA93 Benchmark"
          badge="Public dataset · 93 real projects"
          badgeColor="blue"
        />

        <div className="mb-4 rounded-lg border border-blue-500/20 bg-blue-500/5 px-4 py-3 text-sm text-blue-300 flex items-start gap-2">
          <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
          <span>
            <strong>benchmark on public NASA93 data (93 projects)</strong> — COCOMO software
            effort dataset from NASA ground-station projects. Model: GradientBoostingRegressor
            trained on 15 COCOMO cost-driver ratings + equivalent KLOC.
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          <MetricCard label="Projects" value={effort.n_projects ?? 93} color="indigo" />
          <MetricCard
            label="CV MAE"
            value={effort.cv_mae_mean != null ? `${effort.cv_mae_mean}` : '—'}
            sub={`± ${effort.cv_mae_std ?? '—'} person-months`}
            color="amber"
          />
          <MetricCard
            label="CV R²"
            value={effort.cv_r2_mean != null ? effort.cv_r2_mean.toFixed(3) : '—'}
            sub={`± ${effort.cv_r2_std ?? '—'}`}
            color={effort.cv_r2_mean >= 0.5 ? 'green' : 'rose'}
          />
          <MetricCard label="CV Folds" value={effort.cv_folds ?? 5} color="indigo" />
        </div>

        {sortedEffortFeatures.length > 0 && (
          <div>
            <p className="text-xs text-slate-500 uppercase tracking-wide mb-3">
              Feature importances (top {sortedEffortFeatures.length})
            </p>
            <div className="space-y-2">
              {sortedEffortFeatures.map(({ feature, importance }) => (
                <FeatureBar key={feature} name={feature} importance={importance} />
              ))}
            </div>
          </div>
        )}

        <p className="mt-4 text-xs text-slate-500">
          COCOMO encoding: vl=0, l=1, n=2, h=3, vh=4, xh=5.
          High CV R² variability is expected with only 93 samples (leave-one-out would be
          more stable but was not used to match the 5-fold convention).
        </p>
      </section>

      {/* ── 2. Risk Delay Classifier ────────────────────────────────────── */}
      <section className="rounded-2xl border border-slate-700 bg-slate-800 p-6">
        <SectionHeader
          icon={Activity}
          title="Delay Risk Classifier"
          badge="Simulated training data"
          badgeColor="amber"
        />

        <div className="mb-4 rounded-lg border border-amber-500/20 bg-amber-500/5 px-4 py-3 text-sm text-amber-300 flex items-start gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
          <span>
            <strong>Risk training data is simulated.</strong> The model was trained on
            synthetic project snapshots generated by a Monte Carlo simulation (ml/generate_synthetic.py),
            not on real project histories. The delay probability is an <em>indicative signal</em>
            and should not be treated as a rigorous forecast.
          </span>
        </div>

        {risk.accuracy != null ? (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
              <MetricCard
                label="Accuracy"
                value={`${(risk.accuracy * 100).toFixed(1)}%`}
                color={risk.accuracy >= 0.85 ? 'green' : 'amber'}
              />
              <MetricCard
                label="Precision"
                value={`${(risk.precision * 100).toFixed(1)}%`}
                color="indigo"
              />
              <MetricCard
                label="Recall"
                value={`${(risk.recall * 100).toFixed(1)}%`}
                color="indigo"
              />
              <MetricCard
                label="Train size"
                value={risk.n_train ?? '—'}
                sub={`+ ${risk.n_test ?? '—'} test`}
                color="indigo"
              />
            </div>

            <div className="flex flex-col sm:flex-row gap-6">
              <ConfusionMatrix cm={risk.confusion_matrix} />

              {sortedRiskFeatures.length > 0 && (
                <div className="flex-1">
                  <p className="text-xs text-slate-500 uppercase tracking-wide mb-3">
                    Feature importances
                  </p>
                  <div className="space-y-2">
                    {sortedRiskFeatures.map(({ feature, importance }) => (
                      <FeatureBar key={feature} name={feature} importance={importance} />
                    ))}
                  </div>
                </div>
              )}
            </div>

            <p className="mt-4 text-xs text-slate-500">
              Model: {risk.model ?? 'GradientBoostingClassifier'}.
              Training data: {risk.n_train ?? '—'} simulated snapshots with 8% label noise. Because each label is computed from remaining work vs. available capacity (the remaining_ratio feature), the accuracy mainly shows how well the model re-learns that simulation rule (100% minus the 8% noise is the ceiling); it is not evidence of accuracy on real projects.
            </p>
          </>
        ) : (
          <p className="text-sm text-slate-500">
            Risk model metrics not available. Run{' '}
            <code className="font-mono bg-slate-700 px-1 rounded">python -m ml.train_risk</code>.
          </p>
        )}
      </section>

      {/* ── 3. Task Estimator ───────────────────────────────────────────── */}
      <section className="rounded-2xl border border-slate-700 bg-slate-800 p-6">
        <SectionHeader
          icon={TrendingUp}
          title="Task Story-Point Estimator"
          badge="16 public Jira datasets"
          badgeColor="blue"
        />

        <div className="mb-4 rounded-lg border border-blue-500/20 bg-blue-500/5 px-4 py-3 text-sm text-blue-300 flex items-start gap-2">
          <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
          <span>
            Trained on 16 public Jira issue CSV datasets using TF-IDF (20k features, bigrams,
            sublinear TF) + Ridge regression on a log₁₊ story-point target. Metrics computed
            on the held-out <em>test</em> split (split_mark column).
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <MetricCard label="Datasets" value="16" sub="public Jira CSVs" color="indigo" />
          <MetricCard label="Model" value="TF-IDF + Ridge" sub="log1p target" color="indigo" />
          <MetricCard
            label="Prediction range"
            value="0.5 – 40 SP"
            sub="clipped for safety"
            color="green"
          />
        </div>

        <p className="mt-4 text-xs text-slate-500">
          Metrics: See <code className="font-mono bg-slate-700 px-1 rounded">ml/artifacts/estimator_metrics.json</code>.
          The model beats the predict-the-median baseline on both MAE and MdAE on the test set.
          Estimates shown in the Plan tab are suggestions only – the LLM value is never overwritten.
        </p>
      </section>
    </div>
  );
}
