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

      const currentToken = getToken() || config.token || '';
      if (slug && !urlStr.includes('workspace=')) {
        const sep = urlStr.includes('?') ? '&' : '?';
        urlStr = `${urlStr}${sep}workspace=${encodeURIComponent(slug)}`;
      }
      if (slug && !requestHeaders.has('X-Workspace-Slug')) {
        requestHeaders.set('X-Workspace-Slug', slug);
      }
      if (currentToken) {
        requestHeaders.set('Authorization', `Bearer ${currentToken}`);
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
      let href = typeof url === 'string' ? url : url.toString();
      const currentToken = getToken() || config.token || '';
      const currentSlug = config.workspaceSlug || '';
      try {
        const u = new URL(href);
        if (currentToken) {
          u.searchParams.set('token', currentToken);
        }
        if (currentSlug && !u.searchParams.has('workspace')) {
          u.searchParams.set('workspace', currentSlug);
        }
        href = u.toString();
      } catch {
        const sep = href.includes('?') ? '&' : '?';
        if (currentSlug && !href.includes('workspace=')) {
          href = `${href}${sep}workspace=${encodeURIComponent(currentSlug)}`;
        }
        if (currentToken && !href.includes('token=')) {
          const s = href.includes('?') ? '&' : '?';
          href = `${href}${s}token=${encodeURIComponent(currentToken)}`;
        }
      }
      super(href, protocols);
    }
  }
  return { ...settings, WebSocket: WorkspaceWebSocket as typeof WebSocket };
}

export function getManagers(config: JupyterConfig) {
  // Rebuild when the workspace, endpoint, or authentication token changes:
  // a manager cached with an old token would keep sending that expired credential.
  const currentToken = getToken() || config.token || '';
  const key = `${config.baseUrl}|${config.wsUrl}|${config.workspaceSlug}|${currentToken}`;
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
