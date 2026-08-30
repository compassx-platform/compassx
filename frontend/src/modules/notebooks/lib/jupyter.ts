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

  const settings = ServerConnection.makeSettings({
    baseUrl,
    wsUrl,
    token,
    appendToken: true,
  });

  // The workspace normally rides in the X-Workspace-Slug header, which a
  // WebSocket cannot send either, so it goes in the query string alongside the
  // token. WebSocket.__proto__ is not patchable, so wrap the socket factory
  // @jupyterlab/services uses.
  const slug = config.workspaceSlug;
  if (!slug) return settings;

  const BaseWebSocket = settings.WebSocket;
  class WorkspaceWebSocket extends BaseWebSocket {
    constructor(url: string | URL, protocols?: string | string[]) {
      const href = typeof url === 'string' ? url : url.toString();
      const sep = href.includes('?') ? '&' : '?';
      super(`${href}${sep}workspace=${encodeURIComponent(slug)}`, protocols);
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
