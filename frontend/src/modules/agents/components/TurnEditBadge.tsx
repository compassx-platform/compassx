import React from 'react';
import { AssetChip, AssetObjectType } from './AssetChip';
import { ChangeRecord } from './DiffSummaryCard';

export interface TurnEditInfo {
  change_id?: string;
  full_name: string;
  object_type: AssetObjectType;
  additions?: number;
  deletions?: number;
}

interface TurnEditBadgeProps {
  edits: TurnEditInfo[];
  agentId?: number | null;
  sessionId?: number | null;
  onOpenDiff?: (record: ChangeRecord) => void;
}

export const TurnEditBadge: React.FC<TurnEditBadgeProps> = ({
  edits,
  agentId,
  sessionId,
  onOpenDiff,
}) => {
  if (!edits || edits.length === 0) return null;

  const handleOpen = (edit: TurnEditInfo) => {
    if (edit.change_id && agentId && sessionId) {
      fetch(`/api/v1/agents/${agentId}/sessions/${sessionId}/changes/${edit.change_id}`)
        .then((r) => r.json())
        .then((rec) => {
          if (rec && !rec.error) {
            onOpenDiff?.(rec);
          }
        })
        .catch((err) => console.error('Failed to load change details:', err));
    } else {
      onOpenDiff?.({
        change_id: edit.change_id || 'temp',
        full_name: edit.full_name,
        object_type: edit.object_type,
        additions: edit.additions || 0,
        deletions: edit.deletions || 0,
        status: 'pending_review',
      });
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 6,
        alignItems: 'center',
        marginTop: 6,
      }}
    >
      <span
        style={{
          fontSize: '0.75rem',
          color: '#64748b',
          fontWeight: 500,
          userSelect: 'none',
        }}
      >
        Edited
      </span>
      {edits.map((edit, idx) => (
        <AssetChip
          key={`${edit.full_name}-${idx}`}
          fullName={edit.full_name}
          objectType={edit.object_type}
          diff={
            edit.additions != null || edit.deletions != null
              ? { additions: edit.additions, deletions: edit.deletions }
              : undefined
          }
          onClick={() => handleOpen(edit)}
        />
      ))}
    </div>
  );
};
