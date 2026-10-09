/**
 * hooks/useProjectSocket.js – live task updates for one project (M13).
 *
 * Connects to  WS /ws/projects/{id}?token=<JWT>  while `enabled` is true (the Board and
 * Graph tabs), patches the react-query tasks cache when another user creates / updates /
 * deletes a task, and reconnects automatically after a drop.
 *
 * The socket is a bonus, never a dependency: every action still goes through the REST API,
 * so if the socket cannot connect the app works exactly as before (changes just appear
 * after a refresh).  Returned status: 'off' | 'connecting' | 'live' | 'reconnecting' | 'offline'.
 */
import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { getToken } from '../api/session';

const PING_MS = 25_000;          // keep-alive: proxies close idle sockets after ~1 minute
const MAX_BACKOFF_MS = 30_000;
const MAX_FAILED_ATTEMPTS = 6;   // consecutive attempts that never opened -> stop and show "offline"

/** http://host/api/v1  ->  ws://host/ws/projects/{id}?token=...  (https -> wss) */
function socketUrl(projectId) {
  const base = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
  const u = new URL(base);
  const proto = u.protocol === 'https:' ? 'wss:' : 'ws:';
  const token = encodeURIComponent(getToken() || '');
  return `${proto}//${u.host}/ws/projects/${projectId}?token=${token}`;
}

/** Apply one server event to the cached task list (pure; exported for clarity). */
export function applyTaskEvent(tasks, event) {
  if (!Array.isArray(tasks) || !event?.task) return tasks;
  const t = event.task;
  switch (event.type) {
    case 'task_deleted':
      return tasks.filter((x) => x.id !== t.id);
    case 'task_created':
    case 'task_updated':
      return tasks.some((x) => x.id === t.id)
        ? tasks.map((x) => (x.id === t.id ? t : x))
        : [...tasks, t];
    default:
      return tasks;
  }
}

export default function useProjectSocket(projectId, enabled) {
  const qc = useQueryClient();
  const [status, setStatus] = useState('off');

  useEffect(() => {
    if (!enabled || !projectId) return undefined;   // returned status is 'off' below

    let ws = null;
    let retryTimer = null;
    let pingTimer = null;
    let stopped = false;
    let failedAttempts = 0;     // consecutive attempts that closed without ever opening
    let hasOpenedBefore = false;
    let delay = 1000;

    const connect = () => {
      if (stopped) return;
      setStatus(hasOpenedBefore ? 'reconnecting' : 'connecting');
      let opened = false;
      try {
        ws = new WebSocket(socketUrl(projectId));
      } catch {
        scheduleRetry(false);
        return;
      }

      ws.onopen = () => {
        opened = true;
        failedAttempts = 0;
        delay = 1000;
        setStatus('live');
        // After a drop we may have missed events: reload once from the server.
        if (hasOpenedBefore) qc.invalidateQueries({ queryKey: ['tasks', projectId] });
        hasOpenedBefore = true;
        pingTimer = setInterval(() => {
          if (ws && ws.readyState === WebSocket.OPEN) ws.send('ping');
        }, PING_MS);
      };

      ws.onmessage = (msg) => {
        let event;
        try { event = JSON.parse(msg.data); } catch { return; }
        if (!event || !String(event.type).startsWith('task_')) return;   // 'connected' / 'pong'
        qc.setQueryData(['tasks', projectId], (old) => applyTaskEvent(old, event));
        // Things derived from tasks: counts, health, forecast, burndown, workload.
        ['project', 'health', 'forecast', 'burndown', 'workload'].forEach((k) =>
          qc.invalidateQueries({ queryKey: [k, projectId] }),
        );
      };

      ws.onclose = () => {
        clearInterval(pingTimer);
        if (stopped) return;
        scheduleRetry(opened);
      };
      ws.onerror = () => { /* onclose follows; nothing to do */ };
    };

    const scheduleRetry = (wasOpen) => {
      if (stopped) return;
      failedAttempts = wasOpen ? 0 : failedAttempts + 1;
      if (failedAttempts >= MAX_FAILED_ATTEMPTS) {
        setStatus('offline');           // e.g. expired token or socket blocked: stop hammering
        return;
      }
      setStatus(hasOpenedBefore ? 'reconnecting' : 'connecting');
      retryTimer = setTimeout(connect, delay);
      delay = Math.min(delay * 2, MAX_BACKOFF_MS);
    };

    connect();

    return () => {
      stopped = true;
      clearTimeout(retryTimer);
      clearInterval(pingTimer);
      if (ws) { ws.onclose = null; ws.close(); }
    };
  }, [projectId, enabled, qc]);

  return enabled && projectId ? status : 'off';
}
