/**
 * components/TaskDrawer.jsx – Slide-out panel showing full task details.
 *
 * Shows: title, description, status, priority, assignee, estimate,
 * due date, required skills, dependencies, and lets the user edit any field.
 * Opens from the Kanban board when a card is clicked.
 */
import { useEffect, useState } from 'react';
import { X, Trash2, Plus, Minus, Loader2, Link2 } from 'lucide-react';
import { useMutation, useQueryClient, useQuery } from '@tanstack/react-query';
import { updateTask, deleteTask, addDependency, removeDependency } from '../api/tasks';
import { listMembers } from '../api/projects';
import { errorMessage } from '../api/errors';

const PRIORITY_COLORS = {
  low: 'text-slate-400', medium: 'text-amber-400',
  high: 'text-orange-400', critical: 'text-red-400',
};

const STATUS_LABELS = {
  todo: 'To Do', in_progress: 'In Progress', done: 'Done',
};

export default function TaskDrawer({ task, projectId, tasks, onClose }) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ ...task });
  const [depInput, setDepInput] = useState('');
  const [depError, setDepError] = useState('');

  const { data: members = [] } = useQuery({
    queryKey: ['members', projectId],
    queryFn: () => listMembers(projectId),
  });

  const updateMut = useMutation({
    mutationFn: (data) => updateTask(task.id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks', projectId] });
      setEditing(false);
    },
  });

  // Escape closes the drawer (expected behaviour for a side panel)
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  // Quick status change from the drawer (same PATCH the drag-and-drop uses)
  const statusMut = useMutation({
    mutationFn: (status) => updateTask(task.id, { status }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks', projectId] });
      qc.invalidateQueries({ queryKey: ['project', projectId] });
    },
  });

  const deleteMut = useMutation({
    mutationFn: () => deleteTask(task.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks', projectId] });
      qc.invalidateQueries({ queryKey: ['project', projectId] });
      onClose();
    },
  });

  const addDepMut = useMutation({
    mutationFn: (depId) => addDependency(task.id, depId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks', projectId] });
      setDepInput('');
      setDepError('');
    },
    onError: (e) => setDepError(errorMessage(e, 'Failed to add dependency.')),
  });

  const removeDepMut = useMutation({
    mutationFn: (depId) => removeDependency(task.id, depId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tasks', projectId] }),
  });

  function handleSave() {
    updateMut.mutate({
      title: form.title,
      description: form.description,
      status: form.status,
      priority: form.priority,
      estimate_hours: form.estimate_hours ? Number(form.estimate_hours) : null,
      actual_hours: form.actual_hours ? Number(form.actual_hours) : null,
      assignee_id: form.assignee_id || null,
      due_date: form.due_date || null,
      required_skills: form.required_skills || [],
    });
  }

  function handleAddDep() {
    const depId = parseInt(depInput, 10);
    if (!depId) { setDepError('Choose a task first.'); return; }
    setDepError('');
    addDepMut.mutate(depId);
  }

  const depTasks = (task.dependencies || [])
    .map((id) => tasks.find((t) => t.id === id))
    .filter(Boolean);

  const assignee = members.find((m) => m.user_id === task.assignee_id);

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="flex-1 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="w-full max-w-md bg-slate-900 border-l border-slate-700 h-full overflow-y-auto flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700 sticky top-0 bg-slate-900 z-10">
          <span className={`text-xs font-semibold uppercase tracking-wider ${PRIORITY_COLORS[task.priority]}`}>
            {task.priority}
          </span>
          <div className="flex items-center gap-2">
            {!editing && (
              <button
                onClick={() => setEditing(true)}
                className="text-xs px-2 py-1 rounded border border-slate-600 text-slate-400 hover:text-white hover:border-indigo-500 transition"
              >
                Edit
              </button>
            )}
            <button
              onClick={() => { if (window.confirm('Delete task?')) deleteMut.mutate(); }}
              className="text-slate-500 hover:text-red-400 transition"
            >
              <Trash2 className="h-4 w-4" />
            </button>
            <button onClick={onClose} className="text-slate-400 hover:text-white">
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        <div className="flex-1 px-5 py-4 space-y-5">
          {/* Title */}
          {editing ? (
            <input
              className="w-full text-lg font-semibold bg-transparent border-b border-slate-600 text-white pb-1 outline-none focus:border-indigo-500"
              value={form.title}
              onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))}
            />
          ) : (
            <h2 className="text-lg font-semibold text-white">{task.title}</h2>
          )}

          {/* Status badge */}
          {editing ? (
            <select
              className="rounded border border-slate-600 bg-slate-800 text-sm text-white px-3 py-1.5 outline-none"
              value={form.status}
              onChange={(e) => setForm((p) => ({ ...p, status: e.target.value }))}
            >
              {Object.entries(STATUS_LABELS).map(([val, label]) => (
                <option key={val} value={val}>{label}</option>
              ))}
            </select>
          ) : (
            // One-click status: no need to press Edit or drag the card (also works on touch screens)
            <div className="inline-flex rounded-lg border border-slate-600 overflow-hidden" role="group" aria-label="Task status">
              {Object.entries(STATUS_LABELS).map(([val, label]) => (
                <button
                  key={val}
                  type="button"
                  data-status-btn={val}
                  disabled={statusMut.isPending}
                  onClick={() => task.status !== val && statusMut.mutate(val)}
                  className={`px-3 py-1.5 text-xs font-medium transition ${
                    task.status === val ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          )}

          {/* Description */}
          <div>
            <p className="text-xs text-slate-400 mb-1.5">Description</p>
            {editing ? (
              <textarea
                rows={4}
                className="w-full rounded-lg border border-slate-600 bg-slate-800 text-sm text-white px-3 py-2 outline-none focus:border-indigo-500 resize-none"
                value={form.description || ''}
                onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
              />
            ) : (
              <p className="text-sm text-slate-300 whitespace-pre-wrap">
                {task.description || <span className="text-slate-600 italic">No description</span>}
              </p>
            )}
          </div>

          {/* Meta grid */}
          <div className="grid grid-cols-2 gap-3 text-sm">
            {/* Assignee */}
            <div className="rounded-lg border border-slate-700 bg-slate-800 p-3">
              <p className="text-xs text-slate-400 mb-1">Assignee</p>
              {editing ? (
                <select
                  className="w-full bg-transparent text-white text-sm outline-none"
                  value={form.assignee_id || ''}
                  onChange={(e) => setForm((p) => ({ ...p, assignee_id: e.target.value ? Number(e.target.value) : null }))}
                >
                  <option value="">Unassigned</option>
                  {members.map((m) => (
                    <option key={m.user_id} value={m.user_id}>{m.full_name}</option>
                  ))}
                </select>
              ) : (
                <p className="text-white font-medium">{assignee?.full_name || '—'}</p>
              )}
            </div>

            {/* Priority */}
            <div className="rounded-lg border border-slate-700 bg-slate-800 p-3">
              <p className="text-xs text-slate-400 mb-1">Priority</p>
              {editing ? (
                <select
                  className="w-full bg-transparent text-white text-sm outline-none"
                  value={form.priority}
                  onChange={(e) => setForm((p) => ({ ...p, priority: e.target.value }))}
                >
                  {['low', 'medium', 'high', 'critical'].map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              ) : (
                <p className={`font-medium ${PRIORITY_COLORS[task.priority]}`}>{task.priority}</p>
              )}
            </div>

            {/* Estimate */}
            <div className="rounded-lg border border-slate-700 bg-slate-800 p-3">
              <p className="text-xs text-slate-400 mb-1">Est. hours</p>
              {editing ? (
                <input type="number" min={0} step={0.5}
                  className="w-full bg-transparent text-white text-sm outline-none"
                  value={form.estimate_hours || ''}
                  onChange={(e) => setForm((p) => ({ ...p, estimate_hours: e.target.value }))}
                />
              ) : (
                <p className="text-white font-medium">{task.estimate_hours ?? '—'}</p>
              )}
            </div>

            {/* Due date */}
            <div className="rounded-lg border border-slate-700 bg-slate-800 p-3">
              <p className="text-xs text-slate-400 mb-1">Due date</p>
              {editing ? (
                <input type="date"
                  className="w-full bg-transparent text-white text-sm outline-none"
                  value={form.due_date || ''}
                  onChange={(e) => setForm((p) => ({ ...p, due_date: e.target.value }))}
                />
              ) : (
                <p className="text-white font-medium">{task.due_date || '—'}</p>
              )}
            </div>
          </div>

          {/* Completed at */}
          {task.completed_at && (
            <div className="text-xs text-green-400">
              ✓ Completed at {new Date(task.completed_at).toLocaleString()}
            </div>
          )}

          {/* Required skills */}
          <div>
            <p className="text-xs text-slate-400 mb-2">Required skills</p>
            {(task.required_skills || []).length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {task.required_skills.map((s) => (
                  <span key={s} className="text-xs px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300">{s}</span>
                ))}
              </div>
            ) : <p className="text-xs text-slate-600">None specified</p>}
          </div>

          {/* Dependencies */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Link2 className="h-3.5 w-3.5 text-slate-400" />
              <p className="text-xs text-slate-400">Depends on ({depTasks.length})</p>
            </div>
            {depTasks.length > 0 ? (
              <ul className="space-y-1.5 mb-3">
                {depTasks.map((dt) => (
                  <li key={dt.id} className="flex items-center justify-between text-sm rounded-lg border border-slate-700 bg-slate-800 px-3 py-2">
                    <span className="text-white">#{dt.number ?? dt.id} {dt.title}</span>
                    <button
                      onClick={() => removeDepMut.mutate(dt.id)}
                      className="text-slate-500 hover:text-red-400 ml-2"
                    >
                      <Minus className="h-3.5 w-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            ) : <p className="text-xs text-slate-600 mb-3">No dependencies</p>}
            <div className="flex gap-2">
              {/* pick by number + title: people see #1, #2 … per project, the API uses the internal id */}
              <select
                id="dependency-picker"
                aria-label="Task this one depends on"
                value={depInput}
                onChange={(e) => setDepInput(e.target.value)}
                className="flex-1 min-w-0 rounded-lg border border-slate-600 bg-slate-800 px-3 py-1.5 text-sm text-white outline-none focus:border-indigo-500"
              >
                <option value="">Depends on…</option>
                {tasks
                  .filter((t) => t.id !== task.id && !(task.dependencies || []).includes(t.id))
                  .map((t) => <option key={t.id} value={t.id}>#{t.number ?? t.id} {t.title}</option>)}
              </select>
              <button
                onClick={handleAddDep}
                className="rounded-lg bg-slate-700 hover:bg-indigo-600 px-3 py-1.5 text-sm text-white transition"
              >
                <Plus className="h-4 w-4" />
              </button>
            </div>
            {depError && <p className="text-xs text-red-400 mt-1">{depError}</p>}
          </div>
        </div>

        {/* Footer (edit mode) */}
        {editing && (
          <div className="px-5 py-4 border-t border-slate-700 flex gap-3">
            <button
              onClick={() => { setEditing(false); setForm({ ...task }); }}
              className="flex-1 rounded-lg border border-slate-600 py-2 text-sm text-slate-300 hover:border-slate-400 transition"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={updateMut.isPending}
              className="flex-1 flex items-center justify-center gap-2 rounded-lg bg-indigo-600 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-60 transition"
            >
              {updateMut.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Save
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
