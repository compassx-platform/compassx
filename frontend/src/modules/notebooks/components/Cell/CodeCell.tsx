import { useRef, useCallback, useMemo } from 'react';
import { EditorView, keymap, lineNumbers, Decoration } from '@codemirror/view';
import { EditorState, RangeSetBuilder } from '@codemirror/state';
import { indentMore, indentLess } from '@codemirror/commands';
import { python } from '@codemirror/lang-python';
import { syntaxHighlighting } from '@codemirror/language';
import { oneDarkHighlightStyle } from '@codemirror/theme-one-dark';
import { tags } from '@lezer/highlight';
import { HighlightStyle } from '@codemirror/language';
import { ChevronDown, ChevronRight } from 'lucide-react';
import ReactCodeMirror from '@uiw/react-codemirror';
import { useNotebookStore, hasDatabaseSideEffects } from '../../store/notebookStore';

type DiffLine = {
  kind: 'context' | 'added' | 'removed';
  text: string;
};

function splitLines(source: string) {
  return source.length ? source.split('\n') : [];
}

function buildDiff(originalSource: string, proposedSource: string): DiffLine[] {
  const original = splitLines(originalSource);
  const proposed = splitLines(proposedSource);
  let prefix = 0;
  while (prefix < original.length && prefix < proposed.length && original[prefix] === proposed[prefix]) {
    prefix += 1;
  }

  let originalSuffix = original.length - 1;
  let proposedSuffix = proposed.length - 1;
  while (
    originalSuffix >= prefix &&
    proposedSuffix >= prefix &&
    original[originalSuffix] === proposed[proposedSuffix]
  ) {
    originalSuffix -= 1;
    proposedSuffix -= 1;
  }

  const lines: DiffLine[] = [];
  original.slice(0, prefix).forEach((text) => lines.push({ kind: 'context', text }));
  original.slice(prefix, originalSuffix + 1).forEach((text) => lines.push({ kind: 'removed', text }));
  proposed.slice(prefix, proposedSuffix + 1).forEach((text) => lines.push({ kind: 'added', text }));
  original.slice(originalSuffix + 1).forEach((text) => lines.push({ kind: 'context', text }));
  return lines.length ? lines : [{ kind: 'context', text: '' }];
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

  /* ── Build diff decorations for pending edits ── */
  const { docText, diffExtensions } = useMemo(() => {
    if (!isPending) {
      return { docText: cell?.source ?? '', diffExtensions: [] as any[] };
    }

    const diffLines = buildDiff(cell?.committedSource || '', cell?.pendingSource || '');
    const text = diffLines.map(l => l.text).join('\n');

    const lineNumbersMap: string[] = [];
    let proposedLineCount = 0;
    diffLines.forEach((line) => {
      if (line.kind === 'removed') {
        lineNumbersMap.push('');
      } else {
        proposedLineCount += 1;
        lineNumbersMap.push(String(proposedLineCount));
      }
    });

    const builder = new RangeSetBuilder<Decoration>();
    let pos = 0;
    diffLines.forEach((line) => {
      if (line.kind === 'added' || line.kind === 'removed') {
        builder.add(pos, pos, Decoration.line({
          attributes: { class: `cm-diff-${line.kind}` }
        }));
      }
      pos += line.text.length + 1;
    });
    const diffDecorations = builder.finish();

    return {
      docText: text,
      diffExtensions: [
        lineNumbers({ formatNumber: (lineNo: number) => lineNumbersMap[lineNo - 1] ?? '' }),
        EditorState.readOnly.of(true),
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
      ],
    };
  }, [isPending, cell?.source, cell?.committedSource, cell?.pendingSource, cellId]);

  /* ── Assemble extensions ── */
  const extensions = useMemo(() => [
    python(),
    syntaxHighlighting(pythonHighlightStyle),
    ...(showLineNumbers && !isPending ? [lineNumbers()] : []),
    keymap.of([
      { key: 'Tab', run: indentMore },
      { key: 'Shift-Tab', run: indentLess },
      { key: 'Shift-Enter', run: () => { runCellRef.current(); return true; } },
    ]),
    ...diffExtensions,
  ], [showLineNumbers, isPending, diffExtensions]);

  const handleChange = useCallback((value: string) => {
    if (!isPending) {
      updateCellSource(cellId, value);
    }
  }, [cellId, isPending, updateCellSource]);

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
          <div className="notebook-editor-container" style={{ position: 'relative' }}>
            <div className="notebook-cell-editor">
              <ReactCodeMirror
                value={docText}
                extensions={extensions}
                onChange={handleChange}
                onFocus={handleFocus}
                readOnly={isPending}
                editable={!isPending}
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
          {cell.cellStatus === 'pending' && (
            <div className="notebook-inline-diff-actions">
              <button
                type="button"
                className="notebook-inline-reject"
                onClick={() => useNotebookStore.getState().rejectAgentCellEdit(cell.id)}
                title="Reject proposed changes"
              >
                Reject <kbd>Esc</kbd>
              </button>
              <button
                type="button"
                className="notebook-inline-accept"
                onClick={() => useNotebookStore.getState().acceptAgentCellEdit(cell.id)}
                title="Accept proposed changes"
              >
                Accept <kbd>CTRL</kbd>
              </button>
            </div>
          )}
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
    </div>
  );
}
