import React, { useState, useEffect, useRef } from "react";
import { createHighlighter, type Highlighter } from "shiki";
import { useFileContent, useWriteFile } from "../hooks/useFiles";

interface Props {
  appId: string;
  branchId: string;
  path: string;
}

// Global highlighter cache to avoid recreating it on every render
let globalHighlighter: Highlighter | null = null;
let highlighterPromise: Promise<Highlighter> | null = null;

function getHighlighter(): Promise<Highlighter> {
  if (globalHighlighter) {
    return Promise.resolve(globalHighlighter);
  }
  if (!highlighterPromise) {
    highlighterPromise = createHighlighter({
      themes: ["github-light", "github-dark"],
      langs: ["python", "javascript", "typescript", "json", "html", "css", "markdown"],
    }).then((hl) => {
      globalHighlighter = hl;
      return hl;
    });
  }
  return highlighterPromise;
}

function getLangFromPath(path: string): string {
  const ext = path.split(".").pop()?.toLowerCase();
  switch (ext) {
    case "py":
      return "python";
    case "js":
    case "jsx":
      return "javascript";
    case "ts":
    case "tsx":
      return "typescript";
    case "json":
      return "json";
    case "html":
    case "htm":
      return "html";
    case "css":
      return "css";
    case "md":
    case "markdown":
      return "markdown";
    default:
      return "text";
  }
}

/**
 * Text editor component using Shiki directly for syntax highlighting.
 * Uses a layered layout where the highlighted text (via Shiki) sits behind a transparent
 * editing textarea, ensuring 100% accurate token colors for Python, Javascript,
 * HTML, CSS, JSON, and Markdown.
 */
export default function MonacoEditor({ appId, branchId, path }: Props) {
  const { data, isLoading } = useFileContent(appId, branchId, path);
  const { mutate: writeFile } = useWriteFile(appId, branchId);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [code, setCode] = useState("");
  const [highlightedHtml, setHighlightedHtml] = useState("");
  const [highlighterReady, setHighlighterReady] = useState(false);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const preContainerRef = useRef<HTMLDivElement>(null);

  // Sync content when data loads
  useEffect(() => {
    if (data?.content !== undefined) {
      setCode(data.content);
    }
  }, [data]);

  // Load highlighter
  useEffect(() => {
    getHighlighter()
      .then(() => setHighlighterReady(true))
      .catch((err) => console.error("Shiki initialization failed:", err));
  }, []);

  const isDarkTheme = document.documentElement.getAttribute("data-theme") === "dark";
  const theme = isDarkTheme ? "github-dark" : "github-light";
  const lang = getLangFromPath(path);

  // Highlight code when code, language, theme, or highlighter readiness changes
  useEffect(() => {
    if (!highlighterReady || !globalHighlighter) {
      setHighlightedHtml(`<pre class="shiki" style="margin:0;padding:16px;font-family:monospace;font-size:14px;line-height:20px;"><code>${escapeHtml(code)}</code></pre>`);
      return;
    }

    try {
      const htmlContent = globalHighlighter.codeToHtml(code, {
        lang,
        theme,
      });
      setHighlightedHtml(htmlContent);
    } catch (err) {
      console.warn("Shiki highlight error, falling back to plaintext:", err);
      setHighlightedHtml(`<pre class="shiki" style="margin:0;padding:16px;font-family:monospace;font-size:14px;line-height:20px;"><code>${escapeHtml(code)}</code></pre>`);
    }
  }, [code, lang, theme, highlighterReady]);

  const handleChange = (val: string) => {
    setCode(val);

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      writeFile({ path, content: val });
    }, 1500);
  };

  const handleScroll = () => {
    if (textareaRef.current && preContainerRef.current) {
      const pre = preContainerRef.current.querySelector("pre");
      if (pre) {
        pre.scrollTop = textareaRef.current.scrollTop;
        pre.scrollLeft = textareaRef.current.scrollLeft;
      }
    }
  };

  useEffect(() => () => { if (debounceRef.current) clearTimeout(debounceRef.current); }, []);

  if (isLoading) {
    return (
      <div
        style={{
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--color-text-muted)",
          fontSize: "13px",
        }}
      >
        Loading {path}…
      </div>
    );
  }

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        background: "var(--color-surface)",
        overflow: "hidden",
      }}
    >
      {/* Syntax Highlighted Layer (behind) */}
      <div
        ref={preContainerRef}
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          pointerEvents: "none",
        }}
        dangerouslySetInnerHTML={{ __html: highlightedHtml }}
      />

      {/* Editing Layer (front) */}
      <textarea
        ref={textareaRef}
        key={path}
        id={`file-editor-${path.replace(/\//g, "-")}`}
        value={code}
        onChange={(e) => handleChange(e.target.value)}
        onScroll={handleScroll}
        spellCheck={false}
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          margin: 0,
          padding: "16px",
          background: "transparent",
          color: "transparent",
          caretColor: "var(--color-text)",
          border: "none",
          fontFamily: "monospace",
          fontSize: "14px",
          lineHeight: "20px",
          whiteSpace: "pre-wrap",
          wordBreak: "break-all",
          resize: "none",
          outline: "none",
          boxSizing: "border-box",
          overflow: "auto",
        }}
      />

      {/* Custom Styles to align Shiki output with Textarea */}
      <style>{`
        #editor-file-tree + div pre.shiki,
        .shiki {
          position: absolute !important;
          top: 0 !important;
          left: 0 !important;
          width: 100% !important;
          height: 100% !important;
          margin: 0 !important;
          padding: 16px !important;
          background: transparent !important;
          font-family: monospace !important;
          font-size: 14px !important;
          line-height: 20px !important;
          white-space: pre-wrap !important;
          word-break: break-all !important;
          box-sizing: border-box !important;
          overflow: hidden !important;
        }
      `}</style>
    </div>
  );
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
