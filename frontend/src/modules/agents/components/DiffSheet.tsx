import React, { useEffect, useRef } from 'react';
import { ChangeRecord } from './DiffSummaryCard';
import { AssetChip } from './AssetChip';

// G7: Side-sheet hosting the diff inside the asset type's native editor surface.
// Opens as an in-place panel overlay — no page navigation.

interface DiffSheetProps {
  record: ChangeRecord | null;
  onClose: () => void;
}

// G7: diff_renderer registry — maps object_type to a renderer component
type DiffRenderer = React.FC<{ before: string | null; after: string | null; fullName: string }>;

const PlainTextDiff: DiffRenderer = ({ before, after }) => {
  const beforeLines = (before ?? '').split('\n');
  const afterLines  = (after  ?? '').split('\n');

  // Simple line-level diff computation
  const diffLines: Array<{ type: 'add' | 'del' | 'ctx'; text: string }> = [];
  const maxLen = Math.max(beforeLines.length, afterLines.length);

  for (let i = 0; i < maxLen; i++) {
    const b = beforeLines[i];
    const a = afterLines[i];
    if (b === undefined) {
      diffLines.push({ type: 'add', text: a });
    } else if (a === undefined) {
      diffLines.push({ type: 'del', text: b });
    } else if (b !== a) {
      diffLines.push({ type: 'del', text: b });
      diffLines.push({ type: 'add', text: a });
    } else {
      diffLines.push({ type: 'ctx', text: b });
    }
  }

  return (
    <pre className="diff-sheet__plain-diff">
      {diffLines.map((line, i) => (
        <div key={i} className={`diff-line diff-line--${line.type}`}>
          <span className="diff-line__gutter">
            {line.type === 'add' ? '+' : line.type === 'del' ? '-' : ' '}
          </span>
          <span className="diff-line__text">{line.text}</span>
        </div>
      ))}
    </pre>
  );
};

const SqlDiff: DiffRenderer = ({ before, after, fullName }) => (
  <div className="diff-sheet__sql">
    <div className="diff-sheet__split">
      <div className="diff-sheet__split-pane diff-sheet__split-pane--before">
        <div className="diff-sheet__split-label">Before</div>
        <pre className="diff-sheet__code">{before ?? '(no prior content)'}</pre>
      </div>
      <div className="diff-sheet__split-pane diff-sheet__split-pane--after">
        <div className="diff-sheet__split-label">After</div>
        <pre className="diff-sheet__code">{after ?? '(empty)'}</pre>
      </div>
    </div>
    <PlainTextDiff before={before} after={after} fullName={fullName} />
  </div>
);

const DIFF_RENDERER_REGISTRY: Record<string, DiffRenderer> = {
  notebook:  PlainTextDiff,  // TODO: replace with NotebookDiffView when available
  dashboard: PlainTextDiff,  // TODO: replace with DashboardDiffView
  query:     SqlDiff,
  table:     SqlDiff,
};

function getDiffRenderer(objectType: string): DiffRenderer {
  return DIFF_RENDERER_REGISTRY[objectType] ?? PlainTextDiff;
}

