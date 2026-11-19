import React, { useEffect, useRef, useState } from 'react';
import { ChevronLeft, Paperclip, Plug, Plus, X } from 'lucide-react';
import { fetchMCPServers, updateMCPServer } from '@/modules/ai_gateway/api';
import type { MCPServer } from '@/modules/ai_gateway/types';

const FILE_LIMIT = 100_000;
const FILE_ACCEPT = '.pdf,.docx,.xlsx,.csv,.txt,.md,.json,.png,.jpg,.jpeg,.webp,.gif,.svg,image/*,text/*';
const MCP_OVERRIDE_KEY = 'agent-runtime-mcp-overrides';

function readMcpOverrides(): Record<string, boolean> {
  try {
    const parsed = JSON.parse(sessionStorage.getItem(MCP_OVERRIDE_KEY) || '{}');
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

function writeMcpOverrides(overrides: Record<string, boolean>) {
  sessionStorage.setItem(MCP_OVERRIDE_KEY, JSON.stringify(overrides));
}

function isBuiltinServer(server: MCPServer) {
  return server.created_by === 'system' || (server.full_name || '').startsWith('system.');
}

export function mcpControlNote(): string {
  const lines = Object.entries(readMcpOverrides()).map(([name, on]) => `${name}: ${on ? 'on' : 'off'}`);
  return lines.length ? `[mcp]\n${lines.join('\n')}` : '';
}

export async function composeMessage(text: string, files: File[]): Promise<string> {
  const parts = [text.trim(), mcpControlNote()].filter(Boolean);
  for (const file of files) {
    if (file.type.startsWith('image/')) {
      parts.push(`[attachment: ${file.name}]`);
      continue;
    }
    if (file.size > FILE_LIMIT) {
      parts.push(`[attachment: ${file.name}]\nThis file is too large to include.`);
      continue;
    }
    try {
      const body = await file.text();
      parts.push(`[attachment: ${file.name}]\n${body}`);
    } catch {
      parts.push(`[attachment: ${file.name}]`);
    }
  }
  return parts.join('\n\n');
}

export function AttachmentChips({ files, onRemove }: { files: File[]; onRemove: (index: number) => void }) {
  if (!files.length) return null;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, padding: '10px 12px 0' }}>
      {files.map((file, index) => (
        <span
          key={`${file.name}-${file.size}-${index}`}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            maxWidth: 240,
            border: '1px solid #e4e4e7',
            borderRadius: 999,
            background: '#fafafa',
            color: '#3f3f46',
            padding: '3px 8px',
            fontSize: 12,
          }}
        >
          <Paperclip size={12} aria-hidden="true" />
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{file.name}</span>
          <button
            type="button"
            aria-label={`Remove ${file.name}`}
            onClick={() => onRemove(index)}
            style={{ border: 'none', background: 'transparent', color: '#71717a', padding: 0, display: 'inline-flex', cursor: 'pointer' }}
          >
            <X size={12} />
          </button>
        </span>
      ))}
    </div>
  );
}

