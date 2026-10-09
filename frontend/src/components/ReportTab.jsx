/**
 * components/ReportTab.jsx – M16 printable project report.
 *
 * Renders GET /projects/{id}/report as a document (white "paper" so it prints as it looks).
 * "Print / Save as PDF" uses the browser's print dialog; index.css has the @media print rules
 * (navigation hidden, no page breaks inside sections, A4 margins).
 * Every sentence in the report comes from fixed rules over the app's own numbers – no LLM.
 */
import { useQuery } from '@tanstack/react-query';
import { Loader2, AlertCircle, Printer, RefreshCw } from 'lucide-react';
import { getReport } from '../api/report';

const pct = (v) => (v == null ? '—' : `${Math.round(v * 100)} %`);
const LABEL = { overloaded: 'Overloaded', at_risk: 'At risk', healthy: 'Healthy', available: 'Available' };
const PENALTIES = [['overdue', 'Overdue tasks', 30], ['blocked', 'Blocked tasks', 20], ['overload', 'Team overload', 15], ['slip', 'Schedule slip', 35]];

function Section({ title, children }) {
  return (
    <section className="report-section mt-6">
      <h2 className="text-base font-semibold text-slate-900 border-b border-slate-300 pb-1 mb-2">{title}</h2>
      {children}
    </section>
  );
}

