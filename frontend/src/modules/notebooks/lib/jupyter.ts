import { ServerConnection, KernelManager } from '@jupyterlab/services';

export interface JupyterConfig {
  baseUrl: string;
  wsUrl: string;
  token: string;
}

let _kernelManager: KernelManager | null = null;

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
  return ServerConnection.makeSettings({
    baseUrl,
    wsUrl,
    token: config.token,
    appendToken: true,
  });
}

export function getManagers(config: JupyterConfig) {
  if (!_kernelManager) {
    const serverSettings = buildServerSettings(config);
    _kernelManager = new KernelManager({ serverSettings });
  }
  return { kernelManager: _kernelManager };
}

export function resetManagers() {
  _kernelManager = null;
}
