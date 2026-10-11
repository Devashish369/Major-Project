/**
 * components/ThemeToggle.jsx – Light / Dark / Auto switch (a radio group, keyboard friendly).
 */
import { Monitor, Moon, Sun } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

const OPTIONS = [
  { value: 'light', label: 'Light', Icon: Sun },
  { value: 'dark', label: 'Dark', Icon: Moon },
  { value: 'system', label: 'Auto', Icon: Monitor, hint: 'Follow this device’s setting' },
];

export default function ThemeToggle({ compact = false, className = '' }) {
  const { mode, setMode } = useTheme();
  return (
    <div
      role="radiogroup"
      aria-label="Colour theme"
      id="theme-toggle"
      className={`theme-toggle inline-flex items-center rounded-lg border border-slate-600 bg-slate-900 p-0.5 ${className}`}
    >
      {OPTIONS.map(({ value, label, Icon, hint }) => {
        const active = mode === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={active}
            data-theme-option={value}
            title={hint || `${label} theme`}
            onClick={() => setMode(value)}
            className={`flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium transition-colors
              focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-indigo-500
              ${active ? 'theme-toggle-active text-white' : 'text-slate-400 hover:text-white'}`}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden="true" />
            <span className={compact ? 'sr-only' : 'hidden md:inline'}>{label}</span>
          </button>
        );
      })}
    </div>
  );
}
