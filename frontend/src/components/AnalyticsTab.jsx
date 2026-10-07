/**
 * components/AnalyticsTab.jsx – M9 analytics: health score + penalty breakdown,
 * forecast histogram (P50/P80/P90 + due date), burndown, workload bars and the
 * ML delay-risk probability.  Every card handles loading, empty and error.
 */
import { useQuery } from '@tanstack/react-query';
import { Loader2, AlertCircle, BarChart2, RefreshCw } from 'lucide-react';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
  ReferenceLine, LineChart, Line, Legend, Cell,
} from 'recharts';
import { getHealth, getForecast, getBurndown } from '../api/analytics';
import { getWorkload } from '../api/assignments';

const GRID = '#334155';
const AXIS = { fill: '#94a3b8', fontSize: 11 };
const TIP = { backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: 8, fontSize: 12 };

// Shared card shell that renders the right state for a react-query result.
function Card({ title, subtitle, query, isEmpty, emptyText, children, className = '' }) {
  let body;
  if (query.isPending) {
    body = <div className="h-48 flex items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-indigo-400" /></div>;
  } else if (query.isError) {
    body = (
      <div className="h-48 flex flex-col items-center justify-center gap-2 text-center">
        <AlertCircle className="h-6 w-6 text-red-400" />
        <p className="text-sm text-red-400">Could not load this chart.</p>
        <button onClick={() => query.refetch()} className="flex items-center gap-1 text-xs text-indigo-400 hover:underline">
          <RefreshCw className="h-3 w-3" /> Retry
        </button>
      </div>
    );
  } else if (isEmpty(query.data)) {
    body = (
      <div className="h-48 flex flex-col items-center justify-center gap-2 text-center">
        <BarChart2 className="h-6 w-6 text-slate-600" />
        <p className="text-sm text-slate-400">{emptyText}</p>
      </div>
    );
  } else {
    body = children(query.data);
  }
  return (
    <div className={`rounded-2xl border border-slate-700 bg-slate-800 p-5 h-full ${className}`}>
      <p className="text-sm font-semibold text-white">{title}</p>
      {subtitle && <p className="text-xs text-slate-400 mb-3">{subtitle}</p>}
      {body}
    </div>
  );
}

const LEVEL_STYLE = {
  'Low risk': 'text-green-400 bg-green-500/10 border-green-500/30',
  'Medium risk': 'text-amber-400 bg-amber-500/10 border-amber-500/30',
  'High risk': 'text-red-400 bg-red-500/10 border-red-500/30',
};
// [key, label, maximum possible penalty from spec 8.5]
const PENALTY_INFO = [
  ['overdue', 'Overdue tasks', 30],
  ['blocked', 'Blocked tasks', 20],
  ['overload', 'Team overload', 15],
  ['slip', 'Schedule slip', 35],
];

