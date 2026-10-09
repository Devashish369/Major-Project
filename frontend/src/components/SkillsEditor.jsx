/**
 * components/SkillsEditor.jsx – Slide-out panel to edit the user's skills.
 *
 * Opens from the Dashboard navbar. Calls PATCH /auth/me with the updated
 * skills dict. Skill levels are integers 1–5.
 */
import { useState } from 'react';
import { X, Plus, Trash2, Loader2, Star } from 'lucide-react';
import { useMutation } from '@tanstack/react-query';
import { useAuth } from '../context/AuthContext';
import { errorMessage } from '../api/errors';

export default function SkillsEditor({ onClose }) {
  const { user, updateProfile } = useAuth();
  const [skills, setSkills] = useState(user?.skills ? { ...user.skills } : {});
  const [newSkill, setNewSkill] = useState('');
  const [newLevel, setNewLevel] = useState(3);
  const [error, setError] = useState('');

  const mut = useMutation({
    mutationFn: (skills) => updateProfile({ skills }),
    onSuccess: () => onClose(),
    onError: (e) => setError(errorMessage(e, 'Failed to save skills.')),
  });

  function addSkill() {
    const key = newSkill.trim().toLowerCase();
    if (!key) return;
    if (skills[key] !== undefined) {
      setError(`'${key}' is already in your skills.`);
      return;
    }
    setSkills((p) => ({ ...p, [key]: newLevel }));
    setNewSkill('');
    setNewLevel(3);
    setError('');
  }

  function removeSkill(key) {
    setSkills((p) => {
      const c = { ...p };
      delete c[key];
      return c;
    });
  }

  function updateLevel(key, level) {
    setSkills((p) => ({ ...p, [key]: Number(level) }));
  }

  function handleSave() {
    setError('');
    mut.mutate(skills);
  }

  const LEVEL_LABEL = { 1: 'Beginner', 2: 'Basic', 3: 'Intermediate', 4: 'Advanced', 5: 'Expert' };

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="flex-1 bg-black/50 backdrop-blur-sm" onClick={onClose} />

      {/* Panel */}
      <div className="w-full max-w-sm bg-slate-900 border-l border-slate-700 h-full overflow-y-auto flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700 sticky top-0 bg-slate-900 z-10">
          <h2 className="font-semibold text-white">Profile &amp; Skills</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 px-5 py-4 space-y-6">
          {/* User info */}
          <div className="rounded-lg bg-slate-800 border border-slate-700 p-4 space-y-1 text-sm">
            <p><span className="text-slate-400">Name:</span> <span className="text-white">{user?.full_name}</span></p>
            <p><span className="text-slate-400">Email:</span> <span className="text-white">{user?.email}</span></p>
            <p><span className="text-slate-400">Username:</span> <span className="text-white">@{user?.username}</span></p>
            <p><span className="text-slate-400">On-time rate:</span> <span className="text-white">{(user?.on_time_rate * 100).toFixed(0)}%</span></p>
          </div>

          {/* Skills */}
          <div>
            <h3 className="text-sm font-medium text-slate-300 mb-3 flex items-center gap-2">
              <Star className="h-4 w-4 text-amber-400" />
              Skills (levels 1–5)
            </h3>

            {error && (
              <p className="text-xs text-red-400 mb-3 rounded-lg bg-red-500/10 border border-red-500/20 px-3 py-2">
                {error}
              </p>
            )}

            {/* Existing skills */}
            <div className="space-y-2 mb-4">
              {Object.keys(skills).length === 0 && (
                <p className="text-xs text-slate-500">No skills added yet.</p>
              )}
              {Object.entries(skills).map(([skill, level]) => (
                <div key={skill} className="flex items-center gap-2">
                  <span className="flex-1 text-sm text-white capitalize">{skill}</span>
                  <select
                    value={level}
                    onChange={(e) => updateLevel(skill, e.target.value)}
                    className="rounded border border-slate-600 bg-slate-800 text-sm text-white px-2 py-1 outline-none focus:border-indigo-500"
                  >
                    {[1, 2, 3, 4, 5].map((l) => (
                      <option key={l} value={l}>{l} – {LEVEL_LABEL[l]}</option>
                    ))}
                  </select>
                  <button
                    onClick={() => removeSkill(skill)}
                    className="text-slate-500 hover:text-red-400 transition"
                    aria-label={`Remove ${skill}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>

            {/* Add new skill */}
            <div className="flex gap-2">
              <input
                id="new-skill-name"
                value={newSkill}
                onChange={(e) => setNewSkill(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addSkill())}
                placeholder="e.g. react"
                className="flex-1 rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 outline-none focus:border-indigo-500 transition"
              />
              <select
                value={newLevel}
                onChange={(e) => setNewLevel(Number(e.target.value))}
                className="rounded-lg border border-slate-600 bg-slate-800 text-sm text-white px-2 py-2 outline-none focus:border-indigo-500"
              >
                {[1, 2, 3, 4, 5].map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
              <button
                id="add-skill-btn"
                onClick={addSkill}
                className="rounded-lg bg-indigo-600 px-3 py-2 text-sm text-white hover:bg-indigo-500 transition"
              >
                <Plus className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-slate-700">
          <button
            id="save-skills-btn"
            onClick={handleSave}
            disabled={mut.isPending}
            className="w-full flex items-center justify-center gap-2 rounded-lg bg-indigo-600 py-2.5 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-60 transition"
          >
            {mut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {mut.isPending ? 'Saving…' : 'Save skills'}
          </button>
        </div>
      </div>
    </div>
  );
}
