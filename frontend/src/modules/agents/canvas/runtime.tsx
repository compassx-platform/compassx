import React, { Component, useEffect, useState, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import { transform } from 'sucrase';
import { canvasBindings, checkCanvasSource, stripCanvasImports } from './canvasSourceGate';
import { CanvasThemeProvider } from './kit';
import * as kit from './kit';
import { lightCanvasTheme, type CanvasTheme } from './theme';

type CanvasMessage = {
  type?: string;
  source?: string;
  theme?: CanvasTheme;
};

type ParentMessage = {
  type: 'compassx-canvas';
  status: 'ready' | 'rendered' | 'error';
  message?: string;
};

function post(status: ParentMessage['status'], message?: string) {
  const payload: ParentMessage = { type: 'compassx-canvas', status, message };
  window.parent.postMessage(payload, '*');
}

function compileCanvas(source: string): React.ComponentType {
  const problem = checkCanvasSource(source);
  if (problem) throw new Error(problem);
  const stripped = stripCanvasImports(source);
  const transformed = transform(stripped, {
    transforms: ['typescript', 'jsx'],
    jsxRuntime: 'classic',
    jsxPragma: 'React.createElement',
    jsxFragmentPragma: 'React.Fragment',
    production: true,
  }).code;
  const prelude = canvasBindings(source)
    .map((binding) => `const ${binding.local} = __kit[${JSON.stringify(binding.imported)}];`)
    .join('\n');
  const body = `${prelude}\n${transformed.replace(/export\s+default\s+/, 'return ')}`;
  const factory = new Function('React', '__kit', body) as (react: typeof React, components: typeof kit) => React.ComponentType;
  const component = factory(React, kit);
  if (typeof component !== 'function') throw new Error('A canvas needs a default export.');
  return component;
}

class CanvasBoundary extends Component<{ children: ReactNode; resetKey: string }, { message: string }> {
  state = { message: '' };

  static getDerivedStateFromError(error: Error) {
    return { message: error.message || 'This canvas could not be shown.' };
  }

  componentDidUpdate(previous: { resetKey: string }) {
    if (previous.resetKey !== this.props.resetKey && this.state.message) {
      this.setState({ message: '' });
    }
  }

  componentDidCatch(error: Error) {
    post('error', error.message || 'This canvas could not be shown.');
  }

  render() {
    if (this.state.message) {
      return <p style={{ margin: 0, color: '#991b1b', font: '14px sans-serif' }}>{this.state.message}</p>;
    }
    return this.props.children;
  }
}

function CanvasHost() {
  const [source, setSource] = useState('');
  const [theme, setTheme] = useState<CanvasTheme>(lightCanvasTheme);
  const [page, setPage] = useState<ReactNode>(null);
  const [failed, setFailed] = useState('');

  useEffect(() => {
    let received = false;
    const onMessage = (event: MessageEvent<CanvasMessage>) => {
      if (event.source !== window.parent) return;
      const data = event.data;
      if (!data || data.type !== 'compassx-canvas') return;
      received = true;
      setTheme(data.theme || lightCanvasTheme);
      setSource(typeof data.source === 'string' ? data.source : '');
    };
    window.addEventListener('message', onMessage);
    post('ready');
    const timer = window.setInterval(() => {
      if (!received) post('ready');
    }, 200);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener('message', onMessage);
    };
  }, []);

  useEffect(() => {
    if (!source.trim()) {
      setPage(null);
      setFailed('');
      return;
    }
    try {
      const Page = compileCanvas(source);
      setFailed('');
      setPage(
        <CanvasBoundary key={source} resetKey={source}>
          <Page />
        </CanvasBoundary>,
      );
      post('rendered');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'This canvas could not be shown.';
      setPage(null);
      setFailed(message);
      post('error', message);
    }
  }, [source]);

  return (
    <CanvasThemeProvider theme={theme}>
      <div style={{ minHeight: '100%', boxSizing: 'border-box', padding: 20, background: theme.bg, color: theme.text, fontFamily: 'system-ui, sans-serif' }}>
        {failed ? <p style={{ margin: 0, color: '#991b1b', font: '14px sans-serif' }}>{failed}</p> : page}
      </div>
    </CanvasThemeProvider>
  );
}

const root = document.getElementById('root');
if (root) createRoot(root).render(<CanvasHost />);
