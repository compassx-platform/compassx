import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, ChevronRight, File, Folder, FolderOpen, GitCompare, Globe, Maximize2, Minimize2, PenLine, Plus, Search, Terminal, X } from 'lucide-react';
import { computeApi } from '@/modules/compute/computeApi';
import { SandboxTerminal } from '@/components/sandbox/SandboxTerminal';
import {
  agentRuntimeApi,
  type AgentChatMessage,
  type ChangeEntry,
  type CommitEntry,
  type WorkspaceEntry,
} from '@/modules/agents/agentRuntimeApi';
import { WorkspaceFileEditor } from '@/modules/agents/components/WorkspaceFileEditor';
import { BrowserAnnotate } from '@/modules/agents/components/BrowserAnnotate';

type EditorKind = 'files' | 'file' | 'changes' | 'browser' | 'terminal';
type MenuKind = 'files' | 'terminal' | 'browser' | 'changes';
type ChangeView = 'files' | 'unstaged' | 'uncommitted' | 'diff' | 'commits';

const CHANGE_VIEWS: { id: ChangeView; label: string }[] = [
  { id: 'files', label: 'File changes' },
  { id: 'unstaged', label: 'Unstaged' },
  { id: 'uncommitted', label: 'Uncommitted' },
  { id: 'diff', label: 'All diff' },
  { id: 'commits', label: 'Commits' },
];

interface EditorTab {
  id: string;
  kind: EditorKind;
  title: string;
  path?: string;
  initialUrl?: string;
}

interface AgentRuntimeRailProps {
  sessionId: string;
  sandboxId?: string;
  sandboxReady?: boolean;
  onResume?: () => void;
  refreshToken: number;
  width: number;
  fullscreen: boolean;
  collapsed?: boolean;
  onWidthChange: (width: number) => void;
  onToggleFullscreen: () => void;
  onClose: () => void;
  onOpen?: () => void;
  onNote?: (message: AgentChatMessage) => void;
  showTerminal?: boolean;
}

const EDITOR_ACTIONS: { kind: MenuKind; label: string; Icon: React.ComponentType<{ size?: number; color?: string }> }[] = [
  { kind: 'files', label: 'File', Icon: File },
  { kind: 'terminal', label: 'Terminal', Icon: Terminal },
  { kind: 'browser', label: 'Browser', Icon: Globe },
  { kind: 'changes', label: 'Changes', Icon: GitCompare },
];

function filesExplorerTab(): EditorTab {
  return { id: 'files', kind: 'files', title: 'Files' };
}

interface TreeNode {
  name: string;
  path: string;
  type: 'file' | 'dir';
  children: TreeNode[];
}

