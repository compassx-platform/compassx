import React, { useEffect, useRef, useState } from 'react';
import { ArrowUp, AudioLines, ChevronDown, GitBranch, Loader2, Mic, Monitor, Plus } from 'lucide-react';

export type RuntimeAgentType = 'nova' | 'antigravity' | 'pi' | 'opencode' | 'claude' | 'codex' | 'cursor';

export interface RuntimeSandboxOption {
  id: string;
  name: string;
  status?: string;
}

export interface RuntimeProjectOption {
  id: string;
  name: string;
}

const SANDBOX_STATUS_COLOR: Record<string, string> = {
  ready: '#10b981',
  running: '#10b981',
  active: '#10b981',
  provisioning: '#f59e0b',
  initializing: '#f59e0b',
  pending: '#f59e0b',
  starting: '#f59e0b',
  stopping: '#f59e0b',
  suspended: '#6b7280',
  stopped: '#6b7280',
  failed: '#ef4444',
  error: '#ef4444',
  terminated: '#9ca3af',
};

function sandboxStatusLabel(status?: string) {
  return (status || '').trim().toLowerCase() || 'unknown';
}

function sandboxStatusColor(status?: string) {
  return SANDBOX_STATUS_COLOR[sandboxStatusLabel(status)] || '#94a3b8';
}

const AGENTS: { id: RuntimeAgentType; label: string }[] = [
  { id: 'nova', label: 'Nova' },
  { id: 'antigravity', label: 'Antigravity' },
  { id: 'pi', label: 'Pi' },
  { id: 'opencode', label: 'OpenCode' },
  { id: 'claude', label: 'Claude Code' },
  { id: 'codex', label: 'Codex' },
  { id: 'cursor', label: 'Cursor' },
];

type ChipId = 'project' | 'sandbox' | 'branch' | 'agent' | 'llm' | 'add';

export interface RuntimeLlmOption {
  id: string;
  label?: string;
}

interface AgentRuntimeComposerProps {
  mode: 'new' | 'followup';
  projects?: RuntimeProjectOption[];
  projectId?: string | null;
  sandboxes: RuntimeSandboxOption[];
  sandboxesLoading?: boolean;
  sandboxId: string;
  agentType: string;
  agents?: { id: string; label: string }[];
  branch?: string;
  branches?: string[];
  branchesLoading?: boolean;
  value: string;
  submitting?: boolean;
  creatingProject?: boolean;
  onProjectChange?: (projectId: string | null) => void;
  onCreateProject?: (name: string) => void;
  onSandboxChange: (sandboxId: string) => void;
  onAgentChange: (agentType: string) => void;
  llmModel?: string | null;
  llmModels?: RuntimeLlmOption[];
  llmModelsLoading?: boolean;
  onLlmModelChange?: (modelId: string) => void;
  onBranchChange?: (branch: string) => void;
  onChange: (value: string) => void;
  onSubmit: () => void;
}

