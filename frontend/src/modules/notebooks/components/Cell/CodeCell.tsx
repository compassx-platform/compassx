import { useEffect, useRef, useCallback } from 'react';
import { EditorView, keymap, lineNumbers, Decoration } from '@codemirror/view';
import { EditorState, RangeSetBuilder } from '@codemirror/state';
import { indentMore, indentLess } from '@codemirror/commands';
import { python } from '@codemirror/lang-python';
import { HighlightStyle, syntaxHighlighting } from '@codemirror/language';
// @ts-ignore
import { tags } from '@lezer/highlight';
import { ChevronDown, ChevronRight } from 'lucide-react';
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

const pythonHighlightStyle = HighlightStyle.define([
  { tag: tags.keyword, color: 'var(--syntax-keyword)', fontWeight: 'bold' },
  { tag: tags.comment, color: 'var(--syntax-comment)', fontStyle: 'italic' },
  { tag: tags.string, color: 'var(--syntax-string)' },
  { tag: tags.number, color: 'var(--syntax-number)' },
  { tag: tags.bool, color: 'var(--syntax-bool)' },
  { tag: tags.null, color: 'var(--syntax-bool)' },
  { tag: tags.operator, color: 'var(--syntax-operator)' },
  { tag: tags.function(tags.variableName), color: 'var(--syntax-function)' },
  { tag: tags.definition(tags.variableName), color: 'var(--syntax-definition)' },
  { tag: tags.className, color: 'var(--syntax-class)' },
  { tag: tags.typeName, color: 'var(--syntax-class)' },
  { tag: tags.standard(tags.variableName), color: 'var(--syntax-builtin)' },
  { tag: tags.special(tags.variableName), color: 'var(--syntax-builtin)' },
  { tag: tags.propertyName, color: 'var(--syntax-property)' },
].filter(style => style.tag !== undefined));

export default function CodeCell({ cellId, cellIndex }: Props) {
  const cell = useNotebookStore((s) => s.cells.find((c) => c.id === cellId));
  const updateCellSource = useNotebookStore((s) => s.updateCellSource);
  const setFocusedCell = useNotebookStore((s) => s.setFocusedCell);
  const focusedCellId = useNotebookStore((s) => s.focusedCellId);
  const showLineNumbers = useNotebookStore((s) => s.showLineNumbers);
  const collapsedOutputs = useNotebookStore((s) => s.collapsedOutputs);
  const toggleCollapseOutput = useNotebookStore((s) => s.toggleCollapseOutput);
  const { executeCell } = useExecuteCell();

  const editorRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView | null>(null);
  const isFocused = focusedCellId === cellId;
  const isCollapsed = collapsedOutputs.has(cellId);

  const runCell = useCallback(() => {
    if (!cell) return;
    executeCell(cell.id, cell.source);
  }, [cell, executeCell]);

  useEffect(() => {
    if (!editorRef.current || viewRef.current) return;

    const isPending = cell?.cellStatus === 'pending';
    const diffLines = isPending
      ? buildDiff(cell?.committedSource || '', cell?.pendingSource || '')
      : [];
    const docText = isPending
      ? diffLines.map(l => l.text).join('\n')
      : (cell?.source ?? '');

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

    const extensions = [
      python(),
      syntaxHighlighting(pythonHighlightStyle),
      ...(showLineNumbers
        ? [
            isPending
              ? lineNumbers({ formatNumber: (lineNo) => lineNumbersMap[lineNo - 1] ?? '' })
              : lineNumbers(),
          ]
        : []),
      isPending ? EditorState.readOnly.of(true) : [],
      isPending ? EditorView.decorations.of(diffDecorations) : [],
      keymap.of([
        { key: 'Tab', run: indentMore },
        { key: 'Shift-Tab', run: indentLess },
        { key: 'Shift-Enter', run: () => { runCellRef.current(); return true; } },
      ]),
      isPending
        ? keymap.of([
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
          ])
        : [],
      EditorView.updateListener.of((update) => {
        if (update.docChanged && !isPending) updateCellSource(cellId, update.state.doc.toString());
        if (update.focusChanged && update.view.hasFocus) setFocusedCell(cellId);
      }),
      EditorView.theme({
        '&': { 
          fontSize: '13px', 
          fontFamily: "var(--cx-font-mono, 'Courier New', monospace)",
          color: 'var(--color-text)',
        },
        '&.cm-focused': {
          outline: 'none',
        },
        '.cm-content': {
          outline: 'none',
        },
        '.cm-cursor': {
          borderLeftColor: 'var(--color-text)',
        },
        '.cm-gutters': { 
          backgroundColor: 'var(--color-bg)', 
          borderRight: '1px solid var(--color-border)',
          color: 'var(--color-text-muted)',
        },
        '.cm-lineNumbers .cm-gutterElement': { 
          color: 'var(--color-text-subtle)', 
          minWidth: '3em', 
          padding: '0 4px' 
        },
        '&.cm-focused .cm-cursor': {
          borderLeftColor: 'var(--color-text)',
        },
        '&.cm-focused .cm-selectionBackground, ::selection': {
          backgroundColor: 'var(--color-primary-bg)',
        },
        '.cm-activeLine': {
          backgroundColor: 'var(--color-surface-hover)',
        },
        '.cm-activeLineGutter': {
          backgroundColor: 'var(--color-surface-hover)',
        },
      }),
    ];

    const view = new EditorView({
      state: EditorState.create({ doc: docText, extensions }),
      parent: editorRef.current,
    });

    viewRef.current = view;
    return () => { view.destroy(); viewRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cellId, cell?.cellStatus, cell?.committedSource, cell?.pendingSource, showLineNumbers]);

  useEffect(() => {
    const view = viewRef.current;
    if (!view || !cell) return;
    const isPending = cell.cellStatus === 'pending';
    if (isPending) return;
    const currentDoc = view.state.doc.toString();
    if (currentDoc === cell.source) return;
    const selection = view.state.selection;
    view.dispatch({
      changes: { from: 0, to: currentDoc.length, insert: cell.source },
      selection,
    });
  }, [cell?.source, cell?.cellStatus]);

  // Keep runCell ref fresh
  const runCellRef = useRef(runCell);
  useEffect(() => { runCellRef.current = runCell; }, [runCell]);

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
            <div ref={editorRef} className="notebook-cell-editor" />
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
