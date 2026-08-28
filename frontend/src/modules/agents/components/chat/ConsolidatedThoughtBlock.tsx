import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ThinkingWaveDots } from './ThoughtAccordion';
import { ToolCard } from './ToolCard';

export type TimelineStep =
  | { type: 'thought'; text: string }
  | { type: 'tool'; name: string; result: any };

interface ConsolidatedThoughtBlockProps {
  steps?: TimelineStep[];
  isStreaming?: boolean;
  activeTool?: string | null;
  activeToolArgs?: any;
}

export function ConsolidatedThoughtBlock({
  steps = [],
  isStreaming = false,
  activeTool,
  activeToolArgs,
}: ConsolidatedThoughtBlockProps) {
  const [open, setOpen] = useState(false);

  const headerContent = isStreaming ? (
    <span style={{ display: 'inline-flex', alignItems: 'center' }}>
      Thinking<ThinkingWaveDots />
    </span>
  ) : (
    'Thinking'
  );

  return (
    <div style={{ margin: '0 0 12px 0', fontSize: '0.85rem', position: 'relative' }}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          padding: 0,
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          color: '#6b7280',
          fontWeight: 600,
          fontSize: '0.83rem',
          textAlign: 'left',
          lineHeight: 1.2,
          position: 'relative',
        }}
      >
        <span
          style={{
            position: 'absolute',
            left: -18,
            top: '50%',
            transform: 'translateY(-50%)',
            display: 'inline-flex',
            alignItems: 'center',
          }}
        >
          {open ? <ChevronDown size={14} color="#6b7280" /> : <ChevronRight size={14} color="#6b7280" />}
        </span>
        <span>{headerContent}</span>
      </button>

      {open && (
        <div
          style={{
            marginTop: 10,
            paddingLeft: 0,
            color: '#6b7280',
            lineHeight: 1.5,
            fontSize: '0.83rem',
            position: 'relative',
          }}
        >
          {/* Timeline connector line aligned under chevron */}
          <div
            style={{
              position: 'absolute',
              top: 8,
              bottom: 8,
              left: -12,
              width: 1.5,
              background: '#e5e7eb',
              zIndex: 0,
            }}
          />

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, position: 'relative', zIndex: 1, minWidth: 0, maxWidth: '100%' }}>
            {steps.map((step, idx) => {
              if (step.type === 'thought') {
                return (
                  <div key={`step-${idx}`} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, minWidth: 0, maxWidth: '100%' }}>
                    <span
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: '50%',
                        background: '#9ca3af',
                        marginTop: 6,
                        marginLeft: -14,
                        flexShrink: 0,
                      }}
                    />
                    <div style={{ flex: 1, minWidth: 0, maxWidth: '100%', overflow: 'hidden' }}>
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{step.text}</ReactMarkdown>
                    </div>
                  </div>
                );
              } else {
                return (
                  <div key={`step-${idx}`} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, minWidth: 0, maxWidth: '100%' }}>
                    <span
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: 1,
                        background: '#9ca3af',
                        marginTop: 6,
                        marginLeft: -14,
                        flexShrink: 0,
                      }}
                    />
                    <div style={{ flex: 1, minWidth: 0, maxWidth: '100%' }}>
                      <ToolCard toolName={step.name} toolResult={step.result} />
                    </div>
                  </div>
                );
              }
            })}
            {activeTool && (
              <div key="active-tool" style={{ display: 'flex', alignItems: 'flex-start', gap: 10, minWidth: 0, maxWidth: '100%' }}>
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: 1,
                    background: '#6366f1',
                    marginTop: 6,
                    marginLeft: -14,
                    flexShrink: 0,
                  }}
                />
                <div style={{ flex: 1, minWidth: 0, maxWidth: '100%' }}>
                  <ToolCard toolName={activeTool} toolResult={{ args: activeToolArgs }} />
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
export default ConsolidatedThoughtBlock;
