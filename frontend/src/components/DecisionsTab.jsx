/**
 * components/DecisionsTab.jsx – M12: decision log + "Ask the project" box.
 *
 * The Ask box sends the question to POST /projects/{id}/ask.  The backend builds the
 * context from this project's tasks, decisions and recent activity and the answer cites
 * ids; here every cited source is shown as a chip with the title it points to.
 */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Loader2, AlertCircle, BookOpen, Plus, Trash2, Sparkles, Send, ListChecks, ScrollText, Activity, RefreshCw,
} from 'lucide-react';
import { listDecisions, createDecision, deleteDecision, askProject } from '../api/decisions';
import { errorMessage } from '../api/errors';

const errText = (e, fallback) => errorMessage(e, fallback);
const fmt = (iso) => new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });

// ── Ask box ───────────────────────────────────────────────────────────────────

function SourceChip({ source, decisions, tasks }) {
  let Icon = Activity, label = 'Activity';
  if (source.type === 'task') {
    Icon = ListChecks;
    const t = tasks.find((x) => x.id === source.id);
    label = `Task #${source.number ?? t?.number ?? source.id}: ${t?.title ?? 'task'}`;
  } else if (source.type === 'decision') {
    Icon = ScrollText;
    const d = decisions.find((x) => x.id === source.id);
    label = `Decision D${source.number ?? d?.number ?? source.id}: ${d?.title ?? 'decision'}`;
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-600 bg-slate-900 px-2.5 py-1 text-xs text-slate-300">
      <Icon className="h-3 w-3 text-indigo-400" /> {label}
    </span>
  );
}

