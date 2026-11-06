import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  allPages,
  flatNav,
  getPage,
  headingId,
  hrefFor,
  neighbors,
  resolveMarkdownHref,
  sections,
  type NavSection,
  type Page,
} from "./content";

export function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const slug = location.pathname.replace(/^\/+|\/+$/g, "");
  const page = getPage(slug);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const activeSection = sections.find((section) => section.items.some((item) => item.slug === slug))?.title;
  const [openSections, setOpenSections] = useState<string[]>(() => (activeSection ? [activeSection] : []));
  const [theme, setTheme] = useState(document.documentElement.dataset.theme ?? "light");

  useEffect(() => {
    setMenuOpen(false);
    setOpen(false);
    document.title = page ? `${page.title} | CompassX Architecture` : "CompassX Architecture";
  }, [location.pathname, page]);

  useEffect(() => {
    if (!activeSection) return;
    setOpenSections((current) => (current.includes(activeSection) ? current : [...current, activeSection]));
  }, [activeSection]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen(true);
      } else if (event.key === "/" && document.activeElement?.tagName !== "INPUT") {
        event.preventDefault();
        setOpen(true);
      } else if (event.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const results = useMemo(() => search(query), [query]);
  return (
    <>
      <header className="topbar">
        <Link className="brand" to="/">
          <svg className="brand-mark" width="22" height="22" viewBox="0 0 24 24" aria-hidden="true">
            <path fill="currentColor" d="M13.2 2.4 4.6 13.2h6.1L10.2 21.6l9.2-11.4h-6.2L13.2 2.4Z" />
          </svg>
          <span>compassx</span>
          <span className="brand-docs">ARCHITECTURE</span>
        </Link>
        <div className="top-actions">
          <button className="search-button" onClick={() => setOpen(true)} aria-label="Search">
            <span>Search</span>
            <kbd>Ctrl K</kbd>
          </button>
          <button
            className="icon-button"
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            onClick={() => {
              const next = theme === "dark" ? "light" : "dark";
              setTheme(next);
              document.documentElement.dataset.theme = next;
              localStorage.setItem("cx-arch-theme", next);
            }}
          >
            {theme === "dark" ? "☀" : "☾"}
          </button>
          <button className="icon-button menu-button" aria-label="Open menu" onClick={() => setMenuOpen((value) => !value)}>
            ☰
          </button>
        </div>
      </header>

      <div className="shell">
        <aside className={menuOpen ? "sidebar open" : "sidebar"}>
          {sections.map((section) => (
            <NavGroup
              key={section.title}
              section={section}
              slug={slug}
              open={openSections.includes(section.title)}
              onToggle={() =>
                setOpenSections((current) =>
                  current.includes(section.title)
                    ? current.filter((title) => title !== section.title)
                    : [...current, section.title],
                )
              }
            />
          ))}
        </aside>

        <main className="article">
          {page ? (
            <Article page={page} />
          ) : (
            <div className="empty">
              <h1>Page not found</h1>
              <p>That path is not in the architecture content.</p>
            </div>
          )}
        </main>

        <aside className="toc">
          {page ? <Toc markdown={page.markdown} /> : null}
        </aside>
      </div>

      {open ? (
        <div className="search-backdrop" onClick={() => setOpen(false)}>
          <div className="search-panel" role="dialog" aria-label="Search" onClick={(event) => event.stopPropagation()}>
            <input
              autoFocus
              placeholder="Search architecture"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setActive(0);
              }}
              onKeyDown={(event) => {
                if (event.key === "ArrowDown") {
                  event.preventDefault();
                  setActive((value) => Math.min(value + 1, Math.max(results.length - 1, 0)));
                } else if (event.key === "ArrowUp") {
                  event.preventDefault();
                  setActive((value) => Math.max(value - 1, 0));
                } else if (event.key === "Enter" && results[active]) {
                  navigate(hrefFor(results[active].slug));
                  setOpen(false);
                }
              }}
            />
            <div className="search-results">
              {results.length === 0 ? <p className="source-path">No matching pages.</p> : null}
              {results.map((result, index) => (
                <button
                  key={result.slug || "home"}
                  className={index === active ? "active" : ""}
                  onMouseEnter={() => setActive(index)}
                  onClick={() => navigate(hrefFor(result.slug))}
                >
                  {result.title}
                  <small>{result.file}</small>
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

function NavGroup({
  section,
  slug,
  open,
  onToggle,
}: {
  section: NavSection;
  slug: string;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="nav-group">
      <button className="nav-section" type="button" aria-expanded={open} onClick={onToggle}>
        <span>{section.title}</span>
        <svg className={open ? "chevron open" : "chevron"} width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
          <path d="M6 4l4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open ? (
        <div className="nav-pages">
          {section.items.length === 0 ? <p className="nav-pending">Pending</p> : null}
          {section.items.map((item) => (
            <Link
              key={item.slug || "home"}
              to={hrefFor(item.slug)}
              className={item.slug === slug ? "nav-link active" : "nav-link"}
            >
              {item.title}
            </Link>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function Article({ page }: { page: Page }) {
  const adjacent = neighbors(page.slug);
  return (
    <>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => {
            const next = href ? resolveMarkdownHref(page.slug, href) : "";
            if (next.startsWith("/")) return <Link to={next}>{children}</Link>;
            return <a href={next}>{children}</a>;
          },
          h2: ({ children }) => <h2 id={headingId(textOf(children))}>{children}</h2>,
          h3: ({ children }) => <h3 id={headingId(textOf(children))}>{children}</h3>,
        }}
      >
        {page.markdown}
      </ReactMarkdown>
      <nav className="pager" aria-label="Adjacent pages">
        {adjacent.prev ? (
          <Link to={hrefFor(adjacent.prev.slug)}>
            <small>Previous</small>
            {adjacent.prev.title}
          </Link>
        ) : <span />}
        {adjacent.next ? (
          <Link className="next" to={hrefFor(adjacent.next.slug)}>
            <small>Next</small>
            {adjacent.next.title}
          </Link>
        ) : <span />}
      </nav>
      <p className="source-path">
        Source <code>{page.file}</code>
      </p>
    </>
  );
}

function Toc({ markdown }: { markdown: string }) {
  const headings = extractHeadings(markdown);
  if (headings.length === 0) return null;
  return (
    <>
      <div className="toc-label">On this page</div>
      {headings.map((heading) => (
        <a key={heading.id} className={heading.depth === 3 ? "depth-3" : ""} href={`#${heading.id}`}>
          {heading.text}
        </a>
      ))}
    </>
  );
}

function extractHeadings(markdown: string): { depth: number; text: string; id: string }[] {
  return markdown
    .split("\n")
    .map((line) => {
      const match = /^(#{2,3})\s+(.+)$/.exec(line.trim());
      if (!match) return undefined;
      const text = match[2].replace(/\[(.*?)\]\(.*?\)/g, "$1");
      return { depth: match[1].length, text, id: headingId(text) };
    })
    .filter((item): item is { depth: number; text: string; id: string } => Boolean(item));
}

function textOf(children: ReactNode): string {
  if (typeof children === "string" || typeof children === "number") return String(children);
  if (Array.isArray(children)) return children.map((child) => textOf(child)).join("");
  if (children && typeof children === "object" && "props" in children) {
    const element = children as { props?: { children?: React.ReactNode } };
    return textOf(element.props?.children);
  }
  return "";
}

function search(query: string): Page[] {
  const needle = query.trim().toLowerCase();
  const pages = allPages();
  const ordered = flatNav
    .map((item) => pages.find((page) => page.slug === item.slug))
    .filter((page): page is Page => Boolean(page));
  if (!needle) return ordered.slice(0, 8);
  return ordered
    .filter((page) => `${page.title}\n${page.markdown}`.toLowerCase().includes(needle))
    .slice(0, 12);
}
