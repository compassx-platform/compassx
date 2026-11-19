import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export interface RuntimePlanDoc {
  id: string;
  title: string;
  content: string;
}

export function planTitle(content: string): string {
  const heading = content.match(/^#{1,3}\s+(.+)$/m);
  const raw = (heading?.[1] || content.split('\n').find((line) => line.trim()) || 'Plan')
    .replace(/[`*]/g, '')
    .trim();
  return raw.slice(0, 80) || 'Plan';
}

export function PlanPanel({
  plan,
  sandboxReady,
  building,
  onBuild,
}: {
  plan: RuntimePlanDoc | null;
  sandboxReady: boolean;
  building: boolean;
  onBuild: (content: string) => void;
}) {
  const [draft, setDraft] = useState(plan?.content || '');
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    setDraft(plan?.content || '');
    setEditing(false);
  }, [plan?.id, plan?.content]);

  if (!plan) {
    return <p style={{ margin: 24, color: '#64748b', fontSize: '0.9rem' }}>No plan in this session yet.</p>;
  }

  return (
    <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', background: '#ffffff' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 20px', borderBottom: '1px solid #e4e4e7', flexShrink: 0 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', color: '#71717a' }}>Plan</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#18181b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{plan.title}</div>
        </div>
        <button
          type="button"
          onClick={() => setEditing((value) => !value)}
          style={{
            border: '1px solid #e4e4e7',
            background: '#ffffff',
            color: '#3f3f46',
            borderRadius: 8,
            padding: '6px 12px',
            fontSize: 13,
            cursor: 'pointer',
          }}
        >
          {editing ? 'Preview' : 'Edit'}
        </button>
        <button
          type="button"
          disabled={!sandboxReady || building || !draft.trim()}
          onClick={() => onBuild(draft)}
          style={{
            border: 'none',
            background: '#18181b',
            color: '#ffffff',
            borderRadius: 8,
            padding: '6px 14px',
            fontSize: 13,
            fontWeight: 600,
            cursor: !sandboxReady || building || !draft.trim() ? 'default' : 'pointer',
            opacity: !sandboxReady || building || !draft.trim() ? 0.5 : 1,
          }}
        >
          Build
        </button>
      </div>
      <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
        {editing ? (
          <textarea
            aria-label="Edit plan"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            style={{
              display: 'block',
              width: '100%',
              height: '100%',
              boxSizing: 'border-box',
              border: 'none',
              outline: 'none',
              resize: 'none',
              padding: '28px 40px 48px',
              font: 'inherit',
              fontSize: 15,
              lineHeight: 1.6,
              color: '#18181b',
            }}
          />
        ) : (
          <article style={{ maxWidth: 760, margin: '0 auto', padding: '36px 40px 64px', color: '#18181b', fontSize: 16, lineHeight: 1.65 }}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                h1: ({ children }) => <h1 style={{ margin: '0 0 16px', fontSize: 28, lineHeight: 1.25 }}>{children}</h1>,
                h2: ({ children }) => <h2 style={{ margin: '24px 0 10px', fontSize: 20 }}>{children}</h2>,
                h3: ({ children }) => <h3 style={{ margin: '20px 0 8px', fontSize: 17 }}>{children}</h3>,
                p: ({ children }) => <p style={{ margin: '0 0 12px' }}>{children}</p>,
                ul: ({ children }) => <ul style={{ margin: '0 0 12px', paddingLeft: 22 }}>{children}</ul>,
                ol: ({ children }) => <ol style={{ margin: '0 0 12px', paddingLeft: 22 }}>{children}</ol>,
                li: ({ children }) => <li style={{ marginBottom: 6 }}>{children}</li>,
                code: ({ children }) => (
                  <code style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace', fontSize: '0.9em', background: '#f4f4f5', borderRadius: 4, padding: '1px 4px' }}>
                    {children}
                  </code>
                ),
                pre: ({ children }) => (
                  <pre style={{ margin: '12px 0', padding: 12, overflow: 'auto', background: '#fafafa', border: '1px solid #e4e4e7', borderRadius: 8, fontSize: 13 }}>
                    {children}
                  </pre>
                ),
              }}
            >
              {draft}
            </ReactMarkdown>
          </article>
        )}
      </div>
    </div>
  );
}
