/**
 * pages/ProjectPage.jsx – Project detail page with tabbed interface.
 *
 * M2 added: Overview tab + Team tab.
 * M3 added: Board tab (Kanban drag-and-drop with @dnd-kit).
 * M4 added: Plan tab (AI planner + apply-plan).
 * M5 added: Workload bars + Recommend Assignments panel in Team tab.
 */
import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft, BarChart2, Users, Loader2, UserPlus, Trash2,
  Shield, User, AlertCircle, LayoutDashboard,
  Sparkles, CheckCircle2,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { getProject, listMembers, addMember, updateMember, removeMember, deleteProject } from '../api/projects';
import { listTasks } from '../api/tasks';
import { recommendAssignments, applyAssignments, getWorkload } from '../api/assignments';
import AddMemberModal from '../components/AddMemberModal';
import KanbanBoard from '../components/KanbanBoard';
import PlanTab from '../components/PlanTab';
import AnalyticsTab from '../components/AnalyticsTab';
import GraphTab from '../components/GraphTab';
import DecisionsTab from '../components/DecisionsTab';
import ReportTab from '../components/ReportTab';
import useProjectSocket from '../hooks/useProjectSocket';

// ── Small reusable bits ───────────────────────────────────────────────────────

const SKILL_BAR = ['', 'bg-sky-600', 'bg-sky-500', 'bg-amber-500', 'bg-indigo-500', 'bg-green-500'];

function SkillPill({ skill, level }) {
  return (
    <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full text-white ${SKILL_BAR[level] || 'bg-slate-600'}`}>
      {skill} <span className="opacity-70">L{level}</span>
    </span>
  );
}

function RoleBadge({ role }) {
  return (
    <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${
      role === 'admin' ? 'bg-indigo-500/20 text-indigo-300' : 'bg-slate-700 text-slate-300'
    }`}>
      {role === 'admin' ? <Shield className="h-3 w-3" /> : <User className="h-3 w-3" />}
      {role}
    </span>
  );
}

// ── Workload label config ─────────────────────────────────────────────────────

const WORKLOAD_CONFIG = {
  overloaded: { bar: 'bg-red-500',    badge: 'text-red-400 bg-red-500/10 border-red-500/30',    text: 'Overloaded' },
  at_risk:    { bar: 'bg-amber-500',  badge: 'text-amber-400 bg-amber-500/10 border-amber-500/30', text: 'At risk' },
  healthy:    { bar: 'bg-green-500',  badge: 'text-green-400 bg-green-500/10 border-green-500/30', text: 'Healthy' },
  available:  { bar: 'bg-slate-500',  badge: 'text-slate-400 bg-slate-500/10 border-slate-500/30', text: 'Available' },
};

