/**
 * Task graph canvas using @xyflow/react (XY Flow v12).
 * Renders task nodes with edges based on depends_on relationships.
 * In editor mode: nodes are clickable/selectable; toolbar button shown.
 * In run-context mode: nodes show status colors, canvas is read-only.
 */
import { useCallback, useEffect, useMemo, useRef } from 'react';
import {
  ReactFlow, Background, Controls, MiniMap,
  Handle, Position,
  useNodesState, useEdgesState,
  type Node, type Edge, type NodeProps,
  MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Code2, Database, LayoutDashboard, Plus } from 'lucide-react';
import type { TaskDefinition, TaskRun, TaskType } from '../lib/jobsTypes';
import StatusPill from './StatusPill';

const TYPE_ICONS: Record<TaskType, React.ReactNode> = {
  notebook:          <Code2 size={14} />,
  query:             <Database size={14} />,
  dashboard_refresh: <LayoutDashboard size={14} />,
};

const STATE_COLORS: Record<string, string> = {
  success:         '#16a34a',
  failed:          '#dc2626',
  running:         '#2563eb',
  queued:          '#6b7280',
  up_for_retry:    '#d97706',
  upstream_failed: '#ef4444',
  skipped:         '#9ca3af',
};

// ── Custom node ────────────────────────────────────────────────────────────────

function TaskNode({ data, selected }: NodeProps) {
  const td = data.task as TaskDefinition;
  const tr = data.taskRun as TaskRun | undefined;
  const isEditor = (data.isEditor as boolean) ?? true;
  const onEdit = data.onEdit as ((key: string) => void) | undefined;

  const stateColor = tr ? (STATE_COLORS[tr.state] ?? 'var(--color-border)') : 'var(--color-primary)';

  return (
    <div
      className={`db-node ${isEditor ? 'db-node-editor' : ''} ${selected ? 'db-node-selected' : ''}`}
      style={{ borderTop: `3px solid ${stateColor}`, cursor: isEditor ? 'pointer' : 'default' }}
    >
      <Handle type="target" position={Position.Left} className="db-handle db-handle-target" />

      <div className="db-node-header">
        <span className="db-node-title" title={td?.name ?? td?.task_key}>{td?.name ?? td?.task_key}</span>
        <span className="db-node-header-icon" style={{ color: 'var(--color-text-muted)' }}>
          {td?.task_type ? TYPE_ICONS[td.task_type] : null}
        </span>
      </div>

      <div className="db-node-subtitle">
        {tr ? (
          <StatusPill state={tr.state} size="sm" />
        ) : (
          <span style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)' }}>
            {td?.task_type ? td.task_type.replace('_', ' ') : 'task'}
          </span>
        )}
      </div>

      {td.target_ref && (
        <div className="db-node-meta-row">
          <span className="db-node-meta-text" title={td.target_ref}>{td.target_ref}</span>
        </div>
      )}

      <Handle type="source" position={Position.Right} className="db-handle db-handle-source" />
    </div>
  );
}

const nodeTypes = { taskNode: TaskNode };

// ── Layout helper (left-to-right topological) ─────────────────────────────────

function layoutNodes(tasks: TaskDefinition[]): { id: string; x: number; y: number }[] {
  const levels: Record<string, number> = {};

  function getLevel(key: string, visited = new Set<string>()): number {
    if (levels[key] !== undefined) return levels[key];
    if (visited.has(key)) return 0;
    visited.add(key);
    const task = tasks.find((t) => t.task_key === key);
    const deps = task?.depends_on ?? [];
    if (!task || deps.length === 0) { levels[key] = 0; return 0; }
    const maxDep = Math.max(...deps.map((d) => getLevel(d, visited)));
    levels[key] = maxDep + 1;
    return levels[key];
  }

  tasks.forEach((t) => getLevel(t.task_key));

  const byLevel: Record<number, string[]> = {};
  tasks.forEach((t) => {
    const l = levels[t.task_key] ?? 0;
    if (!byLevel[l]) byLevel[l] = [];
    byLevel[l].push(t.task_key);
  });

  const NODE_W = 240, NODE_H = 110, H_GAP = 80, V_GAP = 28;
  const result: { id: string; x: number; y: number }[] = [];

  Object.entries(byLevel).forEach(([lvl, keys]) => {
    const x = parseInt(lvl) * (NODE_W + H_GAP) + 40;
    const totalH = keys.length * (NODE_H + V_GAP) - V_GAP;
    keys.forEach((key, i) => {
      result.push({ id: key, x, y: i * (NODE_H + V_GAP) - totalH / 2 + 120 });
    });
  });

  return result;
}

