import React, { useRef } from 'react';
import { Paperclip, ArrowRight, Loader2, X as XIcon } from 'lucide-react';
import { ContextUsageBadge } from '../ContextUsageBadge';
import { SessionChangesDock } from '../SessionChangesDock';
import { ChangeRecord } from '../DiffSummaryCard';

interface LLMConnection {
  id: number;
  name: string;
  is_fallback?: boolean;
}

interface ChatComposerProps {
  input: string;
  onInputChange: (val: string) => void;
  onSend: (override?: string) => void;
  isStreaming: boolean;
  attachedFiles: File[];
  onUploadFiles: (files: File[]) => void;
  onRemoveFile: (idx: number) => void;
  agentId?: number | null;
  sessionId?: number | null;
  messagesCount?: number;
  selectedLlmConnectionId: number | null;
  onSelectLlmConnectionId: (id: number | null) => void;
  llmConnections: LLMConnection[];
  dockedPlanElement?: React.ReactNode;
  onOpenDiff?: (record: ChangeRecord) => void;
  onStatusChange?: (changeId: string, newStatus: 'accepted' | 'rejected') => void;
}

export const ChatComposer: React.FC<ChatComposerProps> = ({
  input,
  onInputChange,
  onSend,
  isStreaming,
  attachedFiles,
  onUploadFiles,
  onRemoveFile,
  agentId,
  sessionId,
  messagesCount = 0,
  selectedLlmConnectionId,
  onSelectLlmConnectionId,
  llmConnections,
  dockedPlanElement,
  onOpenDiff,
  onStatusChange,
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    const files: File[] = [];
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.kind === 'file') {
        const file = item.getAsFile();
        if (file) files.push(file);
      }
    }
    if (files.length > 0) {
      e.preventDefault();
      onUploadFiles(files);
    }
  };

  return (
    <div
      style={{
        padding: '0 24px 8px',
        maxWidth: 780,
        margin: '0 auto',
        width: '100%',
        flexShrink: 0,
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 780,
          display: 'flex',
          flexDirection: 'column',
          background: '#ffffff',
          border: '1px solid var(--color-border, #e5e7eb)',
          borderRadius: '16px',
          overflow: 'hidden',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.03)',
        }}
      >
        {/* 1. Docked Plan (Top of Composer Card) */}
        {dockedPlanElement}

        {/* 2. Docked Session Changes Panel */}
        {agentId && sessionId && (
          <SessionChangesDock
            isDocked={true}
            agentId={agentId}
            sessionId={sessionId}
            refreshTrigger={messagesCount}
            onOpenDiff={onOpenDiff}
            onStatusChange={onStatusChange}
          />
        )}

        {/* 3. Input Composer */}
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const files = Array.from(e.dataTransfer.files ?? []);
            if (files.length > 0) onUploadFiles(files);
          }}
          style={{
            display: 'flex',
            flexDirection: 'column',
            background: '#ffffff',
            padding: '10px 14px',
            gap: 8,
          }}
        >
          {/* Hidden file input */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.xlsx,.csv,.txt,.md,.json,.png,.jpg,.jpeg,.webp,.gif,.svg,image/*"
            style={{ display: 'none' }}
            onChange={(e) => {
              const files = Array.from(e.target.files ?? []);
              if (files.length > 0) {
                onUploadFiles(files);
              }
              e.target.value = '';
            }}
          />

          {/* Attached file chips */}
          {attachedFiles.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
              {attachedFiles.map((f, i) => (
                <span
                  key={i}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    padding: '2px 8px',
                    borderRadius: 4,
                    background: '#f1f5f9',
                    border: '1px solid #e2e8f0',
                    fontSize: '0.75rem',
                    color: '#475569',
                    fontWeight: 500,
                  }}
                >
                  <Paperclip size={11} style={{ color: '#64748b', flexShrink: 0 }} />
                  <span
                    style={{
                      maxWidth: 220,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {f.name}
                  </span>
                  <button
                    type="button"
                    onClick={() => onRemoveFile(i)}
                    style={{
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      padding: 0,
                      color: '#94a3b8',
                      display: 'inline-flex',
                      alignItems: 'center',
                      marginLeft: 2,
                      lineHeight: 1,
                    }}
                    title="Remove file"
                  >
                    <XIcon size={12} />
                  </button>
                </span>
              ))}
            </div>
          )}

          {/* Message Textarea */}
          <textarea
            ref={textareaRef}
            className="form-input"
            style={{
              width: '100%',
              border: 'none',
              outline: 'none',
              boxShadow: 'none',
              resize: 'none',
              minHeight: 36,
              maxHeight: 160,
              fontSize: '0.88rem',
              lineHeight: 1.5,
              background: 'transparent',
              color: 'var(--color-text, #111827)',
              padding: '2px 0',
            }}
            rows={1}
            placeholder="Message the agent… (Enter to send, Shift+Enter for newline)"
            value={input}
            onPaste={handlePaste}
            onChange={(e) => {
              onInputChange(e.target.value);
              e.target.style.height = 'auto';
              e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                onSend();
              }
            }}
            disabled={isStreaming}
          />

          {/* Bottom Bar: Attachment icon (left), LLM Selector & Context Counter & Send icon (right) */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 10,
              paddingTop: 4,
              borderTop: '1px solid #f3f4f6',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center' }}>
              <button
                type="button"
                title="Attach a document"
                onClick={() => fileInputRef.current?.click()}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#6b7280',
                  cursor: 'pointer',
                  padding: 4,
                  borderRadius: 4,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Paperclip size={17} />
              </button>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {agentId && sessionId && (
                <ContextUsageBadge
                  agentId={agentId}
                  sessionId={sessionId}
                  onCompact={() => onSend('/compact')}
                  isCompactLoading={isStreaming}
                />
              )}

              <select
                value={selectedLlmConnectionId ?? ''}
                onChange={(e) =>
                  onSelectLlmConnectionId(e.target.value ? Number(e.target.value) : null)
                }
                disabled={isStreaming || llmConnections.length === 0}
                title="LLM Connection"
                style={{
                  border: 'none',
                  background: 'transparent',
                  fontSize: '0.74rem',
                  color: '#6b7280',
                  cursor: 'pointer',
                  outline: 'none',
                  fontWeight: 500,
                }}
              >
                {llmConnections.length === 0 && <option value="">No LLM connections</option>}
                {llmConnections.map((connection) => (
                  <option key={connection.id} value={connection.id}>
                    {connection.name}
                    {connection.is_fallback ? ' (default)' : ''}
                  </option>
                ))}
              </select>

              <button
                type="button"
                onClick={() => onSend()}
                disabled={!input.trim() || isStreaming}
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: '50%',
                  border: '1px solid #e5e7eb',
                  background: input.trim() && !isStreaming ? '#f3f4f6' : '#fafafa',
                  color: input.trim() && !isStreaming ? '#374151' : '#d1d5db',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: input.trim() && !isStreaming ? 'pointer' : 'not-allowed',
                  flexShrink: 0,
                }}
              >
                {isStreaming ? (
                  <Loader2 size={14} className="spin" />
                ) : (
                  <ArrowRight size={15} />
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
export default ChatComposer;
