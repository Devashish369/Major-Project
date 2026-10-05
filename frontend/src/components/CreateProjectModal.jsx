/**
 * components/CreateProjectModal.jsx – Modal for creating a new project.
 */
import { useState } from 'react';
import { X, Loader2, FolderPlus } from 'lucide-react';

export default function CreateProjectModal({ onClose, onSubmit, loading, error }) {
  const [form, setForm] = useState({
    title: '', description: '', status: 'pending',
    priority: 'medium', start_date: '', due_date: '',
  });

  function handleChange(e) {
    setForm((p) => ({ ...p, [e.target.name]: e.target.value }));
  }

  function handleSubmit(e) {
    e.preventDefault();
    // Strip empty optional strings to avoid sending ""
    const body = { ...form };
    if (!body.description) delete body.description;
    if (!body.start_date) delete body.start_date;
    if (!body.due_date) delete body.due_date;
    onSubmit(body);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-2xl border border-slate-700 bg-slate-800 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700">
          <div className="flex items-center gap-2.5">
            <FolderPlus className="h-5 w-5 text-indigo-400" />
            <h2 className="text-base font-semibold text-white">New Project</h2>
          </div>
          <button
            id="modal-close-btn"
            onClick={onClose}
            className="text-slate-400 hover:text-white transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          {error && (
            <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-4 py-2.5 text-sm text-red-400">
              {error}
            </div>
          )}

          {/* Title */}
          <div>
            <label htmlFor="proj-title" className="block text-sm font-medium text-slate-300 mb-1.5">
              Project title *
            </label>
            <input
              id="proj-title"
              name="title"
              required
              value={form.title}
              onChange={handleChange}
              placeholder="e.g. Hospital Management System"
              className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3.5 py-2.5 text-sm text-white placeholder-slate-500 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition"
            />
          </div>

          {/* Description */}
          <div>
            <label htmlFor="proj-desc" className="block text-sm font-medium text-slate-300 mb-1.5">
              Description
            </label>
            <textarea
              id="proj-desc"
              name="description"
              rows={3}
              value={form.description}
              onChange={handleChange}
              placeholder="What is this project about?"
              className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3.5 py-2.5 text-sm text-white placeholder-slate-500 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition resize-none"
            />
          </div>

          {/* Status + Priority row */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="proj-status" className="block text-sm font-medium text-slate-300 mb-1.5">
                Status
              </label>
              <select
                id="proj-status"
                name="status"
                value={form.status}
                onChange={handleChange}
                className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2.5 text-sm text-white outline-none focus:border-indigo-500 transition"
              >
                <option value="pending">Pending</option>
                <option value="in_progress">In Progress</option>
                <option value="completed">Completed</option>
              </select>
            </div>
            <div>
              <label htmlFor="proj-priority" className="block text-sm font-medium text-slate-300 mb-1.5">
                Priority
              </label>
              <select
                id="proj-priority"
                name="priority"
                value={form.priority}
                onChange={handleChange}
                className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2.5 text-sm text-white outline-none focus:border-indigo-500 transition"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </div>
          </div>

          {/* Dates */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="proj-start" className="block text-sm font-medium text-slate-300 mb-1.5">
                Start date
              </label>
              <input
                id="proj-start"
                name="start_date"
                type="date"
                value={form.start_date}
                onChange={handleChange}
                className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2.5 text-sm text-white outline-none focus:border-indigo-500 transition"
              />
            </div>
            <div>
              <label htmlFor="proj-due" className="block text-sm font-medium text-slate-300 mb-1.5">
                Due date
              </label>
              <input
                id="proj-due"
                name="due_date"
                type="date"
                value={form.due_date}
                onChange={handleChange}
                className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2.5 text-sm text-white outline-none focus:border-indigo-500 transition"
              />
            </div>
          </div>

          {/* Footer */}
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg border border-slate-600 text-sm text-slate-300 hover:border-slate-400 hover:text-white transition"
            >
              Cancel
            </button>
            <button
              id="create-project-submit"
              type="submit"
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-60 transition"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FolderPlus className="h-4 w-4" />}
              {loading ? 'Creating…' : 'Create project'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
