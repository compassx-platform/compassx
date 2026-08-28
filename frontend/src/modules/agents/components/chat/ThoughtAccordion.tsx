import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export interface ParsedContent {
  thought: string | null;
  response: string;
}

export function parseThoughtContent(rawContent: string | null): ParsedContent {
  if (!rawContent) return { thought: null, response: '' };

  let text = rawContent.trim();
  let thought: string | null = null;

  // 1. Check for XML tags: <thought>...</thought> or <thinking>...</thinking>
  const tagMatch = text.match(/<(?:thought|thinking)>([\s\S]*?)<\/(?:thought|thinking)>/i);
  if (tagMatch) {
    thought = tagMatch[1].trim();
    text = text.replace(/<(?:thought|thinking)>[\s\S]*?<\/(?:thought|thinking)>/gi, '').trim();
    return { thought: thought || null, response: text };
  }

  // 2. Check for ReAct Markdown patterns: "Thought: ...", "**Thought:** ...", "### Thought ..."
  const thoughtHeaderMatch = text.match(/^(?:(?:\*{0,2}|#{1,4}\s*)Thought:?\*{0,2}|Reasoning:?)\s*([\s\S]*?)(?=(?:\n\s*(?:\*{0,2}|#{1,4}\s*)Action:?|\n\s*(?:\*{0,2}|#{1,4}\s*)Final Answer:?|\n\n[A-Z0-9])|$)/i);
  if (thoughtHeaderMatch) {
    const captured = thoughtHeaderMatch[1].trim();
    const actionIndex = text.search(/\n\s*(?:\*{0,2}|#{1,4}\s*)Action:?/i);
    const finalAnswerMatch = text.match(/\n\s*(?:\*{0,2}|#{1,4}\s*)Final Answer:?\s*([\s\S]*)/i);

    if (finalAnswerMatch) {
      thought = captured.replace(/(?:\*{0,2}|#{1,4}\s*)Action:?[\s\S]*/i, '').trim();
      text = finalAnswerMatch[1].trim();
    } else if (actionIndex !== -1) {
      thought = captured.replace(/(?:\*{0,2}|#{1,4}\s*)Action:?[\s\S]*/i, '').trim();
      text = '';
    } else {
      const parts = text.split(/\n{2,}/);
      if (parts.length > 1 && parts[0].toLowerCase().includes('thought')) {
        thought = parts[0].replace(/^(?:\*{0,2}|#{1,4}\s*)Thought:?\*{0,2}\s*/i, '').trim();
        text = parts.slice(1).join('\n\n').trim();
      } else {
        thought = text.replace(/^(?:\*{0,2}|#{1,4}\s*)Thought:?\*{0,2}\s*/i, '').trim();
        text = '';
      }
    }
    return { thought: thought || null, response: text };
  }

  return { thought: null, response: text };
}

export function ThinkingWaveDots() {
  return (
    <span className="thinking-wave-dots" aria-label="Thinking in progress">
      <span className="thinking-dot" />
      <span className="thinking-dot" />
      <span className="thinking-dot" />
    </span>
  );
}

interface ThoughtAccordionProps {
  thought: string;
  isStreaming?: boolean;
}

export function ThoughtAccordion({ thought, isStreaming = false }: ThoughtAccordionProps) {
  const [open, setOpen] = useState(false);

  const rawItems = thought
    .split(/\n+/)
    .map((item) => item.trim().replace(/^[-*•]\s*/, ''))
    .filter((item) => item.length > 0);

  const headerContent = isStreaming ? (
    <span style={{ display: 'inline-flex', alignItems: 'center' }}>
      Thinking<ThinkingWaveDots />
    </span>
  ) : (
    'Thinking'
  );

  return (
    <div
      style={{
        margin: '0 0 12px 0',
        fontSize: '0.85rem',
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 4,
          padding: 0,
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          color: 'var(--color-text, #111827)',
          fontWeight: 600,
          fontSize: '0.85rem',
          textAlign: 'left',
          lineHeight: 1.2,
        }}
      >
        <span style={{ display: 'inline-flex', alignItems: 'center' }}>
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>
        <span>{headerContent}</span>
      </button>

      {open && (
        <div
          style={{
            marginTop: 8,
            paddingLeft: 4,
            color: '#6b7280',
            lineHeight: 1.5,
            fontSize: '0.83rem',
          }}
        >
          <ul style={{ margin: 0, paddingLeft: 18, listStyleType: 'disc' }}>
            {rawItems.map((item, idx) => (
              <li key={idx} style={{ marginBottom: 6 }}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{item}</ReactMarkdown>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
export default ThoughtAccordion;