function Table({ head, rows, empty }) {
  if (!rows.length) return <p className="text-sm text-slate-500">{empty}</p>;
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-slate-500">{head.map((h, i) => <th key={i} className="py-1 pr-3 font-medium">{h}</th>)}</tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i} className="border-t border-slate-200 align-top">
            {r.map((c, j) => <td key={j} className="py-1 pr-3">{c}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function ReportTab({ projectId }) {
  const { data: r, isPending, isError, refetch, isFetching } = useQuery({
    queryKey: ['report', projectId],
    queryFn: () => getReport(projectId),
    networkMode: 'always',
  });

  if (isPending) {
    return <div className="flex justify-center py-16"><Loader2 className="h-6 w-6 animate-spin text-indigo-400" /></div>;
  }
  if (isError) {
    return (
      <div className="flex flex-col items-center gap-2 py-16 text-center">
        <AlertCircle className="h-6 w-6 text-red-400" />
        <p className="text-sm text-red-400">Could not generate the report.</p>
        <button onClick={() => refetch()} className="flex items-center gap-1 text-xs text-indigo-400 hover:underline">
          <RefreshCw className="h-3 w-3" /> Retry
        </button>
      </div>
    );
  }

  const generated = new Date(r.generated_at).toLocaleString();
  const summary = r.insights.slice(0, 3).join(' ');

  return (
    <div>
      <div className="no-print flex items-center justify-end gap-3 mb-3">
        <button onClick={() => refetch()} disabled={isFetching}
          className="flex items-center gap-1.5 rounded-lg border border-slate-600 px-3 py-1.5 text-sm text-slate-300 hover:text-white">
          <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} /> Refresh
        </button>
        <button id="print-report-btn" onClick={() => window.print()}
          className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500">
          <Printer className="h-4 w-4" /> Print / Save as PDF
        </button>
      </div>

      <article id="report-doc" className="print-doc rounded-xl bg-white text-slate-800 p-8 shadow">
        <header className="report-header">
          <p className="text-xs uppercase tracking-wide text-slate-500">IntelliPM project report</p>
          <h1 className="text-2xl font-bold text-slate-900">{r.project.title}</h1>
          <p className="text-xs text-slate-500 mt-1">
            Generated {generated} · status {r.project.status.replace('_', ' ')} · priority {r.project.priority}
            {r.project.start_date && <> · start {r.project.start_date}</>}{r.project.due_date && <> · due {r.project.due_date}</>}
            · {r.project.member_count} members
          </p>
        </header>

        <Section title="Executive summary">
          <p className="text-sm leading-relaxed">{summary}</p>
          {r.tasks.total === 0 && (
            <p className="text-sm text-slate-500 mt-2">There is nothing to report yet – the sections fill in once the project has tasks.</p>
          )}
        </Section>

        <div className="grid sm:grid-cols-2 gap-x-8">
          <Section title="Key insights">
            <ul className="list-disc pl-5 text-sm space-y-1">{r.insights.map((s, i) => <li key={i}>{s}</li>)}</ul>
          </Section>
          <Section title="Suggested actions (the manager decides)">
            <ol className="list-decimal pl-5 text-sm space-y-1">{r.suggested_actions.map((s, i) => <li key={i}>{s}</li>)}</ol>
          </Section>
        </div>

        <div className="grid sm:grid-cols-3 gap-x-8">
          <Section title="Health score">
            <p className="text-3xl font-bold text-slate-900">{Math.round(r.health.health_score)}<span className="text-base font-normal text-slate-500"> / 100 · {r.health.level}</span></p>
            <Table head={['Penalty', 'Points']} empty="—"
              rows={PENALTIES.map(([k, label, max]) => [label, `−${(r.health.penalties?.[k] ?? 0).toFixed(1)} / ${max}`])} />
          </Section>
          <Section title="Forecast (Monte Carlo, primary)">
            <Table head={['', '']} empty="—" rows={[
              ['P50 finish', r.forecast.p50 ?? '—'], ['P80 finish', r.forecast.p80 ?? '—'], ['P90 finish', r.forecast.p90 ?? '—'],
              ['Due date', r.forecast.due_date ?? 'not set'], ['Chance of missing it', pct(r.forecast.delay_probability)],
            ]} />
          </Section>
          <Section title="Tasks">
            <Table head={['', '']} empty="—" rows={[
              ['Total', r.tasks.total], ['To do / in progress / done', `${r.tasks.by_status.todo} / ${r.tasks.by_status.in_progress} / ${r.tasks.by_status.done}`],
              ['Overdue', r.tasks.overdue], ['Blocked', r.tasks.blocked], ['Unassigned (open)', r.tasks.unassigned_open],
              ['Hours total / remaining', `${r.tasks.total_hours} / ${r.tasks.remaining_hours}`],
            ]} />
          </Section>
        </div>

        <Section title="Workload">
          <Table head={['Member', 'Utilisation', 'Status', 'Open hours', 'Capacity / week']} empty="No members."
            rows={r.workload.map((m) => [m.full_name, pct(m.utilization), LABEL[m.label] ?? m.label, m.open_hours_assigned, `${m.capacity_hours_per_week} h`])} />
        </Section>

        <Section title="Delay risk – ML signal (experimental, secondary)">
          {r.risk ? (
            <>
              <p className="text-sm">Probability of finishing late: <strong>{pct(r.risk.delay_probability)}</strong> ({r.risk.risk_level}).</p>
              {r.risk.top_factors?.length > 0 && (
                <p className="text-sm text-slate-600">Main factors for this project: {r.risk.top_factors.map((f) => `${f.feature.replace(/_/g, ' ')} = ${f.value} (${f.direction})`).join('; ')}.</p>
              )}
              <p className="text-xs text-slate-500 mt-1">{r.risk.note}</p>
            </>
          ) : <p className="text-sm text-slate-500">Risk model not available.</p>}
        </Section>

        <div className="grid sm:grid-cols-2 gap-x-8">
          <Section title="Most overdue tasks">
            <Table head={['Task', 'Due', 'Late', 'Assignee']} empty="No overdue tasks."
              rows={r.overdue_tasks.map((t) => [`#${t.id} ${t.title}`, t.due_date, `${t.days_overdue} d`, t.assignee ?? '—'])} />
          </Section>
          <Section title="Blocked tasks">
            <Table head={['Task', 'Waiting for']} empty="No blocked tasks."
              rows={r.blocked_tasks.map((t) => [`#${t.id} ${t.title}`, t.blockers.map((b) => `#${b.id} ${b.title} (${b.status.replace('_', ' ')})`).join(', ')])} />
          </Section>
        </div>

        <Section title="Recent decisions">
          <Table head={['Decision', 'Why', 'By']} empty="No decisions recorded."
            rows={r.decisions.map((d) => [<><strong>{d.title}</strong>: {d.decision}</>, d.reason ?? '—', d.made_by ?? '—'])} />
        </Section>

        <Section title="Recent activity">
          <Table head={['When', 'Who', 'What']} empty="No activity yet."
            rows={r.activity.map((a) => [new Date(a.created_at).toLocaleDateString(), a.user ?? '—', `${a.action.replace(/_/g, ' ')}${a.task_id ? ` (task #${a.task_id})` : ''}`])} />
        </Section>

        <footer className="report-section mt-8 border-t border-slate-300 pt-3 text-xs text-slate-500 space-y-1">
          <p><strong>Decision support only: the AI recommends, the manager decides.</strong> Insights and actions are generated by fixed rules from the numbers above; no language model is used in this report.</p>
          <p>The ML delay-risk signal is experimental and trained on SIMULATED project data, not real project histories. The primary forecast is the Monte Carlo simulation.</p>
        </footer>
      </article>
    </div>
  );
}
