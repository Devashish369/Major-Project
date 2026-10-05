/**
 * components/PlanTab.jsx – AI Project Planner tab (M4).
 *
 * UI flow:
 *   1. User enters a description, team size, duration.
 *   2. Click "Generate Plan" → calls POST /ai/generate-plan.
 *   3. Draft plan is shown: AI/Cached label, sprints, task cards.
 *   4. Admin clicks "Apply to Project" → calls POST /projects/{id}/apply-plan.
 *
 * Spec §8.1: source "llm" → green "AI Generated" badge,
 *             source "fallback" → amber "Cached Plan" badge.
 */
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Sparkles, Loader2, ChevronRight, CheckCircle2, AlertTriangle,
  Cpu, Archive, Play,
} from 'lucide-react';
import { generatePlan, applyPlan } from '../api/ai';

const PRIORITY_COLORS = {
  low: 'text-slate-400', medium: 'text-amber-400',
  high: 'text-orange-400', critical: 'text-red-400',
};

// ── Source badge ──────────────────────────────────────────────────────────────
function SourceBadge({ source }) {
  if (source === 'llm') {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-green-500/15 border border-green-500/30 text-green-400 font-medium">
        <Cpu className="h-3 w-3" />
        AI Generated
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-400 font-medium">
      <Archive className="h-3 w-3" />
      Cached Plan
    </span>
  );
}

