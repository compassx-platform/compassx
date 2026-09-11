import React, { useState } from 'react';
import {
  Plus,
  ListOrdered,
  PlayCircle,
  FlaskConical,
  Rocket,
  CheckCircle2,
  Inbox,
} from 'lucide-react';
import {
  AppTask,
  ColumnConfig,
  TaskStatus,
} from '../../hooks/useAppTasks';
import { TaskCard } from './TaskCard';

interface KanbanColumnProps {
  column: ColumnConfig;
  tasks: AppTask[];
  onAddTask: (status: TaskStatus) => void;
  onEditTask: (task: AppTask) => void;
  onDeleteTask: (task: AppTask) => void;
  onStatusChange: (taskId: string, newStatus: TaskStatus) => void;
  onDropTask: (taskId: string, targetStatus: TaskStatus) => void;
}

const COLUMN_ICONS: Record<string, React.ReactNode> = {
  ListOrdered: <ListOrdered size={15} />,
  PlayCircle: <PlayCircle size={15} />,
  FlaskConical: <FlaskConical size={15} />,
  Rocket: <Rocket size={15} />,
  CheckCircle2: <CheckCircle2 size={15} />,
};

export const KanbanColumn: React.FC<KanbanColumnProps> = ({
  column,
  tasks,
  onAddTask,
  onEditTask,
  onDeleteTask,
  onStatusChange,
  onDropTask,
}) => {
  const [isDragOver, setIsDragOver] = useState(false);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    if (!isDragOver) setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    // Only deactivate if leaving this column container
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setIsDragOver(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    try {
      const dataStr = e.dataTransfer.getData('text/plain');
      if (dataStr) {
        const { taskId } = JSON.parse(dataStr);
        if (taskId) {
          onDropTask(taskId, column.id);
        }
      }
    } catch {
      // Ignore parse failure
    }
  };

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      style={{
        display: 'flex',
        flexDirection: 'column',
        minWidth: '270px',
        maxWidth: '340px',
        flex: '1 1 0',
        background: isDragOver
          ? 'var(--color-surface-hover, #f1f5f9)'
          : 'var(--color-bg-secondary, rgba(0, 0, 0, 0.02))',
        border: isDragOver
          ? `2px dashed ${column.badgeColor}`
          : '1px solid var(--color-border, #e2e8f0)',
        borderRadius: 10,
        height: 'calc(100vh - 280px)',
        minHeight: '520px',
        transition: 'all 0.15s ease',
        overflow: 'hidden',
      }}
    >
      {/* Column Header */}
      <div
        style={{
          padding: '12px 14px',
          borderBottom: '1px solid var(--color-border, #e2e8f0)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: column.headerBg,
          borderTop: `3px solid ${column.badgeColor}`,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ color: column.badgeColor, display: 'flex', alignItems: 'center' }}>
            {COLUMN_ICONS[column.iconName] || <ListOrdered size={15} />}
          </div>
          <span
            style={{
              fontSize: '0.85rem',
              fontWeight: 600,
              color: 'var(--color-text, #0f172a)',
              letterSpacing: '-0.01em',
            }}
          >
            {column.title}
          </span>
          <span
            style={{
              fontSize: '0.72rem',
              fontWeight: 700,
              padding: '1px 6px',
              borderRadius: 999,
              background: column.badgeColor,
              color: '#ffffff',
              minWidth: '18px',
              textAlign: 'center',
            }}
          >
            {tasks.length}
          </span>
        </div>

        {/* Quick Add Button in Header */}
        <button
          type="button"
          onClick={() => onAddTask(column.id)}
          style={{
            border: 'none',
            background: 'transparent',
            color: 'var(--color-text-muted, #64748b)',
            padding: 4,
            borderRadius: 4,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'background 0.15s ease, color 0.15s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(0, 0, 0, 0.06)';
            e.currentTarget.style.color = column.badgeColor;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent';
            e.currentTarget.style.color = 'var(--color-text-muted, #64748b)';
          }}
          title={`Add task to ${column.title}`}
        >
          <Plus size={15} />
        </button>
      </div>

      {/* Cards List Area */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '12px 10px',
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
        }}
        className="sidebar-hover-scrollbar"
      >
        {tasks.length === 0 ? (
          <div
            style={{
              height: '100%',
              minHeight: 120,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              color: 'var(--color-text-muted, #94a3b8)',
              fontSize: '0.8rem',
              border: '1px dashed var(--color-border, #cbd5e1)',
              borderRadius: 8,
              padding: 16,
              textAlign: 'center',
              background: 'rgba(0, 0, 0, 0.01)',
            }}
          >
            <Inbox size={22} style={{ opacity: 0.5 }} />
            <span>No tasks in {column.title.toLowerCase()}</span>
            <button
              type="button"
              onClick={() => onAddTask(column.id)}
              style={{
                fontSize: '0.75rem',
                fontWeight: 600,
                color: 'var(--color-primary, #2563eb)',
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                padding: '2px 6px',
                borderRadius: 4,
              }}
            >
              + Add Task
            </button>
          </div>
        ) : (
          tasks.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              onEdit={onEditTask}
              onDelete={onDeleteTask}
              onStatusChange={onStatusChange}
            />
          ))
        )}
      </div>

      {/* Bottom Quick Add Card Footer */}
      <div
        style={{
          padding: '8px 10px',
          borderTop: '1px solid var(--color-border, #e2e8f0)',
          background: 'var(--color-surface, #ffffff)',
        }}
      >
        <button
          type="button"
          onClick={() => onAddTask(column.id)}
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 6,
            padding: '7px 10px',
            fontSize: '0.8rem',
            fontWeight: 500,
            color: 'var(--color-text-muted, #64748b)',
            background: 'transparent',
            border: '1px dashed var(--color-border, #cbd5e1)',
            borderRadius: 6,
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = 'var(--color-primary, #2563eb)';
            e.currentTarget.style.color = 'var(--color-primary, #2563eb)';
            e.currentTarget.style.background = 'rgba(37, 99, 235, 0.04)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = 'var(--color-border, #cbd5e1)';
            e.currentTarget.style.color = 'var(--color-text-muted, #64748b)';
            e.currentTarget.style.background = 'transparent';
          }}
        >
          <Plus size={13} />
          <span>Add Task</span>
        </button>
      </div>
    </div>
  );
};
