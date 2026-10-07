/**
 * components/KanbanBoard.jsx – Drag-and-drop Kanban board using @dnd-kit.
 *
 * Three columns: To Do | In Progress | Done
 * Dragging a card between columns calls PATCH /tasks/{id} with the new status.
 * Clicking a card opens the TaskDrawer.
 * "New Task" button at the top of each column opens CreateTaskModal.
 *
 * Persistence: moves call the API immediately; the board re-fetches from the
 * server after each mutation so state is always server-authoritative.
 * After a page refresh the board reflects the last server state (spec done-when).
 */
import { useState } from 'react';
import {
  DndContext,
  PointerSensor,
  useSensor,
  useSensors,
  DragOverlay,
  closestCenter,
} from '@dnd-kit/core';
import {
  SortableContext,
  verticalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Clock, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { updateTask } from '../api/tasks';
import TaskDrawer from './TaskDrawer';
import CreateTaskModal from './CreateTaskModal';

// ── Column config ─────────────────────────────────────────────────────────────
const COLUMNS = [
  { id: 'todo',        label: 'To Do',       icon: Clock,         color: 'border-t-slate-500' },
  { id: 'in_progress', label: 'In Progress', icon: AlertTriangle, color: 'border-t-blue-500'  },
  { id: 'done',        label: 'Done',        icon: CheckCircle2,  color: 'border-t-green-500' },
];

const PRIORITY_LEFT = {
  low: 'border-l-slate-600', medium: 'border-l-amber-500',
  high: 'border-l-orange-500', critical: 'border-l-red-500',
};

// ── Sortable Task Card ────────────────────────────────────────────────────────
function TaskCard({ task, onClick }) {
  const {
    attributes, listeners, setNodeRef,
    transform, transition, isDragging: localDragging,
  } = useSortable({ id: task.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: localDragging ? 0.4 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      onClick={(e) => { e.stopPropagation(); onClick(task); }}
      className={`group cursor-pointer rounded-lg border border-slate-700 bg-slate-800 p-3
        hover:border-indigo-500/50 transition-all border-l-4 ${PRIORITY_LEFT[task.priority] || 'border-l-slate-600'}
        ${localDragging ? 'shadow-2xl shadow-indigo-500/20 ring-1 ring-indigo-500' : ''}`}
    >
      <p className="text-sm text-white font-medium leading-snug mb-1.5 group-hover:text-indigo-200 transition-colors">
        {task.title}
      </p>
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span>#{task.id}</span>
        <div className="flex items-center gap-2">
          {task.estimate_hours && <span>{task.estimate_hours}h</span>}
          {task.due_date && <span>{task.due_date}</span>}
          {task.assignee_id && (
            <span className="w-5 h-5 rounded-full bg-indigo-600 flex items-center justify-center text-white text-xs">
              {task.assignee_id}
            </span>
          )}
        </div>
      </div>
      {(task.dependencies || []).length > 0 && (
        <div className="mt-1.5 text-xs text-slate-600">
          ↳ {task.dependencies.length} dep{task.dependencies.length > 1 ? 's' : ''}
        </div>
      )}
    </div>
  );
}

// ── Column ────────────────────────────────────────────────────────────────────
function Column({ column, tasks, onCardClick, onAddTask }) {
  const Icon = column.icon;
  return (
    <div className={`flex flex-col min-h-[400px] rounded-xl border border-slate-700 bg-slate-800/50 border-t-4 ${column.color}`}>
      {/* Column header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700">
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-slate-400" />
          <span className="text-sm font-semibold text-slate-300">{column.label}</span>
          <span className="text-xs bg-slate-700 text-slate-400 rounded-full px-2 py-0.5">{tasks.length}</span>
        </div>
        <button
          id={`add-task-${column.id}`}
          onClick={() => onAddTask(column.id)}
          className="text-slate-500 hover:text-indigo-400 transition"
          title={`Add ${column.label} task`}
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>

      {/* Cards */}
      <div className="flex-1 p-3 space-y-2">
        <SortableContext items={tasks.map((t) => t.id)} strategy={verticalListSortingStrategy}>
          {tasks.map((task) => (
            <TaskCard key={task.id} task={task} onClick={onCardClick} />
          ))}
        </SortableContext>
      </div>
    </div>
  );
}

// ── Main Board ────────────────────────────────────────────────────────────────
export default function KanbanBoard({ tasks, projectId }) {
  const qc = useQueryClient();
  const [activeTask, setActiveTask] = useState(null);
  const [selectedTask, setSelectedTask] = useState(null);
  const [createStatus, setCreateStatus] = useState(null); // column id to create into

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  );

  const moveMut = useMutation({
    mutationFn: ({ taskId, status }) => updateTask(taskId, { status }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks', projectId] });
      qc.invalidateQueries({ queryKey: ['project', projectId] });
    },
  });

  function handleDragStart(event) {
    const task = tasks.find((t) => t.id === event.active.id);
    setActiveTask(task || null);
  }

  function handleDragEnd(event) {
    setActiveTask(null);
    const { active, over } = event;
    if (!over) return;

    // Determine target column: over.id is either a task id or a column id
    const targetTask = tasks.find((t) => t.id === over.id);
    const targetStatus = targetTask
      ? targetTask.status
      : COLUMNS.find((c) => c.id === over.id)?.id;

    if (!targetStatus) return;

    const draggedTask = tasks.find((t) => t.id === active.id);
    if (!draggedTask || draggedTask.status === targetStatus) return;

    moveMut.mutate({ taskId: draggedTask.id, status: targetStatus });
  }

  const tasksByCol = (colId) => tasks.filter((t) => t.status === colId);

  // When task drawer edits complete, refresh selected task from latest tasks list
  const latestSelected = selectedTask
    ? tasks.find((t) => t.id === selectedTask.id) || selectedTask
    : null;

  return (
    <>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <div className="grid grid-cols-3 gap-4">
          {COLUMNS.map((col) => (
            <Column
              key={col.id}
              column={col}
              tasks={tasksByCol(col.id)}
              onCardClick={(t) => setSelectedTask(t)}
              onAddTask={(status) => setCreateStatus(status)}
            />
          ))}
        </div>

        {/* Drag overlay – ghost card */}
        <DragOverlay>
          {activeTask && (
            <div className="rounded-lg border border-indigo-500 bg-slate-800 p-3 shadow-2xl opacity-90">
              <p className="text-sm text-white font-medium">{activeTask.title}</p>
            </div>
          )}
        </DragOverlay>
      </DndContext>

      {/* Task drawer */}
      {latestSelected && (
        <TaskDrawer
          task={latestSelected}
          projectId={projectId}
          tasks={tasks}
          onClose={() => setSelectedTask(null)}
        />
      )}

      {/* Create task modal */}
      {createStatus && (
        <CreateTaskModal
          projectId={projectId}
          defaultStatus={createStatus}
          onClose={() => setCreateStatus(null)}
        />
      )}
    </>
  );
}
