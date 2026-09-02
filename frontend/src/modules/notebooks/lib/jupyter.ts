import { ServerConnection, KernelManager } from '@jupyterlab/services';
import { getToken } from '@/lib/auth';

export interface JupyterConfig {
  baseUrl: string;
  wsUrl: string;
  token: string;
  workspaceSlug: string;
}

let _kernelManager: KernelManager | null = null;
let _settingsKey: string | null = null;

export function buildServerSettings(config: JupyterConfig) {
  // In K8s the backend returns a relative path (e.g. "/api/v1/notebook/jupyter")
  // because the Jupyter Server ClusterIP is not reachable from the browser.
  // @jupyterlab/services requires absolute URLs, so we prepend window.location.origin.
  const origin = window.location.origin;
  const baseUrl = config.baseUrl.startsWith('/')
    ? origin + config.baseUrl
    : config.baseUrl;
  // Derive wsUrl from baseUrl (http→ws, https→wss) when a relative path is given.
  const wsUrl = config.wsUrl.startsWith('/')
    ? origin.replace(/^http/, 'ws') + config.wsUrl
    : config.wsUrl;

  // The kernel proxy authorizes by user, so it needs the signed-in user's
  // token — not the deployment-wide Jupyter token, which identified nobody.
  // `appendToken` puts it in the query string, which is the only way to carry
  // a credential on a browser WebSocket (no custom headers are possible there).
  const token = config.token || getToken() || '';
  const slug = config.workspaceSlug || '';

  const settings = ServerConnection.makeSettings({
    baseUrl,
    wsUrl,
    token,
    appendToken: true,
    init: {
      headers: {
        ...(slug ? { 'X-Workspace-Slug': slug } : {}),
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      },
    },
    fetch: (input: RequestInfo | URL, init?: RequestInit) => {
      let urlStr: string;
      let requestHeaders: Headers;

      if (typeof input === 'string') {
        urlStr = input;
        requestHeaders = new Headers(init?.headers || {});
      } else if (input instanceof URL) {
        urlStr = input.toString();
        requestHeaders = new Headers(init?.headers || {});
      } else if (typeof Request !== 'undefined' && input instanceof Request) {
        urlStr = input.url;
        requestHeaders = new Headers(input.headers);
        if (init?.headers) {
          new Headers(init.headers).forEach((v, k) => requestHeaders.set(k, v));
        }
      } else if (typeof input === 'object' && input !== null && 'url' in (input as any)) {
        urlStr = (input as any).url;
        requestHeaders = new Headers((input as any).headers || init?.headers || {});
      } else {
        urlStr = String(input);
        requestHeaders = new Headers(init?.headers || {});
      }

      if (slug && !urlStr.includes('workspace=')) {
        const sep = urlStr.includes('?') ? '&' : '?';
        urlStr = `${urlStr}${sep}workspace=${encodeURIComponent(slug)}`;
      }
      if (slug && !requestHeaders.has('X-Workspace-Slug')) {
        requestHeaders.set('X-Workspace-Slug', slug);
      }
      if (token && !requestHeaders.has('Authorization')) {
        requestHeaders.set('Authorization', `Bearer ${token}`);
      }

      if (typeof Request !== 'undefined' && input instanceof Request) {
        return window.fetch(new Request(urlStr, { ...init, headers: requestHeaders }));
      }
      return window.fetch(urlStr, { ...init, headers: requestHeaders });
    },
  });

  const BaseWebSocket = settings.WebSocket;
  class WorkspaceWebSocket extends BaseWebSocket {
    constructor(url: string | URL, protocols?: string | string[]) {
      const href = typeof url === 'string' ? url : url.toString();
      const sep = href.includes('?') ? '&' : '?';
      const wsHref = slug && !href.includes('workspace=')
        ? `${href}${sep}workspace=${encodeURIComponent(slug)}`
        : href;
      super(wsHref, protocols);
    }
  }
  return { ...settings, WebSocket: WorkspaceWebSocket as typeof WebSocket };
}

export function getManagers(config: JupyterConfig) {
  // Rebuild when the workspace or endpoint changes: a manager cached from a
  // previous workspace would keep sending that workspace's slug.
  const key = `${config.baseUrl}|${config.wsUrl}|${config.workspaceSlug}`;
  if (_kernelManager && _settingsKey !== key) {
    resetManagers();
  }
  if (!_kernelManager) {
    const serverSettings = buildServerSettings(config);
    _kernelManager = new KernelManager({ serverSettings });
    _settingsKey = key;
  }
  return { kernelManager: _kernelManager };
}

export function resetManagers() {
  _kernelManager?.dispose();
  _kernelManager = null;
  _settingsKey = null;
}
