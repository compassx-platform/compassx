/**
 * DashboardTopBar — name, draft badge, publish/discard, share, settings.
 * Reference: Databricks dashboard editor top bar.
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCurrentAppId, useCurrentWorkspaceSlug, useScopedNavigate } from '@/lib/appNavigation';
import { ArrowLeft, Settings, Share2, CheckCircle, RotateCcw, Pencil, Plus, BarChart2, Filter, FileText, ExternalLink } from 'lucide-react';
import { useDashboardStore } from '@/modules/dashboards/stores/dashboardStore';
import { usePublishDashboard, useDiscardDraft } from '@/modules/dashboards/hooks/useDashboard';
import { useToast } from '@/lib/toast';

interface Props {
  onOpenSettings: () => void;
  onAddChart: () => void;
  onAddFilter: () => void;
  onAddHtmlReport: () => void;
  saveStatus?: 'idle' | 'saving' | 'saved' | 'error';
  hideBackButton?: boolean;
}

export default function DashboardTopBar({ onOpenSettings, onAddChart, onAddFilter, onAddHtmlReport, saveStatus = 'idle', hideBackButton = false }: Props) {
  const navigate = useScopedNavigate();
  const rawNavigate = useNavigate();
  const appId = useCurrentAppId();
  const workspaceSlug = useCurrentWorkspaceSlug();
  const isBusinessCenter = appId === 'business_center';

  const toast = useToast();
  const { activeDashboard, editMode, setEditMode } = useDashboardStore();
  const publishMutation = usePublishDashboard();
  const discardMutation = useDiscardDraft();
  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState('');
  const [showAddMenu, setShowAddMenu] = useState(false);

  if (!activeDashboard) return null;


  async function handlePublish() {
    try {
      await publishMutation.mutateAsync(activeDashboard!.id);
      toast.success('Dashboard published');
    } catch {
      toast.error('Publish failed');
    }
  }

  async function handleDiscard() {
    if (!confirm('Discard all draft changes and restore last published version?')) return;
    try {
      await discardMutation.mutateAsync(activeDashboard!.id);
      toast.success('Draft discarded');
    } catch {
      toast.error('Discard failed');
    }
  }

  function startEditName() {
    setNameValue(activeDashboard!.name);
    setEditingName(true);
  }

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      padding: '0 16px',
      height: 48,
      borderBottom: '1px solid var(--color-border)',
      background: 'var(--color-surface)',
      flexShrink: 0,
    }}>
      {/* Back */}
      {!hideBackButton && !isBusinessCenter && (
        <>
          <button className="btn-icon" onClick={() => navigate('/dashboards')} title="Back to dashboards">
            <ArrowLeft size={16} />
          </button>
          <div style={{ width: 1, height: 20, background: 'var(--color-border)', margin: '0 4px' }} />
        </>
      )}

      {/* Name */}
      {editingName ? (
        <input
          autoFocus
          value={nameValue}
          onChange={(e) => setNameValue(e.target.value)}
          onBlur={() => setEditingName(false)}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === 'Escape') setEditingName(false); }}
          style={{
            fontSize: '0.9rem',
            fontWeight: 600,
            border: '1px solid var(--color-primary)',
            borderRadius: 4,
            padding: '2px 8px',
            background: 'var(--color-surface)',
            color: 'var(--color-text)',
            width: 220,
          }}
        />
      ) : (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{activeDashboard.name}</span>
          {editMode && (
            <button className="btn-icon" style={{ opacity: 0.5 }} onClick={startEditName} title="Rename">
              <Pencil size={12} />
            </button>
          )}
          {isBusinessCenter && (
            <button
              className="btn-icon"
              style={{ opacity: 0.7 }}
              onClick={() => rawNavigate(`/w/${workspaceSlug}/platform/dashboards/${activeDashboard.id}/edit`)}
              title="Open in Catalog"
            >
              <ExternalLink size={14} />
            </button>
          )}
        </div>
      )}


      {/* Draft badge */}
      {activeDashboard.isDraft && (
        <span style={{
          fontSize: '0.68rem',
          fontWeight: 600,
          background: 'var(--color-warning-bg)',
          color: 'var(--color-warning)',
          padding: '2px 7px',
          borderRadius: 4,
        }}>
          DRAFT
        </span>
      )}

      <div style={{ flex: 1 }} />

      {editMode && saveStatus !== 'idle' && (
        <span style={{
          fontSize: '0.72rem',
          fontWeight: 600,
          color:
            saveStatus === 'error'
              ? 'var(--color-danger)'
              : saveStatus === 'saving'
                ? 'var(--color-text-muted)'
                : 'var(--color-success, #1f8f4c)',
          minWidth: 64,
          textAlign: 'right',
        }}>
          {saveStatus === 'saving' ? 'Saving...' : saveStatus === 'saved' ? 'Saved' : 'Save failed'}
        </span>
      )}

      {/* Edit / View toggle */}
      {!isBusinessCenter && (
        <button
          className={editMode ? 'btn btn-secondary' : 'btn btn-secondary'}
          style={{ fontSize: '0.78rem', padding: '4px 12px' }}
          onClick={() => setEditMode(!editMode)}
        >
          {editMode ? 'View mode' : 'Edit'}
        </button>
      )}

      {!isBusinessCenter && editMode && (
        <>
          <div style={{ position: 'relative' }}>
            <button
              className="btn btn-secondary"
              style={{ fontSize: '0.78rem', padding: '4px 12px' }}
              onClick={() => setShowAddMenu((open) => !open)}
            >
              <Plus size={13} style={{ marginRight: 4 }} />
              Add
            </button>
            {showAddMenu && (
              <div className="dropdown-menu" style={{ right: 0, top: 34, minWidth: 180, zIndex: 300 }}>
                <button className="dropdown-item" onClick={() => { setShowAddMenu(false); onAddChart(); }}>
                  <BarChart2 size={13} style={{ marginRight: 6 }} /> Add chart
                </button>
                <button className="dropdown-item" onClick={() => { setShowAddMenu(false); onAddFilter(); }}>
                  <Filter size={13} style={{ marginRight: 6 }} /> Add filter
                </button>
                <button className="dropdown-item" onClick={() => { setShowAddMenu(false); onAddHtmlReport(); }}>
                  <FileText size={13} style={{ marginRight: 6 }} /> Add HTML widget
                </button>
              </div>
            )}
          </div>
          {activeDashboard.isDraft && (
            <button
              className="btn btn-secondary"
              style={{ fontSize: '0.78rem', padding: '4px 10px' }}
              onClick={handleDiscard}
              disabled={discardMutation.isPending}
              title="Discard draft"
            >
              <RotateCcw size={13} style={{ marginRight: 4 }} />
              Discard
            </button>
          )}
          <button
            className="btn btn-primary"
            style={{ fontSize: '0.78rem', padding: '4px 14px' }}
            onClick={handlePublish}
            disabled={publishMutation.isPending}
          >
            <CheckCircle size={13} style={{ marginRight: 4 }} />
            Publish
          </button>
        </>
      )}

      {!isBusinessCenter && (
        <>
          <button className="btn-icon" title="Share" onClick={() => toast.info('Share coming soon')}>
            <Share2 size={15} />
          </button>

          <button className="btn-icon" title="Settings" onClick={onOpenSettings}>
            <Settings size={15} />
          </button>
        </>
      )}
    </div>
  );
}


