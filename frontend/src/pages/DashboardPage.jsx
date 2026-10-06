/**
 * pages/DashboardPage.jsx – Project dashboard for IntelliPM.
 *
 * Features:
 *   - Lists all projects the logged-in user is a member of
 *   - Project cards show status, priority, member count, done ratio
 *   - "New Project" button opens a modal to create a project
 *   - Health score shown as badge (null until M7)
 *   - Global user profile skill editor in the navbar
 *
 * Uses @tanstack/react-query for server state.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  BarChart2, Plus, LogOut, User, Calendar, Users,
  CheckCircle, Clock, AlertCircle, Loader2, FolderOpen,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { listProjects, createProject } from '../api/projects';
import CreateProjectModal from '../components/CreateProjectModal';
import SkillsEditor from '../components/SkillsEditor';

// ── Status badge helper ───────────────────────────────────────────────────────
const STATUS_CONFIG = {
  pending:     { label: 'Pending',     color: 'bg-slate-700 text-slate-300', icon: Clock },
  in_progress: { label: 'In Progress', color: 'bg-blue-500/20 text-blue-300', icon: AlertCircle },
  completed:   { label: 'Completed',   color: 'bg-green-500/20 text-green-300', icon: CheckCircle },
};

const PRIORITY_COLOR = {
  low:    'border-l-slate-500',
  medium: 'border-l-amber-500',
  high:   'border-l-red-500',
};

function StatusBadge({ status }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.pending;
  const Icon = cfg.icon;
  return (
    <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${cfg.color}`}>
      <Icon className="h-3 w-3" />
      {cfg.label}
    </span>
  );
}

function ProjectCard({ project, onClick }) {
  const donePercent = Math.round((project.done_ratio || 0) * 100);
  return (
    <div
      onClick={onClick}
      className={`group cursor-pointer rounded-xl border border-slate-700 bg-slate-800 p-5 
        hover:border-indigo-500/50 hover:bg-slate-750 transition-all duration-200
        border-l-4 ${PRIORITY_COLOR[project.priority] || 'border-l-slate-700'}`}
    >
      <div className="flex items-start justify-between gap-2 mb-3">
        <h3 className="font-semibold text-white group-hover:text-indigo-300 transition-colors leading-tight">
          {project.title}
        </h3>
        <StatusBadge status={project.status} />
      </div>

      {project.description && (
        <p className="text-xs text-slate-400 mb-3 line-clamp-2">{project.description}</p>
      )}

      {/* Progress bar */}
      <div className="mb-3">
        <div className="flex justify-between text-xs text-slate-400 mb-1">
          <span>Progress</span>
          <span>{donePercent}%</span>
        </div>
        <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-indigo-500 rounded-full transition-all"
            style={{ width: `${donePercent}%` }}
          />
        </div>
      </div>

      <div className="flex items-center justify-between text-xs text-slate-400">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <Users className="h-3 w-3" />
            {project.member_count} member{project.member_count !== 1 ? 's' : ''}
          </span>
          <span className="flex items-center gap-1">
            <CheckCircle className="h-3 w-3" />
            {project.task_count} tasks
          </span>
        </div>
        {project.due_date && (
          <span className="flex items-center gap-1">
            <Calendar className="h-3 w-3" />
            {project.due_date}
          </span>
        )}
      </div>

      {/* Health badge: >=75 low risk, 50-74 medium, <50 high (spec 8.5) */}
      {project.health_score != null && (() => {
        const h = project.health_score;
        const [text, cls] =
          h >= 75 ? ['Low risk', 'text-green-400 bg-green-500/10 border-green-500/30']
          : h >= 50 ? ['Medium risk', 'text-amber-400 bg-amber-500/10 border-amber-500/30']
          : ['High risk', 'text-red-400 bg-red-500/10 border-red-500/30'];
        return (
          <div className="mt-3 pt-3 border-t border-slate-700 flex items-center justify-between">
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${cls}`}>● {text}</span>
            <span className="text-xs text-slate-400">Health {Math.round(h)}</span>
          </div>
        );
      })()}
    </div>
  );
}

// ── Main Dashboard ────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [showCreate, setShowCreate] = useState(false);
  const [showSkills, setShowSkills] = useState(false);

  const { data: projects = [], isLoading, error } = useQuery({
    queryKey: ['projects'],
    queryFn: listProjects,
  });

  const createMut = useMutation({
    mutationFn: createProject,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] });
      setShowCreate(false);
    },
  });

  function handleLogout() {
    logout();
    navigate('/login', { replace: true });
  }

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      {/* ── Navbar ─────────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-30 border-b border-slate-700 bg-slate-900/95 backdrop-blur px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-indigo-600 p-1.5">
            <BarChart2 className="h-5 w-5 text-white" />
          </div>
          <span className="text-lg font-bold">IntelliPM</span>
        </div>
        <div className="flex items-center gap-3">
          <button
            id="skills-editor-btn"
            onClick={() => setShowSkills(true)}
            className="flex items-center gap-1.5 rounded-lg border border-slate-600 px-3 py-1.5 text-sm text-slate-300 hover:border-indigo-500 hover:text-white transition"
          >
            <User className="h-4 w-4" />
            {user?.full_name}
          </button>
          <button
            id="logout-button"
            onClick={handleLogout}
            className="flex items-center gap-1.5 rounded-lg border border-slate-600 px-3 py-1.5 text-sm text-slate-300 hover:border-slate-400 hover:text-white transition"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      </header>

      {/* ── Body ───────────────────────────────────────────────────────────── */}
      <main className="max-w-6xl mx-auto px-6 py-8">
        {/* Header row */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-white">Projects</h1>
            <p className="text-slate-400 text-sm mt-0.5">
              {projects.length} project{projects.length !== 1 ? 's' : ''} you're a member of
            </p>
          </div>
          <button
            id="new-project-btn"
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 transition"
          >
            <Plus className="h-4 w-4" />
            New Project
          </button>
        </div>

        {/* Loading state */}
        {isLoading && (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-8 w-8 animate-spin text-indigo-400" />
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="rounded-lg bg-red-500/10 border border-red-500/30 p-4 text-red-400 text-sm">
            Failed to load projects. {error.message}
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !error && projects.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <div className="w-16 h-16 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center mb-4">
              <FolderOpen className="h-7 w-7 text-slate-500" />
            </div>
            <h3 className="text-lg font-semibold text-slate-300 mb-2">No projects yet</h3>
            <p className="text-slate-500 text-sm mb-6">Create your first project to get started.</p>
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 transition"
            >
              <Plus className="h-4 w-4" />
              Create a project
            </button>
          </div>
        )}

        {/* Project grid */}
        {!isLoading && projects.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((p) => (
              <ProjectCard
                key={p.id}
                project={p}
                onClick={() => navigate(`/projects/${p.id}`)}
              />
            ))}
          </div>
        )}
      </main>

      {/* ── Modals ─────────────────────────────────────────────────────────── */}
      {showCreate && (
        <CreateProjectModal
          onClose={() => setShowCreate(false)}
          onSubmit={(data) => createMut.mutate(data)}
          loading={createMut.isPending}
          error={createMut.error?.response?.data?.detail || createMut.error?.message}
        />
      )}

      {showSkills && (
        <SkillsEditor onClose={() => setShowSkills(false)} />
      )}
    </div>
  );
}
