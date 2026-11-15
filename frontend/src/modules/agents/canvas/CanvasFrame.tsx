import React, { Component, useMemo, type ReactNode } from 'react';
import { compileCanvas } from './compileCanvas';
import { checkCanvasSource } from './canvasSourceGate';
import { CanvasThemeProvider } from './kit';
import { lightCanvasTheme } from './theme';

interface CanvasFrameProps {
  source: string;
  rejected: string;
}

class CanvasBoundary extends Component<{ children: ReactNode }, { message: string }> {
  state = { message: '' };

  static getDerivedStateFromError(error: Error) {
    return { message: error.message || 'This canvas could not be shown.' };
  }

  render() {
    if (this.state.message) {
      return <p role="alert" style={{ margin: 0, color: '#991b1b', fontSize: 14 }}>{this.state.message}</p>;
    }
    return this.props.children;
  }
}

export function CanvasFrame({ source, rejected }: CanvasFrameProps) {
  const compiled = useMemo(() => {
    if (rejected || !source.trim()) return { Page: null as React.ComponentType | null, error: rejected };
    const problem = checkCanvasSource(source);
    if (problem) return { Page: null, error: problem };
    try {
      return { Page: compileCanvas(source), error: '' };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'This canvas could not be shown.';
      return { Page: null, error: message };
    }
  }, [rejected, source]);

  if (compiled.error) {
    return (
      <div role="alert" style={{ margin: 16, padding: '10px 12px', border: '1px solid #fecaca', borderRadius: 8, color: '#991b1b', fontSize: '0.84rem' }}>
        {compiled.error}
      </div>
    );
  }

  const Page = compiled.Page;
  if (!Page) return null;

  return (
    <div style={{ flex: 1, minHeight: 0, overflow: 'auto', background: lightCanvasTheme.bg }}>
      <CanvasThemeProvider theme={lightCanvasTheme}>
        <div style={{ boxSizing: 'border-box', minHeight: '100%', padding: 20, color: lightCanvasTheme.text, fontFamily: 'system-ui, sans-serif' }}>
          <CanvasBoundary key={source}>
            <Page />
          </CanvasBoundary>
        </div>
      </CanvasThemeProvider>
    </div>
  );
}
