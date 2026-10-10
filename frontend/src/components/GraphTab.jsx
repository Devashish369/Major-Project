/**
 * components/GraphTab.jsx – M11 dependency graph (@xyflow/react).
 *
 *  - one node per task, one edge per dependency (arrow: prerequisite -> dependent)
 *  - node colour = status (todo grey, in progress blue, done green)
 *  - BLOCKED = an open task with at least one unfinished dependency -> red
 *  - layout = layered by dependency depth:
 *        depth(task) = 0 if it has no dependencies, else 1 + max(depth of its dependencies)
 *    columns are depths, rows are the tasks of that depth in list order
 *  - click a node to open the same TaskDrawer used on the Board
 */
import { useMemo, useState } from 'react';
import { ReactFlow, Background, Controls, MarkerType } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Network } from 'lucide-react';
import TaskDrawer from './TaskDrawer';

const NODE_W = 210;
const NODE_H = 64;
const COL_GAP = 90;
const ROW_GAP = 22;

const STATUS_STYLE = {
  todo:        { bg: '#1e293b', border: '#64748b', label: 'To do' },
  in_progress: { bg: '#172554', border: '#3b82f6', label: 'In progress' },
  done:        { bg: '#052e16', border: '#22c55e', label: 'Done' },
};
const BLOCKED = { bg: '#450a0a', border: '#ef4444' };

/** Depth of every task; ignores edges to unknown ids and survives (impossible) cycles. */
function computeDepths(tasks) {
  const byId = new Map(tasks.map((t) => [t.id, t]));
  const memo = new Map();
  const visiting = new Set();
  const depth = (id) => {
    if (memo.has(id)) return memo.get(id);
    if (visiting.has(id)) return 0;
    visiting.add(id);
    const deps = (byId.get(id)?.dependencies || []).filter((d) => byId.has(d));
    const d = deps.length ? 1 + Math.max(...deps.map(depth)) : 0;
    visiting.delete(id);
    memo.set(id, d);
    return d;
  };
  tasks.forEach((t) => depth(t.id));
  return memo;
}

function buildGraph(tasks) {
  const byId = new Map(tasks.map((t) => [t.id, t]));
  const depths = computeDepths(tasks);
  const rowInCol = {};
  const blockedIds = new Set(
    tasks
      .filter((t) => t.status !== 'done')
      .filter((t) => (t.dependencies || []).some((d) => byId.has(d) && byId.get(d).status !== 'done'))
      .map((t) => t.id),
  );

  const nodes = tasks.map((t) => {
    const col = depths.get(t.id) || 0;
    const row = (rowInCol[col] = (rowInCol[col] ?? -1) + 1);
    const blocked = blockedIds.has(t.id);
    const st = blocked ? BLOCKED : STATUS_STYLE[t.status] || STATUS_STYLE.todo;
    return {
      id: String(t.id),
      position: { x: col * (NODE_W + COL_GAP), y: row * (NODE_H + ROW_GAP) },
      data: {
        label: (
          <div style={{ textAlign: 'left', lineHeight: 1.25 }}>
            <div style={{ fontSize: 12, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {t.title}
            </div>
            <div style={{ fontSize: 10, opacity: 0.75, marginTop: 3 }}>
              #{t.number ?? t.id} · {blocked ? 'Blocked' : STATUS_STYLE[t.status]?.label} · {t.estimate_hours ?? '?'}h
            </div>
          </div>
        ),
      },
      style: {
        width: NODE_W, height: NODE_H, background: st.bg, color: '#e2e8f0',
        border: `2px solid ${st.border}`, borderRadius: 10, padding: '8px 10px',
        boxShadow: blocked ? '0 0 12px rgba(239,68,68,0.45)' : 'none',
      },
      width: NODE_W,
      height: NODE_H,
      draggable: false,
    };
  });

  const edges = tasks.flatMap((t) =>
    (t.dependencies || []).filter((d) => byId.has(d)).map((d) => {
      // An edge is "blocking" when the prerequisite is unfinished and the dependent is open.
      const blocking = byId.get(d).status !== 'done' && t.status !== 'done';
      const color = blocking ? '#ef4444' : '#64748b';
      return {
        id: `e${d}-${t.id}`, source: String(d), target: String(t.id),
        animated: blocking, style: { stroke: color, strokeWidth: 1.6 },
        markerEnd: { type: MarkerType.ArrowClosed, color },
      };
    }),
  );
  return { nodes, edges, blocked: blockedIds.size, edgeCount: edges.length };
}

function Legend({ blocked }) {
  const items = [
    ...Object.values(STATUS_STYLE).map((s) => [s.label, s.border]),
    ['Blocked', BLOCKED.border],
  ];
  return (
    <div className="flex flex-wrap items-center gap-4 text-xs text-slate-300 mb-3">
      {items.map(([label, color]) => (
        <span key={label} className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded border-2" style={{ borderColor: color }} /> {label}
        </span>
      ))}
      <span className="ml-auto text-slate-400">
        {blocked} blocked task{blocked === 1 ? '' : 's'} · arrows point from prerequisite to dependent
      </span>
    </div>
  );
}

export default function GraphTab({ tasks, projectId }) {
  const [selectedId, setSelectedId] = useState(null);
  const graph = useMemo(() => buildGraph(tasks), [tasks]);
  const selected = tasks.find((t) => t.id === selectedId);

  if (tasks.length === 0) {
    return (
      <div className="rounded-2xl border border-slate-700 bg-slate-800 py-16 text-center">
        <Network className="h-8 w-8 text-slate-600 mx-auto mb-2" />
        <p className="text-sm text-slate-400">No tasks yet. Add tasks on the Board to see their dependencies here.</p>
      </div>
    );
  }

  return (
    <div>
      <Legend blocked={graph.blocked} />
      <div className="rounded-2xl border border-slate-700 bg-slate-900 overflow-hidden" style={{ height: 560 }}>
        <ReactFlow
          nodes={graph.nodes}
          edges={graph.edges}
          onNodeClick={(_, node) => setSelectedId(Number(node.id))}
          fitView
          fitViewOptions={{ padding: 0.15 }}
          nodesConnectable={false}
          colorMode="dark"
          proOptions={{ hideAttribution: true }}
          minZoom={0.2}
        >
          <Background color="#334155" gap={20} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      {graph.edgeCount === 0 && (
        <p className="text-xs text-slate-400 mt-2">
          This project has no dependencies yet. Add them from a task's drawer on the Board.
        </p>
      )}
      {selected && (
        <TaskDrawer task={selected} projectId={projectId} tasks={tasks} onClose={() => setSelectedId(null)} />
      )}
    </div>
  );
}
