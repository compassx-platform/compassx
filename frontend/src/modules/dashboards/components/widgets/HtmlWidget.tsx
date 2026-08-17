/**
 * HtmlWidget — reusable custom HTML widget for dashboards.
 * Authors can enter HTML/CSS/JS in the widget settings and render custom UI.
 * Runs in a sandboxed iframe with CSP headers to ensure security.
 */

import { useEffect, useMemo, useRef } from 'react';
import { useDashboardStore } from '@/modules/dashboards/stores/dashboardStore';
import { useDatasetQuery } from '@/modules/dashboards/hooks/useDashboard';
import type { Widget } from '@/types/dashboard';

interface Props {
  widget: Widget;
}

function normalizeHtml(html?: string): string {
  return (html ?? '').trim();
}

function escapeHtml(text: unknown): string {
  return String(text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function toCamelCase(str: string): string {
  return str
    .replace(/(?:^\w|[A-Z]|\b\w)/g, (word, index) => index === 0 ? word.toLowerCase() : word.toUpperCase())
    .replace(/\s+/g, '');
}

function buildTable(columns: string[], rows: Record<string, unknown>[]): string {
  const head = columns.map((c) => `<th style="text-align:left;padding:8px 10px;border-bottom:1px solid #e5e7eb;color:#64748b;white-space:nowrap;">${escapeHtml(c)}</th>`).join('');
  const body = rows.slice(0, 200).map((row) => {
    const cells = columns.map((c) => `<td style="padding:8px 10px;border-bottom:1px solid #f1f5f9;white-space:nowrap;max-width:220px;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(row[c] ?? '')}</td>`).join('');
    return `<tr>${cells}</tr>`;
  }).join('');
  return `<div style="overflow:auto;"><table style="width:100%;border-collapse:collapse;font-size:12px;background:#fff;"><thead><tr style="background:#f8fafc;">${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

const platformSdk = `
(function () {
  const _datasets = window.__INITIAL_DATASETS__ || {};
  const _listeners = [];
  let _ready = false;

  window.platform = {
    version: "1.0",

    // Synchronous read — works immediately on first paint using embedded data
    getData(alias) {
      return _datasets[alias] ?? null;
    },

    // Subscribe to both the initial load and every subsequent refresh
    onData(callback) {
      _listeners.push(callback);
      if (Object.keys(_datasets).length) callback(_datasets); // fire immediately if data already present
    },

    // For datasets too large to embed: async pull from host
    async query(alias, { limit = 500, offset = 0 } = {}) {
      const requestId = typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 15);
      return new Promise((resolve, reject) => {
        function handler(e) {
          if (e.data?.type === "QUERY_RESPONSE" && e.data.requestId === requestId) {
            window.removeEventListener("message", handler);
            e.data.error ? reject(new Error(e.data.error)) : resolve(e.data.result);
          }
        }
        window.addEventListener("message", handler);
        window.parent.postMessage({ type: "QUERY_REQUEST", requestId, alias, limit, offset }, "*");
      });
    },

    // Tell the host the widget has finished its first meaningful render
    ready() {
      if (_ready) return;
      _ready = true;
      window.parent.postMessage({ type: "WIDGET_READY" }, "*");
    }
  };

  window.addEventListener("message", (e) => {
    if (e.data?.type === "DATA_UPDATE") {
      Object.assign(_datasets, e.data.datasets);
      _listeners.forEach((cb) => cb(_datasets));
    }
  });

  window.addEventListener("error", (e) => {
    window.parent.postMessage({ type: "WIDGET_ERROR", message: e.message, stack: e.error?.stack || null }, "*");
  });
})();
`;

function buildSrcDoc(html: string, initialDatasets: Record<string, unknown>) {
  const injectedData = JSON.stringify(initialDatasets).replace(/</g, '\\u003c');

  return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta http-equiv="Content-Security-Policy" content="connect-src 'none'; frame-src 'none'; form-action 'none';" />
    <style>
      html, body { margin: 0; padding: 0; width: 100%; min-height: 100%; }
      body { font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
      * { box-sizing: border-box; }
    </style>
    <script>
      window.__INITIAL_DATASETS__ = ${injectedData};
    </script>
    <script>
      ${platformSdk}
    </script>
  </head>
  <body>
    ${html}
  </body>
</html>`;
}

export default function HtmlWidget({ widget }: Props) {
  const { filterState, paramState, activeDashboard } = useDashboardStore();
  const cfg = widget.htmlConfig;
  const { data: queryResult, isLoading } = useDatasetQuery(cfg?.datasetId, paramState as any, filterState as any, !!cfg?.datasetId);

  const iframeRef = useRef<HTMLIFrameElement>(null);

  const rawHtml = normalizeHtml(widget.content);
  const columns = queryResult?.columns ?? [];
  const rows = queryResult?.rows ?? [];

  const dataset = activeDashboard?.datasets.find((d) => d.id === cfg?.datasetId);
  const datasetName = dataset?.name;

  const html = useMemo(() => {
    if (!rawHtml) return '';
    const tableHtml = buildTable(columns, rows);
    return rawHtml
      .replace(/\{\{\s*table\s*\}\}/g, tableHtml)
      .replace(/\{\{\s*rowsJson\s*\}\}/g, escapeHtml(JSON.stringify(rows, null, 2)))
      .replace(/\{\{\s*columnsJson\s*\}\}/g, escapeHtml(JSON.stringify(columns, null, 2)))
      .replace(/\{\{\s*rowCount\s*\}\}/g, escapeHtml(rows.length))
      .replace(/\{\{\s*columnCount\s*\}\}/g, escapeHtml(columns.length));
  }, [rawHtml, columns, rows]);

  // Construct initial datasets object with 'default', camelCase dataset name, and custom alias
  const initialDatasets = useMemo(() => {
    const payload = {
      schema: columns.map(c => ({ name: c, type: 'string', nullable: true })),
      rows,
      rowCount: rows.length,
      truncated: false,
    };
    const datasets: Record<string, unknown> = {
      default: payload,
    };
    if (datasetName) {
      datasets[toCamelCase(datasetName)] = payload;
    }
    if (cfg?.alias) {
      datasets[cfg.alias] = payload;
    }
    return datasets;
  }, [columns, rows, datasetName, cfg?.alias]);

  const srcDoc = useMemo(() => buildSrcDoc(html, initialDatasets), [html, initialDatasets]);

  // Live Refresh: Send postMessage data updates when dataset queryResult refreshes
  useEffect(() => {
    if (iframeRef.current && queryResult) {
      const payload = {
        schema: queryResult.columns.map(c => ({ name: c, type: 'string', nullable: true })),
        rows: queryResult.rows,
        rowCount: queryResult.rowCount,
        truncated: false,
      };
      const datasets: Record<string, unknown> = {
        default: payload,
      };
      if (datasetName) {
        datasets[toCamelCase(datasetName)] = payload;
      }
      if (cfg?.alias) {
        datasets[cfg.alias] = payload;
      }

      iframeRef.current.contentWindow?.postMessage(
        { type: 'DATA_UPDATE', datasets },
        '*'
      );
    }
  }, [queryResult, datasetName, cfg?.alias]);

  // Handle postMessages from iframe
  useEffect(() => {
    function handleMessage(e: MessageEvent) {
      if (iframeRef.current && e.source === iframeRef.current.contentWindow) {
        if (e.data?.type === 'WIDGET_READY') {
          console.log(`[Widget Ready] ${widget.title || widget.id}`);
        } else if (e.data?.type === 'WIDGET_ERROR') {
          console.error(`[Widget Error] ${widget.title || widget.id}: ${e.data.message}`, e.data.stack);
        } else if (e.data?.type === 'QUERY_REQUEST') {
          const alias = cfg?.alias || (datasetName ? toCamelCase(datasetName) : 'default');
          const isMatch = e.data.alias === 'default' || 
                          e.data.alias === alias || 
                          (cfg?.alias && e.data.alias === cfg.alias) ||
                          (datasetName && e.data.alias === toCamelCase(datasetName));

          if (isMatch) {
            iframeRef.current.contentWindow?.postMessage({
              type: 'QUERY_RESPONSE',
              requestId: e.data.requestId,
              result: {
                schema: queryResult?.columns.map(c => ({ name: c, type: 'string', nullable: true })) || [],
                rows: queryResult?.rows || [],
                rowCount: queryResult?.rowCount || 0,
                truncated: false,
              }
            }, '*');
          } else {
            iframeRef.current.contentWindow?.postMessage({
              type: 'QUERY_RESPONSE',
              requestId: e.data.requestId,
              error: `Dataset alias "${e.data.alias}" not found`
            }, '*');
          }
        }
      }
    }

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [widget.id, queryResult, datasetName, cfg?.alias]);


  if (isLoading) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 18, color: 'var(--color-text-muted)' }}>
        Loading data…
      </div>
    );
  }

  if (!rawHtml) {
    return (
      <div style={{
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 18,
        color: 'var(--color-text-muted)',
        textAlign: 'center',
      }}>
        <div>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--color-text)', marginBottom: 6 }}>
            Empty HTML widget
          </div>
          <div style={{ fontSize: 12, lineHeight: 1.5, maxWidth: 280 }}>
            Open the widget settings and write HTML/CSS/JS to build a reusable custom UI.
          </div>
        </div>
      </div>
    );
  }

  return (
    <iframe
      ref={iframeRef}
      title={widget.title || 'HTML widget'}
      srcDoc={srcDoc}
      sandbox="allow-scripts"
      style={{
        width: '100%',
        height: '100%',
        border: 'none',
        display: 'block',
        background: 'var(--color-surface)',
      }}
    />
  );
}