// ── Plan preview ──────────────────────────────────────────────────────────────
function PlanPreview({ plan }) {
  const [openSprint, setOpenSprint] = useState(null);

  const tasksBySprint = (idx) =>
    (plan.tasks || []).filter((t) => t.sprint_index === idx);

  return (
    <div className="space-y-3">
      {/* Project title */}
      <div className="rounded-xl border border-slate-700 bg-slate-800 p-4">
        <p className="text-xs text-slate-400 mb-1">Project title</p>
        <p className="text-base font-semibold text-white">{plan.project_title}</p>
        {plan.summary && <p className="text-sm text-slate-400 mt-1">{plan.summary}</p>}
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-3 gap-3">
        {[
          ['Sprints', (plan.sprints || []).length],
          ['Tasks', (plan.tasks || []).length],
          ['Est. hours', (plan.tasks || []).reduce((s, t) => s + (t.estimate_hours || 0), 0)],
        ].map(([label, val]) => (
          <div key={label} className="rounded-lg border border-slate-700 bg-slate-800 p-3 text-center">
            <p className="text-2xl font-bold text-white">{val}</p>
            <p className="text-xs text-slate-400 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      {/* Sprints accordion */}
      {(plan.sprints || []).map((sprint, idx) => {
        const sprintTasks = tasksBySprint(idx);
        const isOpen = openSprint === idx;
        return (
          <div key={idx} className="rounded-xl border border-slate-700 bg-slate-800 overflow-hidden">
            <button
              onClick={() => setOpenSprint(isOpen ? null : idx)}
              className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-700/50 transition"
            >
              <div className="flex items-center gap-3">
                <span className="text-xs font-mono text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded">
                  S{idx + 1}
                </span>
                <div className="text-left">
                  <p className="text-sm font-medium text-white">{sprint.name}</p>
                  {sprint.goal && <p className="text-xs text-slate-500">{sprint.goal}</p>}
                </div>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <span>{sprintTasks.length} tasks</span>
                <ChevronRight className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-90' : ''}`} />
              </div>
            </button>

            {isOpen && (
              <div className="border-t border-slate-700 divide-y divide-slate-700/50">
                {sprintTasks.map((task, ti) => (
                  <div key={ti} className="px-4 py-3 hover:bg-slate-700/30 transition">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <p className="text-sm font-medium text-white truncate">{task.title}</p>
                          <span className={`text-xs font-medium ${PRIORITY_COLORS[task.priority] || ''}`}>
                            {task.priority}
                          </span>
                        </div>
                        {task.description && (
                          <p className="text-xs text-slate-400 line-clamp-2">{task.description}</p>
                        )}
                        {(task.required_skills || []).length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1.5">
                            {task.required_skills.map((s) => (
                              <span key={s} className="text-xs px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-300">
                                {s}
                              </span>
                            ))}
                          </div>
                        )}
                        {(task.depends_on || []).length > 0 && (
                          <p className="text-xs text-slate-500 mt-1">
                            ↳ needs: {task.depends_on.join(', ')}
                          </p>
                        )}
                      </div>
                      <span className="shrink-0 text-xs text-slate-400 font-mono mt-0.5">
                        {task.estimate_hours}h
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Plan Tab ──────────────────────────────────────────────────────────────────
export default function PlanTab({ projectId, isAdmin }) {
  const qc = useQueryClient();
  const [description, setDescription] = useState('');
  const [teamSize, setTeamSize] = useState(3);
  const [durationWeeks, setDurationWeeks] = useState(8);
  const [draft, setDraft] = useState(null);   // {plan, source}
  const [applyError, setApplyError] = useState('');
  const [applied, setApplied] = useState(false);

  const generateMut = useMutation({
    mutationFn: () => generatePlan(description, teamSize, durationWeeks),
    onSuccess: (result) => {
      setDraft(result);
      setApplied(false);
      setApplyError('');
    },
  });

  const applyMut = useMutation({
    mutationFn: () => applyPlan(projectId, draft.plan, draft.source),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks', projectId] });
      qc.invalidateQueries({ queryKey: ['project', projectId] });
      setApplied(true);
      setApplyError('');
    },
    onError: (e) => setApplyError(e.response?.data?.detail || 'Failed to apply plan.'),
  });

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Input form */}
      <div className="rounded-2xl border border-slate-700 bg-slate-800 p-6">
        <div className="flex items-center gap-3 mb-5">
          <div className="p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/20">
            <Sparkles className="h-5 w-5 text-indigo-400" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-white">AI Project Planner</h2>
            <p className="text-xs text-slate-400">Describe your project and get a sprint plan instantly</p>
          </div>
        </div>

        {/* Description */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-slate-300 mb-1.5">
            Project description *
          </label>
          <textarea
            id="plan-description"
            rows={4}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="e.g. Build a hospital management system with patient registration, appointment scheduling, billing, pharmacy, and lab modules..."
            className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3.5 py-2.5 text-sm text-white placeholder-slate-500 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition resize-none"
          />
        </div>

        {/* Team size + duration */}
        <div className="grid grid-cols-2 gap-3 mb-5">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1.5">Team size</label>
            <input
              id="plan-team-size"
              type="number" min={1} max={50}
              value={teamSize}
              onChange={(e) => setTeamSize(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3.5 py-2.5 text-sm text-white outline-none focus:border-indigo-500 transition"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1.5">Duration (weeks)</label>
            <input
              id="plan-duration"
              type="number" min={1} max={104}
              value={durationWeeks}
              onChange={(e) => setDurationWeeks(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3.5 py-2.5 text-sm text-white outline-none focus:border-indigo-500 transition"
            />
          </div>
        </div>

        <button
          id="generate-plan-btn"
          onClick={() => generateMut.mutate()}
          disabled={generateMut.isPending || description.trim().length < 10}
          className="w-full flex items-center justify-center gap-2 rounded-xl bg-indigo-600 py-2.5 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50 transition"
        >
          {generateMut.isPending
            ? <><Loader2 className="h-4 w-4 animate-spin" />Generating plan…</>
            : <><Sparkles className="h-4 w-4" />Generate Plan</>
          }
        </button>

        {generateMut.isError && (
          <div className="mt-3 rounded-lg bg-red-500/10 border border-red-500/30 px-4 py-2.5 text-sm text-red-400">
            {generateMut.error?.response?.data?.detail || 'Failed to generate plan. Check your API key.'}
          </div>
        )}
      </div>

      {/* Draft preview */}
      {draft && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <h3 className="text-sm font-semibold text-white">Plan Draft</h3>
              <SourceBadge source={draft.source} />
            </div>
            {isAdmin && !applied && (
              <button
                id="apply-plan-btn"
                onClick={() => applyMut.mutate()}
                disabled={applyMut.isPending}
                className="flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white hover:bg-green-500 disabled:opacity-60 transition"
              >
                {applyMut.isPending
                  ? <Loader2 className="h-4 w-4 animate-spin" />
                  : <Play className="h-4 w-4" />
                }
                Apply to Project
              </button>
            )}
            {applied && (
              <span className="flex items-center gap-2 text-sm text-green-400 font-medium">
                <CheckCircle2 className="h-4 w-4" />
                Applied! Check the Board tab.
              </span>
            )}
          </div>

          {applyError && (
            <div className="mb-3 rounded-lg bg-red-500/10 border border-red-500/30 px-4 py-2.5 text-sm text-red-400 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              {applyError}
            </div>
          )}

          <PlanPreview plan={draft.plan} />
        </div>
      )}
    </div>
  );
}
