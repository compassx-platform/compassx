import React, { useMemo, useRef } from 'react';
import ReactCodeMirror from '@uiw/react-codemirror';
import { css } from '@codemirror/lang-css';
import { html } from '@codemirror/lang-html';
import { javascript } from '@codemirror/lang-javascript';
import { json } from '@codemirror/lang-json';
import { markdown } from '@codemirror/lang-markdown';
import { python } from '@codemirror/lang-python';
import { syntaxTree } from '@codemirror/language';
import { Prec, RangeSetBuilder } from '@codemirror/state';
import { Decoration, EditorView, keymap, ViewPlugin } from '@codemirror/view';

const KEYWORDS = new Set([
  'def', 'return', 'if', 'elif', 'else', 'for', 'while', 'class', 'import', 'from', 'as',
  'try', 'except', 'finally', 'with', 'lambda', 'pass', 'raise', 'yield', 'async', 'await',
  'in', 'not', 'and', 'or', 'is', 'global', 'nonlocal', 'assert', 'del', 'break', 'continue',
  'function', 'const', 'let', 'var', 'new', 'this', 'export', 'extends', 'typeof', 'of',
  'switch', 'case', 'default', 'throw', 'catch', 'interface', 'type', 'enum', 'public',
  'private', 'protected', 'static', 'package',
]);

function tokenClass(node: { name: string; node: { parent: { name: string } | null } }) {
  const name = node.name;
  if (name === 'Number' || name === 'Boolean' || name === 'None' || name === 'True' || name === 'False' || name === 'null' || name === 'Null') return 'cx-tok-literal';
  if (name === 'String' || name === 'StringContent' || name === 'FormatString' || name === 'Character' || name === 'Regexp' || name === 'TemplateString') return 'cx-tok-string';
  if (name === 'Comment' || name === 'LineComment' || name === 'BlockComment') return 'cx-tok-comment';
  if (name === 'PropertyName' || name === 'PropertyDefinition' || name === 'AttributeName') return 'cx-tok-property';
  if (name === 'ClassName' || name === 'TypeName') return 'cx-tok-type';
  if (name === 'Keyword' || KEYWORDS.has(name)) return 'cx-tok-keyword';
  const parent = node.node.parent?.name;
  if (name === 'VariableName' && (parent === 'CallExpression' || parent === 'FunctionDefinition' || parent === 'MemberExpression')) return 'cx-tok-function';
  return '';
}

const tokenHighlighter = ViewPlugin.fromClass(
  class {
    decorations: ReturnType<typeof buildTokenDecorations>;
    constructor(view: EditorView) {
      this.decorations = buildTokenDecorations(view);
    }
    update(update: { docChanged: boolean; viewportChanged: boolean; view: EditorView; state: EditorView['state']; startState: EditorView['state'] }) {
      if (update.docChanged || update.viewportChanged || syntaxTree(update.state) !== syntaxTree(update.startState)) {
        this.decorations = buildTokenDecorations(update.view);
      }
    }
  },
  { decorations: (value) => value.decorations },
);

function buildTokenDecorations(view: EditorView) {
  const builder = new RangeSetBuilder<Decoration>();
  const tree = syntaxTree(view.state);
  for (const range of view.visibleRanges) {
    tree.iterate({
      from: range.from,
      to: range.to,
      enter(node) {
        if (node.node.firstChild || node.to <= node.from) return;
        const token = tokenClass(node);
        if (token) builder.add(node.from, node.to, Decoration.mark({ class: token }));
      },
    });
  }
  return builder.finish();
}

const editorTheme = EditorView.theme(
  {
    '&': {
      height: '100%',
      backgroundColor: '#ffffff',
      color: '#0f172a',
    },
    '.cm-scroller': {
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
      lineHeight: '1.55',
      overflow: 'auto',
    },
    '.cm-content': {
      caretColor: '#0f172a',
    },
    '.cm-gutters': {
      backgroundColor: '#ffffff',
      color: '#94a3b8',
      borderRight: 'none',
    },
    '.cm-activeLine': {
      backgroundColor: 'rgba(15, 23, 42, 0.03)',
    },
    '.cx-tok-keyword': { color: '#7c3aed' },
    '.cx-tok-string': { color: '#0284c7' },
    '.cx-tok-literal': { color: '#2563eb' },
    '.cx-tok-comment': { color: '#94a3b8', fontStyle: 'italic' },
    '.cx-tok-function': { color: '#0369a1' },
    '.cx-tok-property': { color: '#dc2626' },
    '.cx-tok-type': { color: '#0d9488' },
  },
  { dark: false },
);

function languageFor(path: string) {
  const ext = path.split('.').pop()?.toLowerCase() || '';
  if (ext === 'py') return python();
  if (ext === 'json') return json();
  if (ext === 'html' || ext === 'htm') return html();
  if (ext === 'css' || ext === 'scss' || ext === 'sass' || ext === 'less') return css();
  if (ext === 'md' || ext === 'markdown') return markdown();
  if (ext === 'js' || ext === 'jsx' || ext === 'mjs' || ext === 'cjs' || ext === 'ts' || ext === 'tsx') {
    return javascript({ jsx: ext === 'jsx' || ext === 'tsx', typescript: ext === 'ts' || ext === 'tsx' });
  }
  return null;
}

export function WorkspaceFileEditor({
  path,
  value,
  readOnly,
  onChange,
  onSave,
}: {
  path: string;
  value: string;
  readOnly?: boolean;
  onChange: (value: string) => void;
  onSave: () => void;
}) {
  const saveRef = useRef(onSave);
  saveRef.current = onSave;
  const extensions = useMemo(() => {
    const language = languageFor(path);
    const saveKey = Prec.highest(
      keymap.of([
        {
          key: 'Mod-s',
          preventDefault: true,
          run: () => {
            saveRef.current();
            return true;
          },
        },
      ]),
    );
    return language ? [language, tokenHighlighter, editorTheme, saveKey] : [editorTheme, saveKey];
  }, [path]);

  return (
    <ReactCodeMirror
      value={value}
      theme="light"
      height="100%"
      editable={!readOnly}
      extensions={extensions}
      basicSetup={{
        lineNumbers: true,
        highlightActiveLine: true,
        foldGutter: false,
        syntaxHighlighting: false,
        bracketMatching: true,
        closeBrackets: true,
        autocompletion: false,
      }}
      onChange={onChange}
      style={{ height: '100%', fontSize: '13px' }}
    />
  );
}
