import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { ChevronDown, ChevronRight, FileText, Check, X, Loader2 } from 'lucide-react';
import { AssetObjectType } from './AssetChip';
import { ChangeRecord } from './DiffSummaryCard';
import { useNotebookStore } from '@/modules/notebooks/store/notebookStore';
import api from '@/lib/api';

export interface UniqueFileSummary {
  full_name: string;
  object_type: AssetObjectType;
  latest_record: ChangeRecord;
  total_additions: number;
  total_deletions: number;
}

interface SessionChangesDockProps {
  agentId?: number | null;
  sessionId?: number | null;
  isDocked?: boolean;
  /** Trigger to force refresh when a turn completes */
  refreshTrigger?: any;
  onOpenDiff?: (record: ChangeRecord) => void;
  onStatusChange?: (changeId: string, newStatus: 'accepted' | 'rejected') => void;
}

export const SessionChangesDock: React.FC<SessionChangesDockProps> = ({
  agentId,
  sessionId,
  isDocked = false,
  refreshTrigger,
  onOpenDiff,
  onStatusChange,
}) => {
  const [records, setRecords] = useState<ChangeRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [isExpanded, setIsExpanded] = useState(true);
  const [actioningId, setActioningId] = useState<string | null>(null);
  const [bulkActioning, setBulkActioning] = useState<boolean>(false);

  const notebookCells = useNotebookStore((s) => s.cells);
  const notebookPath = useNotebookStore((s) => s.notebookPath);

  const pendingNotebookCells = useMemo(() => {
    return notebookCells.filter((c) => c.cellStatus === 'pending');
  }, [notebookCells]);

  const loadChanges = useCallback(() => {
    if (!agentId || !sessionId) return;
    api
      .get(`/agents/${agentId}/sessions/${sessionId}/changes`)
      .then((res) => {
        if (Array.isArray(res.data)) {
          setRecords(res.data);
        }
      })
      .catch((err) => console.error('Failed to load session changes:', err))
      .finally(() => setLoading(false));
  }, [agentId, sessionId]);

  useEffect(() => {
    setRecords([]);
    loadChanges();
  }, [loadChanges, refreshTrigger]);

  // Aggregate by full_name into unique files (in chronological order)
  const uniqueFiles: UniqueFileSummary[] = useMemo(() => {
    const map = new Map<string, ChangeRecord[]>();
    records.forEach((r) => {
      const existing = map.get(r.full_name) || [];
      existing.push(r);
      map.set(r.full_name, existing);
    });

    const list: (UniqueFileSummary & { first_captured_at?: string })[] = [];
    map.forEach((fileRecords, fullName) => {
      const sorted = [...fileRecords].sort((a, b) => {
        const tA = a.captured_at ? new Date(a.captured_at).getTime() : 0;
        const tB = b.captured_at ? new Date(b.captured_at).getTime() : 0;
        return tA - tB;
      });
      let latest = sorted[sorted.length - 1];
      let totalAdditions = sorted.reduce((sum, r) => sum + (r.additions || 0), 0);
      let totalDeletions = sorted.reduce((sum, r) => sum + (r.deletions || 0), 0);

      // If this file corresponds to active notebook with live pending edits
      const isThisActiveNotebook =
        latest.object_type === 'notebook' ||
        fullName.endsWith('.ipynb') ||
        (notebookPath && (fullName.includes(notebookPath) || notebookPath.includes(fullName)));

      if (isThisActiveNotebook && pendingNotebookCells.length > 0) {
        let storeAdditions = 0;
        let storeDeletions = 0;
        pendingNotebookCells.forEach((c) => {
          const lines = (c.pendingSource || c.source || '').split('\n').length;
          const origLines = (c.pendingAgentEdit?.originalSource || '').split('\n').filter(Boolean).length;
          storeAdditions += lines;
          storeDeletions += origLines;
        });
        latest = {
          ...latest,
          status: 'pending_review',
          additions: storeAdditions || latest.additions,
          deletions: storeDeletions || latest.deletions,
        };
        totalAdditions = storeAdditions || totalAdditions;
        totalDeletions = storeDeletions || totalDeletions;
      }

      list.push({
        full_name: fullName,
        object_type: latest.object_type,
        latest_record: latest,
        total_additions: totalAdditions,
        total_deletions: totalDeletions,
        first_captured_at: sorted[0]?.captured_at || undefined,
      });
    });

    // If there are pending cells in notebookStore but NO matching change record was loaded yet from DB:
    if (pendingNotebookCells.length > 0) {
      const hasNotebookInList = list.some((f) => f.object_type === 'notebook' || f.full_name.endsWith('.ipynb'));
      if (!hasNotebookInList) {
        let storeAdditions = 0;
        let storeDeletions = 0;
        pendingNotebookCells.forEach((c) => {
          const lines = (c.pendingSource || c.source || '').split('\n').length;
          const origLines = (c.pendingAgentEdit?.originalSource || '').split('\n').filter(Boolean).length;
          storeAdditions += lines;
          storeDeletions += origLines;
        });
        const nbName = notebookPath || 'workspace.notebooks.analysis_notebook';
        const virtualRecord: ChangeRecord = {
          change_id: 'active_notebook_live',
          full_name: nbName,
          object_type: 'notebook',
          additions: storeAdditions,
          deletions: storeDeletions,
          status: 'pending_review',
        };
        list.push({
          full_name: nbName,
          object_type: 'notebook',
          latest_record: virtualRecord,
          total_additions: storeAdditions,
          total_deletions: storeDeletions,
        });
      }
    }

    // Chronological order by first appearance
    list.sort((a, b) => {
      const tA = a.first_captured_at ? new Date(a.first_captured_at).getTime() : 0;
      const tB = b.first_captured_at ? new Date(b.first_captured_at).getTime() : 0;
      return tA - tB;
    });

    return list;
  }, [records, pendingNotebookCells, notebookPath]);

  // Count pending reviews
  const pendingFiles = useMemo(() => {
    return uniqueFiles.filter((f) => f.latest_record.status === 'pending_review');
  }, [uniqueFiles]);

  const handleAction = async (changeId: string, action: 'accept' | 'reject', e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (action === 'accept') {
      useNotebookStore.getState().acceptAllAgentEdits();
    } else {
      useNotebookStore.getState().rejectAllAgentEdits();
    }
    if (!agentId || !sessionId) return;
    setActioningId(changeId);
    try {
      if (changeId !== 'active_notebook_live') {
        const res = await api.post(
          `/agents/${agentId}/sessions/${sessionId}/changes/${changeId}/${action}`
        );
        if (res.status === 200) {
          const nextStatus = action === 'accept' ? 'accepted' : 'rejected';
          setRecords((prev) =>
            prev.map((r) => (r.change_id === changeId ? { ...r, status: nextStatus } : r))
          );
          onStatusChange?.(changeId, nextStatus);
          loadChanges();
        }
      } else {
        const nextStatus = action === 'accept' ? 'accepted' : 'rejected';
        onStatusChange?.(changeId, nextStatus);
      }
    } catch (err) {
      console.error(`Failed to ${action} change:`, err);
    } finally {
      setActioningId(null);
    }
  };

  const handleBulkAction = async (action: 'accept_all' | 'reject_all', e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (action === 'accept_all') {
      useNotebookStore.getState().acceptAllAgentEdits();
    } else {
      useNotebookStore.getState().rejectAllAgentEdits();
    }
    if (!agentId || !sessionId || pendingFiles.length === 0) return;
    setBulkActioning(true);
    try {
      const res = await api.post(
        `/agents/${agentId}/sessions/${sessionId}/changes/bulk-review`,
        { action }
      );
      if (res.status === 200) {
        loadChanges();
      }
    } catch (err) {
      console.error(`Failed to bulk ${action}:`, err);
    } finally {
      setBulkActioning(false);
    }
  };

  if (!loading && uniqueFiles.length === 0) {
    return null;
  }

  const content = (
    <div
      style={{
        width: '100%',
        padding: '6px 14px 4px',
        borderBottom: isDocked ? '1px solid var(--color-border, #f1f5f9)' : undefined,
        background: 'transparent',
        fontSize: '0.78rem',
        color: 'var(--color-text, #334155)',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      }}
    >
      {/* ── Compact Header Bar ── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '2px 0 6px',
          userSelect: 'none',
          gap: 8,
        }}
      >
        {/* Left: File count & Pending indicator */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontSize: '0.75rem',
            fontWeight: 600,
            color: '#475569',
            cursor: 'pointer',
          }}
          onClick={() => setIsExpanded((prev) => !prev)}
        >
          {isExpanded ? (
            <ChevronDown size={13} color="#64748b" />
          ) : (
            <ChevronRight size={13} color="#64748b" />
          )}
          <span>
            {uniqueFiles.length} {uniqueFiles.length === 1 ? 'file changed' : 'files changed'}
          </span>

          {pendingFiles.length > 0 && (
            <span
              style={{
                fontSize: '0.68rem',
                padding: '1px 5px',
                borderRadius: 999,
                background: '#fef3c7',
                color: '#92400e',
                fontWeight: 600,
              }}
            >
              {pendingFiles.length} pending
            </span>
          )}
        </div>

        {/* Right: Bulk Actions whenever pending files exist */}
        {pendingFiles.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }} onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              disabled={bulkActioning}
              onClick={(e) => handleBulkAction('accept_all', e)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 3,
                padding: '2px 7px',
                borderRadius: 4,
                border: '1px solid #bbf7d0',
                background: '#f0fdf4',
                color: '#16a34a',
                fontSize: '0.7rem',
                fontWeight: 600,
                cursor: bulkActioning ? 'not-allowed' : 'pointer',
              }}
              title="Accept and apply all pending changes"
            >
              {bulkActioning ? <Loader2 size={10} className="spin" /> : <Check size={10} />}
              <span>Accept all</span>
            </button>

            <button
              type="button"
              disabled={bulkActioning}
              onClick={(e) => handleBulkAction('reject_all', e)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 3,
                padding: '2px 7px',
                borderRadius: 4,
                border: '1px solid #fecaca',
                background: '#fef2f2',
                color: '#dc2626',
                fontSize: '0.7rem',
                fontWeight: 600,
                cursor: bulkActioning ? 'not-allowed' : 'pointer',
              }}
              title="Reject and revert all pending changes"
            >
              <X size={10} />
              <span>Reject all</span>
            </button>
          </div>
        )}
      </div>

      {/* ── Compact File Items List ── */}
      {isExpanded && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, paddingBottom: 4 }}>
          {uniqueFiles.map((file) => {
            const rec = file.latest_record;
            const isPending = rec.status === 'pending_review';
            const isRejected = rec.status === 'rejected';
            const isActioningThis = actioningId === rec.change_id;

            return (
              <div
                key={file.full_name}
                onClick={() => onOpenDiff?.(rec)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 8,
                  fontSize: '0.76rem',
                  padding: '3px 6px',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  userSelect: 'none',
                  background: 'transparent',
                  transition: 'background 0.1s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = '#f1f5f9';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                }}
                title="Click to view code diff"
              >
                {/* File info: Icon, Name & Diff numbers */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0, flex: 1 }}>
                  <FileText size={13} style={{ color: '#64748b', flexShrink: 0 }} />

                  <span
                    style={{
                      fontWeight: 500,
                      color: '#1e293b',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                    title={file.full_name}
                  >
                    {file.full_name}
                  </span>

                  {/* Diff stats (+X -Y) */}
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 3,
                      fontSize: '0.7rem',
                      fontWeight: 600,
                      flexShrink: 0,
                      marginLeft: 2,
                    }}
                  >
                    <span style={{ color: '#16a34a' }}>+{file.total_additions}</span>
                    <span style={{ color: '#dc2626' }}>-{file.total_deletions}</span>
                  </span>
                </div>

                {/* Right part: Actions / Reverted */}
                <div
                  style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}
                  onClick={(e) => e.stopPropagation()}
                >
                  {isPending ? (
                    <>
                      <button
                        type="button"
                        disabled={isActioningThis || bulkActioning}
                        onClick={(e) => handleAction(rec.change_id, 'accept', e)}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 2,
                          padding: '2px 6px',
                          borderRadius: 4,
                          border: '1px solid #bbf7d0',
                          background: '#f0fdf4',
                          color: '#16a34a',
                          fontSize: '0.7rem',
                          fontWeight: 600,
                          cursor: isActioningThis ? 'not-allowed' : 'pointer',
                        }}
                        title="Accept change"
                      >
                        {isActioningThis ? <Loader2 size={9} className="spin" /> : <Check size={9} />}
                        <span>Accept</span>
                      </button>

                      <button
                        type="button"
                        disabled={isActioningThis || bulkActioning}
                        onClick={(e) => handleAction(rec.change_id, 'reject', e)}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 2,
                          padding: '2px 6px',
                          borderRadius: 4,
                          border: '1px solid #fecaca',
                          background: '#fef2f2',
                          color: '#dc2626',
                          fontSize: '0.7rem',
                          fontWeight: 600,
                          cursor: isActioningThis ? 'not-allowed' : 'pointer',
                        }}
                        title="Reject change"
                      >
                        <X size={9} />
                        <span>Reject</span>
                      </button>
                    </>
                  ) : isRejected ? (
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 2,
                        fontSize: '0.68rem',
                        fontWeight: 500,
                        color: '#dc2626',
                        background: '#fef2f2',
                        border: '1px solid #fee2e2',
                        padding: '1px 5px',
                        borderRadius: 3,
                      }}
                    >
                      <X size={9} /> Reverted
                    </span>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );

  if (isDocked) {
    return content;
  }

  return (
    <div
      style={{
        width: '100%',
        maxWidth: 1100,
        margin: '0 auto 8px',
        padding: '0 24px',
      }}
    >
      {content}
    </div>
  );
};
