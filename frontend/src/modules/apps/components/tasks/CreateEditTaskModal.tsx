import React, { useState, useEffect } from 'react';
import { X, Plus, Tag, Loader2, Calendar, AlertCircle } from 'lucide-react';
import {
  AppTask,
  CreateAppTaskPayload,
  UpdateAppTaskPayload,
  TaskStatus,
  TaskPriority,
  TASK_COLUMNS,
  PRIORITY_CONFIG,
} from '../../hooks/useAppTasks';

interface CreateEditTaskModalProps {
  isOpen: boolean;
  onClose: () => void;
  task?: AppTask | null;
  defaultStatus?: TaskStatus;
  onSubmit: (payload: CreateAppTaskPayload | UpdateAppTaskPayload) => Promise<void>;
}

const COMMON_TAG_SUGGESTIONS = ['Feature', 'Bug', 'Enhancement', 'UI/UX', 'Backend', 'API', 'Hotfix', 'Docs', 'Refactor'];

export const CreateEditTaskModal: React.FC<CreateEditTaskModalProps> = ({
  isOpen,
  onClose,
  task,
  defaultStatus = 'backlog',
  onSubmit,
}) => {
  const isEditing = Boolean(task);

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [status, setStatus] = useState<TaskStatus>(defaultStatus);
  const [priority, setPriority] = useState<TaskPriority>('medium');
  const [tags, setTags] = useState<string[]>([]);
  const [newTagInput, setNewTagInput] = useState('');
  const [assignee, setAssignee] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (task) {
      setTitle(task.title || '');
      setDescription(task.description || '');
      setStatus(task.status || 'backlog');
      setPriority(task.priority || 'medium');
      setTags(task.tags || []);
      setAssignee(task.assignee || '');
      if (task.due_date) {
        try {
          const d = new Date(task.due_date);
          setDueDate(d.toISOString().split('T')[0]);
        } catch {
          setDueDate('');
        }
      } else {
        setDueDate('');
      }
    } else {
      setTitle('');
      setDescription('');
      setStatus(defaultStatus);
      setPriority('medium');
      setTags([]);
      setAssignee('');
      setDueDate('');
    }
    setErrorMsg(null);
  }, [task, defaultStatus, isOpen]);

  if (!isOpen) return null;

  const handleAddTag = (tagToAdd: string) => {
    const trimmed = tagToAdd.trim();
    if (!trimmed) return;
    if (!tags.includes(trimmed)) {
      setTags((prev) => [...prev, trimmed]);
    }
    setNewTagInput('');
  };

  const handleRemoveTag = (tagToRemove: string) => {
    setTags((prev) => prev.filter((t) => t !== tagToRemove));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setErrorMsg('Task title is required');
      return;
    }

    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      const payload: CreateAppTaskPayload = {
        title: title.trim(),
        description: description.trim() || null,
        status,
        priority,
        tags: tags.length > 0 ? tags : [],
        assignee: assignee.trim() || null,
        due_date: dueDate ? new Date(dueDate).toISOString() : null,
      };
      await onSubmit(payload);
      onClose();
    } catch (err: any) {
      setErrorMsg(err?.response?.data?.detail || err?.message || 'Failed to save task');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: 'rgba(15, 23, 42, 0.65)',
        backdropFilter: 'blur(3px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'var(--color-surface, #ffffff)',
          border: '1px solid var(--color-border, #cbd5e1)',
          borderRadius: 12,
          width: '100%',
          maxWidth: '560px',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2), 0 10px 10px -5px rgba(0, 0, 0, 0.1)',
          display: 'flex',
          flexDirection: 'column',
          maxHeight: '90vh',
          overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--color-border, #e2e8f0)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ fontWeight: 600, fontSize: '1.05rem', color: 'var(--color-text, #0f172a)' }}>
            {isEditing ? 'Edit Task' : 'Create New Task'}
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{
              border: 'none',
              background: 'transparent',
              color: 'var(--color-text-muted, #64748b)',
              cursor: 'pointer',
              padding: 4,
              borderRadius: 4,
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body / Form */}
        <form onSubmit={handleSubmit} style={{ overflowY: 'auto', padding: '20px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          {errorMsg && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '10px 12px',
                borderRadius: 6,
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                color: '#ef4444',
                fontSize: '0.82rem',
              }}
            >
              <AlertCircle size={15} />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Title */}
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text, #334155)', marginBottom: 6 }}>
              Task Title <span style={{ color: '#ef4444' }}>*</span>
            </label>
            <input
              type="text"
              className="input-field"
              placeholder="e.g. Implement OAuth2 callback handler"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              autoFocus
              style={{
                width: '100%',
                padding: '8px 12px',
                fontSize: '0.875rem',
                borderRadius: 6,
                border: '1px solid var(--color-border, #cbd5e1)',
                background: 'var(--color-bg, #ffffff)',
                color: 'var(--color-text, #0f172a)',
              }}
            />
          </div>

          {/* Description */}
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text, #334155)', marginBottom: 6 }}>
              Description
            </label>
            <textarea
              className="input-field"
              rows={3}
              placeholder="Provide context, acceptance criteria, or implementation details..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                fontSize: '0.85rem',
                borderRadius: 6,
                border: '1px solid var(--color-border, #cbd5e1)',
                background: 'var(--color-bg, #ffffff)',
                color: 'var(--color-text, #0f172a)',
                fontFamily: 'inherit',
                resize: 'vertical',
              }}
            />
          </div>

          {/* Row: Status & Priority */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            {/* Status */}
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text, #334155)', marginBottom: 6 }}>
                Stage / Column
              </label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as TaskStatus)}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  fontSize: '0.85rem',
                  borderRadius: 6,
                  border: '1px solid var(--color-border, #cbd5e1)',
                  background: 'var(--color-bg, #ffffff)',
                  color: 'var(--color-text, #0f172a)',
                  cursor: 'pointer',
                }}
              >
                {TASK_COLUMNS.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title}
                  </option>
                ))}
              </select>
            </div>

            {/* Priority */}
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text, #334155)', marginBottom: 6 }}>
                Priority
              </label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value as TaskPriority)}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  fontSize: '0.85rem',
                  borderRadius: 6,
                  border: '1px solid var(--color-border, #cbd5e1)',
                  background: 'var(--color-bg, #ffffff)',
                  color: 'var(--color-text, #0f172a)',
                  cursor: 'pointer',
                }}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </div>
          </div>

          {/* Row: Assignee & Due Date */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text, #334155)', marginBottom: 6 }}>
                Assignee
              </label>
              <input
                type="text"
                className="input-field"
                placeholder="e.g. Alex, Team Lead"
                value={assignee}
                onChange={(e) => setAssignee(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  fontSize: '0.85rem',
                  borderRadius: 6,
                  border: '1px solid var(--color-border, #cbd5e1)',
                  background: 'var(--color-bg, #ffffff)',
                  color: 'var(--color-text, #0f172a)',
                }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text, #334155)', marginBottom: 6 }}>
                Due Date
              </label>
              <input
                type="date"
                className="input-field"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  fontSize: '0.85rem',
                  borderRadius: 6,
                  border: '1px solid var(--color-border, #cbd5e1)',
                  background: 'var(--color-bg, #ffffff)',
                  color: 'var(--color-text, #0f172a)',
                }}
              />
            </div>
          </div>

          {/* Tags */}
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text, #334155)', marginBottom: 6 }}>
              Tags & Labels
            </label>
            <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
              <input
                type="text"
                placeholder="Type tag name..."
                value={newTagInput}
                onChange={(e) => setNewTagInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleAddTag(newTagInput);
                  }
                }}
                style={{
                  flex: 1,
                  padding: '6px 10px',
                  fontSize: '0.82rem',
                  borderRadius: 6,
                  border: '1px solid var(--color-border, #cbd5e1)',
                  background: 'var(--color-bg, #ffffff)',
                  color: 'var(--color-text, #0f172a)',
                }}
              />
              <button
                type="button"
                className="btn btn-outline"
                style={{ padding: '6px 12px', fontSize: '0.8rem' }}
                onClick={() => handleAddTag(newTagInput)}
              >
                <Plus size={13} /> Add
              </button>
            </div>

            {/* Existing tags pills */}
            {tags.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
                {tags.map((t, idx) => (
                  <span
                    key={idx}
                    style={{
                      fontSize: '0.75rem',
                      fontWeight: 500,
                      padding: '2px 8px',
                      borderRadius: 999,
                      background: 'rgba(37, 99, 235, 0.1)',
                      color: 'var(--color-primary, #2563eb)',
                      border: '1px solid rgba(37, 99, 235, 0.25)',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 4,
                    }}
                  >
                    <Tag size={10} />
                    {t}
                    <X
                      size={12}
                      style={{ cursor: 'pointer', marginLeft: 2 }}
                      onClick={() => handleRemoveTag(t)}
                    />
                  </span>
                ))}
              </div>
            )}

            {/* Suggestions */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center' }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--color-text-muted, #94a3b8)' }}>Quick add:</span>
              {COMMON_TAG_SUGGESTIONS.filter((s) => !tags.includes(s)).slice(0, 6).map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => handleAddTag(suggestion)}
                  style={{
                    fontSize: '0.7rem',
                    padding: '1px 6px',
                    borderRadius: 4,
                    border: '1px dashed var(--color-border, #cbd5e1)',
                    background: 'transparent',
                    color: 'var(--color-text-muted, #64748b)',
                    cursor: 'pointer',
                  }}
                >
                  +{suggestion}
                </button>
              ))}
            </div>
          </div>

          {/* Modal Actions */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-end',
              gap: 10,
              paddingTop: 14,
              borderTop: '1px solid var(--color-border, #e2e8f0)',
              marginTop: 6,
            }}
          >
            <button
              type="button"
              className="btn btn-outline"
              onClick={onClose}
              disabled={isSubmitting}
              style={{ padding: '7px 16px', fontSize: '0.85rem' }}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={isSubmitting}
              style={{
                padding: '7px 20px',
                fontSize: '0.85rem',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              {isSubmitting && <Loader2 size={14} className="spin" />}
              <span>{isEditing ? 'Save Changes' : 'Create Task'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