export function AgentRuntimeComposer({
  projects = [],
  projectId = null,
  sandboxes,
  sandboxesLoading = false,
  sandboxId,
  agentType,
  agents = AGENTS,
  branch = '',
  branches = [],
  branchesLoading = false,
  value,
  submitting = false,
  creatingProject = false,
  onProjectChange,
  onCreateProject,
  onSandboxChange,
  onAgentChange,
  llmModel = null,
  llmModels = [],
  llmModelsLoading = false,
  onLlmModelChange,
  onBranchChange,
  onChange,
  onSubmit,
}: AgentRuntimeComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const [openChip, setOpenChip] = useState<ChipId | null>(null);
  const [projectName, setProjectName] = useState('');
  const project = projects.find((item) => item.id === projectId);
  const sandbox = sandboxes.find((item) => item.id === sandboxId);
  const agent = agents.find((item) => item.id === agentType);
  const showLlm = agentType === 'nova';
  const selectedLlm = llmModels.find((item) => item.id === llmModel);
  const showBranch = branches.length > 0 || branchesLoading;
  const canSend = Boolean(value.trim()) && !submitting;

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 220)}px`;
  }, [value]);

  useEffect(() => {
    if (!openChip) return undefined;
    const close = (event: MouseEvent) => {
      const target = event.target;
      if (target instanceof Node && rootRef.current?.contains(target)) return;
      setOpenChip(null);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [openChip]);

  const submit = () => {
    if (submitting || !value.trim()) return;
    onSubmit();
  };

  const choose = (action: () => void) => {
    action();
    setOpenChip(null);
  };

  const createProject = (event: React.FormEvent) => {
    event.preventDefault();
    const name = projectName.trim();
    if (!name || creatingProject) return;
    onCreateProject?.(name);
    setProjectName('');
    setOpenChip(null);
  };

  return (
    <div ref={rootRef} className="agent-runtime-composer" style={{ width: '100%', maxWidth: 680, boxSizing: 'border-box' }}>
      <style>{`.agent-runtime-composer textarea::placeholder { color: #a1a1aa; }`}</style>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 10, marginBottom: 8, paddingLeft: 4 }}>
        <span style={{ position: 'relative' }}>
          <ContextChip
            label={project?.name || 'Project'}
            open={openChip === 'project'}
            onClick={() => setOpenChip(openChip === 'project' ? null : 'project')}
          />
          {openChip === 'project' && (
            <Menu>
              {projectId && (
                <MenuRow selected={false} onClick={() => choose(() => onProjectChange?.(null))}>
                  No project
                </MenuRow>
              )}
              {projects.length === 0 && <MenuNote>No projects yet.</MenuNote>}
              {projects.map((item) => (
                <MenuRow key={item.id} selected={item.id === projectId} onClick={() => choose(() => onProjectChange?.(item.id))}>
                  {item.name}
                </MenuRow>
              ))}
              <form onSubmit={createProject} style={projectFormStyle}>
                <input
                  value={projectName}
                  aria-label="New project name"
                  placeholder="New project"
                  onChange={(event) => setProjectName(event.target.value)}
                  style={menuInputStyle}
                />
              </form>
            </Menu>
          )}
        </span>
        <span style={{ position: 'relative' }}>
          <ContextChip
            label={sandboxId === 'new' ? 'New sandbox' : sandbox?.name || 'Sandbox'}
            icon={sandboxId === 'new' ? <Monitor size={13} strokeWidth={1.75} /> : <StatusDot status={sandbox?.status} />}
            open={openChip === 'sandbox'}
            onClick={() => setOpenChip(openChip === 'sandbox' ? null : 'sandbox')}
          />
          {openChip === 'sandbox' && (
            <Menu>
              <MenuRow selected={sandboxId === 'new'} onClick={() => choose(() => onSandboxChange('new'))}>
                New sandbox
              </MenuRow>
              {sandboxesLoading && <MenuNote>Loading sandboxes…</MenuNote>}
              {sandboxes.map((item) => (
                <MenuRow key={item.id} selected={item.id === sandboxId} onClick={() => choose(() => onSandboxChange(item.id))}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', minWidth: 0 }}>
                    <StatusDot status={item.status} />
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.name}</span>
                    <span style={{ marginLeft: 'auto', color: '#71717a', fontSize: 12, flexShrink: 0 }}>{sandboxStatusLabel(item.status)}</span>
                  </span>
                </MenuRow>
              ))}
            </Menu>
          )}
        </span>
        {showBranch && (
          <span style={{ position: 'relative' }}>
            <ContextChip
              label={branchesLoading ? 'Branch' : branch || 'Branch'}
              icon={<GitBranch size={13} strokeWidth={1.75} />}
              open={openChip === 'branch'}
              onClick={() => setOpenChip(openChip === 'branch' ? null : 'branch')}
            />
            {openChip === 'branch' && (
              <Menu>
                {branchesLoading && <MenuNote>Loading branches…</MenuNote>}
                {branches.map((item) => (
                  <MenuRow key={item} selected={item === branch} onClick={() => choose(() => onBranchChange?.(item))}>
                    {item}
                  </MenuRow>
                ))}
              </Menu>
            )}
          </span>
        )}
      </div>

      <div
        style={{
          background: '#ffffff',
          border: '1px solid #e4e4e7',
          boxShadow: '0 1px 2px rgba(15, 23, 42, 0.04)',
          borderRadius: 12,
        }}
      >
        <textarea
          ref={textareaRef}
          value={value}
          placeholder="Plan, Build, / for skills, @ for context"
          rows={2}
          disabled={submitting}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
          style={{
            width: '100%',
            minHeight: 52,
            border: 'none',
            resize: 'none',
            outline: 'none',
            padding: '12px 14px 4px',
            fontSize: 15,
            lineHeight: 1.45,
            color: '#18181b',
            background: 'transparent',
            fontFamily: 'inherit',
            boxSizing: 'border-box',
          }}
        />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 8px 8px' }}>
          <span style={{ position: 'relative' }}>
            <button
              type="button"
              aria-label="Add"
              aria-expanded={openChip === 'add'}
              onClick={() => setOpenChip(openChip === 'add' ? null : 'add')}
              style={circleButtonStyle(openChip === 'add')}
            >
              <Plus size={16} strokeWidth={1.75} />
            </button>
            {openChip === 'add' && (
              <Menu upward>
                <form onSubmit={createProject} style={{ padding: 6 }}>
                  <input
                    value={projectName}
                    aria-label="New project name"
                    placeholder="New project"
                    onChange={(event) => setProjectName(event.target.value)}
                    style={menuInputStyle}
                  />
                </form>
              </Menu>
            )}
          </span>
          <span style={{ flex: 1 }} />
          <span style={{ position: 'relative' }}>
            <button
              type="button"
              aria-expanded={openChip === 'agent'}
              onClick={() => setOpenChip(openChip === 'agent' ? null : 'agent')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                border: 'none',
                background: openChip === 'agent' ? '#f4f4f5' : 'transparent',
                color: '#3f3f46',
                borderRadius: 6,
                padding: '4px 6px',
                fontSize: 13,
                cursor: 'pointer',
              }}
            >
              <span>{agent?.label || agentType || 'Agent'}</span>
              <ChevronDown size={13} strokeWidth={1.75} />
            </button>
            {openChip === 'agent' && (
              <Menu upward align="right">
                {agents.map((item) => (
                  <MenuRow key={item.id} selected={item.id === agentType} onClick={() => choose(() => onAgentChange(item.id))}>
                    {item.label}
                  </MenuRow>
                ))}
              </Menu>
            )}
          </span>
          {showLlm && (
            <span style={{ position: 'relative' }}>
              <button
                type="button"
                aria-label="Select model"
                aria-expanded={openChip === 'llm'}
                onClick={() => setOpenChip(openChip === 'llm' ? null : 'llm')}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  border: 'none',
                  background: openChip === 'llm' ? '#f4f4f5' : 'transparent',
                  color: '#3f3f46',
                  borderRadius: 6,
                  padding: '4px 6px',
                  fontSize: 13,
                  cursor: 'pointer',
                }}
              >
                <span>{selectedLlm?.label || selectedLlm?.id || llmModel || 'Model'}</span>
                <ChevronDown size={13} strokeWidth={1.75} />
              </button>
              {openChip === 'llm' && (
                <Menu upward align="right">
                  {llmModelsLoading && <MenuNote>Loading models…</MenuNote>}
                  {!llmModelsLoading && llmModels.length === 0 && <MenuNote>No AI Gateway models.</MenuNote>}
                  {llmModels.map((item) => (
                    <MenuRow key={item.id} selected={item.id === llmModel} onClick={() => choose(() => onLlmModelChange?.(item.id))}>
                      {item.label || item.id}
                    </MenuRow>
                  ))}
                </Menu>
              )}
            </span>
          )}
          <button type="button" aria-label="Voice" style={iconButtonStyle}>
            <Mic size={15} strokeWidth={1.75} />
          </button>
          <button
            type="button"
            aria-label="Start agent"
            disabled={!canSend}
            onClick={submit}
            style={{
              width: 28,
              height: 28,
              borderRadius: 999,
              border: 'none',
              background: canSend ? '#18181b' : '#f4f4f5',
              color: canSend ? '#ffffff' : '#a1a1aa',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: canSend ? 'pointer' : 'default',
              flexShrink: 0,
            }}
          >
            {submitting ? <Loader2 size={15} className="spin" /> : canSend ? <ArrowUp size={15} strokeWidth={2.25} /> : <AudioLines size={14} strokeWidth={2} />}
          </button>
        </div>
      </div>
    </div>
  );
}