// ── Main component ─────────────────────────────────────────────────────────────

interface Props {
  tasks: TaskDefinition[];
  taskRuns?: TaskRun[];
  isEditor?: boolean;
  onTaskClick?: (taskKey: string) => void;
  onAddTask?: () => void;
}

export default function TaskGraphCanvas({
  tasks,
  taskRuns = [],
  isEditor = true,
  onTaskClick,
  onAddTask,
}: Props) {
  const taskRunMap = useMemo(() => {
    const m: Record<string, TaskRun> = {};
    taskRuns.forEach((tr) => { m[tr.task_key] = tr; });
    return m;
  }, [taskRuns]);

  const onClickRef = useRef(onTaskClick);
  useEffect(() => {
    onClickRef.current = onTaskClick;
  });

  const positions = useMemo(() => layoutNodes(tasks), [tasks]);
  const posMap = useMemo(() => {
    const m: Record<string, { x: number; y: number }> = {};
    positions.forEach((p) => { m[p.id] = { x: p.x, y: p.y }; });
    return m;
  }, [positions]);

  const initialNodes: Node[] = useMemo(() => tasks.map((t) => ({
    id: t.task_key,
    type: 'taskNode',
    position: posMap[t.task_key] ?? { x: 40, y: 40 },
    data: {
      task: t,
      taskRun: taskRunMap[t.task_key],
      isEditor,
      onEdit: (key: string) => onClickRef.current?.(key),
    },
    selectable: isEditor,
    draggable: isEditor,
  })), [tasks, posMap, taskRunMap, isEditor]);

  const initialEdges: Edge[] = useMemo(() => {
    const edges: Edge[] = [];
    tasks.forEach((t) => {
      (t.depends_on ?? []).forEach((dep) => {
        edges.push({
          id: `${dep}->${t.task_key}`,
          source: dep,
          target: t.task_key,
          markerEnd: {
            type: MarkerType.ArrowClosed, width: 16, height: 16,
            color: 'var(--color-border-strong, #94a3b8)',
          },
          style: { stroke: 'var(--color-border-strong, #94a3b8)', strokeWidth: 1.5 },
          animated: taskRunMap[t.task_key]?.state === 'running',
        });
      });
    });
    return edges;
  }, [tasks, taskRunMap]);

  const tasksKey = useMemo(() => {
    return tasks.map((t) => `${t.task_key}:${(t.depends_on ?? []).join(',')}:${t.name}`).join('|');
  }, [tasks]);

  const taskRunsKey = useMemo(() => {
    return taskRuns.map((tr) => `${tr.task_run_id}:${tr.state}`).join('|');
  }, [taskRuns]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Sync state only when task keys or task runs structure actually changes
  useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tasksKey, taskRunsKey]);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    if (isEditor && onClickRef.current) onClickRef.current(node.id);
  }, [isEditor]);

  if (tasks.length === 0) {
    return (
      <div style={{
        flex: 1, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', gap: 14,
        color: 'var(--color-text-muted)', fontSize: '0.875rem',
        width: '100%', height: '100%', minHeight: 350,
      }}>
        <p style={{ margin: 0 }}>No tasks yet. Add your first task to get started.</p>
        {isEditor && onAddTask && (
          <button className="btn btn-primary" onClick={onAddTask}>
            <Plus size={15} /> Add task
          </button>
        )}
      </div>
    );
  }

  return (
    <div
      style={{
        flex: 1, minHeight: 350, width: '100%', height: '100%',
        display: 'flex', flexDirection: 'column', position: 'relative',
        background: 'var(--color-bg-secondary, #f8fafc)',
        border: '1px solid var(--color-border)',
        borderRadius: '8px',
        overflow: 'hidden',
        boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.04)',
      }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={isEditor ? onNodesChange : undefined}
        onEdgesChange={isEditor ? onEdgesChange : undefined}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 1.4, maxZoom: 0.75 }}
        nodesDraggable={isEditor}
        nodesConnectable={false}
        elementsSelectable={isEditor}
        panOnDrag
        zoomOnScroll
        minZoom={0.2}
        maxZoom={2.5}
        style={{ background: 'transparent', width: '100%', height: '100%' }}
      >
        <Background color="#cbd5e1" gap={8} size={1.2} />
        <Controls showInteractive={false} />
        <MiniMap
          nodeColor={(n) => {
            const tr = taskRunMap[(n as Node).id];
            return tr ? (STATE_COLORS[tr.state] ?? '#94a3b8') : 'var(--color-primary)';
          }}
          maskColor="rgba(0,0,0,0.04)"
        />
      </ReactFlow>
    </div>
  );
}