export const DiffSheet: React.FC<DiffSheetProps> = ({ record, onClose }) => {
  const sheetRef = useRef<HTMLDivElement>(null);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  // Trap focus and prevent scroll behind sheet
  useEffect(() => {
    if (record) {
      document.body.style.overflow = 'hidden';
      sheetRef.current?.focus();
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [record]);

  if (!record) return null;

  const Renderer = getDiffRenderer(record.object_type);

  return (
    <>
      {/* Backdrop */}
      <div className="diff-sheet__backdrop" onClick={onClose} aria-hidden />

      {/* Sheet panel */}
      <div
        className="diff-sheet"
        ref={sheetRef}
        role="dialog"
        aria-modal="true"
        aria-label={`Diff: ${record.full_name}`}
        tabIndex={-1}
      >
        {/* Header */}
        <div className="diff-sheet__header">
          <div className="diff-sheet__header-left">
            <AssetChip
              fullName={record.full_name}
              objectType={record.object_type}
            />
            <span className="diff-sheet__stat-badge">
              <span className="diff-stat--add">+{record.additions}</span>
              &nbsp;
              <span className="diff-stat--del">-{record.deletions}</span>
            </span>
            <span className={`diff-sheet__status diff-sheet__status--${record.status}`}>
              {record.status.replace('_', ' ')}
            </span>
          </div>
          <button className="diff-sheet__close" onClick={onClose} aria-label="Close diff sheet">✕</button>
        </div>

        {/* Diff body */}
        <div className="diff-sheet__body">
          {record.before_content === null && record.after_content !== null
            ? <div className="diff-sheet__new-badge">🆕 New file</div>
            : null}
          <Renderer
            before={record.before_content ?? null}
            after={record.after_content ?? null}
            fullName={record.full_name}
          />
        </div>
      </div>

      <style>{`
        .diff-sheet__backdrop {
          position: fixed; inset: 0;
          background: rgba(0,0,0,0.55);
          z-index: 400;
          backdrop-filter: blur(2px);
          animation: fadeIn 0.2s ease;
        }
        .diff-sheet {
          position: fixed;
          top: 0; right: 0; bottom: 0;
          width: min(680px, 100vw);
          background: #0f1117;
          border-left: 1px solid rgba(255,255,255,0.1);
          z-index: 401;
          display: flex;
          flex-direction: column;
          overflow: hidden;
          animation: slideIn 0.22s cubic-bezier(0.22,1,0.36,1);
          outline: none;
        }
        @keyframes fadeIn  { from { opacity: 0; } to { opacity: 1; } }
        @keyframes slideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }

        .diff-sheet__header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 14px 18px;
          border-bottom: 1px solid rgba(255,255,255,0.1);
          background: rgba(255,255,255,0.03);
          gap: 10px;
          flex-shrink: 0;
        }
        .diff-sheet__header-left {
          display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
        }
        .diff-sheet__stat-badge {
          font-family: ui-monospace, monospace;
          font-size: 0.82rem;
          padding: 2px 8px;
          border-radius: 4px;
          border: 1px solid rgba(255,255,255,0.12);
        }
        .diff-stat--add { color: #4ade80; }
        .diff-stat--del { color: #f87171; }
        .diff-sheet__status {
          font-size: 0.72rem;
          padding: 2px 8px;
          border-radius: 999px;
          border: 1px solid rgba(255,255,255,0.15);
          color: rgba(255,255,255,0.5);
          text-transform: capitalize;
        }
        .diff-sheet__status--accepted { color: #4ade80; border-color: #4ade80; }
        .diff-sheet__status--rejected  { color: #f87171; border-color: #f87171; }
        .diff-sheet__close {
          background: none; border: none; color: rgba(255,255,255,0.5);
          font-size: 1.1rem; cursor: pointer; padding: 4px 8px; border-radius: 4px;
          transition: color 0.15s ease, background 0.15s ease;
        }
        .diff-sheet__close:hover { color: #fff; background: rgba(255,255,255,0.08); }
        .diff-sheet__body {
          flex: 1; overflow: auto; padding: 16px;
        }
        .diff-sheet__new-badge {
          font-size: 0.78rem; color: #4ade80;
          margin-bottom: 10px; padding: 4px 10px;
          background: rgba(74,222,128,0.1); border-radius: 4px; display: inline-block;
        }
        .diff-sheet__plain-diff {
          font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace;
          font-size: 0.78rem;
          line-height: 1.6;
          margin: 0;
          white-space: pre-wrap;
          word-break: break-all;
        }
        .diff-line { display: flex; align-items: flex-start; gap: 8px; }
        .diff-line--add { background: rgba(74,222,128,0.08); }
        .diff-line--del { background: rgba(248,113,113,0.08); }
        .diff-line__gutter {
          width: 14px;
          flex-shrink: 0;
          font-weight: bold;
          color: rgba(255,255,255,0.3);
          user-select: none;
        }
        .diff-line--add .diff-line__gutter { color: #4ade80; }
        .diff-line--del .diff-line__gutter { color: #f87171; }
        .diff-line__text { color: rgba(255,255,255,0.85); }

        .diff-sheet__split {
          display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px;
        }
        .diff-sheet__split-pane {
          border-radius: 8px; overflow: hidden;
          border: 1px solid rgba(255,255,255,0.08);
        }
        .diff-sheet__split-label {
          padding: 4px 10px; font-size: 0.72rem; font-weight: 600;
          background: rgba(255,255,255,0.05); color: rgba(255,255,255,0.5);
          text-transform: uppercase; letter-spacing: 0.05em;
        }
        .diff-sheet__code {
          margin: 0; padding: 10px; font-size: 0.75rem;
          font-family: ui-monospace, monospace; white-space: pre-wrap; word-break: break-all;
          color: rgba(255,255,255,0.8); line-height: 1.5;
        }
      `}</style>
    </>
  );
};

// Augment ChangeRecord type with content fields (fetched lazily when sheet opens)
declare module './DiffSummaryCard' {
  interface ChangeRecord {
    before_content?: string | null;
    after_content?: string | null;
  }
}