function ContextChip({
  label,
  icon,
  open,
  onClick,
}: {
  label: string;
  icon?: React.ReactNode;
  open: boolean;
  onClick: () => void;
}) {
  const [hover, setHover] = useState(false);
  return (
    <button
      type="button"
      aria-expanded={open}
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        maxWidth: 220,
        border: 'none',
        background: open || hover ? '#f4f4f5' : 'transparent',
        color: '#52525b',
        borderRadius: 6,
        padding: '3px 6px',
        fontSize: 13,
        fontWeight: 400,
        cursor: 'pointer',
      }}
    >
      {icon}
      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>
      <ChevronDown size={12} strokeWidth={1.75} />
    </button>
  );
}

function Menu({
  children,
  upward = false,
  align = 'left',
}: {
  children: React.ReactNode;
  upward?: boolean;
  align?: 'left' | 'right';
}) {
  return (
    <div
      role="menu"
      style={{
        position: 'absolute',
        top: upward ? undefined : '100%',
        bottom: upward ? '100%' : undefined,
        left: align === 'left' ? 0 : undefined,
        right: align === 'right' ? 0 : undefined,
        zIndex: 30,
        minWidth: 220,
        maxWidth: 360,
        maxHeight: 280,
        overflow: 'auto',
        marginTop: upward ? undefined : 6,
        marginBottom: upward ? 6 : undefined,
        background: '#ffffff',
        border: '1px solid #e4e4e7',
        borderRadius: 10,
        boxShadow: '0 12px 32px rgba(15, 23, 42, 0.12)',
        padding: 4,
      }}
    >
      {children}
    </div>
  );
}

