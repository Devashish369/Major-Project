/**
 * pages/RegisterPage.jsx – Account creation form for IntelliPM.
 */
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { UserPlus, Loader2, Eye, EyeOff, BarChart2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState({
    full_name: '',
    email: '',
    username: '',
    password: '',
    confirm: '',
  });
  const [showPw, setShowPw]   = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  function handleChange(e) {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');

    // Client-side password confirmation check
    if (form.password !== form.confirm) {
      setError("Passwords don't match.");
      return;
    }

    setLoading(true);
    try {
      await register(form.email, form.username, form.full_name, form.password);
      navigate('/dashboard', { replace: true });
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        err.response?.data?.message ||
        'Registration failed. Please try again.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  const fields = [
    { id: 'reg-full-name', name: 'full_name', label: 'Full name', type: 'text',
      placeholder: 'Ada Lovelace', autoComplete: 'name' },
    { id: 'reg-email', name: 'email', label: 'Email', type: 'email',
      placeholder: 'you@example.com', autoComplete: 'email' },
    { id: 'reg-username', name: 'username', label: 'Username', type: 'text',
      placeholder: 'ada_codes', autoComplete: 'username' },
  ];

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900 p-4">
      <div className="w-full max-w-md">

        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="rounded-xl bg-indigo-600 p-2.5">
            <BarChart2 className="h-6 w-6 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">IntelliPM</h1>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-slate-700 bg-slate-800 p-8 shadow-2xl">
          <h2 className="text-xl font-semibold text-white mb-1">Create an account</h2>
          <p className="text-sm text-slate-400 mb-6">Get started with IntelliPM for free</p>

          {error && (
            <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {fields.map(({ id, name, label, type, placeholder, autoComplete }) => (
              <div key={name}>
                <label htmlFor={id} className="block text-sm font-medium text-slate-300 mb-1.5">
                  {label}
                </label>
                <input
                  id={id}
                  name={name}
                  type={type}
                  autoComplete={autoComplete}
                  required
                  value={form[name]}
                  onChange={handleChange}
                  placeholder={placeholder}
                  className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3.5 py-2.5 text-sm text-white placeholder-slate-500 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition"
                />
              </div>
            ))}

            {/* Password */}
            <div>
              <label htmlFor="reg-password" className="block text-sm font-medium text-slate-300 mb-1.5">
                Password <span className="text-slate-500 font-normal">(min. 8 chars)</span>
              </label>
              <div className="relative">
                <input
                  id="reg-password"
                  name="password"
                  type={showPw ? 'text' : 'password'}
                  autoComplete="new-password"
                  required
                  minLength={8}
                  value={form.password}
                  onChange={handleChange}
                  placeholder="••••••••"
                  className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3.5 py-2.5 pr-10 text-sm text-white placeholder-slate-500 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition"
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200"
                  aria-label="Toggle password visibility"
                >
                  {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {/* Confirm password */}
            <div>
              <label htmlFor="reg-confirm" className="block text-sm font-medium text-slate-300 mb-1.5">
                Confirm password
              </label>
              <input
                id="reg-confirm"
                name="confirm"
                type={showPw ? 'text' : 'password'}
                autoComplete="new-password"
                required
                value={form.confirm}
                onChange={handleChange}
                placeholder="••••••••"
                className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3.5 py-2.5 text-sm text-white placeholder-slate-500 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition"
              />
            </div>

            <button
              id="register-submit"
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-60 disabled:cursor-not-allowed transition mt-2"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <UserPlus className="h-4 w-4" />
              )}
              {loading ? 'Creating account…' : 'Create account'}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-400">
            Already have an account?{' '}
            <Link to="/login" className="text-indigo-400 hover:text-indigo-300 font-medium">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
