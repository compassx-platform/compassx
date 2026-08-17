import { useState, useEffect } from 'react';
import { X, Plus, Trash2, ChevronDown, ChevronUp } from 'lucide-react';
import type { TaskDefinition, TaskType } from '../lib/jobsTypes';

interface Props {
  task?: TaskDefinition;
  allTaskKeys: string[];
  onSave: (task: TaskDefinition) => void;
  onCancel: () => void;
  onDelete?: () => void;
}

const TASK_TYPES: { value: TaskType; label: string }[] = [
  { value: 'notebook',          label: 'Notebook'          },
  { value: 'query',             label: 'SQL Query (adapter required)'         },
  { value: 'dashboard_refresh', label: 'Dashboard Refresh (adapter required)' },
];

function slugify(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
}

export default function TaskDrawer({ task, allTaskKeys, onSave, onCancel, onDelete }: Props) {
  const isNew = !task;
  const [name, setName] = useState(task?.name ?? '');
  const [taskKey, setTaskKey] = useState(task?.task_key ?? '');
  const [taskType, setTaskType] = useState<TaskType>(task?.task_type ?? 'notebook');
  const [targetRef, setTargetRef] = useState(task?.target_ref ?? '');
  const defaultDeps = isNew && allTaskKeys.length > 0
    ? [allTaskKeys[allTaskKeys.length - 1]]
    : (task?.depends_on ?? []);

  const [dependsOn, setDependsOn] = useState<string[]>(defaultDeps);
  const [params, setParams] = useState<{ k: string; v: string }[]>(
    Object.entries(task?.parameters ?? {}).map(([k, v]) => ({ k, v: String(v) }))
  );
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [retryCount, setRetryCount] = useState(task?.retry_count ?? 0);
  const [retryDelay, setRetryDelay] = useState(task?.retry_delay_seconds ?? 300);
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Auto-slug task key from name when creating new
  useEffect(() => {
    if (isNew && name) setTaskKey(slugify(name));
  }, [isNew, name]);

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (!name.trim()) e.name = 'Task name is required';
    if (!taskKey.trim()) e.taskKey = 'Task key is required';
    if (/[^a-z0-9_]/.test(taskKey)) e.taskKey = 'Task key: lowercase letters, digits, underscores only';
    // Circular dependency check (simple)
    if (dependsOn.includes(taskKey)) e.dependsOn = 'A task cannot depend on itself';
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  function handleSave() {
    if (!validate()) return;
    const parameters: Record<string, unknown> = {};
    params.forEach(({ k, v }) => { if (k.trim()) parameters[k.trim()] = v; });
    onSave({
      task_key: taskKey,
      name,
      task_type: taskType,
      target_ref: targetRef || undefined,
      parameters,
      depends_on: dependsOn,
      retry_count: retryCount || undefined,
      retry_delay_seconds: retryDelay || undefined,
    });
  }

  const otherKeys = allTaskKeys.filter((k) => k !== taskKey);

  return (
    <div className="config-panel">
      {/* Header */}
      <div className="config-panel-header">
        <span className="config-panel-title">{isNew ? 'Add task' : 'Edit task'}</span>
        <div style={{ display: 'flex', gap: 4 }}>
          {!isNew && onDelete && (
            <button type="button" className="btn-icon btn-icon-danger" onClick={onDelete} title="Delete task">
              <Trash2 size={15} />
            </button>
          )}
          <button type="button" className="btn-icon" onClick={onCancel}><X size={16} /></button>
        </div>
      </div>

      {/* Body */}
      <div className="config-panel-body">
        {/* Name */}
        <div className="form-field">
          <label className="form-label">Task name *</label>
          <input
            type="text" className="form-input" placeholder="e.g. Ingest data"
            value={name} onChange={(e) => setName(e.target.value)}
            style={errors.name ? { borderColor: 'var(--color-danger)' } : {}}
          />
          {errors.name && <span style={{ fontSize: '0.72rem', color: 'var(--color-danger)' }}>{errors.name}</span>}
        </div>

        {/* Task key (advanced collapsed by default for new tasks) */}
        <div className="form-field">
          <label className="form-label">Task key</label>
          <input
            type="text" className="form-input" placeholder="ingest_data"
            value={taskKey} onChange={(e) => setTaskKey(e.target.value)}
            style={{ fontFamily: 'monospace', ...(errors.taskKey ? { borderColor: 'var(--color-danger)' } : {}) }}
          />
          <span className="form-hint">Stable identifier used for dependency wiring. Lowercase, underscores only.</span>
          {errors.taskKey && <span style={{ fontSize: '0.72rem', color: 'var(--color-danger)' }}>{errors.taskKey}</span>}
        </div>

        {/* Type */}
        <div className="form-field">
          <label className="form-label">Task type</label>
          <select className="form-input" value={taskType} onChange={(e) => setTaskType(e.target.value as TaskType)}>
            {TASK_TYPES.map((t) => (
              <option key={t.value} value={t.value} disabled={t.value !== 'notebook'}>
                {t.label}
              </option>
            ))}
          </select>
        </div>

        {/* Target */}
        <div className="form-field">
          <label className="form-label">
            {taskType === 'notebook' ? 'Notebook path' : taskType === 'query' ? 'Query ID / name' : 'Dashboard ID'}
          </label>
          <input
            type="text" className="form-input"
            placeholder={taskType === 'notebook' ? '/notebooks/my_notebook.ipynb' : 'ID or name'}
            value={targetRef} onChange={(e) => setTargetRef(e.target.value)}
          />
        </div>

        {/* Depends on */}
        {otherKeys.length > 0 && (
          <div className="form-field">
            <label className="form-label">Depends on (Upstream tasks)</label>
            
            {dependsOn.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
                {dependsOn.map((depKey) => (
                  <span
                    key={depKey}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: 4,
                      padding: '2px 8px', borderRadius: 4, fontSize: '0.75rem',
                      background: 'rgba(27,110,243,0.12)', color: 'var(--color-primary)',
                      border: '1px solid rgba(27,110,243,0.2)', fontWeight: 600,
                    }}
                  >
                    <code>{depKey}</code>
                    <button
                      type="button"
                      style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: 'var(--color-primary)', display: 'flex', alignItems: 'center' }}
                      onClick={() => setDependsOn(dependsOn.filter((d) => d !== depKey))}
                      title={`Remove connection to ${depKey}`}
                    >
                      <X size={12} />
                    </button>
                  </span>
                ))}
              </div>
            )}

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {otherKeys.map((k) => (
                <label key={k} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: '0.8rem', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={dependsOn.includes(k)}
                    onChange={(e) => {
                      setDependsOn(e.target.checked ? [...dependsOn, k] : dependsOn.filter((d) => d !== k));
                    }}
                    style={{ accentColor: 'var(--color-primary)' }}
                  />
                  <code style={{ fontSize: '0.75rem' }}>{k}</code>
                </label>
              ))}
            </div>
            {errors.dependsOn && <span style={{ fontSize: '0.72rem', color: 'var(--color-danger)' }}>{errors.dependsOn}</span>}
          </div>
        )}

        {/* Parameters */}
        <div className="form-field">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
            <label className="form-label" style={{ margin: 0 }}>Parameters</label>
            <button
              type="button" className="btn btn-sm btn-secondary"
              onClick={() => setParams([...params, { k: '', v: '' }])}
            >
              <Plus size={12} /> Add
            </button>
          </div>
          {params.length === 0 && <span className="form-hint">No parameters defined.</span>}
          {params.map((p, i) => (
            <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
              <input
                type="text" className="form-input" placeholder="key"
                value={p.k} onChange={(e) => { const n = [...params]; n[i].k = e.target.value; setParams(n); }}
                style={{ flex: 1, fontFamily: 'monospace' }}
              />
              <input
                type="text" className="form-input" placeholder="value"
                value={p.v} onChange={(e) => { const n = [...params]; n[i].v = e.target.value; setParams(n); }}
                style={{ flex: 2 }}
              />
              <button type="button" className="btn-icon btn-icon-danger"
                onClick={() => setParams(params.filter((_, j) => j !== i))}>
                <Trash2 size={13} />
              </button>
            </div>
          ))}
        </div>

        {/* Advanced: retry */}
        <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: 8 }}>
          <button
            type="button"
            onClick={() => setAdvancedOpen(!advancedOpen)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--color-text-muted)', fontSize: '0.78rem', fontFamily: 'var(--font-family)',
            }}
          >
            {advancedOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            Retry policy override
          </button>
          {advancedOpen && (
            <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div className="form-field">
                <label className="form-label">Retry count</label>
                <input type="number" className="form-input" min={0} max={10}
                  value={retryCount} onChange={(e) => setRetryCount(parseInt(e.target.value) || 0)} />
              </div>
              <div className="form-field">
                <label className="form-label">Retry delay (seconds)</label>
                <input type="number" className="form-input" min={0}
                  value={retryDelay} onChange={(e) => setRetryDelay(parseInt(e.target.value) || 0)} />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="config-panel-footer">
        <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
        <button type="button" className="btn btn-primary" onClick={handleSave}>Save task</button>
      </div>
    </div>
  );
}
