import React, { useState, useEffect, useMemo } from 'react';
import { ChevronDown, ChevronRight, FileText } from 'lucide-react';
import { AssetObjectType } from './AssetChip';
import { ChangeRecord } from './DiffSummaryCard';

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
}

export const SessionChangesDock: React.FC<SessionChangesDockProps> = ({
  agentId,
  sessionId,
  isDocked = false,
  refreshTrigger,
  onOpenDiff,
}) => {
  const [records, setRecords] = useState<ChangeRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [isExpanded, setIsExpanded] = useState(true);

  const loadChanges = React.useCallback(() => {
    if (!agentId || !sessionId) return;
    fetch(`/api/v1/agents/${agentId}/sessions/${sessionId}/changes`)
      .then((r) => r.json())
      .then((data) => {
        if (Array.isArray(data)) {
          setRecords(data);
        }
      })
      .catch((err) => console.error('Failed to load session changes:', err))
      .finally(() => setLoading(false));
  }, [agentId, sessionId]);

  useEffect(() => {
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
      const latest = sorted[sorted.length - 1];
      const totalAdditions = sorted.reduce((sum, r) => sum + (r.additions || 0), 0);
      const totalDeletions = sorted.reduce((sum, r) => sum + (r.deletions || 0), 0);

      list.push({
        full_name: fullName,
        object_type: latest.object_type,
        latest_record: latest,
        total_additions: totalAdditions,
        total_deletions: totalDeletions,
        first_captured_at: sorted[0]?.captured_at || undefined,
      });
    });

    // Chronological order by first appearance
    list.sort((a, b) => {
      const tA = a.first_captured_at ? new Date(a.first_captured_at).getTime() : 0;
      const tB = b.first_captured_at ? new Date(b.first_captured_at).getTime() : 0;
      return tA - tB;
    });

    return list;
  }, [records]);

  if (!loading && uniqueFiles.length === 0) {
    return null;
  }

  const content = (
    <div
      style={{
        width: '100%',
        borderRadius: isDocked ? 0 : '12px',
        border: isDocked ? 'none' : '1px solid var(--color-border, #e5e7eb)',
        borderBottom: isDocked ? '1px solid var(--color-border, #e5e7eb)' : undefined,
        background: isDocked ? '#f9fafb' : 'var(--color-surface, #fcfcfc)',
        boxShadow: 'none',
        fontSize: '0.8rem',
        color: 'var(--color-text, #1f2937)',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        overflow: 'hidden',
      }}
    >
        {/* ── Header Bar ── */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '8px 14px',
            cursor: 'pointer',
            userSelect: 'none',
          }}
          onClick={() => setIsExpanded((prev) => !prev)}
        >
          {/* Left: Collapsible Chevron & File count */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: '0.8rem',
              fontWeight: 500,
              color: '#374151',
            }}
          >
            {isExpanded ? (
              <ChevronDown size={14} color="#6b7280" />
            ) : (
              <ChevronRight size={14} color="#6b7280" />
            )}
            <span>
              {uniqueFiles.length} {uniqueFiles.length === 1 ? 'file changed' : 'files changed'}
            </span>
          </div>
        </div>

        {/* ── Asset / File Items List ── */}
        {isExpanded && (
          <div style={{ padding: '0 14px 10px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {uniqueFiles.map((file) => (
                <div
                  key={file.full_name}
                  onClick={() => onOpenDiff?.(file.latest_record)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    fontSize: '0.8rem',
                    padding: '4px 6px',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    userSelect: 'none',
                    transition: 'background 0.15s ease',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = '#f3f4f6')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                  title="Click to view code diff"
                >
                  {/* Left: Icon */}
                  <FileText size={15} style={{ color: '#4b5563', flexShrink: 0 }} />

                  {/* File Name */}
                  <span
                    style={{
                      fontWeight: 500,
                      color: '#1f2937',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                    title={file.full_name}
                  >
                    {file.full_name}
                  </span>

                  {/* Diff Numbers right beside the file name: +X in green, -Y in red */}
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 4,
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      flexShrink: 0,
                      marginLeft: 2,
                    }}
                  >
                    <span style={{ color: '#16a34a' }}>+{file.total_additions}</span>
                    <span style={{ color: '#dc2626' }}>-{file.total_deletions}</span>
                  </span>
                </div>
              ))}
            </div>
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