function WorkloadBar({ utilization, label }) {
  const cfg = WORKLOAD_CONFIG[label] || WORKLOAD_CONFIG.available;
  const realPct = Math.round(utilization * 100);   // shown as-is, e.g. 194%
  const pct = Math.min(100, realPct);                // bar width only
  return (
    <div className="mt-3">
      <div className="flex justify-between items-center mb-1">
        <span className="text-xs text-slate-400">Workload</span>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-300">{realPct}%</span>
          <span className={`text-xs px-1.5 py-0.5 rounded border ${cfg.badge} font-medium`}>
            {cfg.text}
          </span>
        </div>
      </div>
      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${cfg.bar}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

// ── Recommendation panel ──────────────────────────────────────────────────────

function RecommendPanel({ projectId, members, isAdmin }) {
  const qc = useQueryClient();
  const [draft, setDraft] = useState(null);      // [{task_id, user_id, ...}]
  const [applied, setApplied] = useState(false);
  const [showPanel, setShowPanel] = useState(false);
  const [applyErr, setApplyErr] = useState('');

  // Map user_id → full_name for display
  const nameMap = Object.fromEntries(members.map((m) => [m.user_id, m.full_name]));

  const recommendMut = useMutation({
    mutationFn: () => recommendAssignments(projectId),
    onSuccess: (data) => {
      setDraft(data);
      setApplied(false);
      setApplyErr('');
      setShowPanel(true);
    },
  });

  const applyMut = useMutation({
    mutationFn: () => applyAssignments(projectId, draft.map((r) => ({ task_id: r.task_id, user_id: r.user_id }))),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks', projectId] });
      qc.invalidateQueries({ queryKey: ['workload', projectId] });
      setApplied(true);
      setApplyErr('');
    },
    onError: (e) => setApplyErr(e.response?.data?.detail || 'Failed to apply.'),
  });

  return (
    <div className="mt-6 rounded-2xl border border-slate-700 bg-slate-800 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/20">
            <Sparkles className="h-4 w-4 text-indigo-400" />
          </div>
          <div>
            <p className="text-sm font-semibold text-white">AI Assignment Recommendations</p>
            <p className="text-xs text-slate-400">Optimised by skill match, availability & on-time rate</p>
          </div>
        </div>
        <button
          id="recommend-btn"
          onClick={() => recommendMut.mutate()}
          disabled={recommendMut.isPending}
          className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-60 transition"
        >
          {recommendMut.isPending
            ? <Loader2 className="h-4 w-4 animate-spin" />
            : <Sparkles className="h-4 w-4" />
          }
          Recommend assignments
        </button>
      </div>

      {/* Results table */}
      {showPanel && draft !== null && (
        <div className="border-t border-slate-700">
          {draft.length === 0 ? (
            <p className="text-sm text-slate-400 text-center py-6">No unassigned open tasks found.</p>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-700 text-xs text-slate-400">
                      <th className="px-4 py-2.5 text-left">Task ID</th>
                      <th className="px-4 py-2.5 text-left">Suggested Assignee</th>
                      <th className="px-4 py-2.5 text-right">Skill</th>
                      <th className="px-4 py-2.5 text-right">Avail</th>
                      <th className="px-4 py-2.5 text-right">Perf</th>
                      <th className="px-4 py-2.5 text-right">Score</th>
                      <th className="px-4 py-2.5 text-left">Reason</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-700/50">
                    {draft.map((row) => (
                      <tr key={row.task_id} className="hover:bg-slate-700/30 transition">
                        <td className="px-4 py-2.5 text-slate-300 font-mono text-xs">#{row.task_id}</td>
                        <td className="px-4 py-2.5 text-white font-medium">{nameMap[row.user_id] || row.user_id}</td>
                        <td className="px-4 py-2.5 text-right text-slate-300">{(row.skill_match * 100).toFixed(0)}%</td>
                        <td className="px-4 py-2.5 text-right text-slate-300">{(row.availability * 100).toFixed(0)}%</td>
                        <td className="px-4 py-2.5 text-right text-slate-300">{(row.performance * 100).toFixed(0)}%</td>
                        <td className="px-4 py-2.5 text-right">
                          <span className="font-semibold text-indigo-300">{row.score.toFixed(2)}</span>
                        </td>
                        <td className="px-4 py-2.5 text-slate-400 text-xs max-w-xs">{row.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {applyErr && (
                <div className="mx-4 mb-3 rounded-lg bg-red-500/10 border border-red-500/30 px-3 py-2 text-sm text-red-400">
                  {applyErr}
                </div>
              )}

              <div className="flex items-center justify-between px-4 py-3 border-t border-slate-700">
                <p className="text-xs text-slate-400">{draft.length} recommendation(s)</p>
                {isAdmin && !applied && (
                  <button
                    id="apply-assignments-btn"
                    onClick={() => applyMut.mutate()}
                    disabled={applyMut.isPending}
                    className="flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-500 disabled:opacity-60 transition"
                  >
                    {applyMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                    Apply assignments
                  </button>
                )}
                {applied && (
                  <span className="flex items-center gap-2 text-sm text-green-400 font-medium">
                    <CheckCircle2 className="h-4 w-4" /> Applied! Check the Board.
                  </span>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ── Team Tab ─────────────────────────────────────────────────────────────────

function TeamTab({ projectId, isAdmin, currentUserId }) {
  const qc = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);

  const { data: members = [], isLoading } = useQuery({
    queryKey: ['members', projectId],
    queryFn: () => listMembers(projectId),
  });

  // Workload data (M5)
  const { data: workload = [] } = useQuery({
    queryKey: ['workload', projectId],
    queryFn: () => getWorkload(projectId),
  });
  const workloadMap = Object.fromEntries(workload.map((w) => [w.user_id, w]));

  const addMut = useMutation({
    mutationFn: (data) => addMember(projectId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['members', projectId] });
      qc.invalidateQueries({ queryKey: ['project', projectId] });
      setShowAdd(false);
    },
  });

  const capacityMut = useMutation({
    mutationFn: ({ userId, capacity }) => updateMember(projectId, userId, { capacity_hours_per_week: capacity }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['members', projectId] });
      qc.invalidateQueries({ queryKey: ['workload', projectId] });
    },
  });

  const removeMut = useMutation({
    mutationFn: (userId) => removeMember(projectId, userId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['members', projectId] });
      qc.invalidateQueries({ queryKey: ['project', projectId] });
      qc.invalidateQueries({ queryKey: ['workload', projectId] });
    },
  });

  if (isLoading) {
    return <div className="flex justify-center py-10"><Loader2 className="h-6 w-6 animate-spin text-indigo-400" /></div>;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-base font-semibold text-white">Team Members ({members.length})</h2>
        {isAdmin && (
          <button
            id="add-member-btn"
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 transition"
          >
            <UserPlus className="h-4 w-4" />
            Add member
          </button>
        )}
      </div>

      <div className="space-y-3">
        {members.map((m) => {
          const wl = workloadMap[m.user_id];
          return (
            <div key={m.user_id} className="rounded-xl border border-slate-700 bg-slate-800 p-4">
              <div className="flex items-start justify-between gap-4">
                {/* Left: name + role */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <p className="font-medium text-white truncate">{m.full_name}</p>
                    <RoleBadge role={m.role} />
                  </div>
                  <p className="text-xs text-slate-400">@{m.username} · {m.email}</p>
                </div>

                {/* Right: capacity + remove */}
                <div className="flex items-center gap-3 shrink-0">
                  <div className="text-right">
                    <p className="text-xs text-slate-400 mb-0.5">Capacity / week</p>
                    {isAdmin ? (
                      <input
                        type="number"
                        min={1}
                        max={168}
                        defaultValue={m.capacity_hours_per_week}
                        onBlur={(e) => {
                          const val = parseInt(e.target.value, 10);
                          if (val !== m.capacity_hours_per_week && val >= 1 && val <= 168) {
                            capacityMut.mutate({ userId: m.user_id, capacity: val });
                          }
                        }}
                        className="w-16 rounded border border-slate-600 bg-slate-900 text-center text-sm text-white py-1 outline-none focus:border-indigo-500"
                      />
                    ) : (
                      <span className="text-sm text-white">{m.capacity_hours_per_week}h</span>
                    )}
                  </div>
                  {isAdmin && m.user_id !== currentUserId && (
                    <button
                      onClick={() => removeMut.mutate(m.user_id)}
                      disabled={removeMut.isPending}
                      className="text-slate-500 hover:text-red-400 transition"
                      aria-label={`Remove ${m.full_name}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>

              {/* Skills */}
              {m.skills && Object.keys(m.skills).length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {Object.entries(m.skills).map(([skill, level]) => (
                    <SkillPill key={skill} skill={skill} level={level} />
                  ))}
                </div>
              )}

              {/* On-time rate + Workload bar (M5) */}
              <div className="mt-3 grid grid-cols-2 gap-3">
                <div>
                  <div className="flex justify-between text-xs text-slate-400 mb-1">
                    <span>On-time rate</span>
                    <span>{Math.round(m.on_time_rate * 100)}%</span>
                  </div>
                  <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                    <div className="h-full bg-indigo-500 rounded-full" style={{ width: `${m.on_time_rate * 100}%` }} />
                  </div>
                </div>
                <div>
                  {wl
                    ? <WorkloadBar utilization={wl.utilization} label={wl.label} />
                    : <div className="mt-3 text-xs text-slate-500">Workload loading…</div>
                  }
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Recommendation panel (M5) */}
      <RecommendPanel projectId={projectId} members={members} isAdmin={isAdmin} />

      {showAdd && (
        <AddMemberModal
          onClose={() => setShowAdd(false)}
          onSubmit={(data) => addMut.mutate(data)}
          loading={addMut.isPending}
          error={addMut.error?.response?.data?.detail || addMut.error?.message}
        />
      )}
    </div>
  );
}

// ── Overview Tab ──────────────────────────────────────────────────────────────

function OverviewTab({ project }) {
  const STATUS_COLOR = {
    pending: 'text-slate-400',
    in_progress: 'text-blue-400',
    completed: 'text-green-400',
  };
  const PRIORITY_COLOR = {
    low: 'text-slate-400', medium: 'text-amber-400', high: 'text-red-400'
  };

  return (
    <div className="grid grid-cols-2 gap-4">
      {[
        ['Status', <span key="status" className={STATUS_COLOR[project.status]}>{project.status.replace('_', ' ')}</span>],
        ['Priority', <span key="priority" className={PRIORITY_COLOR[project.priority]}>{project.priority}</span>],
        ['Start date', project.start_date || '—'],
        ['Due date', project.due_date || '—'],
        ['Members', project.member_count],
        ['Tasks', project.task_count],
        ['Done', `${Math.round((project.done_ratio || 0) * 100)}%`],
        ['Health', project.health_score != null ? Math.round(project.health_score) : '—'],
      ].map(([label, value]) => (
        <div key={label} className="rounded-lg border border-slate-700 bg-slate-800 p-4">
          <p className="text-xs text-slate-400 mb-1">{label}</p>
          <p className="text-sm font-medium text-white">{value}</p>
        </div>
      ))}

      {project.description && (
        <div className="col-span-2 rounded-lg border border-slate-700 bg-slate-800 p-4">
          <p className="text-xs text-slate-400 mb-1">Description</p>
          <p className="text-sm text-white whitespace-pre-wrap">{project.description}</p>
        </div>
      )}
    </div>
  );
}

// ── Live-updates badge (M13) ──────────────────────────────────────────────────
const LIVE_STYLE = {
  live:         ['bg-green-400',  'text-green-400',  'Live'],
  connecting:   ['bg-amber-400',  'text-amber-400',  'Connecting…'],
  reconnecting: ['bg-amber-400',  'text-amber-400',  'Reconnecting…'],
  offline:      ['bg-slate-500',  'text-slate-400',  "Offline – refresh to see others' changes"],
};

function LiveBadge({ status }) {
  const style = LIVE_STYLE[status];
  if (!style) return null;
  return (
    <span id="live-badge" data-status={status} className={`ml-auto self-center flex items-center gap-1.5 text-xs ${style[1]}`}>
      <span className={`h-2 w-2 rounded-full ${style[0]} ${status === 'live' ? '' : 'animate-pulse'}`} />
      {style[2]}
    </span>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

const TABS = ['Overview', 'Board', 'Plan', 'Team', 'Analytics', 'Graph', 'Decisions', 'Report'];

export default function ProjectPage() {
  const { id } = useParams();
  const projectId = parseInt(id, 10);
  const navigate = useNavigate();
  const { user } = useAuth();
  const qc = useQueryClient();
  const [tab, setTab] = useState('Board');
  // Live updates only while a tab that shows tasks is open (spec: connect when the Board opens)
  const liveStatus = useProjectSocket(projectId, tab === 'Board' || tab === 'Graph');

  const { data: project, isLoading, error } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
  });

  const { data: members = [] } = useQuery({
    queryKey: ['members', projectId],
    queryFn: () => listMembers(projectId),
    enabled: !!project,
  });

  const { data: tasks = [] } = useQuery({
    queryKey: ['tasks', projectId],
    queryFn: () => listTasks(projectId),
    enabled: !!project,
  });

  const deleteMut = useMutation({
    mutationFn: () => deleteProject(projectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] });
      navigate('/dashboard');
    },
  });

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="h-10 w-10 text-red-400 mx-auto mb-3" />
          <p className="text-white font-semibold">Project not found</p>
          <button onClick={() => navigate('/dashboard')} className="mt-4 text-indigo-400 text-sm hover:underline">
            Back to dashboard
          </button>
        </div>
      </div>
    );
  }

  const myMembership = members.find((m) => m.user_id === user?.id);
  const isAdmin = myMembership?.role === 'admin';

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      {/* Navbar */}
      <header className="sticky top-0 z-30 border-b border-slate-700 bg-slate-900/95 backdrop-blur px-6 py-3 flex items-center gap-4">
        <button onClick={() => navigate('/dashboard')} className="text-slate-400 hover:text-white transition">
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="flex items-center gap-2">
          <BarChart2 className="h-5 w-5 text-indigo-400" />
          <span className="font-semibold text-white truncate">{project?.title}</span>
        </div>
        {isAdmin && (
          <button
            id="delete-project-btn"
            onClick={() => { if (window.confirm('Delete this project?')) deleteMut.mutate(); }}
            className="ml-auto flex items-center gap-1.5 text-sm text-red-400 hover:text-red-300 border border-red-500/30 hover:border-red-400/50 px-3 py-1.5 rounded-lg transition"
          >
            <Trash2 className="h-4 w-4" />
            Delete project
          </button>
        )}
      </header>

      {/* Tabs */}
      <div className="border-b border-slate-700 px-6">
        <nav className="flex gap-1">
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-3 text-sm font-medium border-b-2 transition ${
                tab === t
                  ? 'border-indigo-500 text-white'
                  : 'border-transparent text-slate-400 hover:text-slate-300'
              }`}
            >
              {t === 'Team' && <Users className="h-3.5 w-3.5 inline mr-1.5" />}
              {t === 'Board' && <LayoutDashboard className="h-3.5 w-3.5 inline mr-1.5" />}
              {t}
            </button>
          ))}
          {(tab === 'Board' || tab === 'Graph') && <LiveBadge status={liveStatus} />}
        </nav>
      </div>

      {/* Content */}
      <main className={`mx-auto px-6 py-6 ${['Board', 'Analytics', 'Graph', 'Report'].includes(tab) ? 'max-w-7xl' : 'max-w-4xl'}`}>
        {tab === 'Overview' && project && <OverviewTab project={project} />}
        {tab === 'Board' && (
          <KanbanBoard tasks={tasks} projectId={projectId} />
        )}
        {tab === 'Plan' && (
          <PlanTab projectId={projectId} isAdmin={isAdmin} />
        )}
        {tab === 'Graph' && <GraphTab tasks={tasks} projectId={projectId} />}
        {tab === 'Report' && <ReportTab projectId={projectId} />}
        {tab === 'Decisions' && (
          <DecisionsTab projectId={projectId} tasks={tasks} isAdmin={isAdmin} currentUserId={user?.id} />
        )}
        {tab === 'Analytics' && <AnalyticsTab projectId={projectId} dueDate={project?.due_date} />}
        {tab === 'Team' && (
          <TeamTab projectId={projectId} isAdmin={isAdmin} currentUserId={user?.id} />
        )}
      </main>
    </div>
  );
}
