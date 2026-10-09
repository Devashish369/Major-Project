/**
 * components/AddMemberModal.jsx – Modal to add a member by email.
 */
import { useState } from 'react';
import { X, UserPlus, Loader2 } from 'lucide-react';

export default function AddMemberModal({ onClose, onSubmit, loading, error }) {
  const [form, setForm] = useState({ email: '', role: 'member', capacity_hours_per_week: 30 });

  function handleChange(e) {
    setForm((p) => ({ ...p, [e.target.name]: e.target.value }));
  }

  function handleSubmit(e) {
    e.preventDefault();
    onSubmit({ ...form, capacity_hours_per_week: Number(form.capacity_hours_per_week) });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-800 shadow-2xl">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700">
          <div className="flex items-center gap-2.5">
            <UserPlus className="h-5 w-5 text-indigo-400" />
            <h2 className="text-base font-semibold text-white">Add Team Member</h2>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          {error && (
            <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-4 py-2.5 text-sm text-red-400">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="member-email" className="block text-sm font-medium text-slate-300 mb-1.5">
              Email address
            </label>
            <input
              id="member-email"
              name="email"
              type="email"
              required
              value={form.email}
              onChange={handleChange}
              placeholder="colleague@example.com"
              className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3.5 py-2.5 text-sm text-white placeholder-slate-500 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition"
            />
            <p className="mt-1.5 text-xs text-slate-500">
              The person must already have an IntelliPM account (they sign up first). Once added, this project appears on their dashboard
              and they can be assigned tasks.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="member-role" className="block text-sm font-medium text-slate-300 mb-1.5">Role</label>
              <select
                id="member-role"
                name="role"
                value={form.role}
                onChange={handleChange}
                className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2.5 text-sm text-white outline-none focus:border-indigo-500 transition"
              >
                <option value="member">Member</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <div>
              <label htmlFor="member-capacity" className="block text-sm font-medium text-slate-300 mb-1.5">
                Hours / week
              </label>
              <input
                id="member-capacity"
                name="capacity_hours_per_week"
                type="number"
                min={1}
                max={168}
                value={form.capacity_hours_per_week}
                onChange={handleChange}
                className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3.5 py-2.5 text-sm text-white outline-none focus:border-indigo-500 transition"
              />
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg border border-slate-600 text-sm text-slate-300 hover:border-slate-400 hover:text-white transition"
            >
              Cancel
            </button>
            <button
              id="add-member-submit"
              type="submit"
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-60 transition"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />}
              {loading ? 'Adding…' : 'Add member'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
