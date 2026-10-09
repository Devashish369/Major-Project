/**
 * components/CreateTaskModal.jsx – Modal to create a new task.
 * Pre-fills status from the column the "+" was clicked in.
 */
import { useState } from 'react';
import { X, Plus, Loader2 } from 'lucide-react';
import { useMutation, useQueryClient, useQuery } from '@tanstack/react-query';
import { createTask, listTasks } from '../api/tasks';
import { listMembers } from '../api/projects';
import { errorMessage } from '../api/errors';

export default function CreateTaskModal({ projectId, defaultStatus = 'todo', onClose }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    title: '', description: '', status: defaultStatus,
    priority: 'medium', estimate_hours: '', due_date: '',
    assignee_id: '', required_skills_str: '',
  });
  const [error, setError] = useState('');

  const { data: members = [] } = useQuery({
    queryKey: ['members', projectId],
    queryFn: () => listMembers(projectId),
  });

  // Existing tasks (cached from the Board) – used to warn about accidental duplicates
  const { data: existing = [] } = useQuery({ queryKey: ['tasks', projectId], queryFn: () => listTasks(projectId) });
  const typed = form.title.trim().toLowerCase();
  const duplicate = typed ? existing.find((t) => t.title.trim().toLowerCase() === typed) : null;
  const STATUS_TEXT = { todo: 'To Do', in_progress: 'In Progress', done: 'Done' };

  const mut = useMutation({
    mutationFn: (data) => createTask(projectId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks', projectId] });
      qc.invalidateQueries({ queryKey: ['project', projectId] });
      onClose();
    },
    onError: (e) => setError(errorMessage(e, 'Failed to create task.')),
  });

  function handleChange(e) {
    setForm((p) => ({ ...p, [e.target.name]: e.target.value }));
  }

  function handleSubmit(e) {
    e.preventDefault();
    setError('');
    const skills = form.required_skills_str
      .split(',').map((s) => s.trim().toLowerCase()).filter(Boolean);
    mut.mutate({
      title: form.title,
      description: form.description || undefined,
      status: form.status,
      priority: form.priority,
      estimate_hours: form.estimate_hours ? Number(form.estimate_hours) : undefined,
      due_date: form.due_date || undefined,
      assignee_id: form.assignee_id ? Number(form.assignee_id) : undefined,
      required_skills: skills.length ? skills : undefined,
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-2xl border border-slate-700 bg-slate-800 shadow-2xl">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700">
          <div className="flex items-center gap-2.5">
            <Plus className="h-5 w-5 text-indigo-400" />
            <h2 className="text-base font-semibold text-white">New Task <span className="font-normal text-slate-400">in {STATUS_TEXT[form.status] ?? 'To Do'}</span></h2>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          {error && (
            <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-4 py-2.5 text-sm text-red-400">{error}</div>
          )}

          {/* Title */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1.5">Title *</label>
            <input
              id="task-title"
              name="title"
              required
              value={form.title}
              onChange={handleChange}
              placeholder="e.g. Design user login screen"
              className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3.5 py-2.5 text-sm text-white placeholder-slate-500 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition"
            />
            {duplicate && (
              <p id="duplicate-warning" className="mt-1.5 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
                A task called “{duplicate.title}” already exists (#{duplicate.id}, {STATUS_TEXT[duplicate.status]}).
                To change its progress, drag it to another column or open it and use the status buttons – no need to add it again.
              </p>
            )}
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1.5">Description</label>
            <textarea
              name="description"
              rows={2}
              value={form.description}
              onChange={handleChange}
              className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3.5 py-2.5 text-sm text-white placeholder-slate-500 outline-none focus:border-indigo-500 transition resize-none"
            />
          </div>

          {/* Status + Priority */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">Status</label>
              <select name="status" value={form.status} onChange={handleChange}
                className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2.5 text-sm text-white outline-none focus:border-indigo-500 transition">
                <option value="todo">To Do</option>
                <option value="in_progress">In Progress</option>
                <option value="done">Done</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">Priority</label>
              <select name="priority" value={form.priority} onChange={handleChange}
                className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2.5 text-sm text-white outline-none focus:border-indigo-500 transition">
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>
          </div>

          {/* Estimate + Due date */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">Est. hours</label>
              <input type="number" min={0} step={0.5} name="estimate_hours"
                value={form.estimate_hours} onChange={handleChange}
                className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3.5 py-2.5 text-sm text-white outline-none focus:border-indigo-500 transition"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1.5">Due date</label>
              <input type="date" name="due_date"
                value={form.due_date} onChange={handleChange}
                className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2.5 text-sm text-white outline-none focus:border-indigo-500 transition"
              />
            </div>
          </div>

          {/* Assignee */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1.5">Assignee</label>
            <select name="assignee_id" value={form.assignee_id} onChange={handleChange}
              className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2.5 text-sm text-white outline-none focus:border-indigo-500 transition">
              <option value="">Unassigned</option>
              {members.map((m) => (
                <option key={m.user_id} value={m.user_id}>{m.full_name}</option>
              ))}
            </select>
          </div>

          {/* Required skills */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1.5">
              Required skills <span className="text-slate-500 font-normal">(comma separated)</span>
            </label>
            <input name="required_skills_str" value={form.required_skills_str} onChange={handleChange}
              placeholder="e.g. react, python, sql"
              className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3.5 py-2.5 text-sm text-white placeholder-slate-500 outline-none focus:border-indigo-500 transition"
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose}
              className="px-4 py-2 rounded-lg border border-slate-600 text-sm text-slate-300 hover:border-slate-400 hover:text-white transition">
              Cancel
            </button>
            <button id="create-task-submit" type="submit" disabled={mut.isPending}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-60 transition">
              {mut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              {mut.isPending ? 'Creating…' : 'Create task'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