function AskBox({ projectId, decisions, tasks }) {
  const [question, setQuestion] = useState('');
  const mut = useMutation({ mutationFn: (q) => askProject(projectId, q) });

  const submit = (e) => {
    e.preventDefault();
    if (question.trim().length >= 3 && !mut.isPending) mut.mutate(question.trim());
  };

  return (
    <div className="rounded-2xl border border-slate-700 bg-slate-800 p-5">
      <div className="flex items-center gap-2 mb-1">
        <Sparkles className="h-4 w-4 text-indigo-400" />
        <p className="text-sm font-semibold text-white">Ask the project</p>
      </div>
      <p className="text-xs text-slate-400 mb-3">
        Answers come only from this project's tasks, decisions and recent activity, with sources.
      </p>
      <form onSubmit={submit} className="flex gap-2">
        <input
          id="ask-input"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          maxLength={500}
          placeholder="e.g. Why did we choose a 10-minute seat hold?"
          className="flex-1 rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-indigo-500"
        />
        <button
          id="ask-btn"
          type="submit"
          disabled={mut.isPending || question.trim().length < 3}
          className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 transition"
        >
          {mut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />} Ask
        </button>
      </form>

      {mut.isError && (
        <div id="ask-error" className="mt-3 flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-300">
          <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
          <span>{errText(mut.error, 'Could not get an answer. Please try again.')}</span>
        </div>
      )}
      {mut.isSuccess && (
        <div id="ask-answer" className="mt-4 rounded-lg border border-slate-700 bg-slate-900 p-4">
          <p className="text-sm text-slate-100 whitespace-pre-wrap">{mut.data.answer}</p>
          <div className="mt-3 border-t border-slate-700 pt-3">
            <p className="text-xs text-slate-400 mb-2">Sources</p>
            {mut.data.sources.length === 0 ? (
              <p className="text-xs text-slate-500">No sources cited.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {mut.data.sources.map((s) => (
                  <SourceChip key={`${s.type}-${s.id}`} source={s} decisions={decisions} tasks={tasks} />
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Add form ──────────────────────────────────────────────────────────────────

function AddDecisionForm({ projectId, tasks, onDone }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({ title: '', decision: '', reason: '', related_task_id: '' });
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const mut = useMutation({
    mutationFn: () => createDecision(projectId, {
      title: form.title, decision: form.decision,
      reason: form.reason || null,
      related_task_id: form.related_task_id ? Number(form.related_task_id) : null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['decisions', projectId] });
      onDone();
    },
  });

  const input = 'w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-indigo-500';
  return (
    <form
      onSubmit={(e) => { e.preventDefault(); mut.mutate(); }}
      className="rounded-2xl border border-slate-700 bg-slate-800 p-5 space-y-3"
    >
      <p className="text-sm font-semibold text-white">Record a decision</p>
      <input id="decision-title" className={input} placeholder="Title (e.g. Use PostgreSQL)" required maxLength={200}
        value={form.title} onChange={set('title')} />
      <textarea id="decision-text" className={input} rows={2} placeholder="What was decided?" required maxLength={2000}
        value={form.decision} onChange={set('decision')} />
      <textarea id="decision-reason" className={input} rows={2} placeholder="Why? (optional)" maxLength={2000}
        value={form.reason} onChange={set('reason')} />
      <select className={input} value={form.related_task_id} onChange={set('related_task_id')}>
        <option value="">Related task (optional)</option>
        {tasks.map((t) => <option key={t.id} value={t.id}>#{t.number ?? t.id} {t.title}</option>)}
      </select>
      {mut.isError && <p className="text-sm text-red-400">{errText(mut.error, 'Could not save the decision.')}</p>}
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onDone} className="rounded-lg px-3 py-2 text-sm text-slate-300 hover:text-white">Cancel</button>
        <button
          id="save-decision-btn"
          type="submit"
          disabled={mut.isPending}
          className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-60"
        >
          {mut.isPending && <Loader2 className="h-4 w-4 animate-spin" />} Save decision
        </button>
      </div>
    </form>
  );
}

// ── Tab ───────────────────────────────────────────────────────────────────────

export default function DecisionsTab({ projectId, tasks, isAdmin, currentUserId }) {
  const qc = useQueryClient();
  const [adding, setAdding] = useState(false);

  const { data: decisions = [], isLoading, isError, refetch } = useQuery({
    queryKey: ['decisions', projectId],
    queryFn: () => listDecisions(projectId),
  });

  const delMut = useMutation({
    mutationFn: deleteDecision,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['decisions', projectId] }),
  });

  const taskTitle = (id) => tasks.find((t) => t.id === id)?.title;

  return (
    <div className="space-y-5">
      <AskBox projectId={projectId} decisions={decisions} tasks={tasks} />

      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-white">Decision log ({decisions.length})</h2>
        {!adding && (
          <button
            id="add-decision-btn"
            onClick={() => setAdding(true)}
            className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 transition"
          >
            <Plus className="h-4 w-4" /> Add decision
          </button>
        )}
      </div>

      {adding && <AddDecisionForm projectId={projectId} tasks={tasks} onDone={() => setAdding(false)} />}

      {isLoading && <div className="flex justify-center py-10"><Loader2 className="h-6 w-6 animate-spin text-indigo-400" /></div>}
      {isError && (
        <div className="flex flex-col items-center gap-2 py-8 text-center">
          <AlertCircle className="h-6 w-6 text-red-400" />
          <p className="text-sm text-red-400">Could not load the decision log.</p>
          <button onClick={() => refetch()} className="flex items-center gap-1 text-xs text-indigo-400 hover:underline">
            <RefreshCw className="h-3 w-3" /> Retry
          </button>
        </div>
      )}
      {!isLoading && !isError && decisions.length === 0 && (
        <div className="rounded-2xl border border-slate-700 bg-slate-800 py-12 text-center">
          <BookOpen className="h-8 w-8 text-slate-600 mx-auto mb-2" />
          <p className="text-sm text-slate-400">No decisions recorded yet. Capture the important ones so the team (and Ask) can find the reasons later.</p>
        </div>
      )}

      <div className="space-y-3">
        {decisions.map((d) => (
          <div key={d.id} className="rounded-xl border border-slate-700 bg-slate-800 p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-medium text-white">
                  <span className="text-xs text-slate-500 font-mono mr-2">D{d.number ?? d.id}</span>{d.title}
                </p>
                <p className="mt-1 text-sm text-slate-200 whitespace-pre-wrap">{d.decision}</p>
                {d.reason && <p className="mt-1 text-sm text-slate-400 whitespace-pre-wrap"><span className="text-slate-500">Why:</span> {d.reason}</p>}
              </div>
              {(isAdmin || d.made_by === currentUserId) && (
                <button
                  onClick={() => { if (window.confirm('Delete this decision?')) delMut.mutate(d.id); }}
                  disabled={delMut.isPending}
                  className="text-slate-500 hover:text-red-400 transition shrink-0"
                  aria-label={`Delete decision ${d.title}`}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
            <p className="mt-2 text-xs text-slate-500">
              {d.made_by_name || 'Unknown'} · {fmt(d.created_at)}
              {d.related_task_id && <> · task #{tasks.find((t) => t.id === d.related_task_id)?.number ?? d.related_task_id}{taskTitle(d.related_task_id) ? `: ${taskTitle(d.related_task_id)}` : ''}</>}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
