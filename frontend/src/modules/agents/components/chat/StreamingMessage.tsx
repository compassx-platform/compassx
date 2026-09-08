import React, { useState } from 'react';
import { Loader2, Zap, ChevronDown, ChevronRight } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { AgentBadge } from './AgentBadge';
import { ThoughtAccordion, ThinkingWaveDots, parseThoughtContent } from './ThoughtAccordion';
import { markdownComponents } from './markdownComponents';
import { transformAssetTagsToMarkdown } from '../AssetChip';

interface StreamingMessageProps {
  text: string;
  activeTool: string | null;
  activeToolArgs: Record<string, unknown> | null;
  agentName?: string | null;
  agentColor?: string | null;
  invocationDepth?: number;
}

export function StreamingMessage({
  text,
  activeTool,
  activeToolArgs,
  agentName,
  agentColor,
  invocationDepth = 0,
}: StreamingMessageProps) {
  const [argsOpen, setArgsOpen] = useState(false);
  const isSubagent = !!agentName && invocationDepth > 0;

  const { thought, response } = parseThoughtContent(text);

  return (
    <div
      style={{
        display: 'flex',
        gap: 10,
        marginBottom: 16,
        paddingLeft: isSubagent ? invocationDepth * 16 : 0,
      }}
    >
      <div style={{ maxWidth: '100%', display: 'flex', flexDirection: 'column', gap: 4, flex: 1 }}>
        {isSubagent && agentName && (
          <AgentBadge name={agentName} color={agentColor} depth={invocationDepth} />
        )}
        <div
          style={{
            background: 'transparent',
            color: 'var(--color-text)',
            padding: 0,
            borderRadius: 0,
            border: 'none',
            fontSize: '0.875rem',
            lineHeight: 1.6,
            width: '100%',
          }}
        >
          {thought && <ThoughtAccordion thought={thought} isStreaming={true} />}

          {response && (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeHighlight]}
              components={markdownComponents}
              urlTransform={(url) => url}
            >
              {transformAssetTagsToMarkdown(response)}
            </ReactMarkdown>
          )}

          {activeTool ? (
            <div style={{ marginTop: thought || response ? 8 : 0 }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  color: 'var(--color-text-muted)',
                  cursor: activeToolArgs ? 'pointer' : 'default',
                  padding: '4px 8px',
                  background: 'var(--color-surface-hover)',
                  borderRadius: 6,
                }}
                onClick={() => activeToolArgs && setArgsOpen((o) => !o)}
              >
                <Loader2 size={12} className="spin" />
                <Zap size={12} color="var(--color-primary)" />
                <span style={{ color: 'var(--color-text)' }}>
                  Calling <strong>{activeTool}</strong>…
                </span>
                {activeToolArgs && (
                  <span style={{ marginLeft: 2 }}>
                    {argsOpen ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                  </span>
                )}
              </div>
              {argsOpen && activeToolArgs && (
                <pre
                  style={{
                    margin: '6px 0 0',
                    maxHeight: 180,
                    overflowY: 'auto',
                    overflowX: 'auto',
                    fontSize: '0.72rem',
                    color: 'var(--color-text-muted)',
                    scrollbarWidth: 'thin',
                  }}
                >
                  {JSON.stringify(activeToolArgs, null, 2)}
                </pre>
              )}
            </div>
          ) : !text ? (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 2, color: 'var(--color-text-muted)' }}>
              Thinking<ThinkingWaveDots />
            </span>
          ) : null}
        </div>
      </div>
    </div>
  );
}
export default StreamingMessage;
