/**
 * AgentChatPage — SSE streaming chat with markdown rendering and Vega-Lite charts.
 * Supports multi-agent swarm: subagent messages are rendered with a colour-coded
 * agent badge so the user can see which agent produced each response.
 */
import { useState, useRef, useEffect, useCallback } from "react";
import { useParams } from "react-router-dom";
import { useScopedNavigate } from "@/lib/appNavigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { VegaEmbed } from "react-vega";
import {
  Send,
  Plus,
  Trash2,
  Bot,
  User,
  Loader2,
  Settings2,
  Zap,
  AlertCircle,
  ChevronDown,
  ChevronRight,
  MessageSquare,
  GitBranch,
  Sparkles,
  MoreVertical,
  ArrowRight,
} from "lucide-react";
import {
  useChatSessions,
  useChatMessages,
  useCreateSession,
  useDeleteSession,
  type ChatSession,
} from "@/modules/agents/hooks/useChat";
import { useAgent } from "@/modules/agents/hooks/useAgents";
import { useResearchEngineRuns, useTriggerResearchEngineRun } from "@/modules/agents/hooks/useResearchEngine";
import { useLLMConnections } from "@/modules/agents/hooks/useLLMConnections";
import { useChatStore } from "@/modules/agents/stores/chatStore";
import { useToast } from "@/lib/toast";
import { useQueryClient } from "@tanstack/react-query";
import { getAuthKey } from "@/lib/auth";
import api from "@/lib/api";
import { PlanTaskViewer } from "@/modules/agents/components/PlanTaskViewer";
import { AssetChip, parseAssetTags } from "@/modules/agents/components/AssetChip";
import { DiffSummaryCard, ChangeRecord } from "@/modules/agents/components/DiffSummaryCard";
import { DiffSheet } from "@/modules/agents/components/DiffSheet";
import { Paperclip, X as XIcon } from "lucide-react";

// ── Vega-Lite chart renderer ──────────────────────────────────────────────────

function ChartBlock({ spec }: { spec: unknown }) {
  try {
    return (
      <div style={{ margin: "8px 0", overflowX: "auto" }}>
        <VegaEmbed
          spec={spec as Parameters<typeof VegaEmbed>[0]["spec"]}
          options={{ actions: false }}
          style={{ background: "transparent" }}
        />
      </div>
    );
  } catch {
    return <pre>{JSON.stringify(spec, null, 2)}</pre>;
  }
}

// ── Agent badge ───────────────────────────────────────────────────────────────

