import { AtSign, Bot, Check, ChevronDown, FileText, History, Loader2, Paperclip, Plus, SendHorizonal, Square, Upload, X } from 'lucide-react';
import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { LLMConnection } from '@/modules/agents/hooks/useLLMConnections';
import type { AgentListItem } from '@/modules/agents/hooks/useAgents';
import type { NovaTarget } from '@/modules/nova/stores/novaStore';
import type { NovaAttachmentRecord } from '@/modules/nova/hooks/useNovaAttachments';
import './nova.css';

export interface NovaEnvelope {
  action?: 'chat' | 'replace_focused' | 'insert_below' | 'append_to_focused' | 'replace_cell' | 'add_cells';
  cell_type?: 'code' | 'markdown' | 'raw';
  code?: string;
  explanation?: string;
  cell_index?: number | null;
  insert_after_cell_index?: number | null;
  cells?: Array<{
    cell_type?: 'code' | 'markdown' | 'raw';
    code?: string;
    explanation?: string;
  }>;
}

export interface NovaMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface NovaSidePanelProps {
  title?: string;
  subtitle?: string;
  sessionTitle?: string;
  status: string;
  requirement: string;
  onRequirementChange: (value: string) => void;
  messages: NovaMessage[];
  historyOpen: boolean;
  sessions: Array<{ id: string; title: string; updatedAt: string }>;
  onNewChat: () => void;
  onToggleHistory: () => void;
  onSelectSession: (sessionId: string) => void;
  activeSessionId: string;
  onSubmit: () => void;
  onStop?: () => void;
  isSubmitting: boolean;
  explanation?: string;
  warning?: string;
  target: NovaTarget | null;
  agents: AgentListItem[];
  onTargetChange: (target: NovaTarget) => void;
  llmConnections: LLMConnection[];
  selectedLlmConnectionId: number | null;
  onSelectedLlmConnectionIdChange: (value: number | null) => void;
  placeholder?: string;
  footerExtras?: ReactNode;
  disableComposer?: boolean;
  attachments?: NovaAttachmentRecord[];
  onUploadFiles?: (files: FileList | File[]) => void;
  onRemoveAttachment?: (fileId: string) => void;
  onPromoteAttachment?: (fileId: string, path: string) => Promise<boolean>;
  isUploadingAttachments?: boolean;
}