export function AgentRuntimeRail({
  sessionId,
  sandboxId,
  sandboxReady = false,
  onResume,
  refreshToken,
  width,
  fullscreen,
  collapsed = false,
  onWidthChange,
  onToggleFullscreen,
  onClose,
  onOpen,
  onNote,
  showTerminal = true,
}: AgentRuntimeRailProps) {
  const [tabs, setTabs] = useState<EditorTab[]>([]);
  const [activeId, setActiveId] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuQuery, setMenuQuery] = useState('');
  const menuRef = useRef<HTMLDivElement | null>(null);
  const tabStripRef = useRef<HTMLDivElement | null>(null);
  const [entries, setEntries] = useState<WorkspaceEntry[]>([]);
  const [changes, setChanges] = useState<ChangeEntry[]>([]);
  const [changeBranch, setChangeBranch] = useState('');
  const [commits, setCommits] = useState<CommitEntry[]>([]);
  const [changeView, setChangeView] = useState<ChangeView>('uncommitted');
  const [changeMenu, setChangeMenu] = useState(false);
  const [patchText, setPatchText] = useState('');
  const [patchLoading, setPatchLoading] = useState(false);
  const changeMenuRef = useRef<HTMLDivElement | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [fileBodies, setFileBodies] = useState<Record<string, { text: string; saved: string; loading: boolean; saving: boolean; truncated: boolean; missing: boolean; error: string }>>({});
  const editorActions = EDITOR_ACTIONS.filter((action) => showTerminal || action.kind !== 'terminal');
  const [openChange, setOpenChange] = useState<string | null>(null);
  const [diffText, setDiffText] = useState('');
  const [diffLoading, setDiffLoading] = useState(false);

  const load = useCallback(async () => {
    try {
      const [files, changeList] = await Promise.all([
        agentRuntimeApi.listFiles(sessionId),
        agentRuntimeApi.listChanges(sessionId),
      ]);
      setEntries(files.entries || []);
      setChanges(changeList.entries || []);
      setChangeBranch(changeList.branch || '');
      setCommits(changeList.commits || []);
      setError('');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Workspace is not ready yet.');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load, refreshToken]);

  useEffect(() => {
    const timer = window.setInterval(load, 5000);
    return () => window.clearInterval(timer);
  }, [load]);

  useEffect(() => {
    if (changeView !== 'diff') return undefined;
    let cancelled = false;
    setPatchLoading(true);
    agentRuntimeApi.readPatch(sessionId)
      .then((result) => {
        if (!cancelled) setPatchText(result.diff || '');
      })
      .catch(() => {
        if (!cancelled) setPatchText('');
      })
      .finally(() => {
        if (!cancelled) setPatchLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [changeView, sessionId, refreshToken]);

  useEffect(() => {
    if (!changeMenu) return undefined;
    const close = (event: MouseEvent) => {
      if (!changeMenuRef.current?.contains(event.target as Node)) setChangeMenu(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [changeMenu]);

  const tree = useMemo(() => buildTree(entries), [entries]);
  const shownChanges = useMemo(() => {
    if (changeView === 'unstaged') return changes.filter((change) => change.unstaged !== false);
    return changes;
  }, [changes, changeView]);

  const openWorkspaceFile = async (path: string) => {
    const existing = tabs.find((item) => item.kind === 'file' && item.path === path);
    if (existing) {
      setActiveId(existing.id);
      return;
    }
    const name = path.split('/').pop() || path;
    const created: EditorTab = { id: `doc-${path}`, kind: 'file', title: name, path };
    setTabs((current) => (current.some((item) => item.kind === 'file' && item.path === path) ? current : [...current, created]));
    setActiveId(created.id);
    setFileBodies((current) => ({
      ...current,
      [path]: {
        text: current[path]?.text || '',
        saved: current[path]?.saved || '',
        loading: true,
        saving: false,
        truncated: false,
        missing: false,
        error: '',
      },
    }));
    try {
      const result = await agentRuntimeApi.readFile(sessionId, path);
      const text = result.missing ? '' : result.content || '';
      setFileBodies((current) => ({
        ...current,
        [path]: {
          text,
          saved: text,
          loading: false,
          saving: false,
          truncated: Boolean(result.truncated),
          missing: Boolean(result.missing),
          error: result.missing ? 'File not found.' : '',
        },
      }));
    } catch (err: any) {
      setFileBodies((current) => ({
        ...current,
        [path]: {
          text: '',
          saved: '',
          loading: false,
          saving: false,
          truncated: false,
          missing: false,
          error: err?.response?.data?.detail || 'Failed to read file.',
        },
      }));
    }
  };

  const saveWorkspaceFile = async (path: string) => {
    const body = fileBodies[path];
    if (!body || body.loading || body.saving || body.truncated || body.missing || body.text === body.saved) return;
    const text = body.text;
    setFileBodies((current) => ({ ...current, [path]: { ...current[path], saving: true, error: '' } }));
    try {
      await agentRuntimeApi.writeFile(sessionId, path, text);
      setFileBodies((current) => {
        const latest = current[path];
        if (!latest) return current;
        return { ...current, [path]: { ...latest, saved: text, saving: false, error: latest.text === text ? '' : latest.error } };
      });
      load();
    } catch (err: any) {
      setFileBodies((current) => ({
        ...current,
        [path]: { ...current[path], saving: false, error: err?.response?.data?.detail || 'Failed to save file.' },
      }));
    }
  };

  const openDiff = async (path: string) => {
    setOpenChange(path);
    setDiffLoading(true);
    try {
      const result = await agentRuntimeApi.readDiff(sessionId, path);
      setDiffText(result.diff || 'No diff.');
    } catch (err: any) {
      setDiffText(err?.response?.data?.detail || 'Failed to load diff.');
    } finally {
      setDiffLoading(false);
    }
  };

  useEffect(() => {
    if (!menuOpen) return undefined;
    const close = (event: MouseEvent) => {
      const target = event.target;
      if (target instanceof Element && menuRef.current?.contains(target)) return;
      setMenuOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false);
    };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', close);
      document.removeEventListener('keydown', onKey);
    };
  }, [menuOpen]);

  useEffect(() => {
    const strip = tabStripRef.current;
    const active = strip?.querySelector('.agent-runtime-editor-tab.is-active');
    if (!strip || !(active instanceof HTMLElement)) return;
    const stripRect = strip.getBoundingClientRect();
    const tabRect = active.getBoundingClientRect();
    if (tabRect.right > stripRect.right) strip.scrollLeft += tabRect.right - stripRect.right + 8;
    else if (tabRect.left < stripRect.left) strip.scrollLeft -= stripRect.left - tabRect.left + 8;
  }, [activeId, tabs.length]);

  const startResize = (event: React.MouseEvent) => {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = width;
    const move = (ev: MouseEvent) => {
      const maxWidth = Math.max(320, window.innerWidth - 980);
      const next = Math.min(Math.max(320, startWidth - (ev.clientX - startX)), maxWidth);
      onWidthChange(next);
    };
    const up = () => {
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', up);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
  };

  const openTab = (kind: MenuKind, initialUrl?: string) => {
    if (kind === 'terminal' && !showTerminal) return;
    onOpen?.();
    setMenuOpen(false);
    setMenuQuery('');
    if (kind === 'files' || kind === 'changes') {
      const existing = tabs.find((item) => item.kind === kind);
      if (existing) {
        setActiveId(existing.id);
        return;
      }
      const created: EditorTab = kind === 'files' ? filesExplorerTab() : { id: 'changes', kind: 'changes', title: 'Changes' };
      setTabs((current) => (current.some((item) => item.kind === kind) ? current : [...current, created]));
      setActiveId(created.id);
      return;
    }
    const same = tabs.filter((item) => item.kind === kind).length;
    const base = kind === 'browser' ? 'Browser' : 'Terminal';
    let title = same === 0 ? base : `${base} ${same + 1}`;
    const normalized = initialUrl ? normalizeUrl(initialUrl) : '';
    if (kind === 'browser' && normalized) {
      try {
        title = new URL(normalized).host || title;
      } catch {
        title = normalized;
      }
    }
    const created: EditorTab = {
      id: `${kind}-${Date.now()}-${same}`,
      kind,
      title,
      initialUrl: normalized || undefined,
    };
    setTabs((current) => [...current, created]);
    setActiveId(created.id);
  };

  const closeTab = (id: string) => {
    const index = tabs.findIndex((item) => item.id === id);
    const next = tabs.filter((item) => item.id !== id);
    setTabs(next);
    if (activeId === id) {
      setActiveId((next[index] || next[index - 1])?.id || '');
    }
  };

  const submitMenu = (value: string) => {
    const query = value.trim().toLowerCase();
    const matches = editorActions.filter((action) => !query || action.label.toLowerCase().includes(query) || action.kind.includes(query));
    if (matches.length === 1 && (!query || matches[0].label.toLowerCase().startsWith(query) || matches[0].kind.startsWith(query))) {
      openTab(matches[0].kind);
      return;
    }
    if (value.trim()) openTab('browser', value.trim());
  };

  const query = menuQuery.trim().toLowerCase();
  const menuActions = editorActions.filter((action) => !query || action.label.toLowerCase().includes(query) || action.kind.includes(query));
  const activeTab = tabs.find((item) => item.id === activeId) || null;
  const showFiles = tabs.some((item) => item.kind === 'files');
  const showChanges = tabs.some((item) => item.kind === 'changes');
  const collapsedIcon = (kind: MenuKind) => {
    const match = tabs.find((item) => item.kind === kind);
    return Boolean(match && match.id === activeId);
  };

  if (collapsed && !fullscreen) {
    return (
      <aside
        aria-label="Editor"
        style={{
          width: 40,
          minWidth: 40,
          flex: '0 0 40px',
          background: '#f8fafc',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 4,
          padding: '8px 0',
          minHeight: 0,
          borderLeft: '1px solid #e2e8f0',
        }}
      >
        {editorActions.map((action) => {
          const selected = collapsedIcon(action.kind);
          return (
            <button
              key={action.kind}
              type="button"
              aria-label={action.label}
              title={action.label}
              onClick={() => openTab(action.kind)}
              style={{
                width: 28,
                height: 28,
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                border: 'none',
                borderRadius: 6,
                background: selected ? '#e2e8f0' : 'transparent',
                color: selected ? '#0f172a' : '#475569',
                cursor: 'pointer',
                padding: 0,
              }}
            >
              <action.Icon size={16} />
            </button>
          );
        })}
      </aside>
    );
  }

  return (
    <aside
      style={{
        width: fullscreen ? undefined : width,
        minWidth: fullscreen ? 0 : width,
        maxWidth: fullscreen ? undefined : width,
        flex: fullscreen ? 1 : '0 0 auto',
        background: '#ffffff',
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
        borderLeft: '1px solid #e2e8f0',
        position: 'relative',
      }}
    >
      {!fullscreen && (
        <div
          className="agent-runtime-rail-resize"
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize panel"
          tabIndex={0}
          onMouseDown={startResize}
        />
      )}
      <div style={{ display: 'flex', alignItems: 'stretch', height: 35, borderBottom: '1px solid #e2e8f0', background: '#f3f4f6', flexShrink: 0, position: 'relative', zIndex: 20 }}>
        <div ref={menuRef} style={{ position: 'relative', display: 'flex', alignItems: 'stretch', minWidth: 0, flex: 1 }}>
          <div ref={tabStripRef} className="agent-runtime-tab-strip" style={{ display: 'flex', alignItems: 'stretch', overflowX: 'auto', minWidth: 0 }}>
            {tabs.map((item) => (
              <EditorTabButton
                key={item.id}
                tab={item}
                active={item.id === activeId}
                dirty={Boolean(item.path && fileBodies[item.path] && !fileBodies[item.path].loading && fileBodies[item.path].text !== fileBodies[item.path].saved)}
                onSelect={() => setActiveId(item.id)}
                onClose={() => closeTab(item.id)}
              />
            ))}
          </div>
          <button
            type="button"
            aria-label="New tab"
            onClick={() => {
              setMenuOpen((open) => !open);
              setMenuQuery('');
            }}
            style={{
              width: 26,
              height: 26,
              alignSelf: 'center',
              flexShrink: 0,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: 'none',
              borderRadius: 6,
              background: menuOpen ? '#e5e7eb' : 'transparent',
              color: '#475569',
              cursor: 'pointer',
            }}
          >
            <Plus size={15} />
          </button>
          {menuOpen && (
            <div
              role="menu"
              style={{
                position: 'absolute',
                top: 32,
                left: 0,
                width: 240,
                zIndex: 30,
                background: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: 10,
                boxShadow: '0 12px 32px rgba(15, 23, 42, 0.16)',
                padding: 6,
              }}
            >
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  submitMenu(menuQuery);
                }}
              >
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 8px' }}>
                  <Search size={14} color="#94a3b8" />
                  <input
                    autoFocus
                    value={menuQuery}
                    onChange={(event) => setMenuQuery(event.target.value)}
                    placeholder="Open any file, URL…"
                    aria-label="Open any file, URL"
                    style={{ flex: 1, border: 'none', outline: 'none', background: 'transparent', fontSize: '0.8rem', color: '#0f172a' }}
                  />
                </label>
              </form>
              {menuActions.map((action) => {
                const singletonOpen = (action.kind === 'files' || action.kind === 'changes') && tabs.some((item) => item.kind === action.kind);
                return (
                  <button
                    key={action.kind}
                    type="button"
                    role="menuitem"
                    onClick={() => openTab(action.kind)}
                    style={{ ...rowButton, borderRadius: 8, padding: '7px 8px' }}
                  >
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                      <action.Icon size={15} color="#475569" />
                      {action.label}
                    </span>
                    {singletonOpen && <span style={{ color: '#94a3b8', fontSize: '0.7rem' }}>Open</span>}
                  </button>
                );
              })}
            </div>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', flexShrink: 0, paddingRight: 4 }}>
          <button
            type="button"
            aria-label={fullscreen ? 'Exit full screen' : 'Full screen'}
            title={fullscreen ? 'Exit full screen' : 'Full screen'}
            onClick={onToggleFullscreen}
            style={panelIconButton}
          >
            {fullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          </button>
          <button type="button" aria-label="Close panel" title="Close panel" onClick={onClose} style={panelIconButton}>
            <X size={14} />
          </button>
        </div>
      </div>
      <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', position: 'relative' }}>
      {!tabs.length && <EditorPicker onOpen={openTab} showTerminal={showTerminal} />}
      {showFiles && (
      <section style={{ flex: 1, minHeight: 0, display: activeTab?.kind === 'files' ? 'flex' : 'none', flexDirection: 'column' }}>
        <div style={{ flex: 1, overflow: 'auto', padding: '6px 8px 10px' }}>
          {error && !entries.length ? (
            <EmptyText>{error}</EmptyText>
          ) : tree.length ? (
            <FileTree nodes={tree} depth={0} onOpen={openWorkspaceFile} />
          ) : (
            <EmptyText>{loading ? 'Loading workspace…' : 'No files in /workspace yet.'}</EmptyText>
          )}
        </div>
      </section>
      )}
      {tabs.filter((item) => item.kind === 'file').map((item) => {
        const path = item.path || '';
        const body = fileBodies[path];
        const dirty = Boolean(body && !body.loading && body.text !== body.saved);
        return (
        <section key={item.id} style={{ flex: 1, minHeight: 0, display: activeId === item.id ? 'flex' : 'none', flexDirection: 'column' }}>
          <div style={{ height: 32, padding: '0 8px 0 12px', borderBottom: '1px solid #f1f5f9', display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
            <span style={{ flex: 1, minWidth: 0, fontSize: '0.72rem', color: '#64748b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{path}</span>
            {body?.error && <span style={{ fontSize: '0.72rem', color: '#b91c1c', flexShrink: 0 }}>{body.error}</span>}
            <button
              type="button"
              disabled={!dirty || Boolean(body?.saving)}
              onClick={() => saveWorkspaceFile(path)}
              style={{
                border: 'none',
                borderRadius: 6,
                background: dirty ? '#18181b' : 'transparent',
                color: dirty ? '#ffffff' : '#94a3b8',
                fontSize: '0.72rem',
                fontWeight: 600,
                padding: '4px 8px',
                cursor: dirty ? 'pointer' : 'default',
              }}
            >
              {body?.saving ? 'Saving…' : dirty ? 'Save' : 'Saved'}
            </button>
          </div>
          <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
            {body?.loading ? (
              <div style={{ padding: 12, fontSize: '0.78rem', color: '#64748b' }}>Loading…</div>
            ) : (
              <WorkspaceFileEditor
                path={path}
                value={body?.text || ''}
                readOnly={Boolean(body?.truncated || body?.missing)}
                onChange={(text) => setFileBodies((current) => ({ ...current, [path]: { ...current[path], text } }))}
                onSave={() => saveWorkspaceFile(path)}
              />
            )}
          </div>
        </section>
        );
      })}
      {showChanges && (
      <section style={{ flex: 1, minHeight: 0, display: activeTab?.kind === 'changes' ? 'flex' : 'none', flexDirection: 'column' }}>
        <ChangesHeader
          menuRef={changeMenuRef}
          open={changeMenu}
          view={changeView}
          branch={changeBranch}
          additions={shownChanges.reduce((sum, change) => sum + (change.additions || 0), 0)}
          deletions={shownChanges.reduce((sum, change) => sum + (change.deletions || 0), 0)}
          onToggle={() => setChangeMenu((value) => !value)}
          onSelect={(view) => {
            setChangeView(view);
            setChangeMenu(false);
            setOpenChange(null);
          }}
        />
        <div style={{ flex: 1, overflow: 'auto', padding: '6px 8px 10px' }}>
          {openChange ? (
            <Viewer title={openChange} loading={diffLoading} text={diffText} diff onBack={() => setOpenChange(null)} />
          ) : changeView === 'diff' ? (
            patchLoading ? <EmptyText>Loading diff…</EmptyText> : patchText ? <DiffText text={patchText} /> : <EmptyText>No uncommitted diff.</EmptyText>
          ) : changeView === 'commits' ? (
            commits.length ? commits.map((commit) => (
              <div key={commit.hash} style={{ ...rowButton, cursor: 'default' }}>
                <span style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', minWidth: 0, flex: 1, gap: 2 }}>
                  <span style={{ fontSize: '0.78rem', color: '#0f172a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '100%' }}>{commit.subject || commit.hash}</span>
                  <span style={{ fontSize: '0.7rem', color: '#64748b' }}>{commit.hash} · {commit.author} · {commit.date}</span>
                </span>
              </div>
            )) : <EmptyText>No commits yet. These files are still uncommitted.</EmptyText>
          ) : shownChanges.length ? (
            shownChanges.map((change) => (
              <button
                key={`${change.status}-${change.path}`}
                type="button"
                onClick={() => openDiff(change.path)}
                style={rowButton}
              >
                <span style={{ minWidth: 0, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', textAlign: 'left' }}>
                  {change.path}
                </span>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, flexShrink: 0, fontSize: '0.7rem', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace' }}>
                  <span style={{ color: '#64748b' }}>{change.status}</span>
                  <span style={{ color: '#15803d' }}>+{change.additions}</span>
                  <span style={{ color: '#b91c1c' }}>-{change.deletions}</span>
                </span>
              </button>
            ))
          ) : (
            <EmptyText>{loading ? 'Looking for changes…' : 'No code changes yet.'}</EmptyText>
          )}
        </div>
      </section>
      )}
      {tabs.filter((item) => item.kind === 'browser').map((item) => (
        <div key={item.id} style={{ flex: 1, minHeight: 0, width: '100%', display: activeId === item.id ? 'flex' : 'none', flexDirection: 'column' }}>
          <BrowserPanel
            sessionId={sessionId}
            tabId={item.id}
            active={activeId === item.id}
            sandboxId={sandboxId}
            initialUrl={item.initialUrl}
            onSent={onNote}
            onTitle={(title) => {
              setTabs((current) => {
                const match = current.find((tab) => tab.id === item.id);
                if (!match || match.title === title) return current;
                return current.map((tab) => (tab.id === item.id ? { ...tab, title } : tab));
              });
            }}
          />
        </div>
      ))}
      {tabs.filter((item) => item.kind === 'terminal').map((item) => (
        <div key={item.id} style={{ flex: 1, minHeight: 0, display: activeId === item.id ? 'flex' : 'none', flexDirection: 'column', background: '#ffffff' }}>
          {sandboxId ? (
            <SandboxTerminal
              sandboxId={sandboxId}
              sandboxName={item.title}
              workingDir="/workspace"
              isRunning={sandboxReady}
              onResume={onResume}
              isDark={false}
              embedded
              fullHeight
            />
          ) : (
            <EmptyText>Sandbox is not ready yet.</EmptyText>
          )}
        </div>
      ))}
      </div>
    </aside>
  );
}

const panelIconButton: React.CSSProperties = {
  width: 26,
  height: 26,
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  border: 'none',
  borderRadius: 6,
  background: 'transparent',
  color: '#475569',
  cursor: 'pointer',
};

function EditorTabButton({
  tab,
  active,
  dirty,
  onSelect,
  onClose,
}: {
  tab: EditorTab;
  active: boolean;
  dirty?: boolean;
  onSelect: () => void;
  onClose: () => void;
}) {
  const Icon = tab.kind === 'changes' ? GitCompare : tab.kind === 'browser' ? Globe : tab.kind === 'terminal' ? Terminal : tab.kind === 'files' ? Folder : File;
  const iconColor = tab.kind === 'files' ? '#b45309' : tab.kind === 'changes' ? '#64748b' : tab.kind === 'browser' ? '#2563eb' : tab.kind === 'terminal' ? '#0f766e' : '#64748b';
  return (
    <div
      className={`agent-runtime-editor-tab${active ? ' is-active' : ''}`}
      title={tab.path || tab.title}
      onClick={onSelect}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        maxWidth: 180,
        flexShrink: 0,
        height: 35,
        padding: '0 4px 0 10px',
        cursor: 'pointer',
        userSelect: 'none',
      }}
    >
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          minWidth: 0,
          fontSize: '13px',
          fontWeight: 400,
          lineHeight: 1,
        }}
      >
        <Icon size={15} color={iconColor} style={{ flexShrink: 0 }} />
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{tab.title}</span>
      </span>
      <span style={{ position: 'relative', width: 18, height: 18, flexShrink: 0 }}>
        {dirty && (
          <span
            data-tab-dirty
            style={{ position: 'absolute', top: 5, left: 5, width: 8, height: 8, borderRadius: 8, background: '#71717a' }}
          />
        )}
        <button
          type="button"
          data-tab-close
          aria-label={`Close ${tab.title}`}
          onClick={(event) => {
            event.stopPropagation();
            onClose();
          }}
          style={{
            position: 'absolute',
            inset: 0,
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            border: 'none',
            borderRadius: 4,
            background: 'transparent',
            color: 'inherit',
            cursor: 'pointer',
            padding: 0,
          }}
        >
          <X size={13} />
        </button>
      </span>
    </div>
  );
}

function EditorPicker({ onOpen, showTerminal = true }: { onOpen: (kind: MenuKind) => void; showTerminal?: boolean }) {
  const tiles = [
    EDITOR_ACTIONS.find((action) => action.kind === 'changes')!,
    EDITOR_ACTIONS.find((action) => action.kind === 'browser')!,
    showTerminal ? EDITOR_ACTIONS.find((action) => action.kind === 'terminal') : null,
    EDITOR_ACTIONS.find((action) => action.kind === 'files')!,
  ].filter(Boolean) as typeof EDITOR_ACTIONS;
  return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f8fafc' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '112px 112px', gap: 12 }}>
        {tiles.map((action) => (
          <button
            key={action.kind}
            type="button"
            onClick={() => onOpen(action.kind)}
            style={{
              height: 92,
              borderRadius: 12,
              border: '1px solid #e2e8f0',
              background: '#ffffff',
              color: '#334155',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              cursor: 'pointer',
              fontSize: '0.78rem',
              fontWeight: 600,
            }}
          >
            <action.Icon size={18} color="#64748b" />
            {action.label}
          </button>
        ))}
      </div>
    </div>
  );
}

const BROWSER_RECENTS_KEY = 'agent-runtime-browser-recents';

function readRecents(): string[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(BROWSER_RECENTS_KEY) || '[]');
    return Array.isArray(parsed) ? parsed.filter((item) => typeof item === 'string') : [];
  } catch {
    return [];
  }
}

function normalizeUrl(value: string) {
  const raw = value.trim();
  if (!raw) return '';
  if (/^https?:\/\//i.test(raw)) return raw;
  if (/^(localhost|127\.0\.0\.1|\d+\.\d+\.\d+\.\d+)(:\d+)?(\/|$)/i.test(raw)) return `http://${raw}`;
  return `https://${raw}`;
}

function BrowserPanel({
  sessionId,
  tabId,
  active,
  sandboxId,
  initialUrl = '',
  onTitle,
  onSent,
}: {
  sessionId: string;
  tabId: string;
  active: boolean;
  sandboxId?: string;
  initialUrl?: string;
  onTitle?: (title: string) => void;
  onSent?: (message: AgentChatMessage) => void;
}) {
  const [draft, setDraft] = useState(initialUrl);
  const [currentUrl, setCurrentUrl] = useState(initialUrl);
  const [recents, setRecents] = useState<string[]>(() => readRecents());
  const [sandboxUrls, setSandboxUrls] = useState<string[]>([]);
  const [annotating, setAnnotating] = useState(false);
  const [frameUrl, setFrameUrl] = useState('');
  const [pageSize, setPageSize] = useState({ width: 0, height: 0 });
  const [browserError, setBrowserError] = useState('');
  const stageRef = useRef<HTMLDivElement | null>(null);
  const viewRef = useRef<HTMLImageElement | null>(null);
  const moveAt = useRef(0);

  useEffect(() => {
    if (!sandboxId) return undefined;
    let cancelled = false;
    computeApi.getSandbox(sandboxId).then((sandbox) => {
      if (cancelled) return;
      const urls = Object.values(sandbox?.endpoints || {}).filter((url) => typeof url === 'string' && url);
      setSandboxUrls(urls as string[]);
    }).catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [sandboxId]);

  useEffect(() => {
    if (!currentUrl || !active) return undefined;
    let stopped = false;
    let timer = 0;
    const openAndWatch = async () => {
      const stage = stageRef.current;
      const width = Math.max(320, Math.round(stage?.clientWidth || 360));
      const height = Math.max(240, Math.round(stage?.clientHeight || 640));
      try {
        const opened = await agentRuntimeApi.openBrowser(sessionId, tabId, currentUrl, width, height);
        if (stopped) return;
        setPageSize({ width: opened.width, height: opened.height });
        setBrowserError(opened.error || '');
      } catch (err: any) {
        if (!stopped) setBrowserError(err?.response?.data?.detail || err?.message || 'Could not open the browser');
        return;
      }
      const pull = async () => {
        if (stopped) return;
        try {
          const blob = await agentRuntimeApi.browserFrame(sessionId, tabId);
          if (stopped) return;
          const next = URL.createObjectURL(blob);
          setFrameUrl((prev) => {
            if (prev) URL.revokeObjectURL(prev);
            return next;
          });
        } catch (err: any) {
          if (!stopped) setBrowserError(err?.response?.data?.detail || err?.message || 'The browser frame failed');
        }
        timer = window.setTimeout(pull, 200);
      };
      pull();
    };
    openAndWatch();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [active, currentUrl, sessionId, tabId]);

  const toPage = (clientX: number, clientY: number) => {
    const view = viewRef.current?.getBoundingClientRect();
    if (!view || !pageSize.width || !pageSize.height) return null;
    return {
      x: ((clientX - view.left) / view.width) * pageSize.width,
      y: ((clientY - view.top) / view.height) * pageSize.height,
    };
  };

  const visit = (value: string) => {
    const url = normalizeUrl(value);
    if (!url) return;
    setCurrentUrl(url);
    setDraft(url);
    try {
      onTitle?.(new URL(url).host || url);
    } catch {
      onTitle?.(url);
    }
    setRecents((current) => {
      const next = [url, ...current.filter((item) => item !== url)].slice(0, 12);
      localStorage.setItem(BROWSER_RECENTS_KEY, JSON.stringify(next));
      return next;
    });
  };

  const suggestions = [...sandboxUrls, ...recents.filter((url) => !sandboxUrls.includes(url))];

  return (
    <section style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', background: '#f8fafc' }}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          visit(draft);
        }}
        style={{ padding: '10px 10px 8px' }}
      >
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 999, padding: '6px 10px' }}>
          <Search size={14} color="#94a3b8" />
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Search or enter URL"
            aria-label="Search or enter URL"
            style={{ flex: 1, border: 'none', outline: 'none', background: 'transparent', fontSize: '0.78rem', color: '#0f172a' }}
          />
          {currentUrl && (
            <button
              type="button"
              aria-pressed={annotating}
              onClick={() => setAnnotating((value) => !value)}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 4, border: 'none', background: annotating ? '#18181b' : 'transparent', color: annotating ? '#ffffff' : '#18181b', borderRadius: 999, padding: '3px 8px', cursor: 'pointer', fontSize: '0.72rem', fontWeight: 650 }}
            >
              <PenLine size={12} />
              Annotate
            </button>
          )}
        </label>
      </form>
      {currentUrl ? (
        <div
          ref={stageRef}
          tabIndex={0}
          onMouseDown={(event) => {
            if (annotating) return;
            stageRef.current?.focus();
            const point = toPage(event.clientX, event.clientY);
            if (!point) return;
            agentRuntimeApi.browserInput(sessionId, tabId, { kind: event.detail === 2 ? 'double' : 'click', x: point.x, y: point.y }).catch(() => undefined);
          }}
          onMouseMove={(event) => {
            if (annotating) return;
            const now = Date.now();
            if (now - moveAt.current < 40) return;
            moveAt.current = now;
            const point = toPage(event.clientX, event.clientY);
            if (!point) return;
            agentRuntimeApi.browserInput(sessionId, tabId, { kind: 'move', x: point.x, y: point.y }).catch(() => undefined);
          }}
          onWheel={(event) => {
            if (annotating) return;
            const point = toPage(event.clientX, event.clientY);
            if (!point) return;
            agentRuntimeApi.browserInput(sessionId, tabId, { kind: 'wheel', x: point.x, y: point.y, delta_y: event.deltaY }).catch(() => undefined);
          }}
          onKeyDown={(event) => {
            if (annotating) return;
            const text = event.key.length === 1 ? event.key : '';
            agentRuntimeApi.browserInput(sessionId, tabId, { kind: 'key', text, key: event.key }).catch(() => undefined);
            if (text || ['Enter', 'Backspace', 'Tab', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Delete'].includes(event.key)) {
              event.preventDefault();
            }
          }}
          style={{ flex: 1, minHeight: 0, position: 'relative', outline: 'none', background: '#ffffff' }}
        >
          {frameUrl ? (
            <img ref={viewRef} src={frameUrl} alt="" draggable={false} style={{ width: '100%', height: '100%', objectFit: 'fill', display: 'block' }} />
          ) : (
            <div style={{ padding: 16, color: '#71717a', fontSize: '0.78rem' }}>{browserError || 'Opening browser…'}</div>
          )}
          {browserError && frameUrl && (
            <div style={{ position: 'absolute', left: 8, right: 8, bottom: 8, zIndex: 2, padding: '6px 8px', borderRadius: 8, background: '#fef2f2', color: '#991b1b', fontSize: '0.72rem' }}>{browserError}</div>
          )}
          {annotating && onSent && frameUrl && (
            <BrowserAnnotate
              viewRef={viewRef}
              stageRef={stageRef}
              pageWidth={pageSize.width}
              pageHeight={pageSize.height}
              onInspect={(x, y) => agentRuntimeApi.inspectBrowser(sessionId, tabId, x, y)}
              onSend={async (box, instruction) => {
                const message = await agentRuntimeApi.sendBrowserNote(sessionId, tabId, {
                  instruction,
                  x: box.left,
                  y: box.top,
                  width: box.width,
                  height: box.height,
                });
                onSent(message);
              }}
              onExit={() => setAnnotating(false)}
            />
          )}
        </div>
      ) : (
        <div style={{ flex: 1, overflow: 'auto', padding: '4px 8px 12px' }}>
          <div style={{ padding: '8px 8px 4px', fontSize: '0.72rem', color: '#94a3b8', fontWeight: 650 }}>Recents</div>
          {suggestions.length ? (
            suggestions.map((url) => (
              <button key={url} type="button" onClick={() => visit(url)} style={{ ...rowButton, justifyContent: 'flex-start', gap: 8 }}>
                <Globe size={14} color="#64748b" />
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{url.replace(/^https?:\/\//, '')}</span>
              </button>
            ))
          ) : (
            <EmptyText>No recent pages. Enter a URL to open the sandbox app.</EmptyText>
          )}
        </div>
      )}
    </section>
  );
}

function ChangesHeader({
  menuRef,
  open,
  view,
  branch,
  additions,
  deletions,
  onToggle,
  onSelect,
}: {
  menuRef: React.RefObject<HTMLDivElement | null>;
  open: boolean;
  view: ChangeView;
  branch: string;
  additions: number;
  deletions: number;
  onToggle: () => void;
  onSelect: (view: ChangeView) => void;
}) {
  const label = CHANGE_VIEWS.find((item) => item.id === view)?.label || 'Uncommitted';
  return (
    <div ref={menuRef} style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', borderBottom: '1px solid #e4e4e7' }}>
      <button
        type="button"
        aria-expanded={open}
        onClick={onToggle}
        style={{ display: 'inline-flex', alignItems: 'center', gap: 4, border: 'none', background: 'transparent', padding: 0, cursor: 'pointer', fontSize: '0.82rem', fontWeight: 650, color: '#18181b' }}
      >
        {label}
        <ChevronDown size={14} color="#71717a" />
      </button>
      <span style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace', fontSize: '0.72rem', color: '#15803d' }}>+{additions}</span>
      <span style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace', fontSize: '0.72rem', color: '#b91c1c' }}>-{deletions}</span>
      <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: '#52525b' }}>{branch || 'main'}</span>
      {open && (
        <div style={{ position: 'absolute', top: '100%', left: 8, zIndex: 5, minWidth: 180, padding: 4, background: '#ffffff', border: '1px solid #e4e4e7', borderRadius: 8, boxShadow: '0 8px 24px rgba(0,0,0,0.08)' }}>
          {CHANGE_VIEWS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onSelect(item.id)}
              style={{ display: 'block', width: '100%', textAlign: 'left', border: 'none', background: item.id === view ? '#f4f4f5' : 'transparent', borderRadius: 6, padding: '7px 8px', cursor: 'pointer', fontSize: '0.8rem', color: '#18181b' }}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function DiffText({ text }: { text: string }) {
  return (
    <pre style={{ margin: 0, padding: 8, background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, fontSize: '0.72rem', lineHeight: 1.45, overflow: 'auto', whiteSpace: 'pre', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace' }}>
      {text.split('\n').map((line, index) => {
        const color = line.startsWith('+') && !line.startsWith('+++') ? '#15803d' : line.startsWith('-') && !line.startsWith('---') ? '#b91c1c' : '#3f3f46';
        return <div key={index} style={{ color }}>{line || ' '}</div>;
      })}
    </pre>
  );
}

function EmptyText({ children }: { children: React.ReactNode }) {
  return <div style={{ padding: '12px 10px', color: '#64748b', fontSize: '0.78rem', lineHeight: 1.45 }}>{children}</div>;
}

function Viewer({
  title,
  text,
  loading,
  diff = false,
  onBack,
}: {
  title: string;
  text: string;
  loading: boolean;
  diff?: boolean;
  onBack: () => void;
}) {
  return (
    <div>
      <button type="button" onClick={onBack} style={{ ...rowButton, fontWeight: 650, marginBottom: 6 }}>
        Back to {diff ? 'changes' : 'files'}
      </button>
      <div style={{ fontSize: '0.75rem', fontWeight: 650, color: '#0f172a', margin: '0 4px 8px', wordBreak: 'break-all' }}>{title}</div>
      {loading ? (
        <EmptyText>Loading…</EmptyText>
      ) : (
        <pre
          style={{
            margin: 0,
            padding: 8,
            background: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: 8,
            fontSize: '0.72rem',
            lineHeight: 1.45,
            overflow: 'auto',
            whiteSpace: 'pre',
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
          }}
        >
          {diff
            ? text.split('\n').map((line, index) => (
                <div key={`${index}-${line.slice(0, 12)}`} style={{ color: diffColor(line) }}>
                  {line || ' '}
                </div>
              ))
            : text}
        </pre>
      )}
    </div>
  );
}

function FileTree({ nodes, depth, onOpen }: { nodes: TreeNode[]; depth: number; onOpen: (path: string) => void }) {
  return (
    <>
      {nodes.map((node) => (
        <TreeRow key={node.path || node.name} node={node} depth={depth} onOpen={onOpen} />
      ))}
    </>
  );
}

function TreeRow({ node, depth, onOpen }: { node: TreeNode; depth: number; onOpen: (path: string) => void }) {
  const [open, setOpen] = useState(depth < 1);
  if (node.type === 'dir') {
    return (
      <div>
        <button type="button" onClick={() => setOpen((value) => !value)} style={{ ...rowButton, justifyContent: 'flex-start', paddingLeft: 8 + depth * 12 }}>
          <ChevronRight size={12} style={{ transform: open ? 'rotate(90deg)' : undefined, color: '#94a3b8', flexShrink: 0 }} />
          {open ? <FolderOpen size={14} color="#64748b" /> : <Folder size={14} color="#64748b" />}
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{node.name}</span>
        </button>
        {open && <FileTree nodes={node.children} depth={depth + 1} onOpen={onOpen} />}
      </div>
    );
  }
  return (
    <button type="button" onClick={() => onOpen(node.path)} style={{ ...rowButton, justifyContent: 'flex-start', paddingLeft: 8 + depth * 12 }}>
      <File size={14} color="#64748b" />
      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{node.name}</span>
    </button>
  );
}

function buildTree(entries: WorkspaceEntry[]): TreeNode[] {
  const root: TreeNode = { name: '', path: '', type: 'dir', children: [] };
  const dirs = new Map<string, TreeNode>([['', root]]);
  const ensureDir = (path: string) => {
    if (dirs.has(path)) return dirs.get(path)!;
    const parentPath = path.includes('/') ? path.slice(0, path.lastIndexOf('/')) : '';
    const parent = ensureDir(parentPath);
    const node: TreeNode = { name: path.slice(path.lastIndexOf('/') + 1), path, type: 'dir', children: [] };
    parent.children.push(node);
    dirs.set(path, node);
    return node;
  };
  entries.forEach((entry) => {
    if (!entry.path) return;
    if (entry.type === 'dir') {
      ensureDir(entry.path);
      return;
    }
    const parentPath = entry.path.includes('/') ? entry.path.slice(0, entry.path.lastIndexOf('/')) : '';
    const parent = ensureDir(parentPath);
    parent.children.push({
      name: entry.path.slice(entry.path.lastIndexOf('/') + 1),
      path: entry.path,
      type: 'file',
      children: [],
    });
  });
  const sortNodes = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => {
      if (a.type !== b.type) return a.type === 'dir' ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    nodes.forEach((node) => sortNodes(node.children));
  };
  sortNodes(root.children);
  return root.children;
}

function diffColor(line: string) {
  if (line.startsWith('+++') || line.startsWith('---')) return '#64748b';
  if (line.startsWith('@@')) return '#1d4ed8';
  if (line.startsWith('+')) return '#15803d';
  if (line.startsWith('-')) return '#b91c1c';
  return '#334155';
}

const rowButton: React.CSSProperties = {
  width: '100%',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 8,
  border: 'none',
  background: 'transparent',
  borderRadius: 6,
  padding: '5px 8px',
  cursor: 'pointer',
  color: '#0f172a',
  fontSize: '0.78rem',
  textAlign: 'left',
};