export function ComposerPlusButton({
  disabled,
  onAddFiles,
}: {
  disabled?: boolean;
  onAddFiles: (files: File[]) => void;
}) {
  const rootRef = useRef<HTMLSpanElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<'root' | 'mcp'>('root');
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [overrides, setOverrides] = useState<Record<string, boolean>>(() => readMcpOverrides());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState<number | null>(null);

  useEffect(() => {
    if (!open) return undefined;
    const close = (event: MouseEvent) => {
      const target = event.target;
      if (target instanceof Node && rootRef.current?.contains(target)) return;
      setOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [open]);

  const openMenu = () => {
    setView('root');
    setOpen((current) => !current);
  };

  const openMcp = () => {
    setView('mcp');
    setError('');
    setLoading(true);
    fetchMCPServers()
      .then((rows) => setServers(rows))
      .catch(() => setError('MCP servers could not be loaded.'))
      .finally(() => setLoading(false));
  };

  const serverEnabled = (server: MCPServer) => (server.name in overrides ? overrides[server.name] : server.is_enabled);

  const rememberOverride = (name: string, enabled: boolean) => {
    const next = { ...readMcpOverrides(), [name]: enabled };
    writeMcpOverrides(next);
    setOverrides(next);
  };

  const toggleServer = (server: MCPServer) => {
    const next = !serverEnabled(server);
    setError('');
    if (isBuiltinServer(server)) {
      if (next === server.is_enabled) {
        const stored = { ...readMcpOverrides() };
        delete stored[server.name];
        writeMcpOverrides(stored);
        setOverrides(stored);
      } else {
        rememberOverride(server.name, next);
      }
      return;
    }
    setBusyId(server.id);
    updateMCPServer(server.id, { is_enabled: next })
      .then((saved) => {
        setServers((current) => current.map((item) => (item.id === server.id ? { ...item, is_enabled: saved.is_enabled } : item)));
        const stored = { ...readMcpOverrides() };
        delete stored[server.name];
        writeMcpOverrides(stored);
        setOverrides(stored);
      })
      .catch(() => setError(`${server.name} could not be updated.`))
      .finally(() => setBusyId(null));
  };

  return (
    <span ref={rootRef} style={{ position: 'relative' }}>
      <style>{`.composer-plus-menu button:hover { background: #f4f4f5; }`}</style>
      <input
        ref={fileRef}
        type="file"
        multiple
        accept={FILE_ACCEPT}
        style={{ display: 'none' }}
        onChange={(event) => {
          const picked = Array.from(event.target.files || []);
          if (picked.length) onAddFiles(picked);
          event.target.value = '';
          setOpen(false);
        }}
      />
      <button
        type="button"
        aria-label="Add"
        aria-haspopup="menu"
        aria-expanded={open}
        title="Add"
        disabled={disabled}
        onClick={openMenu}
        style={{
          width: 28,
          height: 28,
          borderRadius: 999,
          border: '1px solid #e4e4e7',
          background: open ? '#f4f4f5' : '#ffffff',
          color: '#3f3f46',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: disabled ? 'default' : 'pointer',
          padding: 0,
        }}
      >
        <Plus size={16} strokeWidth={1.75} />
      </button>
      {open && (
        <div
          role="menu"
          className="composer-plus-menu"
          style={{
            position: 'absolute',
            bottom: '100%',
            left: 0,
            zIndex: 30,
            width: 280,
            maxHeight: 320,
            overflow: 'auto',
            marginBottom: 6,
            background: '#ffffff',
            border: '1px solid #e4e4e7',
            borderRadius: 10,
            boxShadow: '0 12px 32px rgba(15, 23, 42, 0.12)',
            padding: 4,
          }}
        >
          {view === 'root' ? (
            <>
              <MenuItem
                icon={<Paperclip size={15} />}
                label="Photos & files"
                onClick={() => {
                  setOpen(false);
                  fileRef.current?.click();
                }}
              />
              <MenuItem icon={<Plug size={15} />} label="MCP" detail="Turn servers on or off" onClick={openMcp} />
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={() => setView('root')}
                style={menuRowStyle}
              >
                <ChevronLeft size={14} />
                MCP
              </button>
              {loading && <Note>Loading MCP servers…</Note>}
              {error && <Note>{error}</Note>}
              {!loading && !error && servers.length === 0 && <Note>No MCP servers yet.</Note>}
              {servers.map((server) => {
                const enabled = serverEnabled(server);
                return (
                  <button
                    key={server.id}
                    type="button"
                    role="menuitemcheckbox"
                    aria-checked={enabled}
                    disabled={busyId === server.id}
                    onClick={() => toggleServer(server)}
                    style={menuRowStyle}
                  >
                    <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{server.name}</span>
                    <span style={{ color: enabled ? '#18181b' : '#a1a1aa', fontSize: 12 }}>{enabled ? 'On' : 'Off'}</span>
                  </button>
                );
              })}
            </>
          )}
        </div>
      )}
    </span>
  );
}

function MenuItem({
  icon,
  label,
  detail,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  detail?: string;
  onClick: () => void;
}) {
  return (
    <button type="button" role="menuitem" onClick={onClick} style={menuRowStyle}>
      <span style={{ width: 18, display: 'inline-flex', justifyContent: 'center', color: '#3f3f46' }}>{icon}</span>
      <span style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', minWidth: 0 }}>
        <span>{label}</span>
        {detail && <span style={{ color: '#71717a', fontSize: 12 }}>{detail}</span>}
      </span>
    </button>
  );
}

function Note({ children }: { children: React.ReactNode }) {
  return <div style={{ padding: '7px 8px', color: '#71717a', fontSize: 13 }}>{children}</div>;
}

const menuRowStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  width: '100%',
  textAlign: 'left',
  border: 'none',
  background: 'transparent',
  color: '#18181b',
  borderRadius: 6,
  padding: '7px 8px',
  fontSize: 13,
  cursor: 'pointer',
};