function AgentBadge({
  name,
  color,
  depth = 0,
  size = "sm",
}: {
  name: string;
  color?: string | null;
  depth?: number;
  size?: "sm" | "xs";
}) {
  const bg = color ?? "#6366f1";
  const fontSize = size === "xs" ? "0.62rem" : "0.68rem";
  const padding = size === "xs" ? "1px 5px" : "2px 7px";
  return (
    <span
      title={`Invocation depth: ${depth}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        background: `${bg}22`,
        border: `1px solid ${bg}55`,
        color: bg,
        borderRadius: 99,
        fontSize,
        fontWeight: 600,
        padding,
        letterSpacing: "0.01em",
        flexShrink: 0,
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: bg,
          display: "inline-block",
          flexShrink: 0,
        }}
      />
      {name}
      {depth > 0 && (
        <span style={{ opacity: 0.6, fontSize: "0.58rem" }}>·{depth}</span>
      )}
    </span>
  );
}

// ── Agent handoff card (🔀 system message) ────────────────────────────────────

function HandoffCard({ toolResult }: { toolResult?: Record<string, unknown> | null }) {
  const content = (toolResult?.content as string) ?? "";
  const meta = toolResult?.metadata as Record<string, unknown> | undefined;
  const invokedAgent = meta?.invoked_agent as string | undefined;
  const invokedBy = meta?.invoked_by as string | undefined;
  const task = meta?.task as string | undefined;

  return (
    <div
      style={{
        margin: "4px 0 12px",
        padding: "8px 12px",
        border: "1px dashed var(--color-border)",
        borderRadius: 8,
        background: "var(--color-surface-hover)",
        display: "flex",
        alignItems: "flex-start",
        gap: 8,
        fontSize: "0.78rem",
        color: "var(--color-text-muted)",
      }}
    >
      <GitBranch size={13} style={{ marginTop: 1, flexShrink: 0, opacity: 0.7 }} />
      <div>
        <div style={{ fontWeight: 500, color: "var(--color-text)" }}>{content || "Agent handoff"}</div>
        {invokedBy && invokedAgent && (
          <div style={{ marginTop: 2 }}>
            <span>{invokedBy}</span>
            <span style={{ margin: "0 4px", opacity: 0.5 }}>→</span>
            <span style={{ fontWeight: 500, color: "var(--color-text)" }}>{invokedAgent}</span>
          </div>
        )}
        {task && (
          <div style={{ marginTop: 3, fontStyle: "italic", opacity: 0.75 }}>
            "{task.slice(0, 120)}{task.length > 120 ? "…" : ""}"
          </div>
        )}
      </div>
    </div>
  );
}

// ── Tool execution card ───────────────────────────────────────────────────────

function ToolCard({
  toolName,
  toolResult,
}: {
  toolName: string;
  toolResult?: Record<string, unknown> | null;
}) {
  if (toolName === "invoke_agent" && toolResult?.source === "system") {
    return <HandoffCard toolResult={toolResult} />;
  }

  const args = toolResult?.args as Record<string, unknown> | undefined;
  const ok = toolResult?.ok !== false;
  const [open, setOpen] = useState(false);

  // Format arguments summary (e.g. query/file/asset)
  const argSummary = args
    ? (args.query ?? args.filename ?? args.path ?? args.name ?? args.asset_id ?? args.prompt ?? "")
    : "";

  return (
    <div style={{ margin: "3px 0 3px 0", color: "#6b7280", fontSize: "0.82rem" }}>
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          cursor: "pointer",
          userSelect: "none",
        }}
        onClick={() => setOpen((o) => !o)}
      >
        <span style={{ display: "inline-flex", alignItems: "center" }}>
          {open ? <ChevronDown size={12} color="#6b7280" /> : <ChevronRight size={12} color="#6b7280" />}
        </span>
        <span>
          {toolName} {argSummary ? <span style={{ opacity: 0.85 }}>({String(argSummary)})</span> : null}
        </span>
      </div>
      {open && (
        <div style={{ marginTop: 6, paddingLeft: 18, fontSize: "0.75rem", fontFamily: "monospace", color: "#4b5563" }}>
          <div style={{ borderTop: "1px solid #e5e7eb", paddingTop: 6, marginTop: 4 }}>
            {args && Object.keys(args).length > 0 && (
              <div style={{ marginBottom: 6 }}>
                <div style={{ fontWeight: 600, fontSize: "0.7rem", color: "#9ca3af", textTransform: "uppercase", marginBottom: 2 }}>Input</div>
                <pre style={{ margin: 0, overflowX: "auto", background: "rgba(0,0,0,0.03)", padding: "4px 8px", borderRadius: 4 }}>
                  {JSON.stringify(args, null, 2)}
                </pre>
              </div>
            )}
            {toolResult?.result != null && (
              <div style={{ marginTop: args && Object.keys(args).length > 0 ? 6 : 0 }}>
                <div style={{ borderTop: args && Object.keys(args).length > 0 ? "1px dashed #e5e7eb" : "none", paddingTop: args && Object.keys(args).length > 0 ? 6 : 0, marginBottom: 2, fontWeight: 600, fontSize: "0.7rem", color: "#9ca3af", textTransform: "uppercase" }}>Result</div>
                <pre style={{ margin: 0, overflowX: "auto", background: "rgba(0,0,0,0.03)", padding: "4px 8px", borderRadius: 4 }}>
                  {JSON.stringify(toolResult.result, null, 2)}
                </pre>
              </div>
            )}
            {toolResult?.error && (
              <div style={{ marginTop: 6 }}>
                <div style={{ fontWeight: 600, fontSize: "0.7rem", color: "#ef4444", textTransform: "uppercase", marginBottom: 2 }}>Error</div>
                <pre style={{ margin: 0, overflowX: "auto", background: "rgba(239,68,68,0.08)", color: "#dc2626", padding: "4px 8px", borderRadius: 4 }}>
                  {String(toolResult.error)}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Message bubble ────────────────────────────────────────────────────────────

// ── Thought / Reasoning Parser & Accordion ───────────────────────────────────

interface ParsedContent {
  thought: string | null;
  response: string;
}

function parseThoughtContent(rawContent: string | null): ParsedContent {
  if (!rawContent) return { thought: null, response: "" };

  let text = rawContent.trim();
  let thought: string | null = null;

  // 1. Check for XML tags: <thought>...</thought> or <thinking>...</thinking>
  const tagMatch = text.match(/<(?:thought|thinking)>([\s\S]*?)<\/(?:thought|thinking)>/i);
  if (tagMatch) {
    thought = tagMatch[1].trim();
    text = text.replace(/<(?:thought|thinking)>[\s\S]*?<\/(?:thought|thinking)>/gi, "").trim();
    return { thought: thought || null, response: text };
  }

  // 2. Check for ReAct Markdown patterns: "Thought: ...", "**Thought:** ...", "### Thought ..."
  const thoughtHeaderMatch = text.match(/^(?:(?:\*{0,2}|#{1,4}\s*)Thought:?\*{0,2}|Reasoning:?)\s*([\s\S]*?)(?=(?:\n\s*(?:\*{0,2}|#{1,4}\s*)Action:?|\n\s*(?:\*{0,2}|#{1,4}\s*)Final Answer:?|\n\n[A-Z0-9])|$)/i);
  if (thoughtHeaderMatch) {
    const captured = thoughtHeaderMatch[1].trim();
    const actionIndex = text.search(/\n\s*(?:\*{0,2}|#{1,4}\s*)Action:?/i);
    const finalAnswerMatch = text.match(/\n\s*(?:\*{0,2}|#{1,4}\s*)Final Answer:?\s*([\s\S]*)/i);

    if (finalAnswerMatch) {
      thought = captured.replace(/(?:\*{0,2}|#{1,4}\s*)Action:?[\s\S]*/i, "").trim();
      text = finalAnswerMatch[1].trim();
    } else if (actionIndex !== -1) {
      thought = captured.replace(/(?:\*{0,2}|#{1,4}\s*)Action:?[\s\S]*/i, "").trim();
      text = "";
    } else {
      const parts = text.split(/\n{2,}/);
      if (parts.length > 1 && parts[0].toLowerCase().includes("thought")) {
        thought = parts[0].replace(/^(?:\*{0,2}|#{1,4}\s*)Thought:?\*{0,2}\s*/i, "").trim();
        text = parts.slice(1).join("\n\n").trim();
      } else {
        thought = text.replace(/^(?:\*{0,2}|#{1,4}\s*)Thought:?\*{0,2}\s*/i, "").trim();
        text = "";
      }
    }
    return { thought: thought || null, response: text };
  }

  return { thought: null, response: text };
}

function ThoughtAccordion({ thought, isStreaming = false }: { thought: string; isStreaming?: boolean }) {
  const [open, setOpen] = useState(false);

  // Split thought into separate items if multiple lines / paragraphs / bullet points exist
  const rawItems = thought
    .split(/\n+/)
    .map((item) => item.trim().replace(/^[-*•]\s*/, ""))
    .filter((item) => item.length > 0);

  const headerText = isStreaming ? "Thinking..." : "Thinking";

  return (
    <div
      style={{
        margin: "0 0 12px 0",
        fontSize: "0.85rem",
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 4,
          padding: 0,
          background: "transparent",
          border: "none",
          cursor: "pointer",
          color: "var(--color-text, #111827)",
          fontWeight: 600,
          fontSize: "0.85rem",
          textAlign: "left",
          lineHeight: 1.2,
        }}
      >
        <span style={{ display: "inline-flex", alignItems: "center" }}>
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>
        <span>{headerText}</span>
      </button>

      {open && (
        <div
          style={{
            marginTop: 8,
            paddingLeft: 4,
            color: "#6b7280", // gray color for thoughts
            lineHeight: 1.5,
            fontSize: "0.83rem",
          }}
        >
          <ul style={{ margin: 0, paddingLeft: 18, listStyleType: "disc" }}>
            {rawItems.map((item, idx) => (
              <li key={idx} style={{ marginBottom: 6 }}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{item}</ReactMarkdown>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ── Sequence step items for timeline execution order ──
export type TimelineStep =
  | { type: "thought"; text: string }
  | { type: "tool"; name: string; result: any };

function ConsolidatedThoughtBlock({
  steps = [],
  isStreaming = false,
  activeTool,
  activeToolArgs,
}: {
  steps?: TimelineStep[];
  isStreaming?: boolean;
  activeTool?: string | null;
  activeToolArgs?: any;
}) {
  const [open, setOpen] = useState(false);

  const headerText = isStreaming ? "Thinking..." : "Thinking";

  return (
    <div style={{ margin: "0 0 12px 0", fontSize: "0.85rem", position: "relative" }}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          padding: 0,
          background: "transparent",
          border: "none",
          cursor: "pointer",
          color: "#6b7280",
          fontWeight: 600,
          fontSize: "0.83rem",
          textAlign: "left",
          lineHeight: 1.2,
          position: "relative",
        }}
      >
        <span
          style={{
            position: "absolute",
            left: -18,
            top: "50%",
            transform: "translateY(-50%)",
            display: "inline-flex",
            alignItems: "center",
          }}
        >
          {open ? <ChevronDown size={14} color="#6b7280" /> : <ChevronRight size={14} color="#6b7280" />}
        </span>
        <span>{headerText}</span>
      </button>

      {open && (
        <div
          style={{
            marginTop: 10,
            paddingLeft: 0,
            color: "#6b7280",
            lineHeight: 1.5,
            fontSize: "0.83rem",
            position: "relative",
          }}
        >
          {/* Timeline connector line aligned under chevron */}
          <div
            style={{
              position: "absolute",
              top: 8,
              bottom: 8,
              left: -12,
              width: 1.5,
              background: "#e5e7eb",
              zIndex: 0,
            }}
          />

          <div style={{ display: "flex", flexDirection: "column", gap: 10, position: "relative", zIndex: 1 }}>
            {steps.map((step, idx) => {
              if (step.type === "thought") {
                return (
                  <div key={`step-${idx}`} style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                    <span
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: "50%",
                        background: "#9ca3af",
                        marginTop: 6,
                        marginLeft: -14,
                        flexShrink: 0,
                      }}
                    />
                    <div style={{ flex: 1 }}>
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{step.text}</ReactMarkdown>
                    </div>
                  </div>
                );
              } else {
                return (
                  <div key={`step-${idx}`} style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                    <span
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: 1,
                        background: "#9ca3af",
                        marginTop: 6,
                        marginLeft: -14,
                        flexShrink: 0,
                      }}
                    />
                    <div style={{ flex: 1 }}>
                      <ToolCard toolName={step.name} toolResult={step.result} />
                    </div>
                  </div>
                );
              }
            })}
            {activeTool && (
              <div key="active-tool" style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: 1,
                    background: "#6366f1",
                    marginTop: 6,
                    marginLeft: -14,
                    flexShrink: 0,
                  }}
                />
                <div style={{ flex: 1 }}>
                  <ToolCard toolName={activeTool} toolResult={{ args: activeToolArgs }} />
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Message bubble ────────────────────────────────────────────────────────────

interface ParsedUserAttachmentContent {
  attachments: string[];
  cleanText: string;
}

function parseUserAttachmentContent(content: string | null): ParsedUserAttachmentContent {
  if (!content) return { attachments: [], cleanText: "" };
  const attachmentRegex = /\[attachment:\s*([^\]]+)\]/gi;
  const attachments: string[] = [];
  let match;
  while ((match = attachmentRegex.exec(content)) !== null) {
    if (match[1]?.trim()) {
      attachments.push(match[1].trim());
    }
  }
  const cleanText = content.replace(/\[attachment:\s*[^\]]+\]\n?/gi, "").trim();
  return { attachments, cleanText };
}

function MessageBubble({
  role,
  content,
  toolName,
  toolResult,
  agentName,
  agentColor,
  invocationDepth = 0,
}: {
  role: string;
  content: string | null;
  toolName?: string | null;
  toolResult?: Record<string, unknown> | null;
  agentName?: string | null;
  agentColor?: string | null;
  invocationDepth?: number;
}) {
  const isUser = role === "user";
  const isTool = role === "tool";
  const isSubagent = !isUser && !!agentName && invocationDepth > 0;

  if (isTool) {
    return (
      <ToolCard
        toolName={toolName ?? "tool"}
        toolResult={toolResult}
      />
    );
  }

  // Parse reasoning thoughts vs final response text
  const { thought, response } = parseThoughtContent(content);

  // Try to extract Vega-Lite spec from assistant messages
  let vegaSpec: unknown = null;
  if (!isUser && response) {
    const jsonMatch = response.match(/```(?:json|vega-lite)\n([\s\S]*?)```/);
    if (jsonMatch) {
      try {
        const parsed = JSON.parse(jsonMatch[1]);
        if (parsed.$schema && parsed.$schema.includes("vega-lite")) {
          vegaSpec = parsed;
        }
      } catch { /* not JSON */ }
    }
  }

  const avatarBg = isUser
    ? "#e5e7eb"
    : isSubagent
    ? `${agentColor ?? "#6366f1"}22`
    : "var(--color-surface-hover)";

  const avatarIcon = isUser ? (
    <User size={14} color="#374151" />
  ) : isSubagent ? (
    <Bot size={14} color={agentColor ?? "#6366f1"} />
  ) : (
    <Bot size={14} color="var(--color-primary)" />
  );

  return (
    <div
      style={{
        display: "flex",
        gap: 10,
        marginBottom: 16,
        flexDirection: isUser ? "row-reverse" : "row",
        paddingLeft: isSubagent ? invocationDepth * 16 : 0, // indent subagent messages
      }}
    >
      {/* Bubble / Content */}
      <div style={{ maxWidth: isUser ? "80%" : "100%", display: "flex", flexDirection: "column", gap: 4, alignItems: isUser ? "flex-end" : "flex-start", flex: isUser ? undefined : 1 }}>
        {/* Agent badge — shown above subagent messages */}
        {isSubagent && agentName && (
          <AgentBadge name={agentName} color={agentColor} depth={invocationDepth} />
        )}
        <div
          style={{
            background: isUser ? "#f3f4f6" : "transparent",
            color: isUser ? "#111827" : "var(--color-text)",
            padding: isUser ? "8px 14px" : "0",
            borderRadius: isUser ? "8px" : "0",
            border: "none",
            fontSize: "0.875rem",
            lineHeight: 1.6,
          }}
        >
          {isUser ? (
            (() => {
              const { attachments, cleanText } = parseUserAttachmentContent(content);
              return (
                <div style={{ display: "flex", flexDirection: "column", gap: 6, alignItems: "flex-end" }}>
                  {attachments.length > 0 && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4, justifyContent: "flex-end" }}>
                      {attachments.map((filename, i) => (
                        <span
                          key={i}
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 4,
                            padding: "2px 8px",
                            borderRadius: 6,
                            background: "rgba(99,102,241,0.15)",
                            border: "1px solid rgba(99,102,241,0.3)",
                            fontSize: "0.75rem",
                            color: "#4f46e5",
                            fontWeight: 600,
                          }}
                        >
                          📎 {filename}
                        </span>
                      ))}
                    </div>
                  )}
                  <span style={{ whiteSpace: "pre-wrap" }}>{cleanText}</span>
                </div>
              );
            })()
          ) : (
            <>
              {thought && <ThoughtAccordion thought={thought} />}
              {vegaSpec ? (
                <ChartBlock spec={vegaSpec} />
              ) : response ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                  {response}
                </ReactMarkdown>
              ) : !thought ? (
                <span style={{ opacity: 0.6, fontStyle: "italic" }}>*(No response content)*</span>
              ) : null}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Streaming indicator ───────────────────────────────────────────────────────

function StreamingMessage({
  text,
  activeTool,
  activeToolArgs,
  agentName,
  agentColor,
  invocationDepth = 0,
}: {
  text: string;
  activeTool: string | null;
  activeToolArgs: Record<string, unknown> | null;
  agentName?: string | null;
  agentColor?: string | null;
  invocationDepth?: number;
}) {
  const [argsOpen, setArgsOpen] = useState(false);
  const isSubagent = !!agentName && invocationDepth > 0;
  const botColor = isSubagent ? (agentColor ?? "#6366f1") : "var(--color-primary)";

  const { thought, response } = parseThoughtContent(text);

  return (
    <div
      style={{
        display: "flex",
        gap: 10,
        marginBottom: 16,
        paddingLeft: isSubagent ? invocationDepth * 16 : 0,
      }}
    >
      <div style={{ maxWidth: "100%", display: "flex", flexDirection: "column", gap: 4, flex: 1 }}>
        {isSubagent && agentName && (
          <AgentBadge name={agentName} color={agentColor} depth={invocationDepth} />
        )}
        <div
          style={{
            background: "transparent",
            color: "var(--color-text)",
            padding: 0,
            borderRadius: 0,
            border: "none",
            fontSize: "0.875rem",
            lineHeight: 1.6,
            width: "100%",
          }}
        >
          {thought && <ThoughtAccordion thought={thought} isStreaming={true} />}

          {response && (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{response}</ReactMarkdown>
          )}

          {activeTool ? (
            <div style={{ marginTop: (thought || response) ? 8 : 0 }}>
              <div
                style={{
                  display: "flex", alignItems: "center", gap: 6,
                  color: "var(--color-text-muted)",
                  cursor: activeToolArgs ? "pointer" : "default",
                  padding: "4px 8px",
                  background: "var(--color-surface-hover)",
                  borderRadius: 6,
                }}
                onClick={() => activeToolArgs && setArgsOpen((o) => !o)}
              >
                <Loader2 size={12} className="spin" />
                <Zap size={12} color="var(--color-primary)" />
                <span style={{ color: "var(--color-text)" }}>Calling <strong>{activeTool}</strong>…</span>
                {activeToolArgs && (
                  <span style={{ marginLeft: 2 }}>
                    {argsOpen ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                  </span>
                )}
              </div>
              {argsOpen && activeToolArgs && (
                <pre style={{ margin: "6px 0 0", fontSize: "0.72rem", overflowX: "auto", color: "var(--color-text-muted)" }}>
                  {JSON.stringify(activeToolArgs, null, 2)}
                </pre>
              )}
            </div>
          ) : !text ? (
            <span style={{ display: "inline-flex", gap: 4, color: "var(--color-text-muted)" }}>
              <Loader2 size={12} className="spin" /> Thinking…
            </span>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function SessionListItem({
  session,
  isActive,
  onSelect,
  onDelete,
}: {
  session: ChatSession;
  isActive: boolean;
  onSelect: () => void;
  onDelete: (e: React.MouseEvent) => void;
}) {
  const [isHovered, setIsHovered] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    if (menuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [menuOpen]);

  return (
    <div
      onClick={onSelect}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "7px 10px",
        borderRadius: 6,
        cursor: "pointer",
        background: isActive
          ? "var(--color-primary-subtle, rgba(27,110,243,0.08))"
          : isHovered
          ? "var(--color-surface-hover)"
          : "transparent",
        color: isActive ? "var(--color-primary)" : "var(--color-text)",
        fontSize: "0.78rem",
        marginBottom: 2,
        position: "relative",
      }}
    >
      <span
        style={{
          flex: 1,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          fontWeight: isActive ? 600 : 400,
        }}
      >
        {session.title ?? `Session #${session.id}`}
      </span>

      {(isHovered || menuOpen || isActive) && (
        <div style={{ position: "relative" }} ref={menuRef} onClick={(e) => e.stopPropagation()}>
          <button
            type="button"
            className="btn-icon"
            style={{
              padding: "2px 4px",
              opacity: menuOpen || isHovered ? 0.8 : 0.4,
              borderRadius: 4,
              border: "none",
              background: "transparent",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
            }}
            onClick={(e) => {
              e.stopPropagation();
              setMenuOpen((open) => !open);
            }}
            title="Session options"
          >
            <MoreVertical size={13} />
          </button>

          {menuOpen && (
            <div
              style={{
                position: "absolute",
                top: "100%",
                right: 0,
                marginTop: 4,
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                borderRadius: 6,
                boxShadow: "0 4px 12px rgba(0,0,0,0.12)",
                zIndex: 999,
                padding: "4px 0",
                minWidth: 100,
              }}
            >
              <button
                type="button"
                onClick={(e) => {
                  setMenuOpen(false);
                  onDelete(e);
                }}
                style={{
                  width: "100%",
                  textAlign: "left",
                  background: "transparent",
                  border: "none",
                  padding: "6px 12px",
                  fontSize: "0.75rem",
                  color: "var(--color-danger, #ef4444)",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                <Trash2 size={12} />
                <span>Delete</span>
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function AgentChatPage() {
  const { agentId: agentIdStr, sessionId: sessionIdStr } = useParams<{ agentId: string; sessionId?: string }>();
  const agentId = agentIdStr ? parseInt(agentIdStr, 10) : null;
  const urlSessionId = sessionIdStr ? parseInt(sessionIdStr, 10) : null;

  const navigate = useScopedNavigate();
  const qc = useQueryClient();
  const toast = useToast();

  const { data: agent } = useAgent(agentId);
  const { data: researchRuns = [] } = useResearchEngineRuns();
  const triggerResearchRun = useTriggerResearchEngineRun();
  const { data: sessions = [] } = useChatSessions(agentId);
  const { data: llmConnections = [] } = useLLMConnections();
  const createSession = useCreateSession();
  const deleteSession = useDeleteSession();

  const [activeSessionId, setActiveSessionId] = useState<number | null>(urlSessionId);

  // Sync activeSessionId with URL param if URL changes
  useEffect(() => {
    if (urlSessionId && urlSessionId !== activeSessionId) {
      setActiveSessionId(urlSessionId);
    }
  }, [urlSessionId]);

  const { data: messages = [] } = useChatMessages(agentId, activeSessionId);
  const isResearchEngineAgent = (agent?.tools ?? []).some((tool) => ["fetch_research_memory", "fetch_research_proposal_history"].includes(tool.tool_name));
  const researchRunsForAgent = researchRuns.filter((run) => run.agent_id === agentId);

  const {
    streamingText,
    isStreaming,
    activeToolName,
    activeToolArgs,
    streamingSteps,
    streamingAgentName,
    streamingAgentColor,
    streamingInvocationDepth,
    appendStreamingText,
    setStreaming,
    setActiveTool,
    addStreamingTimelineItem,
    setStreamingAgent,
    resetStream,
  } = useChatStore();

  const [input, setInput] = useState("");
  const [selectedLlmConnectionId, setSelectedLlmConnectionId] = useState<number | null>(null);
  const [optimisticUserMsg, setOptimisticUserMsg] = useState<string | null>(null);
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  // File upload state (Part F)
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [uploadedDocIds, setUploadedDocIds] = useState<number[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // Diff sheet state (Part G)
  const [diffSheetRecord, setDiffSheetRecord] = useState<ChangeRecord | null>(null);
  // Known asset names for this session (for D14 deny-by-default resolution)
  const [knownAssetNames, setKnownAssetNames] = useState<Set<string>>(new Set());
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Keep track of the active session ID to close it when switching or unmounting
  const activeSessionRef = useRef<number | null>(activeSessionId);

  useEffect(() => {
    const prevSessionId = activeSessionRef.current;
    activeSessionRef.current = activeSessionId;
    
    if (prevSessionId && prevSessionId !== activeSessionId) {
      api.post(`/sessions/${prevSessionId}/close`, {}).catch(() => {});
    }
  }, [activeSessionId]);

  useEffect(() => {
    return () => {
      const sessId = activeSessionRef.current;
      if (sessId) {
        api.post(`/sessions/${sessId}/close`, {}).catch(() => {});
      }
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText]);

  // G1/D14: Fetch known asset names on session change so asset chips resolve correctly
  useEffect(() => {
    if (!agentId || !activeSessionId) return;
    const authkey = getAuthKey();
    const headers: Record<string, string> = authkey
      ? { authkey, Authorization: `Bearer ${authkey}` }
      : {};
    fetch(`/api/v1/agents/${agentId}/sessions/${activeSessionId}/assets`, { headers })
      .then((r) => r.ok ? r.json() : [])
      .then((data: Array<{ full_name: string }>) => {
        setKnownAssetNames(new Set(data.map((a) => a.full_name)));
      })
      .catch(() => {});
  }, [agentId, activeSessionId]);

  // Re-fetch known assets after each streaming turn ends
  useEffect(() => {
    if (!isStreaming && agentId && activeSessionId) {
      const authkey = getAuthKey();
      const headers: Record<string, string> = authkey
        ? { authkey, Authorization: `Bearer ${authkey}` }
        : {};
      fetch(`/api/v1/agents/${agentId}/sessions/${activeSessionId}/assets`, { headers })
        .then((r) => r.ok ? r.json() : [])
        .then((data: Array<{ full_name: string }>) => {
          setKnownAssetNames(new Set(data.map((a) => a.full_name)));
        })
        .catch(() => {});
    }
  }, [isStreaming]);

  useEffect(() => {
    if (!llmConnections.length) {
      setSelectedLlmConnectionId(null);
      return;
    }
    setSelectedLlmConnectionId((current) => {
      if (current && llmConnections.some((connection) => connection.id === current)) return current;
      return llmConnections.find((connection) => connection.is_fallback)?.id ?? llmConnections[0].id;
    });
  }, [llmConnections]);

  // Select session from URL or auto-select first session
  useEffect(() => {
    if (urlSessionId) {
      setActiveSessionId(urlSessionId);
    } else if (sessions.length > 0 && !activeSessionId) {
      const firstId = sessions[0].id;
      setActiveSessionId(firstId);
      if (agentId) {
        navigate(`/agents/${agentId}/chat/${firstId}`, { replace: true });
      }
    }
  }, [sessions, urlSessionId, agentId]);

  const selectSession = useCallback((sessionId: number) => {
    setActiveSessionId(sessionId);
    if (agentId) {
      navigate(`/agents/${agentId}/chat/${sessionId}`);
    }
  }, [agentId, navigate]);

  async function handleNewSession() {
    if (!agentId) return;
    setIsCreatingSession(true);
    try {
      const session = await createSession.mutateAsync({ agentId });
      selectSession(session.id);
    } catch {
      toast.error("Failed to create session");
    } finally {
      setIsCreatingSession(false);
    }
  }

  async function handleDeleteSession(e: React.MouseEvent, session: ChatSession) {
    e.stopPropagation();
    if (!confirm("Delete this conversation?")) return;
    try {
      await deleteSession.mutateAsync({
        agentId: agentId!,
        sessionId: session.id,
      });
      if (activeSessionId === session.id) setActiveSessionId(null);
    } catch {
      toast.error("Failed to delete session");
    }
  }

  async function handleTriggerResearchRun() {
    if (!agentId || triggerResearchRun.isPending) return;
    try {
      const result = await triggerResearchRun.mutateAsync({ agentId });
      selectSession(result.session_id);
      setInput(result.initial_prompt);
      qc.invalidateQueries({ queryKey: ["agents", agentId, "sessions"] });
      toast.success("Research run session created. Send the prefilled prompt to start it.");
    } catch {
      toast.error("Failed to trigger research run");
    }
  }

  const sendMessage = useCallback(async (textOverride?: unknown) => {
    const textStr = typeof textOverride === "string" ? textOverride : input;
    const rawText = String(textStr ?? "");
    const connId = selectedLlmConnectionId ?? (llmConnections.find((c) => c.is_fallback)?.id ?? llmConnections[0]?.id);
    let content = rawText.trim();
    if (typeof textOverride !== "string" && attachedFiles.length > 0) {
      const attPrefix = attachedFiles.map((f) => `[attachment: ${f.name}]`).join("\n");
      content = `${attPrefix}\n${content}`;
    }
    if (typeof textOverride !== "string") {
      setInput("");
      setAttachedFiles([]);
      setUploadedDocIds([]);
    }
    setOptimisticUserMsg(content);
    resetStream();
    setStreaming(true);

    const baseUrl = (import.meta.env.VITE_API_BASE_URL || "/api/v1").replace(/\/$/, "");
    const match = window.location.pathname.match(/^\/w\/([^/]+)/);
    const workspaceSlug = match ? match[1] : null;
    const url = `${baseUrl}/agents/${agentId}/sessions/${activeSessionId}/stream${workspaceSlug ? `?workspace=${workspaceSlug}` : ""}`;

    abortRef.current = new AbortController();
    try {
      const authkey = getAuthKey();
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (authkey) {
        headers["authkey"] = authkey;
        headers["Authorization"] = `Bearer ${authkey}`;
      }
      if (workspaceSlug) headers["X-Workspace-Slug"] = workspaceSlug;

      const response = await fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify({ content, sandbox: false, llm_connection_id: connId }),
        signal: abortRef.current.signal,
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) return;

      let lineBuffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        lineBuffer += decoder.decode(value, { stream: true });
        const lines = lineBuffer.split("\n");
        lineBuffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const rawJson = line.slice(6).trim();
          if (!rawJson) continue;
          try {
            const ev = JSON.parse(rawJson);

            // ── Swarm: update which agent is currently streaming ─────────────
            if (ev.agent_name !== undefined) {
              setStreamingAgent(
                ev.agent_name ?? null,
                ev.agent_color ?? null,
                ev.invocation_depth ?? 0,
              );
            }

            if (ev.type === "text" && ev.delta) appendStreamingText(ev.delta);
            if (ev.type === "tool_start") {
              const currentText = useChatStore.getState().streamingText;
              if (currentText) {
                const { thought } = parseThoughtContent(currentText);
                if (thought) {
                  const items = thought
                    .split(/\n+/)
                    .map((item) => item.trim().replace(/^[-*•]\s*/, ""))
                    .filter((item) => item.length > 0);
                  items.forEach((txt) => addStreamingTimelineItem({ type: "thought", text: txt }));
                }
                // Reset streaming text buffer for next turn segment
                useChatStore.setState({ streamingText: "" });
              }
              setActiveTool(ev.tool_name ?? "tool", ev.args);
            }
            if (ev.type === "tool_end") {
              addStreamingTimelineItem({
                type: "tool",
                name: ev.tool_name ?? "tool",
                args: ev.args,
                result: ev.result,
                error: ev.error,
                ok: ev.ok,
              });
              setActiveTool(null);
            }
            if (ev.type === "error") {
              const errMsg = ev.message ?? "Agent encountered an error";
              toast.error(errMsg);
              appendStreamingText(`\n\n> ⚠️ **Error**: ${errMsg}`);
              setStreaming(false);
              setActiveTool(null);
              qc.invalidateQueries({
                queryKey: ["agents", agentId, "sessions", activeSessionId, "messages"],
              });
            }
            if (ev.type === "done") {
              qc.invalidateQueries({
                queryKey: ["agents", agentId, "sessions", activeSessionId, "messages"],
              }).then(() => setOptimisticUserMsg(null));
              qc.invalidateQueries({
                queryKey: ["agents", agentId, "sessions"],
              });
            }
          } catch { /* skip */ }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== "AbortError") {
        const errMsg = err.message || "Stream connection failed";
        toast.error(`Stream error — ${errMsg}`);
        appendStreamingText(`\n\n> ⚠️ **Stream Connection Error**: ${errMsg}`);
      }
    } finally {
      setStreaming(false);
      setActiveTool(null);
      setOptimisticUserMsg(null);
    }
  }, [input, activeSessionId, agentId, selectedLlmConnectionId, isStreaming]);

  return (
    <div
      style={{
        display: "flex",
        flex: 1,
        height: "100%",
        width: "100%",
        gap: 0,
        overflow: "hidden",
      }}
    >
      {/* ── Sessions sidebar ── */}
      <div
        style={{
          width: 240,
          borderRight: "1px solid var(--color-border)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          flexShrink: 0,
        }}
      >
        <div
          style={{
            padding: "12px 12px 8px",
            borderBottom: "1px solid var(--color-border)",
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <Bot size={14} color="var(--color-primary)" />
          <span style={{ fontWeight: 600, fontSize: "0.8rem", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {agent?.name ?? "Agent"}
          </span>
          <button
            className="btn-icon"
            title="Edit agent"
            onClick={() => navigate(`/agents/${agentId}/edit`)}
          >
            <Settings2 size={13} />
          </button>
        </div>

        <div style={{ padding: "8px 8px 4px" }}>
          <button
            className="btn btn-secondary"
            style={{ width: "100%", fontSize: "0.78rem" }}
            onClick={handleNewSession}
            disabled={isCreatingSession}
          >
            {isCreatingSession ? <Loader2 size={13} className="spin" /> : <Plus size={13} />}
            {isCreatingSession ? "Creating…" : "New conversation"}
          </button>
        </div>

        <div style={{ flex: 1, overflowY: "auto", padding: "4px 4px" }}>
          {isResearchEngineAgent && (
            <div style={{ margin: "4px 4px 10px", padding: "8px", border: "1px solid var(--color-border)", borderRadius: 8 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                <span style={{ fontSize: "0.74rem", fontWeight: 700, color: "var(--color-text-muted)" }}>Research Runs</span>
                <button className="btn btn-primary" style={{ height: 28, padding: "0 10px", fontSize: "0.72rem" }} onClick={handleTriggerResearchRun} disabled={triggerResearchRun.isPending}>
                  {triggerResearchRun.isPending ? <Loader2 size={12} className="spin" /> : <Zap size={12} />} Trigger Run
                </button>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {researchRunsForAgent.length === 0 ? (
                  <div style={{ fontSize: "0.73rem", color: "var(--color-text-muted)" }}>No research runs yet.</div>
                ) : researchRunsForAgent.map((run) => {
                  const linkedSessionId = Number((run.context_package as Record<string, unknown> | undefined)?.chat_session_id ?? 0) || null;
                  return (
                    <button
                      key={run.id}
                      type="button"
                      onClick={() => linkedSessionId && selectSession(linkedSessionId)}
                      style={{
                        textAlign: "left",
                        border: "1px solid var(--color-border)",
                        background: linkedSessionId === activeSessionId ? "var(--color-surface-hover)" : "var(--color-surface)",
                        borderRadius: 8,
                        padding: "8px",
                        cursor: linkedSessionId ? "pointer" : "default",
                        width: "100%",
                      }}
                    >
                      <div style={{ fontSize: "0.75rem", fontWeight: 600 }}>Run {run.id.slice(0, 8)}</div>
                      <div style={{ fontSize: "0.68rem", color: "var(--color-text-muted)" }}>{run.status} - {run.started_at ? new Date(run.started_at).toLocaleString() : "pending"}</div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
          {sessions.map((s) => (
            <SessionListItem
              key={s.id}
              session={s}
              isActive={activeSessionId === s.id}
              onSelect={() => selectSession(s.id)}
              onDelete={(e) => handleDeleteSession(e, s)}
            />
          ))}
          {sessions.length === 0 && (
            <div style={{ padding: "16px 8px", fontSize: "0.75rem", color: "var(--color-text-muted)", textAlign: "center" }}>
              No conversations yet
            </div>
          )}
        </div>
      </div>

      {/* ── Chat area ── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {!activeSessionId ? (
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 12,
              color: "var(--color-text-muted)",
            }}
          >
            <Bot size={40} style={{ opacity: 0.2 }} />
            <div style={{ fontSize: "0.9rem" }}>Select or create a conversation to start.</div>
            <button className="btn btn-primary" onClick={handleNewSession}>
              <Plus size={14} /> New conversation
            </button>
          </div>
        ) : (
          <>
            {/* Messages */}
            <div
              style={{
                flex: 1,
                overflowY: "auto",
                padding: "20px 24px",
                display: "flex",
                justifyContent: "center",
              }}
            >
              <div
                style={{
                  width: "100%",
                  maxWidth: 1100,
                  display: "flex",
                  flexDirection: "column",
                }}
              >
              {(() => {
                // Group messages into user bubbles vs combined assistant turns
                type MessageGroup = {
                  type: "user" | "assistant_turn";
                  id: string;
                  userMsg?: (typeof messages)[0];
                  items?: (typeof messages);
                  isStreamingActive?: boolean;
                };

                const groups: MessageGroup[] = [];
                let currentAssistantTurn: MessageGroup | null = null;

                for (const msg of messages) {
                  if (msg.role === "user") {
                    if (currentAssistantTurn) {
                      groups.push(currentAssistantTurn);
                      currentAssistantTurn = null;
                    }
                    groups.push({
                      type: "user",
                      id: `user-${msg.id}`,
                      userMsg: msg,
                    });
                  } else {
                    if (!currentAssistantTurn) {
                      currentAssistantTurn = {
                        type: "assistant_turn",
                        id: `turn-${msg.id}`,
                        items: [],
                      };
                    }
                    currentAssistantTurn.items!.push(msg);
                  }
                }

                if (currentAssistantTurn) {
                  groups.push(currentAssistantTurn);
                }

                // If streaming, attach to current open assistant turn or create a new turn
                if (isStreaming || optimisticUserMsg) {
                  if (optimisticUserMsg) {
                    groups.push({
                      type: "user",
                      id: "optimistic-user",
                      userMsg: { id: -1, role: "user", content: optimisticUserMsg } as any,
                    });
                  }
                  if (isStreaming) {
                    const lastGroup = groups[groups.length - 1];
                    if (lastGroup && lastGroup.type === "assistant_turn") {
                      lastGroup.isStreamingActive = true;
                    } else {
                      groups.push({
                        type: "assistant_turn",
                        id: "streaming-turn",
                        items: [],
                        isStreamingActive: true,
                      });
                    }
                  }
                }

                return groups.map((grp) => {
                  if (grp.type === "user" && grp.userMsg) {
                    return (
                      <MessageBubble
                        key={grp.id}
                        role="user"
                        content={grp.userMsg.content}
                      />
                    );
                  }

                  // Render single combined assistant turn
                  const turnItems = grp.items ?? [];
                  const timelineSteps: TimelineStep[] = [];
                  let finalResponse = "";

                  turnItems.forEach((m) => {
                    if (m.role === "tool") {
                      timelineSteps.push({
                        type: "tool",
                        name: m.tool_name ?? "tool",
                        result: m.tool_result,
                      });
                    } else {
                      const { thought, response } = parseThoughtContent(m.content);
                      if (thought) {
                        const items = thought
                          .split(/\n+/)
                          .map((item) => item.trim().replace(/^[-*•]\s*/, ""))
                          .filter((item) => item.length > 0);
                        items.forEach((txt) => timelineSteps.push({ type: "thought", text: txt }));
                      }
                      if (response) {
                        finalResponse += (finalResponse ? "\n\n" : "") + response;
                      }
                    }
                  });

                  if (grp.isStreamingActive) {
                    // Push live streaming steps in exact chronological order (thoughts + tools)
                    streamingSteps.forEach((st) => {
                      timelineSteps.push(st);
                    });

                    const { thought, response } = parseThoughtContent(streamingText);
                    if (thought) {
                      const items = thought
                        .split(/\n+/)
                        .map((item) => item.trim().replace(/^[-*•]\s*/, ""))
                        .filter((item) => item.length > 0);
                      items.forEach((txt) => timelineSteps.push({ type: "thought", text: txt }));
                    }
                    if (response) {
                      finalResponse += (finalResponse ? "\n\n" : "") + response;
                    }
                  }

                  const cleanFinalResponse = finalResponse.replace(/\r\n/g, "\n").replace(/\n{3,}/g, "\n\n").trim();

                  // Check if this turn contains the final step completion for an active plan
                  let inlineCompletedPlanData: any = null;
                  const createPlanMsg = [...messages].reverse().find((m) => m.role === "tool" && m.tool_name === "create_plan");
                  if (createPlanMsg && createPlanMsg.tool_result) {
                    const r = createPlanMsg.tool_result.result as any;
                    const a = createPlanMsg.tool_result.args as any;
                    const steps = a?.steps || r?.steps || [];
                    
                    const stepStatusMap: Record<number, string> = {};
                    messages.forEach((m) => {
                      if (m.role === "tool" && m.tool_name === "mark_step" && m.tool_result) {
                        const mr = m.tool_result.result as any;
                        const stepId = mr?.updated_step ?? m.tool_result.args?.step_id;
                        const status = mr?.status ?? m.tool_result.args?.status;
                        if (stepId && status) stepStatusMap[stepId] = status;
                      }
                    });
                    
                    const computedSteps = steps.map((s: any, idx: number) => {
                      const id = s.id ?? idx + 1;
                      return {
                        id,
                        description: s.description ?? s.text ?? "",
                        status: stepStatusMap[id] || s.status || "pending",
                        verification: s.verification ?? "Automatic check",
                        corrections: s.corrections ?? [],
                        attempts: s.attempts ?? 1,
                      };
                    });
                    
                    const isAllDone = computedSteps.length > 0 && computedSteps.every((s: any) => s.status === "done");
                    // Only attach inline card to this turn if this turn performed the final step completion
                    const turnHasFinalMarkStep = turnItems.some(
                      (m) => m.role === "tool" && m.tool_name === "mark_step"
                    );

                    if (isAllDone && turnHasFinalMarkStep) {
                      inlineCompletedPlanData = {
                        plan_id: r?.plan_id || "plan",
                        goal: a?.goal || r?.goal || "Execution Plan",
                        steps: computedSteps,
                        approved_at: r?.approved_at || new Date().toISOString(),
                      };
                    }
                  }

                  return (
                    <div key={grp.id} style={{ marginBottom: 16 }}>
                      {/* Single consolidated Thinking block for thoughts + tool calls */}
                      {(timelineSteps.length > 0 || (grp.isStreamingActive && !cleanFinalResponse) || (grp.isStreamingActive && activeToolName)) && (
                        <ConsolidatedThoughtBlock
                          steps={timelineSteps}
                          isStreaming={grp.isStreamingActive}
                          activeTool={grp.isStreamingActive ? activeToolName : null}
                          activeToolArgs={grp.isStreamingActive ? activeToolArgs : null}
                        />
                      )}

                      {/* Final response — parse <asset> tags into chips, rest to ReactMarkdown */}
                      {cleanFinalResponse && (() => {
                        const segments = parseAssetTags(cleanFinalResponse, knownAssetNames);
                        // If no asset tags found, render as plain markdown
                        if (segments.length === 1 && typeof segments[0] === 'string') {
                          return (
                            <div
                              className="assistant-response-content"
                              style={{ marginTop: timelineSteps.length > 0 ? 12 : 0, fontSize: "0.9rem", lineHeight: 1.65, color: "var(--color-text, #1f2937)" }}
                            >
                              <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                                {cleanFinalResponse}
                              </ReactMarkdown>
                            </div>
                          );
                        }
                        // Mixed content: render each segment
                        return (
                          <div
                            className="assistant-response-content"
                            style={{ marginTop: timelineSteps.length > 0 ? 12 : 0, fontSize: "0.9rem", lineHeight: 1.65, color: "var(--color-text, #1f2937)" }}
                          >
                            {segments.map((seg, i) =>
                              typeof seg === 'string' ? (
                                <ReactMarkdown key={i} remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                                  {seg}
                                </ReactMarkdown>
                              ) : (
                                <AssetChip
                                  key={i}
                                  fullName={seg.chip.fullName}
                                  objectType={seg.chip.objectType}
                                  displayName={seg.chip.displayName}
                                />
                              )
                            )}
                          </div>
                        );
                      })()}

                      {/* Inline Completed Plan Card in turn history */}
                      {inlineCompletedPlanData && (
                        <div style={{ marginTop: 10 }}>
                          <PlanTaskViewer
                            plan={{
                              plan_id: inlineCompletedPlanData.plan_id,
                              agent_id: "agent",
                              goal: inlineCompletedPlanData.goal,
                              steps: inlineCompletedPlanData.steps,
                              approved_at: inlineCompletedPlanData.approved_at,
                            }}
                          />
                        </div>
                      )}

                      {/* G6: Diff Summary Card — shown after completed non-streaming turns */}
                      {!grp.isStreamingActive && agentId && activeSessionId && (
                        <DiffSummaryCard
                          agentId={agentId}
                          sessionId={activeSessionId}
                          stepId={(() => {
                            // find the last mark_step tool call in this turn to scope changes
                            const markMsg = [...(grp.items ?? [])]
                              .reverse()
                              .find((m) => m.role === "tool" && m.tool_name === "mark_step");
                            return (markMsg?.tool_result?.result as any)?.updated_step ?? undefined;
                          })()}
                          onOpenDiff={(record) => setDiffSheetRecord(record as any)}
                        />
                      )}
                    </div>
                  );
                });
              })()}
              <div ref={messagesEndRef} />
              </div>
            </div>

            {/* Docked Active Plan Task Viewer at bottom — hides automatically when all steps are completed */}
            {(() => {
              const createPlanMsg = [...messages].reverse().find((m) => m.role === "tool" && m.tool_name === "create_plan");
              if (!createPlanMsg || !createPlanMsg.tool_result) return null;

              const res = createPlanMsg.tool_result.result as any;
              const args = createPlanMsg.tool_result.args as any;
              const stepsData = args?.steps || res?.steps || [];
              const goalData = args?.goal || res?.goal || "Execution Plan";
              const planIdData = res?.plan_id || "plan";

              // Compute live step status map (checking persisted messages + live streaming tool steps)
              const stepStatusMap: Record<number, string> = {};
              messages.forEach((m) => {
                if (m.role === "tool" && m.tool_name === "mark_step" && m.tool_result) {
                  const r = m.tool_result.result as any;
                  const stepId = r?.updated_step ?? m.tool_result.args?.step_id;
                  const status = r?.status ?? m.tool_result.args?.status;
                  if (stepId && status) stepStatusMap[stepId] = status;
                }
              });
              streamingSteps.forEach((st) => {
                if (st.type === "tool" && st.name === "mark_step" && st.result) {
                  const r = st.result as any;
                  const stepId = r?.updated_step ?? st.args?.step_id;
                  const status = r?.status ?? st.args?.status;
                  if (stepId && status) stepStatusMap[stepId] = status;
                }
              });

              const mappedSteps = stepsData.map((s: any, idx: number) => {
                const stepId = s.id ?? idx + 1;
                return {
                  id: stepId,
                  description: s.description ?? s.text ?? "",
                  status: stepStatusMap[stepId] || s.status || "pending",
                  verification: s.verification ?? "Automatic check",
                  corrections: s.corrections ?? [],
                  attempts: s.attempts ?? 1,
                };
              });

              // Un-dock plan from bottom once all steps are completed
              const isAllDone = mappedSteps.length > 0 && mappedSteps.every((s: any) => s.status === "done");
              if (isAllDone) return null;

              return (
                <div style={{ width: "100%", maxWidth: 1100, margin: "0 auto", padding: "0 24px" }}>
                  <PlanTaskViewer
                    plan={{
                      plan_id: planIdData,
                      agent_id: "agent",
                      goal: goalData,
                      steps: mappedSteps,
                      approved_at: res?.approved_at || (messages.some(m => (m.role === "tool" && m.tool_name === "mark_step") || (m.role === "user" && m.content.toLowerCase().includes("approved"))) ? new Date().toISOString() : null),
                      execution_approved_at: res?.execution_approved_at,
                    }}
                    onApprovePlan={() => sendMessage("Approved. Proceed to execute the plan.")}
                    onRejectPlan={() => sendMessage("Plan rejected. Re-evaluate the requirements and propose a different approach.")}
                    onRequestChange={(feedback) => sendMessage(`Plan changes requested: ${feedback}`)}
                  />
                </div>
              );
            })()}

            {/* Input Composer */}
            {(() => {
              const activePlan = [...messages].reverse().find((m) => m.role === "tool" && m.tool_name === "create_plan");
              const hasPlan = !!activePlan?.tool_result;
              return (
                <div
                  style={{
                    borderTop: "none",
                    padding: "0 24px 8px",
                    display: "flex",
                    justifyContent: "center",
                  }}
                >
                  <div
                    style={{
                      width: "100%",
                      maxWidth: 1100,
                      display: "flex",
                      flexDirection: "column",
                      background: "#ffffff",
                      border: "1px solid var(--color-border, #e5e7eb)",
                      borderRadius: "16px",
                      boxShadow: "none",
                      padding: "10px 14px",
                      gap: 8,
                    }}
                  >
                    {/* Hidden file input */}
                    <input
                      ref={fileInputRef}
                      type="file"
                      multiple
                      accept=".pdf,.docx,.xlsx,.csv,.txt,.md,.json"
                      style={{ display: "none" }}
                      onChange={async (e) => {
                        const files = Array.from(e.target.files ?? []);
                        if (!files.length || !agentId || !activeSessionId) return;
                        setAttachedFiles(prev => [...prev, ...files]);
                        const formData = new FormData();
                        files.forEach(f => formData.append("files", f));
                        const authkey = (window as any).__authkey__ ?? "";
                        const resp = await fetch(
                          `/api/v1/agents/${agentId}/sessions/${activeSessionId}/documents`,
                          { method: "POST", body: formData, headers: authkey ? { authkey, Authorization: `Bearer ${authkey}` } : {} }
                        );
                        if (resp.ok) {
                          const data = await resp.json();
                          const ids = (data.uploaded ?? []).filter((u: any) => u.ok).map((u: any) => u.doc_id as number);
                          setUploadedDocIds(prev => [...prev, ...ids]);
                        }
                        e.target.value = "";
                      }}
                    />

                    {/* Attached file chips */}
                    {attachedFiles.length > 0 && (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                        {attachedFiles.map((f, i) => (
                          <span key={i} style={{
                            display: "inline-flex", alignItems: "center", gap: 4,
                            padding: "2px 8px", borderRadius: 6,
                            background: "rgba(99,102,241,0.12)", border: "1px solid rgba(99,102,241,0.3)",
                            fontSize: "0.75rem", color: "#6366f1",
                          }}>
                            📎 {f.name}
                            <button
                              type="button"
                              onClick={() => setAttachedFiles(prev => prev.filter((_, j) => j !== i))}
                              style={{ background: "none", border: "none", cursor: "pointer", padding: 0, color: "inherit", lineHeight: 1 }}
                            ><XIcon size={11} /></button>
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Top Message Textarea */}
                    <textarea
                      ref={textareaRef}
                      className="form-input"
                      style={{
                        width: "100%",
                        border: "none",
                        outline: "none",
                        boxShadow: "none",
                        resize: "none",
                        minHeight: 36,
                        maxHeight: 160,
                        fontSize: "0.88rem",
                        lineHeight: 1.5,
                        background: "transparent",
                        color: "var(--color-text, #111827)",
                        padding: "2px 0",
                      }}
                      rows={1}
                      placeholder="Message the agent… (Enter to send, Shift+Enter for newline)"
                      value={input}
                      onChange={(e) => {
                        setInput(e.target.value);
                        e.target.style.height = "auto";
                        e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          sendMessage();
                        }
                      }}
                      disabled={isStreaming}
                    />

                    {/* Bottom Row: File attachment icon (left), LLM Selection & Send icon (right) */}
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, paddingTop: 4, borderTop: "1px solid #f3f4f6" }}>
                      <div style={{ display: "flex", alignItems: "center" }}>
                        <button
                          type="button"
                          title="Attach a document"
                          onClick={() => fileInputRef.current?.click()}
                          style={{
                            background: "none",
                            border: "none",
                            color: "#6b7280",
                            cursor: "pointer",
                            padding: 4,
                            borderRadius: 4,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                          }}
                        >
                          <Paperclip size={17} />
                        </button>
                      </div>

                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <select
                          value={selectedLlmConnectionId ?? ""}
                          onChange={(e) => setSelectedLlmConnectionId(e.target.value ? Number(e.target.value) : null)}
                          disabled={isStreaming || llmConnections.length === 0}
                          title="LLM Connection"
                          style={{
                            border: "none",
                            background: "transparent",
                            fontSize: "0.74rem",
                            color: "#6b7280",
                            cursor: "pointer",
                            outline: "none",
                            fontWeight: 500,
                          }}
                        >
                          {llmConnections.length === 0 && <option value="">No LLM connections</option>}
                          {llmConnections.map((connection) => (
                            <option key={connection.id} value={connection.id}>
                              {connection.name}{connection.is_fallback ? " (default)" : ""}
                            </option>
                          ))}
                        </select>

                        <button
                          type="button"
                          onClick={() => sendMessage()}
                          disabled={!input.trim() || isStreaming}
                          style={{
                            width: 28,
                            height: 28,
                            borderRadius: "50%",
                            border: "1px solid #e5e7eb",
                            background: input.trim() && !isStreaming ? "#f3f4f6" : "#fafafa",
                            color: input.trim() && !isStreaming ? "#374151" : "#d1d5db",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            cursor: input.trim() && !isStreaming ? "pointer" : "not-allowed",
                            flexShrink: 0,
                          }}
                        >
                          {isStreaming ? <Loader2 size={14} className="spin" /> : <ArrowRight size={15} />}
                        </button>
                      </div>
                    </div>
                  </div>
              </div>
            );
          })()}

            {/* Disclaimer */}
            <div
              style={{
                textAlign: "center",
                fontSize: "0.68rem",
                color: "var(--color-text-subtle, var(--color-text-muted))",
                padding: "4px 0 8px",
              }}
            >
              Always review the accuracy of responses.
            </div>
          </>
        )}
      </div>

      {/* G7: DiffSheet side-panel — fixed overlay outside layout */}
      <DiffSheet record={diffSheetRecord} onClose={() => setDiffSheetRecord(null)} />
    </div>
  );
}


