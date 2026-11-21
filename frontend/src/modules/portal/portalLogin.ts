/** Sign-in address for someone who opened a workspace portal while signed out. */

export function portalWorkspaceFromPath(pathname: string): string | null {
  const match = pathname.match(/^\/w\/([^/]+)\/portal(?:\/|$)/);
  if (!match) return null;
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return match[1];
  }
}

export function portalLoginPath(pathname: string, search = ""): string | null {
  const slug = portalWorkspaceFromPath(pathname);
  if (!slug) return null;
  const next = `${pathname}${search}`;
  return `/login/portal/${encodeURIComponent(slug)}?next=${encodeURIComponent(next)}`;
}

export function portalHomeAfterLogin(slug: string, next: string | null): string {
  const home = `/w/${slug}/portal`;
  if (!next || !next.startsWith("/") || next.startsWith("//")) return home;
  const path = next.split("?")[0];
  if (path === home || path.startsWith(`${home}/`)) return next;
  return home;
}
