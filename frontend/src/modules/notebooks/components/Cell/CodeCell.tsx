import { useRef, useCallback, useMemo } from 'react';
import { EditorView, keymap, lineNumbers, Decoration, WidgetType } from '@codemirror/view';
import { RangeSetBuilder } from '@codemirror/state';
import { indentMore, indentLess } from '@codemirror/commands';
import { python } from '@codemirror/lang-python';
import { syntaxHighlighting } from '@codemirror/language';
import { oneDarkHighlightStyle } from '@codemirror/theme-one-dark';
import { tags } from '@lezer/highlight';
import { HighlightStyle } from '@codemirror/language';
import { ChevronDown, ChevronRight, Check, X } from 'lucide-react';
import ReactCodeMirror from '@uiw/react-codemirror';
import { useNotebookStore, hasDatabaseSideEffects } from '../../store/notebookStore';

function splitLines(source: string) {
  return source.length ? source.split('\n') : [];
}

class RemovedLinesWidget extends WidgetType {
  constructor(readonly lines: string[]) {
    super();
  }

  toDOM() {
    const container = document.createElement('div');
    container.className = 'cm-diff-removed-container';
    this.lines.forEach((line) => {
      const div = document.createElement('div');
      div.className = 'cm-diff-removed-line';
      div.textContent = '- ' + (line || ' ');
      container.appendChild(div);
    });
    return container;
  }

  eq(other: RemovedLinesWidget) {
    return this.lines.join('\n') === other.lines.join('\n');
  }

  ignoreEvent() {
    return true;
  }
}

type DiffOp =
  | { type: 'equal'; line: string; currentIdx: number }
  | { type: 'delete'; line: string }
  | { type: 'insert'; line: string; currentIdx: number };

function computeLineDiff(original: string[], current: string[]): {
  addedLineIndices: Set<number>;
  removedWidgets: { currentIdx: number; lines: string[] }[];
} {
  const m = original.length;
  const n = current.length;

  if (m === 0) {
    const addedLineIndices = new Set<number>();
    for (let j = 0; j < n; j++) addedLineIndices.add(j);
    return { addedLineIndices, removedWidgets: [] };
  }

  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = 0; i < m; i++) {
    for (let j = 0; j < n; j++) {
      if (original[i] === current[j]) {
        dp[i + 1][j + 1] = dp[i][j] + 1;
      } else {
        dp[i + 1][j + 1] = Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
  }

  let i = m;
  let j = n;
  const ops: DiffOp[] = [];
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && original[i - 1] === current[j - 1]) {
      ops.unshift({ type: 'equal', line: original[i - 1], currentIdx: j - 1 });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      ops.unshift({ type: 'insert', line: current[j - 1], currentIdx: j - 1 });
      j--;
    } else if (i > 0) {
      ops.unshift({ type: 'delete', line: original[i - 1] });
      i--;
    }
  }

  const addedLineIndices = new Set<number>();
  const removedWidgets: { currentIdx: number; lines: string[] }[] = [];
  let pendingRemoved: string[] = [];

  for (const op of ops) {
    if (op.type === 'delete') {
      pendingRemoved.push(op.line);
    } else if (op.type === 'insert') {
      addedLineIndices.add(op.currentIdx);
      if (pendingRemoved.length > 0) {
        removedWidgets.push({ currentIdx: op.currentIdx, lines: pendingRemoved });
        pendingRemoved = [];
      }
    } else if (op.type === 'equal') {
      if (pendingRemoved.length > 0) {
        removedWidgets.push({ currentIdx: op.currentIdx, lines: pendingRemoved });
        pendingRemoved = [];
      }
    }
  }

  if (pendingRemoved.length > 0) {
    removedWidgets.push({ currentIdx: n, lines: pendingRemoved });
  }

  return { addedLineIndices, removedWidgets };
}
import { useExecuteCell } from '../../hooks/useExecuteCell';
import CellOutput from './CellOutput';
import CellToolbar from './CellToolbar';
import AgentEditDiff from './AgentEditDiff';

interface Props {
  cellId: string;
  cellIndex: number;
}

