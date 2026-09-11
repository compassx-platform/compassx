import React, { useState } from 'react';
import {
  MoreVertical,
  Calendar,
  User,
  Tag,
  ArrowRight,
  ArrowLeft,
  Edit2,
  Trash2,
  GripVertical,
  Clock,
  AlertTriangle,
} from 'lucide-react';
import {
  AppTask,
  TaskStatus,
  TASK_COLUMNS,
  PRIORITY_CONFIG,
} from '../../hooks/useAppTasks';

interface TaskCardProps {
  task: AppTask;
  onEdit: (task: AppTask) => void;
  onDelete: (task: AppTask) => void;
  onStatusChange: (taskId: string, newStatus: TaskStatus) => void;
  onDragStart?: (e: React.DragEvent, task: AppTask) => void;
  onDragEnd?: (e: React.DragEvent) => void;
}

export const TaskCard: React.FC<TaskCardProps> = ({
  task,
  onEdit,
  onDelete,
  onStatusChange,
  onDragStart,
  onDragEnd,
}) => {
  const [showMenu, setShowMenu] = useState(false);
  const [isHovered, setIsHovered] = useState(false);

  const priorityMeta = PRIORITY_CONFIG[task.priority] || PRIORITY_CONFIG.medium;
  const currentColumnIdx = TASK_COLUMNS.findIndex((c) => c.id === task.status);
  const prevColumn = currentColumnIdx > 0 ? TASK_COLUMNS[currentColumnIdx - 1] : null;
  const nextColumn =
    currentColumnIdx < TASK_COLUMNS.length - 1 ? TASK_COLUMNS[currentColumnIdx + 1] : null;

  // Due date formatting and overdue check
  let isOverdue = false;
  let formattedDueDate = '';
  if (task.due_date) {
    try {
      const d = new Date(task.due_date);
      formattedDueDate = d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
      });
      isOverdue = d.getTime() < Date.now() && task.status !== 'completed';
    } catch {
      formattedDueDate = task.due_date;
    }
  }

  const handleDragStartInternal = (e: React.DragEvent) => {
    e.dataTransfer.setData('text/plain', JSON.stringify({ taskId: task.id, fromStatus: task.status }));
    e.dataTransfer.effectAllowed = 'move';
    if (onDragStart) onDragStart(e, task);
  };

  return (
    <div
      draggable
      onDragStart={handleDragStartInternal}
      onDragEnd={onDragEnd}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => {
        setIsHovered(false);
        setShowMenu(false);
      }}
      style={{
        background: 'var(--color-surface, #ffffff)',
        borderRadius: 8,
        border: isHovered ? '1px solid var(--color-primary, #2563eb)' : '1px solid var(--color-border, #e2e8f0)',
        padding: '12px 14px',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        boxShadow: isHovered
          ? '0 4px 14px -2px rgba(0, 0, 0, 0.08), 0 2px 6px -1px rgba(0, 0, 0, 0.04)'
          : '0 1px 3px rgba(0, 0, 0, 0.04)',
        cursor: 'grab',
        position: 'relative',
        transition: 'all 0.15s ease',
        userSelect: 'none',
      }}
    >
      {/* Top Header: Priority Badge + Actions */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div
            style={{
              color: 'var(--color-text-muted, #94a3b8)',
              display: 'flex',
              alignItems: 'center',
              cursor: 'grab',
            }}
            title="Drag to move"
          >
            <GripVertical size={14} />
          </div>

          {/* Priority Pill */}
          <span
            style={{
              fontSize: '0.7rem',
              fontWeight: 600,
              padding: '2px 7px',
              borderRadius: 4,
              color: priorityMeta.color,
              background: priorityMeta.bg,
              border: `1px solid ${priorityMeta.border}`,
              letterSpacing: '0.02em',
              textTransform: 'uppercase',
            }}
          >
            {priorityMeta.label}
          </span>
        </div>

        {/* Quick Menu / Options */}
        <div style={{ position: 'relative' }}>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setShowMenu((prev) => !prev);
            }}
            style={{
              border: 'none',
              background: 'transparent',
              color: 'var(--color-text-muted, #64748b)',
              padding: '2px 4px',
              borderRadius: 4,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
            }}
            title="Task actions"
          >
            <MoreVertical size={14} />
          </button>

          {showMenu && (
            <div
              onClick={(e) => e.stopPropagation()}
              style={{
                position: 'absolute',
                top: 24,
                right: 0,
                zIndex: 30,
                background: 'var(--color-surface, #ffffff)',
                border: '1px solid var(--color-border, #e2e8f0)',
                borderRadius: 6,
                boxShadow: '0 8px 24px rgba(0, 0, 0, 0.12)',
                minWidth: 140,
                padding: '4px 0',
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              <button
                type="button"
                onClick={() => {
                  setShowMenu(false);
                  onEdit(task);
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '7px 12px',
                  fontSize: '0.8rem',
                  border: 'none',
                  background: 'transparent',
                  color: 'var(--color-text, #1e293b)',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-surface-hover, #f1f5f9)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
              >
                <Edit2 size={13} /> Edit Task
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowMenu(false);
                  onDelete(task);
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '7px 12px',
                  fontSize: '0.8rem',
                  border: 'none',
                  background: 'transparent',
                  color: '#ef4444',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(239, 68, 68, 0.08)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
              >
                <Trash2 size={13} /> Delete Task
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Task Title */}
      <div
        onClick={() => onEdit(task)}
        style={{
          fontSize: '0.88rem',
          fontWeight: 600,
          color: 'var(--color-text, #0f172a)',
          lineHeight: 1.35,
          cursor: 'pointer',
          wordBreak: 'break-word',
        }}
      >
        {task.title}
      </div>

      {/* Task Description Snippet */}
      {task.description && (
        <div
          onClick={() => onEdit(task)}
          style={{
            fontSize: '0.78rem',
            color: 'var(--color-text-muted, #64748b)',
            lineHeight: 1.4,
            cursor: 'pointer',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {task.description}
        </div>
      )}

      {/* Tags */}
      {task.tags && task.tags.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {task.tags.map((tag, idx) => (
            <span
              key={idx}
              style={{
                fontSize: '0.7rem',
                fontWeight: 500,
                padding: '2px 6px',
                borderRadius: 4,
                background: 'var(--color-surface-hover, #f1f5f9)',
                color: 'var(--color-text-muted, #475569)',
                border: '1px solid var(--color-border, #e2e8f0)',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 3,
              }}
            >
              <Tag size={10} style={{ opacity: 0.7 }} />
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Metadata Row: Assignee, Due Date */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          paddingTop: 6,
          borderTop: '1px solid var(--color-border, #f1f5f9)',
          fontSize: '0.73rem',
          color: 'var(--color-text-muted, #64748b)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {task.assignee ? (
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                color: 'var(--color-text, #334155)',
                fontWeight: 500,
              }}
              title={`Assignee: ${task.assignee}`}
            >
              <div
                style={{
                  width: 18,
                  height: 18,
                  borderRadius: '50%',
                  background: 'var(--color-primary, #2563eb)',
                  color: '#fff',
                  fontSize: '0.62rem',
                  fontWeight: 700,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {task.assignee.slice(0, 1).toUpperCase()}
              </div>
              <span>{task.assignee}</span>
            </div>
          ) : (
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 3, opacity: 0.7 }}>
              <User size={12} />
              <span>Unassigned</span>
            </div>
          )}
        </div>

        {task.due_date && (
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 3,
              color: isOverdue ? '#ef4444' : 'var(--color-text-muted, #64748b)',
              fontWeight: isOverdue ? 600 : 500,
            }}
            title={isOverdue ? 'Overdue!' : `Due ${formattedDueDate}`}
          >
            {isOverdue ? <AlertTriangle size={12} /> : <Calendar size={12} />}
            <span>{formattedDueDate}</span>
          </div>
        )}
      </div>

      {/* Bottom Row: Direct Status Selector + Quick Stage Advance Arrows */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 6,
          marginTop: 2,
        }}
      >
        {/* Status Dropdown */}
        <select
          value={task.status}
          onChange={(e) => onStatusChange(task.id, e.target.value as TaskStatus)}
          onClick={(e) => e.stopPropagation()}
          style={{
            fontSize: '0.72rem',
            fontWeight: 500,
            padding: '3px 6px',
            borderRadius: 4,
            border: '1px solid var(--color-border, #cbd5e1)',
            background: 'var(--color-bg, #ffffff)',
            color: 'var(--color-text, #334155)',
            cursor: 'pointer',
            flex: 1,
            maxWidth: '150px',
          }}
        >
          {TASK_COLUMNS.map((col) => (
            <option key={col.id} value={col.id}>
              {col.title}
            </option>
          ))}
        </select>

        {/* Stage Shift Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
          {prevColumn && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onStatusChange(task.id, prevColumn.id);
              }}
              style={{
                border: '1px solid var(--color-border, #cbd5e1)',
                background: 'var(--color-surface, #ffffff)',
                color: 'var(--color-text-muted, #64748b)',
                borderRadius: 4,
                padding: '2px 5px',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
              }}
              title={`Move back to ${prevColumn.title}`}
            >
              <ArrowLeft size={11} />
            </button>
          )}

          {nextColumn && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onStatusChange(task.id, nextColumn.id);
              }}
              style={{
                border: '1px solid var(--color-primary, #2563eb)',
                background: 'rgba(37, 99, 235, 0.08)',
                color: 'var(--color-primary, #2563eb)',
                borderRadius: 4,
                padding: '2px 5px',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
              }}
              title={`Move forward to ${nextColumn.title}`}
            >
              <ArrowRight size={11} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
