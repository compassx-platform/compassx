import React, { useState, useEffect } from 'react';
import { AssetChip, AssetObjectType } from './AssetChip';
import api from '@/lib/api';

// G6: Per-turn diff summary card — one row per asset changed, with +X -Y badge
// and Accept / Reject buttons per row (D20).

export interface ChangeRecord {
  change_id: string;
  full_name: string;
  object_type: AssetObjectType;
  additions: number;
  deletions: number;
  status: 'pending_review' | 'accepted' | 'rejected';
  step_id?: number | null;
  plan_id?: string | null;
  reverted_by_change_id?: string | null;
  captured_at?: string | null;
  url?: string;
  before_content?: string | null;
  after_content?: string | null;
}

interface DiffSummaryCardProps {
  agentId: number;
  sessionId: number;
  stepId?: number;
  /** Pre-fetched records (pass if already loaded) */
  records?: ChangeRecord[];
  onOpenDiff?: (record: ChangeRecord) => void;
}

export const DiffSummaryCard: React.FC<DiffSummaryCardProps> = ({
  agentId,
  sessionId,
  stepId,
  records: initialRecords,
  onOpenDiff,
}) => {
  const [records, setRecords] = useState<ChangeRecord[]>(initialRecords ?? []);
  const [loading, setLoading] = useState(!initialRecords);
  const [actioning, setActioning] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (initialRecords) return;
    const params = stepId !== undefined ? `?step_id=${stepId}` : '';
    api
      .get(`/agents/${agentId}/sessions/${sessionId}/changes${params}`)
      .then(res => {
        if (Array.isArray(res.data)) {
          setRecords(res.data);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [agentId, sessionId, stepId, initialRecords]);

  const pendingRecords = records.filter(r => r.status === 'pending_review');
  if (!loading && records.length === 0) return null;

  const doAction = async (changeId: string, action: 'accept' | 'reject') => {
    setActioning(a => ({ ...a, [changeId]: true }));
    try {
      const res = await api.post(
        `/agents/${agentId}/sessions/${sessionId}/changes/${changeId}/${action}`
      );
      if (res.status === 200) {
        const data = res.data;
        setRecords(prev =>
          prev.map(r => {
            if (r.change_id === changeId) return { ...r, status: action === 'accept' ? 'accepted' : 'rejected' };
            return r;
          })
        );
        // If reject created a revert record, refresh list
        if (action === 'reject' && data.revert_change_id) {
          const refreshed = await api
            .get(`/agents/${agentId}/sessions/${sessionId}/changes${stepId !== undefined ? `?step_id=${stepId}` : ''}`)
            .then(r => r.data);
          if (Array.isArray(refreshed)) {
            setRecords(refreshed);
          }
        }
      }
    } finally {
      setActioning(a => ({ ...a, [changeId]: false }));
    }
  };

  const acceptAll = () => pendingRecords.forEach(r => doAction(r.change_id, 'accept'));
  const rejectAll = () => pendingRecords.forEach(r => doAction(r.change_id, 'reject'));

  return (
    <div className="diff-summary-card">
      <div className="diff-summary-card__header">
        <span className="diff-summary-card__title">
          <span className="diff-summary-card__icon">📝</span>
          Changes ({records.length})
        </span>
        {pendingRecords.length > 1 && (
          <div className="diff-summary-card__bulk">
            <button className="diff-btn diff-btn--accept" onClick={acceptAll}>Accept all</button>
            <button className="diff-btn diff-btn--reject" onClick={rejectAll}>Reject all</button>
          </div>
        )}
      </div>

      {loading ? (
        <div className="diff-summary-card__loading">Loading changes…</div>
      ) : (
        <div className="diff-summary-card__rows">
          {records.map(record => (
            <div key={record.change_id} className={`diff-summary-row diff-summary-row--${record.status}`}>
              <AssetChip
                fullName={record.full_name}
                objectType={record.object_type}
                className="diff-summary-row__chip"
              />

              <button
                className="diff-summary-row__stat"
                title="View diff"
                onClick={() => onOpenDiff?.(record)}
              >
                <span className="diff-stat diff-stat--add">+{record.additions}</span>
                <span className="diff-stat diff-stat--del">-{record.deletions}</span>
              </button>

              <div className="diff-summary-row__status-badge" data-status={record.status}>
                {record.status === 'pending_review' ? '●' : record.status === 'accepted' ? '✓' : '✗'}
                &nbsp;{record.status.replace('_', ' ')}
              </div>

              {record.status === 'pending_review' && (
                <div className="diff-summary-row__actions">
                  <button
                    className="diff-btn diff-btn--accept"
                    disabled={actioning[record.change_id]}
                    onClick={() => doAction(record.change_id, 'accept')}
                  >✓ Accept</button>
                  <button
                    className="diff-btn diff-btn--reject"
                    disabled={actioning[record.change_id]}
                    onClick={() => doAction(record.change_id, 'reject')}
                  >✗ Reject</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <style>{`
        .diff-summary-card {
          border: 1px solid rgba(255,255,255,0.1);
          border-radius: 10px;
          background: rgba(255,255,255,0.03);
          margin-top: 12px;
          overflow: hidden;
          font-size: 0.83rem;
        }
        .diff-summary-card__header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 8px 14px;
          border-bottom: 1px solid rgba(255,255,255,0.08);
          background: rgba(255,255,255,0.04);
        }
        .diff-summary-card__title {
          display: flex;
          align-items: center;
          gap: 6px;
          font-weight: 600;
          color: rgba(255,255,255,0.8);
          font-size: 0.82rem;
        }
        .diff-summary-card__bulk { display: flex; gap: 6px; }
        .diff-summary-card__loading {
          padding: 12px 14px;
          color: rgba(255,255,255,0.4);
          font-style: italic;
        }
        .diff-summary-card__rows { display: flex; flex-direction: column; }
        .diff-summary-row {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 8px 14px;
          border-bottom: 1px solid rgba(255,255,255,0.05);
          transition: background 0.15s ease;
        }
        .diff-summary-row:last-child { border-bottom: none; }
        .diff-summary-row:hover { background: rgba(255,255,255,0.04); }
        .diff-summary-row--accepted { opacity: 0.6; }
        .diff-summary-row--rejected { opacity: 0.45; }
        .diff-summary-row__stat {
          display: flex;
          gap: 4px;
          background: none;
          border: 1px solid rgba(255,255,255,0.12);
          border-radius: 4px;
          padding: 2px 7px;
          cursor: pointer;
          font-family: ui-monospace, monospace;
          font-size: 0.78rem;
          transition: border-color 0.15s ease;
        }
        .diff-summary-row__stat:hover { border-color: rgba(255,255,255,0.3); }
        .diff-stat--add { color: #4ade80; }
        .diff-stat--del { color: #f87171; }
        .diff-summary-row__status-badge {
          font-size: 0.72rem;
          padding: 2px 7px;
          border-radius: 999px;
          white-space: nowrap;
          color: rgba(255,255,255,0.5);
          border: 1px solid rgba(255,255,255,0.12);
        }
        .diff-summary-row__status-badge[data-status="accepted"] { color: #4ade80; border-color: #4ade80; }
        .diff-summary-row__status-badge[data-status="rejected"]  { color: #f87171; border-color: #f87171; }
        .diff-summary-row__actions { display: flex; gap: 5px; margin-left: auto; }
        .diff-btn {
          border: none;
          border-radius: 5px;
          padding: 3px 10px;
          font-size: 0.76rem;
          font-weight: 600;
          cursor: pointer;
          transition: opacity 0.15s ease, transform 0.1s ease;
        }
        .diff-btn:hover:not(:disabled) { opacity: 0.85; transform: translateY(-1px); }
        .diff-btn:disabled { opacity: 0.35; cursor: not-allowed; }
        .diff-btn--accept { background: rgba(74,222,128,0.18); color: #4ade80; }
        .diff-btn--reject { background: rgba(248,113,113,0.15); color: #f87171; }
      `}</style>
    </div>
  );
};
