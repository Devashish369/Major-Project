/**
 * pages/SecurityPage.jsx – account security.
 *
 *  - Recent sign-in activity (threat detection / digital forensics): successful and failed
 *    sign-ins, blocked attempts, password changes, with time, IP address and browser.
 *  - Change password (cryptography: bcrypt hashing + a password policy); signs out every
 *    other tab and device by revoking their tokens.
 *  - Sign out everywhere.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { ArrowLeft, Loader2, LogOut, ShieldCheck, ShieldAlert, KeyRound, CheckCircle2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { changePassword, getSecurityEvents, logoutAll } from '../api/auth';
import { errorMessage } from '../api/errors';
import { passwordProblem } from '../api/passwordPolicy';

const EVENT_TEXT = {
  login_success: { text: 'Signed in', bad: false },
  login_failed: { text: 'Failed sign-in (wrong password)', bad: true },
  login_blocked: { text: 'Sign-in blocked (too many failed attempts)', bad: true },
  register: { text: 'Account created', bad: false },
  password_changed: { text: 'Password changed', bad: false },
  password_change_failed: { text: 'Password change refused (wrong current password)', bad: true },
  sessions_revoked: { text: 'Signed out everywhere', bad: false },
};

function browserOf(ua) {
  if (!ua) return 'Unknown';
  const name = /Edg\//.test(ua) ? 'Edge' : /OPR\//.test(ua) ? 'Opera' : /Chrome\//.test(ua) ? 'Chrome'
    : /Firefox\//.test(ua) ? 'Firefox' : /Safari\//.test(ua) ? 'Safari' : ua.split(' ')[0].slice(0, 30);
  const os = /Windows/.test(ua) ? 'Windows' : /Android/.test(ua) ? 'Android' : /iPhone|iPad/.test(ua) ? 'iOS'
    : /Mac OS/.test(ua) ? 'macOS' : /Linux/.test(ua) ? 'Linux' : '';
  return os ? `${name} on ${os}` : name;
}

const input = 'w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-indigo-500';

export default function SecurityPage() {
  const navigate = useNavigate();
  const { user, logout, replaceToken } = useAuth();
  const [form, setForm] = useState({ current: '', next: '', confirm: '' });
  const [formErr, setFormErr] = useState('');
  const [done, setDone] = useState('');
  const [weekAgo] = useState(() => Date.now() - 7 * 24 * 3600 * 1000);   // fixed when the page opens

  const events = useQuery({ queryKey: ['security-events'], queryFn: getSecurityEvents, staleTime: 0 });

  const pwMut = useMutation({
    mutationFn: () => changePassword(form.current, form.next),
    onSuccess: (data) => {
      replaceToken(data.access_token);   // this tab stays signed in, every other one is signed out
      setForm({ current: '', next: '', confirm: '' });
      setDone('Password changed. Every other tab and device has been signed out.');
      events.refetch();
    },
    onError: (e) => setFormErr(errorMessage(e, 'Could not change the password.')),
  });

  const allMut = useMutation({
    mutationFn: logoutAll,
    onSuccess: () => { logout(); navigate('/login', { replace: true }); },
  });

  function submit(e) {
    e.preventDefault();
    setFormErr(''); setDone('');
    const problem = passwordProblem(form.next, user);
    if (problem) { setFormErr(problem); return; }
    if (form.next !== form.confirm) { setFormErr("The new passwords don't match."); return; }
    pwMut.mutate();
  }

  const rows = events.data || [];
  const recentFailures = rows.filter((r) => EVENT_TEXT[r.event]?.bad
    && new Date(r.created_at).getTime() > weekAgo).length;

  return (
    <div className="min-h-screen bg-slate-900 text-white">
      <header className="border-b border-slate-800 px-6 py-4 flex items-center gap-3">
        <button onClick={() => navigate('/dashboard')} aria-label="Back to dashboard" className="text-slate-400 hover:text-white">
          <ArrowLeft className="h-5 w-5" />
        </button>
        <ShieldCheck className="h-5 w-5 text-indigo-400" />
        <h1 className="text-lg font-semibold">Account security</h1>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-8 space-y-6">
        {/* Summary */}
        <section className={`rounded-2xl border p-5 flex items-start gap-3 ${recentFailures ? 'border-amber-500/40 bg-amber-500/5' : 'border-slate-700 bg-slate-800'}`}>
          {recentFailures
            ? <ShieldAlert className="h-5 w-5 text-amber-400 mt-0.5" />
            : <ShieldCheck className="h-5 w-5 text-green-400 mt-0.5" />}
          <div className="text-sm">
            <p className="font-semibold">
              {recentFailures
                ? `${recentFailures} failed or blocked sign-in attempt${recentFailures > 1 ? 's' : ''} in the last 7 days`
                : 'No failed sign-in attempts in the last 7 days'}
            </p>
            <p className="text-slate-400 mt-1">
              After 5 wrong passwords in 15 minutes, sign-in from that network is paused for 15 minutes.
              If you see activity that was not you, change your password – that also signs out every other device.
            </p>
          </div>
        </section>

        {/* Activity */}
        <section className="rounded-2xl border border-slate-700 bg-slate-800 overflow-hidden">
          <h2 className="px-5 py-4 text-sm font-semibold border-b border-slate-700">Recent sign-in activity</h2>
          {events.isLoading ? (
            <div className="p-6"><Loader2 className="h-5 w-5 animate-spin text-slate-400" /></div>
          ) : events.isError ? (
            <p className="p-5 text-sm text-red-400">{errorMessage(events.error, 'Could not load activity.')}</p>
          ) : rows.length === 0 ? (
            <p className="p-5 text-sm text-slate-400">No activity recorded yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table id="security-events" className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-slate-400 border-b border-slate-700">
                    <th className="px-5 py-2 text-left">When</th>
                    <th className="px-5 py-2 text-left">What</th>
                    <th className="px-5 py-2 text-left">IP address</th>
                    <th className="px-5 py-2 text-left">Browser</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/50">
                  {rows.map((r) => {
                    const ev = EVENT_TEXT[r.event] || { text: r.event, bad: false };
                    return (
                      <tr key={r.id} data-event={r.event}>
                        <td className="px-5 py-2 text-slate-300 whitespace-nowrap">{new Date(r.created_at).toLocaleString()}</td>
                        <td className={`px-5 py-2 ${ev.bad ? 'text-amber-300' : 'text-slate-200'}`}>{ev.text}</td>
                        <td className="px-5 py-2 text-slate-400 font-mono text-xs">{r.ip || '—'}</td>
                        <td className="px-5 py-2 text-slate-400">{browserOf(r.user_agent)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <div className="grid gap-6 md:grid-cols-2">
          {/* Change password */}
          <section className="rounded-2xl border border-slate-700 bg-slate-800 p-5">
            <h2 className="text-sm font-semibold flex items-center gap-2"><KeyRound className="h-4 w-4 text-indigo-400" /> Change password</h2>
            <form id="change-password-form" onSubmit={submit} className="mt-4 space-y-3">
              <input id="pw-current" className={input} type="password" autoComplete="current-password" placeholder="Current password"
                required maxLength={128} value={form.current} onChange={(e) => setForm({ ...form, current: e.target.value })} />
              <input id="pw-new" className={input} type="password" autoComplete="new-password" placeholder="New password"
                required maxLength={72} value={form.next} onChange={(e) => setForm({ ...form, next: e.target.value })} />
              <input id="pw-confirm" className={input} type="password" autoComplete="new-password" placeholder="Repeat new password"
                required maxLength={72} value={form.confirm} onChange={(e) => setForm({ ...form, confirm: e.target.value })} />
              <p className="text-xs text-slate-500">At least 8 characters with a letter and a number; not a common password; not your username or email.</p>
              {formErr && <p className="text-sm text-red-400">{formErr}</p>}
              {done && <p className="text-sm text-green-400 flex items-center gap-1.5"><CheckCircle2 className="h-4 w-4" /> {done}</p>}
              <button type="submit" disabled={pwMut.isPending}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium hover:bg-indigo-500 disabled:opacity-60">
                {pwMut.isPending ? 'Saving…' : 'Change password'}
              </button>
            </form>
          </section>

          {/* Sign out everywhere */}
          <section className="rounded-2xl border border-slate-700 bg-slate-800 p-5">
            <h2 className="text-sm font-semibold flex items-center gap-2"><LogOut className="h-4 w-4 text-indigo-400" /> Sign out everywhere</h2>
            <p className="mt-3 text-sm text-slate-400">
              Ends every session of this account – all tabs, browsers and devices, including this one.
              Use it after signing in on a shared or public computer.
            </p>
            {allMut.isError && <p className="mt-2 text-sm text-red-400">{errorMessage(allMut.error, 'Could not sign out everywhere.')}</p>}
            <button id="logout-all-button" onClick={() => { if (window.confirm('Sign out on every device and tab?')) allMut.mutate(); }}
              disabled={allMut.isPending}
              className="mt-4 rounded-lg border border-red-500/40 px-4 py-2 text-sm text-red-300 hover:bg-red-500/10 disabled:opacity-60">
              {allMut.isPending ? 'Signing out…' : 'Sign out everywhere'}
            </button>
          </section>
        </div>
      </main>
    </div>
  );
}
