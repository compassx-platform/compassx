import React, { useState } from 'react';
import { ListChecks, ChevronRight, Plus } from 'lucide-react';
import { agentRuntimeApi, type AgentRuntimeTask } from '@/modules/agents/agentRuntimeApi';

const STAGE_LABEL: Record<string, string> = {
  draft: 'Draft',
  waiting: 'Waiting',
  ready: 'Ready',
  in_progress: 'In progress',
  in_review: 'In review',
  done: 'Done',
  cancelled: 'Cancelled',
};

function errorDetail(err: any, fallback: string) {
  return err?.response?.data?.detail || err?.message || fallback;
}

const fieldStyle: React.CSSProperties = {
  width: '100%',
  boxSizing: 'border-box',
  border: '1px solid #e4e4e7',
  borderRadius: 6,
  padding: '8px 10px',
  fontSize: '0.84rem',
  color: '#1c1c1f',
  background: '#ffffff',
};

const buttonStyle: React.CSSProperties = {
  border: '1px solid #e4e4e7',
  background: '#ffffff',
  color: '#1c1c1f',
  borderRadius: 6,
  padding: '6px 10px',
  fontSize: '0.78rem',
  fontWeight: 600,
  cursor: 'pointer',
};

export function AgentRuntimeTaskList({
  tasks,
  selectedId,
  collapsed = false,
  onToggle,
  onSelect,
  onCreate,
}: {
  tasks: AgentRuntimeTask[];
  selectedId?: string | null;
  collapsed?: boolean;
  onToggle?: () => void;
  onSelect: (task: AgentRuntimeTask) => void;
  onCreate: () => void;
}) {
  return (
    <div>
      <div className="agent-runtime-section" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingRight: 2 }}>
        <button
          type="button"
          aria-expanded={!collapsed}
          onClick={onToggle}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 2, padding: '10px 4px 4px 2px', border: 'none', background: 'transparent', color: '#8a8a93', fontSize: '0.75rem', fontWeight: 500, cursor: 'pointer' }}
        >
          <ChevronRight size={14} style={{ transform: collapsed ? undefined : 'rotate(90deg)', color: '#71717a' }} />
          Tasks
        </button>
        <button type="button" aria-label="New task" title="New task" onClick={onCreate} style={{ border: 'none', background: 'transparent', color: '#3f3f46', cursor: 'pointer', padding: 4, display: 'inline-flex' }}>
          <Plus size={14} />
        </button>
      </div>
      {!collapsed && tasks.length === 0 && (
        <div style={{ padding: '2px 8px 8px', color: '#8a8a93', fontSize: '0.75rem' }}>File work here until it is ready to run.</div>
      )}
      {!collapsed && tasks.map((task) => (
        <button
          key={task.id}
          type="button"
          onClick={() => onSelect(task)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            width: '100%',
            border: 'none',
            borderRadius: 6,
            padding: '6px 8px',
            background: selectedId === task.id ? '#ececef' : 'transparent',
            color: '#1c1c1f',
            cursor: 'pointer',
            textAlign: 'left',
          }}
        >
          <ListChecks size={14} style={{ color: '#71717a', flexShrink: 0 }} />
          <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '0.82rem' }}>{task.title}</span>
          <span style={{ fontSize: '0.68rem', color: '#8a8a93', flexShrink: 0 }}>{STAGE_LABEL[task.stage] || task.stage}</span>
        </button>
      ))}
    </div>
  );
}

