/** Address of one portal screen inside an embedded app. */
export function moduleFrameSrc(base: string, modulePath?: string | null, origin = 'http://localhost'): string {
  const raw = (modulePath ?? '').trim();
  const hashAt = raw.indexOf('#');
  const beforeHash = hashAt >= 0 ? raw.slice(0, hashAt) : raw;
  const hash = hashAt >= 0 ? raw.slice(hashAt + 1) : '';
  const queryAt = beforeHash.indexOf('?');
  const pathOnly = queryAt >= 0 ? beforeHash.slice(0, queryAt) : beforeHash;
  const params = new URLSearchParams(queryAt >= 0 ? beforeHash.slice(queryAt + 1) : '');
  params.set('embed', '1');

  const absolute = /^[a-zA-Z][a-zA-Z\d+\-.]*:/.test(base);
  const baseUrl = new URL(base, origin);
  const basePath = baseUrl.pathname.endsWith('/') ? baseUrl.pathname : `${baseUrl.pathname}/`;
  const extra = pathOnly.replace(/^\/+/, '');
  baseUrl.pathname = `${basePath}${extra}`;
  params.forEach((value, key) => baseUrl.searchParams.set(key, value));
  baseUrl.hash = hash;

  if (absolute) return baseUrl.toString();
  return `${baseUrl.pathname}${baseUrl.search}${baseUrl.hash}`;
}

export function portalItemTo(item: { id: string; type: string; target_id: string; url?: string | null }): string {
  const query = `item=${encodeURIComponent(item.id)}`;
  if (item.type === 'app') return `/portal/app/${encodeURIComponent(item.target_id)}?${query}`;
  if (item.type === 'dashboard') return `/portal/dashboard/${encodeURIComponent(item.target_id)}?${query}`;
  return item.url || '/portal';
}

export function activePortalItem<T extends { id: string; type: string; target_id: string; is_visible: boolean }>(
  sections: { items: T[] }[] | undefined,
  itemId: string | null,
  targetId?: string,
  kind?: string,
): T | undefined {
  const items = sections?.flatMap((section) => section.items) ?? [];
  if (itemId) {
    const match = items.find((item) => item.id === itemId);
    if (match) return match;
  }
  if (!targetId || !kind) return undefined;
  return items.find((item) => item.is_visible && item.type === kind && item.target_id === targetId)
    ?? items.find((item) => item.type === kind && item.target_id === targetId);
}

export function portalTargetFromPath(pathname: string): { kind: 'app' | 'dashboard'; id: string } | undefined {
  const appMatch = pathname.match(/\/app\/([^/]+)/);
  if (appMatch) return { kind: 'app', id: decodeURIComponent(appMatch[1]) };
  const dashboardMatch = pathname.match(/\/dashboard\/([^/]+)/);
  if (dashboardMatch) return { kind: 'dashboard', id: decodeURIComponent(dashboardMatch[1]) };
  return undefined;
}
