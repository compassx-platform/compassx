import { X } from 'lucide-react';
import type { Widget } from '@/types/dashboard';
import FieldRow from '../common/FieldRow';
import Select from '../common/Select';

interface HtmlConfigSectionProps {
  widget: Widget;
  datasetOptions: Array<{ value: string; label: string }>;
  updateWidget: (widgetId: string, patch: Partial<Widget>) => void;
  onClose: () => void;
}

function lintHtmlWidget(content: string): string[] {
  const findings: string[] = [];
  if (!content) return findings;
  if (/fetch\(|XMLHttpRequest|WebSocket/i.test(content)) {
    findings.push(
      'Network access attempts detected (fetch, XMLHttpRequest, WebSocket). Direct network requests are blocked by Content Security Policy.'
    );
  }
  if (/window\.top|window\.parent|parent\.location|parent\.document/i.test(content)) {
    findings.push(
      'Attempts to access parent window context detected (window.top, window.parent, etc.). Access is restricted by iframe sandbox.'
    );
  }
  if (/document\.cookie|localStorage|sessionStorage/i.test(content)) {
    findings.push(
      'Storage access detected (document.cookie, localStorage, sessionStorage). Sandboxed iframe runs with unique origin and cannot access parent store.'
    );
  }
  if (/eval\(|new Function\(/i.test(content)) {
    findings.push('Dynamic evaluation detected (eval, new Function). Use with caution.');
  }
  return findings;
}

export default function HtmlConfigSection({
  widget,
  datasetOptions,
  updateWidget,
  onClose,
}: HtmlConfigSectionProps) {
  const findings = lintHtmlWidget(widget.content ?? '');

  return (
    <>
      <div
        style={{
          padding: '12px 14px',
          borderBottom: '1px solid #f0f0f0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div>
          <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#1a1a1a' }}>HTML widget</div>
          <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginTop: 2 }}>
            Write HTML/CSS to render custom UI
          </div>
        </div>
        <button
          type="button"
          className="btn-icon"
          onClick={onClose}
          style={{ background: 'none', border: 'none', cursor: 'pointer' }}
        >
          <X size={14} />
        </button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <FieldRow label="Title">
          <input
            value={widget.title ?? ''}
            onChange={(e) => updateWidget(widget.id, { title: e.target.value })}
            placeholder="Widget title"
            style={{
              width: '100%',
              padding: '5px 8px',
              fontSize: '0.77rem',
              border: '1px solid var(--color-border)',
              borderRadius: 4,
              background: 'var(--color-surface)',
              color: 'var(--color-text)',
            }}
          />
        </FieldRow>

        <FieldRow label="Dataset (optional)">
          <Select
            value={widget.htmlConfig?.datasetId ?? ''}
            onChange={(v) =>
              updateWidget(widget.id, {
                htmlConfig: { ...(widget.htmlConfig ?? {}), datasetId: v || undefined },
              })
            }
            options={datasetOptions}
            placeholder="Bind a dataset for data-driven HTML"
          />
        </FieldRow>

        {widget.htmlConfig?.datasetId && (
          <FieldRow label="Dataset Alias">
            <input
              value={widget.htmlConfig?.alias ?? ''}
              onChange={(e) =>
                updateWidget(widget.id, {
                  htmlConfig: { ...(widget.htmlConfig ?? {}), alias: e.target.value },
                })
              }
              placeholder="Alias used in JS (e.g. kpiData)"
              style={{
                width: '100%',
                padding: '5px 8px',
                fontSize: '0.77rem',
                border: '1px solid var(--color-border)',
                borderRadius: 4,
                background: 'var(--color-surface)',
                color: 'var(--color-text)',
              }}
            />
          </FieldRow>
        )}

        <FieldRow label="HTML / CSS / JS">
          <textarea
            value={widget.content ?? ''}
            onChange={(e) => updateWidget(widget.id, { content: e.target.value })}
            placeholder={`<div style="padding:16px">\n  <h3>My custom widget</h3>\n  <p>Build any HTML layout here.</p>\n</div>`}
            style={{
              width: '100%',
              minHeight: 280,
              resize: 'vertical',
              padding: '8px 10px',
              fontSize: '0.75rem',
              lineHeight: 1.5,
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
              border: '1px solid var(--color-border)',
              borderRadius: 6,
              background: 'var(--color-surface)',
              color: 'var(--color-text)',
            }}
          />
        </FieldRow>

        {/* Real-time Static Analysis / Lint Warnings */}
        {findings.length > 0 && (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 6,
              padding: 10,
              background: 'var(--color-danger-bg)',
              border: '1px solid var(--color-border)',
              borderRadius: 6,
            }}
          >
            <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--color-danger)' }}>
              Static Analysis Alerts
            </span>
            {findings.map((f, i) => (
              <div key={i} style={{ fontSize: '0.7rem', color: 'var(--color-danger)', lineHeight: 1.4 }}>
                ⚠️ {f}
              </div>
            ))}
          </div>
        )}

        <div
          style={{
            fontSize: '0.72rem',
            color: 'var(--color-text-muted)',
            lineHeight: 1.5,
            background: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: 6,
            padding: 10,
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 4 }}>Template tokens</div>
          <div>{'{{table}}'} inserts an auto-rendered data table.</div>
          <div>{'{{rowsJson}}'} inserts the dataset rows as JSON.</div>
          <div>{'{{columnsJson}}'} inserts the column list as JSON.</div>
          <div style={{ marginTop: 6 }}>JavaScript execution is enabled via sandboxed <code>platform</code> SDK.</div>
        </div>
      </div>
    </>
  );
}