function MenuRow({ children, selected, onClick }: { children: React.ReactNode; selected?: boolean; onClick: () => void }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      type="button"
      role="menuitem"
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: 'block',
        width: '100%',
        textAlign: 'left',
        border: 'none',
        background: selected || hover ? '#f4f4f5' : 'transparent',
        color: '#18181b',
        borderRadius: 6,
        padding: '7px 8px',
        fontSize: 13,
        cursor: 'pointer',
      }}
    >
      {children}
    </button>
  );
}

function StatusDot({ status }: { status?: string }) {
  const label = sandboxStatusLabel(status);
  return (
    <span
      title={label}
      aria-hidden="true"
      style={{
        width: 8,
        height: 8,
        borderRadius: '50%',
        background: sandboxStatusColor(status),
        flexShrink: 0,
        display: 'inline-block',
      }}
    />
  );
}

function MenuNote({ children }: { children: React.ReactNode }) {
  return <div style={{ padding: '7px 8px', color: '#71717a', fontSize: 13 }}>{children}</div>;
}

function circleButtonStyle(active: boolean): React.CSSProperties {
  return {
    width: 28,
    height: 28,
    borderRadius: 999,
    border: '1px solid #e4e4e7',
    background: active ? '#f4f4f5' : '#ffffff',
    color: '#3f3f46',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    padding: 0,
  };
}

const projectFormStyle: React.CSSProperties = {
  display: 'flex',
  gap: 6,
  padding: 6,
  borderTop: '1px solid #f4f4f5',
};

const iconButtonStyle: React.CSSProperties = {
  width: 28,
  height: 28,
  border: 'none',
  background: 'transparent',
  color: '#52525b',
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  cursor: 'default',
  padding: 0,
};

const menuInputStyle: React.CSSProperties = {
  width: '100%',
  boxSizing: 'border-box',
  border: '1px solid #e4e4e7',
  background: '#ffffff',
  color: '#18181b',
  borderRadius: 8,
  padding: '6px 8px',
  fontSize: 13,
  outline: 'none',
};
