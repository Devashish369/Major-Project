/**
 * pages/DashboardPage.jsx – Placeholder dashboard for M1.
 *
 * Shows the logged-in user's name and a logout button.
 * Full dashboard content (project cards, health badges) is built in M9.
 *
 * This page is PROTECTED – only reachable if the user is authenticated.
 */
import { useNavigate } from 'react-router-dom';
import { LogOut, BarChart2, User } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function DashboardPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate('/login', { replace: true });
  }

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      {/* Top nav */}
      <header className="border-b border-slate-700 bg-slate-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-indigo-600 p-1.5">
            <BarChart2 className="h-5 w-5 text-white" />
          </div>
          <span className="text-lg font-bold">IntelliPM</span>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm text-slate-300">
            <User className="h-4 w-4" />
            <span>{user?.full_name}</span>
            <span className="text-slate-500">·</span>
            <span className="text-slate-400">@{user?.username}</span>
          </div>
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

      {/* Body */}
      <main className="max-w-4xl mx-auto px-6 py-12">
        <div className="rounded-2xl border border-indigo-500/30 bg-indigo-600/10 p-8 text-center">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-indigo-600/20 mb-4">
            <BarChart2 className="h-7 w-7 text-indigo-400" />
          </div>
          <h1 className="text-2xl font-bold mb-2">Welcome, {user?.full_name}!</h1>
          <p className="text-slate-400 mb-6">
            You're logged in as <span className="text-indigo-400">@{user?.username}</span>.
            The project dashboard will appear here in M2.
          </p>

          {/* User info card */}
          <div className="mt-4 inline-block rounded-xl border border-slate-700 bg-slate-800 px-6 py-4 text-left text-sm space-y-1.5">
            <p><span className="text-slate-400">Email:</span> <span className="text-white">{user?.email}</span></p>
            <p><span className="text-slate-400">Member since:</span> <span className="text-white">{user?.created_at?.slice(0, 10)}</span></p>
            <p><span className="text-slate-400">On-time rate:</span> <span className="text-white">{(user?.on_time_rate * 100).toFixed(0)}%</span></p>
            <p>
              <span className="text-slate-400">Skills:</span>{' '}
              <span className="text-white">
                {user?.skills && Object.keys(user.skills).length > 0
                  ? Object.entries(user.skills).map(([k, v]) => `${k}:${v}`).join(', ')
                  : 'None set yet'}
              </span>
            </p>
          </div>

          <p className="mt-6 text-xs text-slate-600">
            M1: Auth complete ✓ · M2: Projects coming next
          </p>
        </div>
      </main>
    </div>
  );
}