/* ── GitHub-style Python highlight (light theme) ── */
const pythonHighlightStyle = HighlightStyle.define([
  // Keywords
  { tag: tags.keyword, color: '#d73a49', fontWeight: '600' },
  { tag: tags.controlKeyword, color: '#d73a49', fontWeight: '600' },
  { tag: tags.operatorKeyword, color: '#d73a49', fontWeight: '600' },
  { tag: tags.definitionKeyword, color: '#d73a49', fontWeight: '600' },
  { tag: tags.moduleKeyword, color: '#d73a49', fontWeight: '600' },

  // Functions & Methods
  { tag: tags.function(tags.variableName), color: '#6f42c1', fontWeight: '500' },
  { tag: tags.function(tags.definition(tags.variableName)), color: '#6f42c1', fontWeight: 'bold' },
  { tag: tags.function(tags.propertyName), color: '#6f42c1', fontWeight: '500' },
  { tag: tags.definition(tags.function(tags.variableName)), color: '#6f42c1', fontWeight: 'bold' },

  // Classes & Types
  { tag: tags.definition(tags.className), color: '#005cc5', fontWeight: 'bold' },
  { tag: tags.className, color: '#005cc5', fontWeight: '600' },
  { tag: tags.typeName, color: '#005cc5', fontWeight: '600' },

  // Variables & Properties
  { tag: tags.propertyName, color: '#005cc5' },
  { tag: tags.self, color: '#e36209', fontStyle: 'italic' },
  { tag: tags.special(tags.variableName), color: '#e36209', fontWeight: '500' },
  { tag: tags.standard(tags.variableName), color: '#e36209', fontWeight: '500' },
  { tag: tags.variableName, color: '#24292e' },

  // Literals: Strings, Numbers, Booleans, None
  { tag: tags.string, color: '#032f62' },
  { tag: tags.special(tags.string), color: '#032f62', fontStyle: 'italic' },
  { tag: tags.docString, color: '#032f62', fontStyle: 'italic' },
  { tag: tags.escape, color: '#d73a49' },
  { tag: tags.number, color: '#005cc5' },
  { tag: tags.integer, color: '#005cc5' },
  { tag: tags.float, color: '#005cc5' },
  { tag: tags.bool, color: '#005cc5', fontWeight: 'bold' },
  { tag: tags.null, color: '#005cc5', fontWeight: 'bold' },

  // Comments
  { tag: tags.comment, color: '#6a737d', fontStyle: 'italic' },
  { tag: tags.lineComment, color: '#6a737d', fontStyle: 'italic' },
  { tag: tags.blockComment, color: '#6a737d', fontStyle: 'italic' },

  // Operators
  { tag: tags.operator, color: '#d73a49' },
  { tag: tags.arithmeticOperator, color: '#d73a49' },
  { tag: tags.bitwiseOperator, color: '#d73a49' },
  { tag: tags.compareOperator, color: '#d73a49' },
  { tag: tags.updateOperator, color: '#d73a49' },
  { tag: tags.definitionOperator, color: '#d73a49' },
  { tag: tags.derefOperator, color: '#24292e' },

  // Decorators & Meta
  { tag: tags.meta, color: '#e36209', fontWeight: '500' },
  { tag: tags.modifier, color: '#e36209', fontWeight: '500' },

  // Punctuation & Brackets
  { tag: tags.punctuation, color: '#24292e' },
  { tag: tags.separator, color: '#24292e' },
  { tag: tags.bracket, color: '#24292e' },
  { tag: tags.paren, color: '#24292e' },
  { tag: tags.squareBracket, color: '#24292e' },
  { tag: tags.brace, color: '#24292e' },
]);

/* ── Custom light theme for the editor chrome ── */
const editorTheme = EditorView.theme({
  '&': {
    fontSize: '13px',
    fontFamily: "var(--cx-font-mono, 'Courier New', monospace)",
    backgroundColor: 'transparent',
  },
  '&.cm-focused': {
    outline: 'none',
  },
  '.cm-content': {
    outline: 'none',
    padding: '4px 0',
  },
  '.cm-cursor': {
    borderLeftColor: '#0969da',
    borderLeftWidth: '2px',
  },
  '.cm-gutters': {
    backgroundColor: '#f8fafc',
    borderRight: '1px solid #e2e8f0',
    color: '#94a3b8',
    userSelect: 'none',
  },
  '.cm-lineNumbers .cm-gutterElement': {
    color: '#94a3b8',
    minWidth: '2.5em',
    padding: '0 8px 0 4px',
    textAlign: 'right',
  },
  '&.cm-focused .cm-cursor': {
    borderLeftColor: '#0969da',
  },
  '&.cm-focused .cm-selectionBackground, ::selection': {
    backgroundColor: '#b3d7ff !important',
  },
});