export default function NovaSidePanel({
  title = 'Nova',
  subtitle,
  sessionTitle,
  status,
  requirement,
  onRequirementChange,
  messages,
  historyOpen,
  sessions,
  onNewChat,
  onToggleHistory,
  onSelectSession,
  activeSessionId,
  onSubmit,
  onStop,
  isSubmitting,
  explanation,
  warning,
  target,
  agents,
  onTargetChange,
  llmConnections,
  selectedLlmConnectionId,
  onSelectedLlmConnectionIdChange,
  placeholder,
  footerExtras,
  disableComposer = false,
  attachments = [],
  onUploadFiles,
  onRemoveAttachment,
  onPromoteAttachment,
  isUploadingAttachments = false,
}: NovaSidePanelProps) {
  const [openSelector, setOpenSelector] = useState<'target' | 'llm' | null>(null);
  const panelRef = useRef<HTMLElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const threadRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [previewAttachment, setPreviewAttachment] = useState<NovaAttachmentRecord | null>(null);
  const [promoteCatalogPath, setPromoteCatalogPath] = useState('');
  const [isPromoting, setIsPromoting] = useState(false);

  useEffect(() => {
    if (threadRef.current) {
      threadRef.current.scrollTop = threadRef.current.scrollHeight;
    }
  }, [messages]);
  const selectorRowRef = useRef<HTMLDivElement | null>(null);
  const targetValue = target ? `agent:${target.agentId}` : '';
  const selectedAgent = target ? agents.find((agent) => agent.id === target.agentId) : null;
  const selectedLlmConnection = llmConnections.find((connection) => connection.id === selectedLlmConnectionId) ?? null;
  const targetOptions = useMemo(
    () => agents.map((agent) => ({ value: `agent:${agent.id}`, label: agent.name, description: 'Run multi-step data and AI tasks' })),
    [agents],
  );

  function selectTarget(value: string) {
    onTargetChange({ type: 'agent', agentId: Number(value.replace('agent:', '')) });
    setOpenSelector(null);
  }

  function selectLlmConnection(value: number | null) {
    onSelectedLlmConnectionIdChange(value);
    setOpenSelector(null);
  }

  useEffect(() => {
    if (!openSelector) return;

    function handlePointerDown(event: MouseEvent) {
      if (!selectorRowRef.current?.contains(event.target as Node)) {
        setOpenSelector(null);
      }
    }

    window.addEventListener('mousedown', handlePointerDown);
    return () => window.removeEventListener('mousedown', handlePointerDown);
  }, [openSelector]);

  useLayoutEffect(() => {
    const input = inputRef.current;
    if (!input) return;

    const resizeInput = () => {
      const panelHeight = panelRef.current?.clientHeight ?? window.innerHeight;
      const maxHeight = Math.max(44, Math.floor(panelHeight * 0.25));
      input.style.maxHeight = `${maxHeight}px`;
      input.style.height = 'auto';
      const nextHeight = Math.min(input.scrollHeight, maxHeight);
      input.style.height = `${nextHeight}px`;
      input.style.overflowY = input.scrollHeight > maxHeight ? 'auto' : 'hidden';
    };

    resizeInput();
    window.addEventListener('resize', resizeInput);
    return () => window.removeEventListener('resize', resizeInput);
  }, [requirement]);

  return (
    <aside className="nova-panel" ref={panelRef}>
      <div className="nova-panel-header">
        <div className="nova-panel-title">
          <Bot size={16} />
          <div className="nova-panel-title-copy">
            <span>{title}</span>
            {subtitle && <div className="nova-panel-subtitle">{subtitle}</div>}
            {sessionTitle && <div className="nova-panel-session-title">{sessionTitle}</div>}
          </div>
        </div>
        <div className="nova-panel-header-actions">
          <button type="button" className="nova-panel-icon-btn" title="New chat" onClick={onNewChat}>
            <Plus size={15} />
          </button>
          <button
            type="button"
            className={`nova-panel-icon-btn ${historyOpen ? 'is-active' : ''}`}
            title="Session history"
            onClick={onToggleHistory}
          >
            <History size={15} />
          </button>
        </div>
      </div>

      <div className="nova-panel-body">
        {historyOpen && (
          <div className="nova-panel-history">
            {sessions.length === 0 && <div className="nova-panel-empty">No saved chats yet.</div>}
            {sessions.map((session) => (
              <button
                key={session.id}
                type="button"
                className={`nova-panel-history-item ${session.id === activeSessionId ? 'is-active' : ''}`}
                onClick={() => onSelectSession(session.id)}
              >
                <div className="nova-panel-history-title">{session.title}</div>
                <div className="nova-panel-history-meta">{new Date(session.updatedAt).toLocaleString()}</div>
              </button>
            ))}
          </div>
        )}

        <div className="nova-panel-thread" ref={threadRef}>
          {messages.length === 0 && <div className="nova-panel-empty">No conversation yet.</div>}
          {messages.map((message, index) => (
            <div key={`${message.role}-${index}`} className={`nova-panel-row nova-panel-row-${message.role}`}>
              <div className={`nova-panel-bubble nova-panel-bubble-${message.role}`}>
                {message.role === 'assistant' ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                ) : (
                  message.content
                )}
              </div>
            </div>
          ))}
        </div>

        {explanation && <div className="nova-panel-explanation">{explanation}</div>}
        {warning && <div className="nova-panel-warning">{warning}</div>}
      </div>

      <div className="nova-panel-composer-shell">
        <div className="nova-panel-status-row">
          <span className="nova-panel-status">{status}</span>
          {footerExtras}
        </div>

        <div className="nova-panel-composer">
          <input
            type="file"
            ref={fileInputRef}
            style={{ display: 'none' }}
            multiple
            onChange={(e) => {
              if (e.target.files && e.target.files.length > 0) {
                onUploadFiles?.(e.target.files);
                e.target.value = '';
              }
            }}
          />

          {attachments && attachments.length > 0 && (
            <div className="nova-attachments-bar">
              {attachments.map((att) => (
                <div
                  key={att.file_id}
                  className={`nova-attachment-chip ${att.status === 'failed' ? 'is-failed' : ''}`}
                  onClick={() => setPreviewAttachment(att)}
                  title={att.filename}
                >
                  <FileText size={12} />
                  <span className="nova-attachment-chip-name">{att.filename}</span>
                  <span className="nova-attachment-chip-size">
                    {att.size_bytes ? `${Math.round(att.size_bytes / 1024)}KB` : ''}
                  </span>
                  {att.status === 'processing' && <Loader2 size={10} className="nova-spin" />}
                  {onRemoveAttachment && (
                    <button
                      type="button"
                      className="nova-attachment-chip-remove"
                      title="Remove attachment"
                      onClick={(e) => {
                        e.stopPropagation();
                        onRemoveAttachment(att.file_id);
                      }}
                    >
                      <X size={10} />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          <textarea
            ref={inputRef}
            className="nova-panel-input"
            value={requirement}
            onChange={(e) => onRequirementChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (!disableComposer && requirement.trim() && !isSubmitting) onSubmit();
              }
            }}
            placeholder={placeholder ?? 'Describe the task for Nova.'}
            disabled={disableComposer}
          />

          <div className="nova-panel-composer-actions">
            <div className="nova-panel-composer-left">
              <button
                type="button"
                className="nova-panel-icon-btn"
                title="Attach files (max 25MB, up to 10 files)"
                disabled={disableComposer || isUploadingAttachments}
                onClick={() => fileInputRef.current?.click()}
              >
                {isUploadingAttachments ? <Loader2 size={15} className="nova-spin" /> : <Paperclip size={15} />}
              </button>

              <div className="nova-panel-selector" ref={selectorRowRef}>
                <button
                  className="nova-panel-select-trigger"
                  type="button"
                  disabled={isSubmitting}
                  onClick={() => setOpenSelector((open) => (open === 'target' ? null : 'target'))}
                  title="Assistant target"
                >
                  <span className="nova-panel-select-text">{selectedAgent?.name ?? 'Select agent'}</span>
                  <ChevronDown size={13} />
                </button>
                {openSelector === 'target' && (
                  <div className="nova-panel-select-menu">
                    {targetOptions.map((option) => (
                      <button
                        key={option.value}
                        type="button"
                        className={`nova-panel-select-option ${option.value === targetValue ? 'is-selected' : ''}`}
                        onClick={() => selectTarget(option.value)}
                      >
                        {option.value === targetValue ? <Check size={16} className="nova-panel-select-check" /> : <span className="nova-panel-select-check" />}
                        <span>
                          <span className="nova-panel-select-option-title">
                            <span className="nova-panel-select-option-label">{option.label}</span>
                          </span>
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="nova-panel-composer-right">
              <div className="nova-panel-selector">
                <button
                  className="nova-panel-select-trigger"
                  type="button"
                  disabled={!llmConnections.length || isSubmitting}
                  onClick={() => setOpenSelector((open) => (open === 'llm' ? null : 'llm'))}
                  title="Selected agent LLM connection"
                >
                  <span className="nova-panel-select-text">{selectedLlmConnection?.name ?? 'No LLM'}</span>
                  <ChevronDown size={13} />
                </button>
                {openSelector === 'llm' && (
                  <div className="nova-panel-select-menu is-right">
                    {llmConnections.length === 0 ? (
                      <div className="nova-panel-select-empty">No LLM connections</div>
                    ) : (
                      llmConnections.map((connection) => (
                        <button
                          key={connection.id}
                          type="button"
                          className={`nova-panel-select-option ${connection.id === selectedLlmConnectionId ? 'is-selected' : ''}`}
                          onClick={() => selectLlmConnection(connection.id)}
                        >
                          {connection.id === selectedLlmConnectionId ? <Check size={16} className="nova-panel-select-check" /> : <span className="nova-panel-select-check" />}
                          <span>
                            <span className="nova-panel-select-option-title">
                              <span className="nova-panel-select-option-label">{connection.name}</span>
                              {connection.is_fallback && <span className="nova-panel-select-badge">Default</span>}
                            </span>
                          </span>
                        </button>
                      ))
                    )}
                  </div>
                )}
              </div>

              <button
                className={`nova-panel-submit ${isSubmitting ? 'is-stopping' : ''}`}
                onClick={isSubmitting ? onStop : onSubmit}
                disabled={isSubmitting ? !onStop : disableComposer || !requirement.trim() || !selectedLlmConnectionId}
                title={isSubmitting ? 'Stop response' : 'Send'}
              >
                {isSubmitting ? <Square size={13} /> : <SendHorizonal size={14} />}
              </button>
            </div>
          </div>
        </div>
      </div>

      {previewAttachment && (
        <div className="nova-attachment-modal-overlay" onClick={() => setPreviewAttachment(null)}>
          <div className="nova-attachment-modal" onClick={(e) => e.stopPropagation()}>
            <div className="nova-attachment-modal-header">
              <div className="nova-attachment-modal-title">
                <FileText size={16} />
                <span>{previewAttachment.filename}</span>
                {previewAttachment.delivery_mode && (
                  <span className="nova-attachment-modal-badge">{previewAttachment.delivery_mode}</span>
                )}
              </div>
              <button
                type="button"
                className="nova-panel-icon-btn"
                onClick={() => setPreviewAttachment(null)}
              >
                <X size={16} />
              </button>
            </div>

            <div className="nova-attachment-modal-body">
              <div style={{ marginBottom: 12, color: '#6b7280' }}>
                <strong>MIME:</strong> {previewAttachment.mime_type} | <strong>Size:</strong> {previewAttachment.size_bytes} bytes
                {previewAttachment.extracted_token_count ? ` | Tokens: ~${previewAttachment.extracted_token_count}` : ''}
              </div>

              {previewAttachment.status === 'failed' && (
                <div className="nova-panel-warning" style={{ background: '#fef2f2', color: '#991b1b', borderColor: '#fca5a5' }}>
                  <strong>Extraction Error:</strong> {previewAttachment.extraction_error || 'Failed to extract content.'}
                </div>
              )}

              {previewAttachment.delivery_mode === 'tool_fetch' && (
                <div className="nova-panel-warning" style={{ marginBottom: 12 }}>
                  💡 Nova can search and read this file using the <code>fetch_attachment</code> tool. Showing preview text:
                </div>
              )}

              {previewAttachment.preview_text ? (
                <pre>{previewAttachment.preview_text}</pre>
              ) : (
                <div style={{ color: '#9ca3af', fontStyle: 'italic' }}>
                  {previewAttachment.status === 'processing' ? 'Processing file extraction...' : 'No preview available.'}
                </div>
              )}
            </div>

            <div className="nova-attachment-modal-footer">
              {previewAttachment.promoted_object_id ? (
                <span style={{ fontSize: 12, color: '#16a34a', fontWeight: 500 }}>
                  ✅ Saved to catalog ({previewAttachment.promoted_object_id.slice(0, 8)}...)
                </span>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%' }}>
                  <input
                    type="text"
                    className="nova-panel-input"
                    style={{ border: '1px solid #d1d5db', borderRadius: 6, padding: '4px 8px', fontSize: 12, flex: 1 }}
                    placeholder="Target catalog path (e.g. main.default.my_file)"
                    value={promoteCatalogPath}
                    onChange={(e) => setPromoteCatalogPath(e.target.value)}
                  />
                  <button
                    type="button"
                    className="nova-attachment-promote-btn"
                    disabled={!promoteCatalogPath.trim() || isPromoting}
                    onClick={async () => {
                      if (!onPromoteAttachment || !promoteCatalogPath.trim()) return;
                      setIsPromoting(true);
                      const ok = await onPromoteAttachment(previewAttachment.file_id, promoteCatalogPath.trim());
                      setIsPromoting(false);
                      if (ok) setPreviewAttachment(null);
                    }}
                  >
                    {isPromoting ? <Loader2 size={14} className="nova-spin" /> : <Upload size={14} />}
                    <span>Promote to Catalog</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}