export function AgentRuntimeTaskDetail({
  task,
  onChanged,
  onOpenSession,
}: {
  task: AgentRuntimeTask;
  onChanged: (task: AgentRuntimeTask) => void;
  onOpenSession: (sessionId: string) => void;
}) {
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const run = async (fn: () => Promise<AgentRuntimeTask>) => {
    setBusy(true);
    setError('');
    try {
      const next = await fn();
      setNote('');
      onChanged(next);
    } catch (err) {
      setError(errorDetail(err, 'Could not update the task'));
    } finally {
      setBusy(false);
    }
  };

  const open = task.stage !== 'done' && task.stage !== 'cancelled';
  return (
    <div style={{ width: 'min(680px, 100%)', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div>
        <div style={{ fontSize: '0.75rem', color: '#8a8a93', marginBottom: 4 }}>{STAGE_LABEL[task.stage] || task.stage}</div>
        <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 650, color: '#0f172a' }}>{task.title}</h2>
      </div>
      <p style={{ margin: 0, whiteSpace: 'pre-wrap', color: '#334155', fontSize: '0.9rem', lineHeight: 1.5 }}>{task.brief || 'No brief yet.'}</p>
      {task.waiting_reason && <div style={{ fontSize: '0.82rem', color: '#92400e' }}>Waiting: {task.waiting_reason}</div>}
      {task.start_error && <div style={{ fontSize: '0.82rem', color: '#b91c1c' }}>Could not start: {task.start_error}</div>}
      {error && <div style={{ fontSize: '0.82rem', color: '#b91c1c' }}>{error}</div>}
      {task.session_id && (
        <button type="button" style={buttonStyle} onClick={() => onOpenSession(task.session_id!)}>Open session</button>
      )}
      {open && (task.stage === 'draft' || task.stage === 'ready' || task.stage === 'in_progress' || task.stage === 'in_review') && (
        <textarea
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder={task.stage === 'in_review' ? 'What should change?' : 'Why is this waiting?'}
          rows={3}
          style={fieldStyle}
        />
      )}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {(task.stage === 'draft' || task.stage === 'waiting' || (task.stage === 'ready' && task.start_error)) && (
          <button type="button" disabled={busy} style={{ ...buttonStyle, background: '#18181b', color: '#ffffff', borderColor: '#18181b' }} onClick={() => run(() => agentRuntimeApi.readyTask(task.id))}>
            {task.stage === 'ready' ? 'Retry' : 'Mark ready'}
          </button>
        )}
        {task.stage === 'draft' && (
          <button type="button" disabled={busy || !note.trim()} style={buttonStyle} onClick={() => run(() => agentRuntimeApi.parkTask(task.id, note.trim(), 'person'))}>Park</button>
        )}
        {task.stage === 'in_progress' && (
          <>
            <button type="button" disabled={busy} style={{ ...buttonStyle, background: '#18181b', color: '#ffffff', borderColor: '#18181b' }} onClick={() => run(() => agentRuntimeApi.submitTask(task.id, note.trim()))}>Submit for review</button>
            <button type="button" disabled={busy || !note.trim()} style={buttonStyle} onClick={() => run(() => agentRuntimeApi.parkTask(task.id, note.trim(), 'agent'))}>Park</button>
          </>
        )}
        {task.stage === 'in_review' && (
          <>
            <button type="button" disabled={busy} style={{ ...buttonStyle, background: '#18181b', color: '#ffffff', borderColor: '#18181b' }} onClick={() => run(() => agentRuntimeApi.acceptTask(task.id))}>Accept</button>
            <button type="button" disabled={busy || !note.trim()} style={buttonStyle} onClick={() => run(() => agentRuntimeApi.requestTaskChanges(task.id, note.trim()))}>Request changes</button>
          </>
        )}
        {open && (
          <button type="button" disabled={busy} style={{ ...buttonStyle, color: '#b91c1c' }} onClick={() => run(() => agentRuntimeApi.cancelTask(task.id, note.trim()))}>Cancel</button>
        )}
      </div>
      {task.events?.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ fontSize: '0.75rem', color: '#8a8a93' }}>History</div>
          {[...task.events].reverse().map((event, index) => (
            <div key={`${event.at}-${index}`} style={{ fontSize: '0.78rem', color: '#475569' }}>
              <span style={{ color: '#8a8a93' }}>{event.actor}</span> {event.note || event.action}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function AgentRuntimeTaskStrip({
  task,
  onChanged,
}: {
  task: AgentRuntimeTask;
  onChanged: (task: AgentRuntimeTask) => void;
}) {
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const run = async (fn: () => Promise<AgentRuntimeTask>) => {
    setBusy(true);
    setError('');
    try {
      const next = await fn();
      setNote('');
      onChanged(next);
    } catch (err) {
      setError(errorDetail(err, 'Could not update the task'));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px', borderBottom: '1px solid #e2e8f0', background: '#f8fafc', flexWrap: 'wrap' }}>
      <span style={{ fontSize: '0.75rem', color: '#64748b' }}>{STAGE_LABEL[task.stage] || task.stage}</span>
      <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#0f172a' }}>{task.title}</span>
      {task.stage === 'in_progress' && (
        <button type="button" disabled={busy} style={buttonStyle} onClick={() => run(() => agentRuntimeApi.submitTask(task.id, note.trim()))}>Submit for review</button>
      )}
      {task.stage === 'in_review' && (
        <>
          <button type="button" disabled={busy} style={buttonStyle} onClick={() => run(() => agentRuntimeApi.acceptTask(task.id))}>Accept</button>
          <input value={note} onChange={(event) => setNote(event.target.value)} placeholder="What should change?" style={{ ...fieldStyle, flex: '1 1 140px', width: 'auto', minWidth: 0, padding: '4px 8px' }} />
          <button type="button" disabled={busy || !note.trim()} style={buttonStyle} onClick={() => run(() => agentRuntimeApi.requestTaskChanges(task.id, note.trim()))}>Request changes</button>
        </>
      )}
      {error && <span style={{ fontSize: '0.75rem', color: '#b91c1c' }}>{error}</span>}
    </div>
  );
}

export function AgentRuntimeTaskCreate({
  initialTitle,
  sourceSessionId,
  projectId,
  agentType,
  llmModel,
  onCreated,
  onClose,
}: {
  initialTitle?: string;
  sourceSessionId?: string;
  projectId?: string | null;
  agentType?: string;
  llmModel?: string;
  onCreated: (task: AgentRuntimeTask) => void;
  onClose: () => void;
}) {
  const [title, setTitle] = useState(initialTitle || '');
  const [brief, setBrief] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const submit = async () => {
    if (!title.trim()) {
      setError('A title is required.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const task = await agentRuntimeApi.createTask({
        title: title.trim(),
        brief: brief.trim(),
        project_id: projectId || undefined,
        source_session_id: sourceSessionId,
        agent_type: agentType,
        llm_model: llmModel || undefined,
        actor: 'person',
      });
      onCreated(task);
    } catch (err) {
      setError(errorDetail(err, 'Could not file the task'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ width: 'min(680px, 100%)', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 650, color: '#0f172a' }}>File a task</h2>
      <p style={{ margin: 0, color: '#64748b', fontSize: '0.84rem' }}>It stays in draft until you mark it ready. Marking it ready starts an agent session.</p>
      <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Title" style={fieldStyle} />
      <textarea value={brief} onChange={(event) => setBrief(event.target.value)} placeholder="What should the agent do?" rows={5} style={fieldStyle} />
      {error && <div style={{ fontSize: '0.82rem', color: '#b91c1c' }}>{error}</div>}
      <div style={{ display: 'flex', gap: 8 }}>
        <button type="button" disabled={busy} style={{ ...buttonStyle, background: '#18181b', color: '#ffffff', borderColor: '#18181b' }} onClick={submit}>File task</button>
        <button type="button" disabled={busy} style={buttonStyle} onClick={onClose}>Close</button>
      </div>
    </div>
  );
}
