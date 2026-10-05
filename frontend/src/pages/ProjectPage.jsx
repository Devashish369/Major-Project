/**
 * pages/ProjectPage.jsx – Project detail page with tabbed interface.
 *
 * M2 added: Overview tab + Team tab.
 * M3 added: Board tab (Kanban drag-and-drop with @dnd-kit).
 * M4 added: Plan tab (AI planner + apply-plan).
 * M5+ will add: Analytics, Graph, Decisions tabs.
 */
import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft, BarChart2, Users, Loader2, UserPlus, Trash2,
  Shield, User, Calendar, AlertCircle, LayoutDashboard,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { getProject, listMembers, addMember, updateMember, removeMember, deleteProject } from '../api/projects';
import { listTasks } from '../api/tasks';
import AddMemberModal from '../components/AddMemberModal';
import KanbanBoard from '../components/KanbanBoard';
import PlanTab from '../components/PlanTab';

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

// ── Team Tab ─────────────────────────────────────────────────────────────────

function TeamTab({ projectId, isAdmin, currentUserId }) {
  const qc = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);

  const { data: members = [], isLoading } = useQuery({
    queryKey: ['members', projectId],
    queryFn: () => listMembers(projectId),
  });

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
    onSuccess: () => qc.invalidateQueries({ queryKey: ['members', projectId] }),
  });

  const removeMut = useMutation({
    mutationFn: (userId) => removeMember(projectId, userId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['members', projectId] });
      qc.invalidateQueries({ queryKey: ['project', projectId] });
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
        {members.map((m) => (
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

            {/* Workload bar: capacity shown, M5 will add actual utilization */}
            <div className="mt-3">
              <div className="flex justify-between text-xs text-slate-400 mb-1">
                <span>On-time rate</span>
                <span>{Math.round(m.on_time_rate * 100)}%</span>
              </div>
              <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-indigo-500 rounded-full"
                  style={{ width: `${m.on_time_rate * 100}%` }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>

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
        ['Status', <span className={STATUS_COLOR[project.status]}>{project.status.replace('_', ' ')}</span>],
        ['Priority', <span className={PRIORITY_COLOR[project.priority]}>{project.priority}</span>],
        ['Start date', project.start_date || '—'],
        ['Due date', project.due_date || '—'],
        ['Members', project.member_count],
        ['Tasks', project.task_count],
        ['Done', `${Math.round((project.done_ratio || 0) * 100)}%`],
        ['Health', project.health_score !== null ? Math.round(project.health_score) : 'TBD (M7)'],
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

// ── Page ──────────────────────────────────────────────────────────────────────

const TABS = ['Overview', 'Board', 'Plan', 'Team'];

export default function ProjectPage() {
  const { id } = useParams();
  const projectId = parseInt(id, 10);
  const navigate = useNavigate();
  const { user } = useAuth();
  const qc = useQueryClient();
  const [tab, setTab] = useState('Board');

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
        </nav>
      </div>

      {/* Content */}
      <main className={`mx-auto px-6 py-6 ${tab === 'Board' ? 'max-w-7xl' : 'max-w-4xl'}`}>
        {tab === 'Overview' && project && <OverviewTab project={project} />}
        {tab === 'Board' && (
          <KanbanBoard tasks={tasks} projectId={projectId} />
        )}
        {tab === 'Plan' && (
          <PlanTab projectId={projectId} isAdmin={isAdmin} />
        )}
        {tab === 'Team' && (
          <TeamTab projectId={projectId} isAdmin={isAdmin} currentUserId={user?.id} />
        )}
      </main>
    </div>
  );
}
