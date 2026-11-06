import navFile from "../content/nav.json";

export type NavItem = { title: string; slug: string };
export type NavSection = { title: string; items: NavItem[] };

export const sections = navFile.sections as NavSection[];

const rawPages = import.meta.glob("../content/**/*.md", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

export type Page = {
  slug: string;
  title: string;
  markdown: string;
  file: string;
};

function slugFromKey(key: string): string {
  const normalized = key.replace(/\\/g, "/");
  const match = normalized.match(/content\/(.+)\.md$/);
  if (!match) return "";
  const path = match[1];
  if (path === "index") return "";
  if (path.endsWith("/index")) return path.slice(0, -"/index".length);
  return path;
}

function fileFromKey(key: string): string {
  const normalized = key.replace(/\\/g, "/");
  const match = normalized.match(/(content\/.+\.md)$/);
  return match ? `architecture-site/${match[1]}` : normalized;
}

function titleFromMarkdown(markdown: string, fallback: string): string {
  const heading = markdown.match(/^#\s+(.+)$/m);
  return heading?.[1]?.trim() || fallback;
}

const pages = new Map<string, Page>();

for (const [key, markdown] of Object.entries(rawPages)) {
  const slug = slugFromKey(key);
  const navTitle = sections.flatMap((section) => section.items).find((item) => item.slug === slug)?.title;
  pages.set(slug, {
    slug,
    title: titleFromMarkdown(markdown, navTitle ?? "Untitled"),
    markdown,
    file: fileFromKey(key),
  });
}

export function getPage(slug: string): Page | undefined {
  return pages.get(slug);
}

export function allPages(): Page[] {
  return [...pages.values()];
}

export const flatNav: NavItem[] = sections.flatMap((section) => section.items);

export function neighbors(slug: string): { prev?: NavItem; next?: NavItem } {
  const index = flatNav.findIndex((item) => item.slug === slug);
  if (index < 0) return {};
  return {
    prev: index > 0 ? flatNav[index - 1] : undefined,
    next: index < flatNav.length - 1 ? flatNav[index + 1] : undefined,
  };
}

export function hrefFor(slug: string): string {
  return slug ? `/${slug}` : "/";
}

export function resolveMarkdownHref(currentSlug: string, href: string): string {
  if (!href || href.startsWith("http://") || href.startsWith("https://") || href.startsWith("mailto:")) {
    return href;
  }
  const [pathPart, hash] = href.split("#");
  if (!pathPart.endsWith(".md") && !pathPart.startsWith(".")) {
    return href;
  }
  const current = getPage(currentSlug);
  const isFolder = Boolean(current?.file.endsWith("/index.md") && currentSlug);
  const baseParts = currentSlug ? currentSlug.split("/") : [];
  if (!isFolder) baseParts.pop();
  const relative = pathPart.replace(/\.md$/, "").replace(/\/index$/, "");
  const parts = [...baseParts];
  for (const segment of relative.split("/")) {
    if (!segment || segment === "." || segment === "index") continue;
    if (segment === "..") parts.pop();
    else parts.push(segment);
  }
  const slug = parts.filter(Boolean).join("/");
  const next = hrefFor(slug);
  return hash ? `${next}#${hash}` : next;
}

export function headingId(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/[`*_]/g, "")
    .replace(/[^\w\s-]/g, "")
    .replace(/\s+/g, "-");
}
