import React, { useState } from 'react';
import { Paperclip, Copy, Check } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { AgentBadge } from './AgentBadge';
import { ToolCard } from './ToolCard';
import { ChartBlock } from './ChartBlock';
import { ThoughtAccordion, parseThoughtContent } from './ThoughtAccordion';
import { markdownComponents } from './markdownComponents';
import { transformAssetTagsToMarkdown } from '../AssetChip';

export function CopyMessageButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy text:', err);
    }
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '4px',
        border: 'none',
        background: 'transparent',
        color: copied ? '#16a34a' : '#9ca3af',
        cursor: 'pointer',
        userSelect: 'none',
        borderRadius: '4px',
        transition: 'color 0.15s ease, background 0.15s ease',
        flexShrink: 0,
      }}
      onMouseEnter={(e) => {
        if (!copied) {
          e.currentTarget.style.color = '#4b5563';
          e.currentTarget.style.background = '#f3f4f6';
        }
      }}
      onMouseLeave={(e) => {
        if (!copied) {
          e.currentTarget.style.color = '#9ca3af';
          e.currentTarget.style.background = 'transparent';
        }
      }}
      title={copied ? 'Copied to clipboard!' : 'Copy message'}
    >
      {copied ? <Check size={14} color="#16a34a" /> : <Copy size={14} />}
    </button>
  );
}

interface ParsedUserAttachmentContent {
  attachments: string[];
  cleanText: string;
}

export function parseUserAttachmentContent(content: string | null): ParsedUserAttachmentContent {
  if (!content) return { attachments: [], cleanText: '' };
  const attachmentRegex = /\[attachment:\s*([^\]]+)\]/gi;
  const attachments: string[] = [];
  let match;
  while ((match = attachmentRegex.exec(content)) !== null) {
    if (match[1]?.trim()) {
      attachments.push(match[1].trim());
    }
  }
  const cleanText = content.replace(/\[attachment:\s*[^\]]+\]\n?/gi, '').trim();
  return { attachments, cleanText };
}

interface MessageBubbleProps {
  role: string;
  content: string | null;
  toolName?: string | null;
  toolResult?: Record<string, unknown> | null;
  agentName?: string | null;
  agentColor?: string | null;
  invocationDepth?: number;
}

export function MessageBubble({
  role,
  content,
  toolName,
  toolResult,
  agentName,
  agentColor,
  invocationDepth = 0,
}: MessageBubbleProps) {
  const isUser = role === 'user';
  const isTool = role === 'tool';
  const isSubagent = !isUser && !!agentName && invocationDepth > 0;

  if (isTool) {
    return (
      <ToolCard
        toolName={toolName ?? 'tool'}
        toolResult={toolResult}
      />
    );
  }

  const { thought, response } = parseThoughtContent(content);

  let vegaSpec: unknown = null;
  if (!isUser && response) {
    const jsonMatch = response.match(/```(?:json|vega-lite)\n([\s\S]*?)```/);
    if (jsonMatch) {
      try {
        const parsed = JSON.parse(jsonMatch[1]);
        if (parsed.$schema && parsed.$schema.includes('vega-lite')) {
          vegaSpec = parsed;
        }
      } catch {
        /* not JSON */
      }
    }
  }

  return (
    <div
      style={{
        display: 'flex',
        gap: 10,
        marginBottom: 16,
        flexDirection: isUser ? 'row-reverse' : 'row',
        paddingLeft: isSubagent ? invocationDepth * 16 : 0,
      }}
    >
      <div
        style={{
          maxWidth: isUser ? '80%' : '100%',
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
          alignItems: isUser ? 'flex-end' : 'flex-start',
          flex: isUser ? undefined : 1,
        }}
      >
        {isSubagent && agentName && (
          <AgentBadge name={agentName} color={agentColor} depth={invocationDepth} />
        )}
        <div
          style={{
            background: isUser ? '#f3f4f6' : 'transparent',
            color: isUser ? '#111827' : 'var(--color-text)',
            padding: isUser ? '8px 14px' : '0',
            borderRadius: isUser ? '8px' : '0',
            border: 'none',
            fontSize: '0.875rem',
            lineHeight: 1.6,
          }}
        >
          {isUser ? (
            (() => {
              const { attachments, cleanText } = parseUserAttachmentContent(content);
              return (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'flex-end' }}>
                  {attachments.length > 0 && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, justifyContent: 'flex-end' }}>
                      {attachments.map((filename, i) => (
                        <span
                          key={i}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 5,
                            padding: '2px 8px',
                            borderRadius: 4,
                            background: '#f1f5f9',
                            border: '1px solid #e2e8f0',
                            fontSize: '0.75rem',
                            color: '#475569',
                            fontWeight: 500,
                          }}
                        >
                          <Paperclip size={11} style={{ color: '#64748b', flexShrink: 0 }} />
                          <span>{filename}</span>
                        </span>
                      ))}
                    </div>
                  )}
                  <span style={{ whiteSpace: 'pre-wrap' }}>{cleanText}</span>
                </div>
              );
            })()
          ) : (
            <>
              {thought && <ThoughtAccordion thought={thought} />}
              {vegaSpec ? (
                <ChartBlock spec={vegaSpec} />
              ) : response ? (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeHighlight]}
                  components={markdownComponents}
                  urlTransform={(url) => url}
                >
                  {transformAssetTagsToMarkdown(response)}
                </ReactMarkdown>
              ) : !thought ? (
                <span style={{ opacity: 0.6, fontStyle: 'italic' }}>*(No response content)*</span>
              ) : null}
              {!isUser && response && (
                <div style={{ display: 'flex', justifyContent: 'flex-start', marginTop: 6 }}>
                  <CopyMessageButton text={response} />
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
export default MessageBubble;
