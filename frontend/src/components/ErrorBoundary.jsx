/**
 * components/ErrorBoundary.jsx – last line of defence against a blank white screen.
 * If any component throws while rendering, show a readable message with a reload button
 * (and log the technical error to the console) instead of an empty page.
 */
import { Component } from 'react';

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error, info) {
    console.error('UI crash caught by ErrorBoundary:', error, info?.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900 p-6">
        <div className="max-w-md rounded-2xl border border-slate-700 bg-slate-800 p-8 text-center">
          <h1 className="text-lg font-semibold text-white">Something went wrong</h1>
          <p className="mt-2 text-sm text-slate-400">
            The page hit an unexpected error. Your data is safe. Reload to continue; if it keeps happening, tell the team what you clicked just before.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="mt-5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
          >
            Reload page
          </button>
        </div>
      </div>
    );
  }
}