function HealthCard({ query }) {
  return (
    <Card title="Health score" subtitle="100 minus four penalties" query={query}
      isEmpty={(d) => !d} emptyText="No health data yet.">
      {(d) => (
        <div>
          <div className="flex items-end gap-3 mb-4">
            <span className="text-5xl font-bold text-white">{Math.round(d.health_score)}</span>
            <span className="text-slate-400 mb-1">/ 100</span>
            <span className={`mb-1 ml-auto text-xs px-2 py-1 rounded-full border font-medium ${LEVEL_STYLE[d.level]}`}>{d.level}</span>
          </div>
          <div className="space-y-2.5">
            {PENALTY_INFO.map(([key, label, max]) => {
              const v = d.penalties?.[key] ?? 0;
              return (
                <div key={key}>
                  <div className="flex justify-between text-xs text-slate-400 mb-1">
                    <span>{label}</span>
                    <span>−{v.toFixed(1)} <span className="text-slate-600">/ {max}</span></span>
                  </div>
                  <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                    <div className="h-full bg-red-500/80 rounded-full" style={{ width: `${Math.min(100, (v / max) * 100)}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </Card>
  );
}

function RiskCard({ query }) {
  return (
    <Card title="Delay risk (ML, experimental)"
      subtitle="Trained on SIMULATED projects. The primary forecast is the Monte Carlo simulation; the ML signal is secondary."
      query={query}
      isEmpty={(d) => !d?.risk || d.diagnostics.open_tasks + d.diagnostics.done_tasks === 0}
      emptyText="Add tasks to see a delay-risk estimate.">
      {(d) => {
        const p = d.risk.delay_probability;
        const color = p >= 0.65 ? 'text-red-400' : p >= 0.35 ? 'text-amber-400' : 'text-green-400';
        return (
          <div>
            <p className={`text-5xl font-bold ${color}`}>{Math.round(p * 100)}%</p>
            <p className="text-xs text-slate-400 mb-4">probability of finishing late · {d.risk.risk_level} risk</p>
            <p className="text-xs text-slate-400 mb-1.5">
              {d.risk.top_factors?.length ? 'Top contributing factors for this project' : d.risk.data_note}
            </p>
            <ul className="space-y-1">
              {(d.risk.top_factors || []).map((f) => (
                <li key={f.feature} className="flex justify-between text-xs text-slate-300">
                  <span>{f.feature.replace(/_/g, ' ')} = {f.value}</span>
                  <span className="text-slate-500">{f.direction}</span>
                </li>
              ))}
            </ul>
          </div>
        );
      }}
    </Card>
  );
}

// Label of the histogram bucket containing a date (clamped to the ends).
function bucketLabel(hist, iso) {
  if (iso < hist[0].start_date) return hist[0].label;
  const hit = hist.find((b) => iso >= b.start_date && iso <= b.end_date);
  return (hit || hist[hist.length - 1]).label;
}

function ForecastCard({ query, dueDate }) {
  return (
    <Card title="Completion forecast" subtitle="Monte Carlo, 5,000 simulated runs" query={query}
      isEmpty={(d) => !d?.histogram?.length} emptyText="No open tasks to forecast.">
      {(d) => {
        const hist = d.histogram.map((b) => ({ ...b, label: b.start_date.slice(5) }));
        const marks = [
          ['P50', d.p50, '#22c55e'], ['P80', d.p80, '#f59e0b'], ['P90', d.p90, '#ef4444'],
          ['Due', dueDate, '#e2e8f0'],
        ].filter(([, date]) => date).map(([n, date, c]) => [n, date, c, bucketLabel(hist, date)]);
        return (
          <div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-300 mb-2">
              {marks.map(([n, date, c]) => (
                <span key={n}><span style={{ color: c }}>●</span> {n}: {date}</span>
              ))}
              {d.delay_probability != null && (
                <span className="ml-auto text-slate-400">P(late) = {Math.round(d.delay_probability * 100)}%</span>
              )}
            </div>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={hist} margin={{ top: 16, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" tick={AXIS} interval="preserveStartEnd" />
                <YAxis tick={AXIS} />
                <Tooltip contentStyle={TIP} formatter={(v) => [v, 'simulations']} labelFormatter={(l) => `from ${l}`} />
                <Bar dataKey="count" fill="#6366f1" radius={[2, 2, 0, 0]} />
                {marks.map(([n, , c, x]) => (
                  <ReferenceLine key={n} x={x} stroke={c} strokeDasharray={n === 'Due' ? '0' : '4 3'} strokeWidth={2}
                    label={{ value: n, fill: c, fontSize: 11, position: 'top' }} />
                ))}
              </BarChart>
            </ResponsiveContainer>
            {dueDate && dueDate < d.histogram[0].start_date && (
              <p className="text-xs text-red-400 mt-1">The due date is earlier than every simulated finish.</p>
            )}
          </div>
        );
      }}
    </Card>
  );
}

function BurndownCard({ query }) {
  return (
    <Card title="Burndown" subtitle="Remaining estimated hours per day" query={query}
      isEmpty={(d) => !d?.points?.length} emptyText="No tasks with estimates yet.">
      {(d) => (
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={d.points} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="date" tick={AXIS} tickFormatter={(v) => v.slice(5)} interval="preserveStartEnd" />
            <YAxis tick={AXIS} />
            <Tooltip contentStyle={TIP} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Line type="linear" dataKey="ideal" name="Ideal" stroke="#64748b" strokeDasharray="5 4" dot={false} />
            <Line type="stepAfter" dataKey="actual" name="Actual" stroke="#6366f1" strokeWidth={2} dot={false} connectNulls={false} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}

const WL_COLOR = { overloaded: '#ef4444', at_risk: '#f59e0b', healthy: '#22c55e', available: '#64748b' };

function WorkloadCard({ query }) {
  return (
    <Card title="Workload" subtitle="Open assigned hours ÷ capacity until due date" query={query}
      isEmpty={(d) => !d?.length} emptyText="No team members yet.">
      {(d) => {
        const rows = d.map((w) => ({
          name: w.full_name || w.username || `User ${w.user_id}`,
          pct: Math.round(w.utilization * 100), label: w.label,
        }));
        return (
          <ResponsiveContainer width="100%" height={Math.max(160, rows.length * 36)}>
            <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 24, left: 8, bottom: 0 }}>
              <CartesianGrid stroke={GRID} strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={AXIS} unit="%" />
              <YAxis type="category" dataKey="name" tick={AXIS} width={90} />
              <Tooltip contentStyle={TIP} formatter={(v, _n, p) => [`${v}% (${p.payload.label})`, 'utilization']} />
              <ReferenceLine x={100} stroke="#ef4444" strokeDasharray="4 3" />
              <Bar dataKey="pct" radius={[0, 3, 3, 0]}>
                {rows.map((r) => <Cell key={r.name} fill={WL_COLOR[r.label] || '#64748b'} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        );
      }}
    </Card>
  );
}

export default function AnalyticsTab({ projectId, dueDate }) {
  const health = useQuery({ queryKey: ['health', projectId], queryFn: () => getHealth(projectId), networkMode: "always" });
  const forecast = useQuery({ queryKey: ['forecast', projectId], queryFn: () => getForecast(projectId), networkMode: "always" });
  const burndown = useQuery({ queryKey: ['burndown', projectId], queryFn: () => getBurndown(projectId), networkMode: "always" });
  const workload = useQuery({ queryKey: ['workload', projectId], queryFn: () => getWorkload(projectId), networkMode: "always" });

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <HealthCard query={health} />
      <RiskCard query={health} />
      <ForecastCard query={forecast} dueDate={dueDate} />
      <BurndownCard query={burndown} />
      <div className="lg:col-span-2"><WorkloadCard query={workload} /></div>
    </div>
  );
}