export default function CodeCell({ cellId, cellIndex }: Props) {
  const cell = useNotebookStore((s) => s.cells.find((c) => c.id === cellId));
  const updateCellSource = useNotebookStore((s) => s.updateCellSource);
  const setFocusedCell = useNotebookStore((s) => s.setFocusedCell);
  const focusedCellId = useNotebookStore((s) => s.focusedCellId);
  const showLineNumbers = useNotebookStore((s) => s.showLineNumbers);
  const collapsedOutputs = useNotebookStore((s) => s.collapsedOutputs);
  const toggleCollapseOutput = useNotebookStore((s) => s.toggleCollapseOutput);
  const { executeCell } = useExecuteCell();

  const isFocused = focusedCellId === cellId;
  const isCollapsed = collapsedOutputs.has(cellId);

  const runCell = useCallback(() => {
    if (!cell) return;
    executeCell(cell.id, cell.source);
  }, [cell, executeCell]);

  const runCellRef = useRef(runCell);
  runCellRef.current = runCell;

  const isPending = cell?.cellStatus === 'pending';
  const docText = cell?.pendingSource ?? cell?.source ?? '';

  /* ── Build diff decorations for pending edits (allowing live editing) ── */
  const diffExtensions = useMemo(() => {
    if (!isPending) {
      return [] as any[];
    }

    const currentLines = splitLines(docText);
    const originalLines = splitLines(cell?.committedSource || '');
    const { addedLineIndices, removedWidgets } = computeLineDiff(originalLines, currentLines);

    // Compute line start character offsets in docText
    const lineStarts: number[] = [];
    let offset = 0;
    for (let idx = 0; idx < currentLines.length; idx++) {
      lineStarts.push(offset);
      offset += currentLines[idx].length + 1;
    }

    const builder = new RangeSetBuilder<Decoration>();

    for (let idx = 0; idx <= currentLines.length; idx++) {
      // 1. Any removed lines before this line (red block widget)
      const widgetItem = removedWidgets.find((rw) => rw.currentIdx === idx);
      const pos = idx < currentLines.length ? lineStarts[idx] : docText.length;

      if (widgetItem) {
        builder.add(
          pos,
          pos,
          Decoration.widget({
            widget: new RemovedLinesWidget(widgetItem.lines),
            block: true,
            side: -1,
          })
        );
      }

      // 2. Added / modified line decoration (green)
      if (idx < currentLines.length && addedLineIndices.has(idx)) {
        builder.add(
          pos,
          pos,
          Decoration.line({
            attributes: { class: 'cm-diff-added' },
          })
        );
      }
    }

    const diffDecorations = builder.finish();

    return [
      EditorView.decorations.of(diffDecorations),
      keymap.of([
        {
          key: 'Escape',
          run: () => {
            useNotebookStore.getState().rejectAgentCellEdit(cellId);
            return true;
          },
        },
        {
          key: 'Ctrl-Enter',
          run: () => {
            useNotebookStore.getState().acceptAgentCellEdit(cellId);
            return true;
          },
        },
      ]),
    ];
  }, [isPending, docText, cell?.committedSource, cellId]);

  /* ── Assemble extensions ── */
  const extensions = useMemo(() => [
    python(),
    syntaxHighlighting(pythonHighlightStyle),
    ...(showLineNumbers ? [lineNumbers()] : []),
    keymap.of([
      { key: 'Tab', run: indentMore },
      { key: 'Shift-Tab', run: indentLess },
      { key: 'Shift-Enter', run: () => { runCellRef.current(); return true; } },
    ]),
    ...diffExtensions,
  ], [showLineNumbers, diffExtensions]);

  const handleChange = useCallback((value: string) => {
    updateCellSource(cellId, value);
  }, [cellId, updateCellSource]);

  const handleFocus = useCallback(() => {
    setFocusedCell(cellId);
  }, [cellId, setFocusedCell]);

  if (!cell) return null;

  const executionLabel = cell.isRunning ? '[*]' : cell.executionCount != null ? `[${cell.executionCount}]` : '[ ]';

  // Format execution time
  const getExecutionTime = () => {
    if (!cell.executedAt) return null;
    const date = new Date(cell.executedAt);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;

    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' });
  };

  const isCellCollapsed = useNotebookStore((s) => s.collapsedCells.has(cellId));

  return (
    <div
      className={`notebook-cell notebook-cell-code ${cell.isRunning ? 'is-running' : ''} ${isFocused ? 'is-focused' : ''}`}
      onClick={() => setFocusedCell(cellId)}
    >
      <CellToolbar
        cellId={cellId}
        cellIndex={cellIndex}
        isRunning={cell.isRunning}
        onRun={runCell}
        executionCount={cell.executionCount}
        executedAt={cell.executedAt}
      />
      <div className="notebook-cell-body">
        {isCellCollapsed && (
            <div
              className="notebook-collapsed-cell-hint"
              onClick={() => useNotebookStore.getState().toggleCollapseCell(cellId)}
              title="Click to expand cell"
            >
              <em>Cell content collapsed ({splitLines(cell.source).length} line(s))</em>
            </div>
          )}
        <div style={{ display: isCellCollapsed ? 'none' : 'block' }}>
          {/* ── Pending Diff Actions: Only the two subtle buttons ── */}
          {cell.cellStatus === 'pending' && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-end',
                padding: '4px 12px 2px',
                gap: 6,
              }}
            >
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  useNotebookStore.getState().rejectAgentCellEdit(cellId);
                }}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: '2px 8px',
                  fontSize: '0.72rem',
                  fontWeight: 500,
                  color: '#64748b',
                  background: '#ffffff',
                  border: '1px solid #e2e8f0',
                  borderRadius: 4,
                  cursor: 'pointer',
                  lineHeight: 1.4,
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = '#dc2626';
                  e.currentTarget.style.borderColor = '#fecaca';
                  e.currentTarget.style.background = '#fef2f2';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = '#64748b';
                  e.currentTarget.style.borderColor = '#e2e8f0';
                  e.currentTarget.style.background = '#ffffff';
                }}
                title="Reject proposed change (Esc)"
              >
                <X size={11} />
                <span>Reject</span>
              </button>

              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  useNotebookStore.getState().acceptAgentCellEdit(cellId);
                }}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: '2px 8px',
                  fontSize: '0.72rem',
                  fontWeight: 500,
                  color: '#15803d',
                  background: '#f0fdf4',
                  border: '1px solid #bbf7d0',
                  borderRadius: 4,
                  cursor: 'pointer',
                  lineHeight: 1.4,
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = '#dcfce7';
                  e.currentTarget.style.borderColor = '#86efac';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = '#f0fdf4';
                  e.currentTarget.style.borderColor = '#bbf7d0';
                }}
                title="Accept proposed change (Ctrl+Enter)"
              >
                <Check size={11} />
                <span>Accept</span>
              </button>
            </div>
          )}

          <div className="notebook-editor-container" style={{ position: 'relative' }}>
            <div className="notebook-cell-editor">
              <ReactCodeMirror
                value={docText}
                extensions={extensions}
                onChange={handleChange}
                onFocus={handleFocus}
                readOnly={false}
                editable={true}
                theme={editorTheme}
                basicSetup={{
                  lineNumbers: false,
                  foldGutter: false,
                  highlightActiveLine: false,
                  highlightActiveLineGutter: false,
                  syntaxHighlighting: false,
                }}
              />
            </div>
          </div>
        </div>
        {cell.outputs.length > 0 && (
          <button
            className="notebook-collapse-btn"
            onClick={(e) => { e.stopPropagation(); toggleCollapseOutput(cellId); }}
            title={isCollapsed ? 'Expand output' : 'Collapse output'}
          >
            {isCollapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
            <span>{isCollapsed ? `${cell.outputs.length} output(s) hidden` : 'Hide output'}</span>
          </button>
        )}
        {!isCollapsed && (
          <div>
            {cell.cellStatus === 'pending' && cell.outputs.length > 0 && (
              <span className="notebook-pending-output-badge">
                Ran from pending edit
              </span>
            )}
            <CellOutput outputs={cell.outputs} />
          </div>
        )}
      </div>
    </div>
  );
}
