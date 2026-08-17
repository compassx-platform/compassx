/**
 * PageTabBar — page tabs with add/rename/clone/delete.
 * Reference: Databricks dashboard page tabs UI.
 */

import { useState, useRef, useEffect } from 'react';
import { Plus, MoreVertical, Copy, Trash2, Database, Funnel } from 'lucide-react';
import { useDashboardStore } from '@/modules/dashboards/stores/dashboardStore';

interface Props {
  activeTab: 'data' | 'page';
  onSelectDataTab: () => void;
  onSelectPageTab: () => void;
}

export default function PageTabBar({ activeTab, onSelectDataTab, onSelectPageTab }: Props) {
  const { activeDashboard, activePageId, editMode } = useDashboardStore();
  const { setActivePageId, addPage, deletePage, renamePage, clonePage } = useDashboardStore();

  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const renameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (renamingId && renameRef.current) renameRef.current.focus();
  }, [renamingId]);

  if (!activeDashboard) return null;

  function startRename(id: string, currentName: string) {
    setOpenMenuId(null);
    setRenamingId(id);
    setRenameValue(currentName);
  }

  function commitRename() {
    if (renamingId && renameValue.trim()) {
      renamePage(renamingId, renameValue.trim());
    }
    setRenamingId(null);
  }

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      borderBottom: '1px solid var(--color-border)',
      background: 'var(--color-surface)',
      paddingLeft: editMode ? 12 : 16,
      paddingRight: editMode ? 12 : 16,
      overflow: 'visible',
      flexShrink: 0,
      zIndex: 100,
    }}>
      {editMode && (
        <>
          <button
            type="button"
            onClick={onSelectDataTab}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              height: 38,
              padding: '0 12px',
              border: 'none',
              borderBottom: activeTab === 'data' ? '2px solid var(--color-primary)' : '2px solid transparent',
              background: 'transparent',
              color: activeTab === 'data' ? 'var(--color-text)' : 'var(--color-text-muted)',
              fontSize: '0.82rem',
              fontWeight: activeTab === 'data' ? 600 : 500,
              cursor: 'pointer',
              flexShrink: 0,
            }}
          >
            <Database size={14} />
            <span>Data</span>
          </button>
          <div style={{ width: 1, height: 18, background: 'var(--color-border)', margin: '0 10px 0 2px', flexShrink: 0 }} />
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              height: 38,
              paddingRight: 10,
              color: 'var(--color-text-muted)',
              flexShrink: 0,
            }}
          >
            <Funnel size={14} />
          </div>
        </>
      )}

      {activeDashboard.pages
        .slice()
        .sort((a, b) => a.order - b.order)
        .map((page) => {
          const isActive = activeTab === 'page' && page.id === activePageId;
          return (
            <div
              key={page.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                padding: '0 4px 0 12px',
                height: 38,
                borderBottom: isActive ? '2px solid var(--color-primary)' : '2px solid transparent',
                cursor: 'pointer',
                flexShrink: 0,
                position: 'relative',
              }}
              onClick={() => {
                if (!renamingId) {
                  onSelectPageTab();
                  setActivePageId(page.id);
                }
              }}
            >
              {renamingId === page.id ? (
                <input
                  ref={renameRef}
                  value={renameValue}
                  onChange={(e) => setRenameValue(e.target.value)}
                  onBlur={commitRename}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') commitRename();
                    if (e.key === 'Escape') setRenamingId(null);
                  }}
                  onClick={(e) => e.stopPropagation()}
                  style={{
                    fontSize: '0.82rem',
                    fontWeight: 500,
                    border: '1px solid var(--color-primary)',
                    borderRadius: 3,
                    padding: '2px 6px',
                    width: 100,
                    background: 'var(--color-surface)',
                    color: 'var(--color-text)',
                  }}
                />
              ) : (
                <span
                  style={{
                    fontSize: '0.82rem',
                    fontWeight: isActive ? 600 : 400,
                    color: isActive ? 'var(--color-text)' : 'var(--color-text-muted)',
                    whiteSpace: 'nowrap',
                    userSelect: 'none',
                  }}
                  onDoubleClick={() => editMode && startRename(page.id, page.name)}
                >
                  {page.name}
                </span>
              )}

              {editMode && (
                <div onClick={(e) => e.stopPropagation()} style={{ position: 'relative' }}>
                  <button
                    className="btn-icon"
                    style={{ opacity: 0.5, padding: '2px 3px' }}
                    onClick={() => setOpenMenuId(openMenuId === page.id ? null : page.id)}
                  >
                    <MoreVertical size={12} />
                  </button>
                  {openMenuId === page.id && (
                    <div className="dropdown-menu" style={{ top: 28, left: 0, minWidth: 140, zIndex: 200 }}>
                      <button className="dropdown-item" onClick={() => startRename(page.id, page.name)}>
                        Rename
                      </button>
                      <button className="dropdown-item" onClick={() => { setOpenMenuId(null); clonePage(page.id); }}>
                        <Copy size={12} style={{ marginRight: 6 }} /> Clone page
                      </button>
                      <div className="dropdown-divider" />
                      <button
                        className="dropdown-item dropdown-item-danger"
                        onClick={() => { setOpenMenuId(null); deletePage(page.id); }}
                        disabled={activeDashboard.pages.length <= 1}
                      >
                        <Trash2 size={12} style={{ marginRight: 6 }} /> Delete
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}

      {editMode && (
        <button
          className="btn-icon"
          style={{ marginLeft: 4, flexShrink: 0 }}
          onClick={() => {
            onSelectPageTab();
            addPage();
          }}
          title="Add page"
        >
          <Plus size={14} />
        </button>
      )}
    </div>
  );
}

