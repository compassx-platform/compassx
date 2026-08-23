/**
 * AgentChatPage — SSE streaming chat with markdown rendering and Vega-Lite charts.
 * Supports multi-agent swarm: subagent messages are rendered with a colour-coded
 * agent badge so the user can see which agent produced each response.
 */
import { useState, useRef, useEffect, useCallback, useMemo } from "react";
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
  Copy,
  Check,
  PanelLeftClose,
  PanelLeftOpen,
  SquarePen,
  SlidersHorizontal,
  Search,
  History,
  Terminal,
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
import { SessionChangesDock } from "@/modules/agents/components/SessionChangesDock";
import { TurnEditBadge, TurnEditInfo } from "@/modules/agents/components/TurnEditBadge";
import { AgentCustomizationsView } from "@/modules/agents/components/AgentCustomizationsView";
import { SessionLlmLogsView } from "@/modules/agents/components/SessionLlmLogsView";
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
            {toolResult?.error ? (
              <div style={{ marginTop: 6 }}>
                <div style={{ fontWeight: 600, fontSize: "0.7rem", color: "#ef4444", textTransform: "uppercase", marginBottom: 2 }}>Error</div>
                <pre style={{ margin: 0, overflowX: "auto", background: "rgba(239,68,68,0.08)", color: "#dc2626", padding: "4px 8px", borderRadius: 4 }}>
                  {String(toolResult.error)}
                </pre>
              </div>
            ) : null}
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

// ── Copy Message Button ───────────────────────────────────────────────────────

function CopyMessageButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy text:", err);
    }
  };

  return (
    <button
      onClick={handleCopy}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "4px",
        border: "none",
        background: "transparent",
        color: copied ? "#16a34a" : "#9ca3af",
        cursor: "pointer",
        userSelect: "none",
        borderRadius: "4px",
        transition: "color 0.15s ease, background 0.15s ease",
        flexShrink: 0,
      }}
      onMouseEnter={(e) => {
        if (!copied) {
          e.currentTarget.style.color = "#4b5563";
          e.currentTarget.style.background = "#f3f4f6";
        }
      }}
      onMouseLeave={(e) => {
        if (!copied) {
          e.currentTarget.style.color = "#9ca3af";
          e.currentTarget.style.background = "transparent";
        }
      }}
      title={copied ? "Copied to clipboard!" : "Copy message"}
    >
      {copied ? <Check size={14} color="#16a34a" /> : <Copy size={14} />}
    </button>
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
              {!isUser && response && (
                <div style={{ display: "flex", justifyContent: "flex-start", marginTop: 6 }}>
                  <CopyMessageButton text={response} />
                </div>
              )}
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

// ── Relative time formatter ───────────────────────────────────────────────────

function formatRelativeTime(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    if (diffMs < 0) return "Just now";

    const diffMins = Math.floor(diffMs / (1000 * 60));
    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h`;

    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) return `${diffDays}d`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}w`;

    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const month = months[d.getMonth()];
    const day = d.getDate();
    return `${month} ${day}`;
  } catch {
    return "";
  }
}

// ── Session list item ─────────────────────────────────────────────────────────

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

  const title = session.title?.trim() || `Session #${session.id}`;
  const snippet = session.last_message?.trim() || "No messages yet";
  const timeFormatted = formatRelativeTime(session.updated_at || session.created_at);
  const hasMessages = (session.message_count ?? 0) > 0 || !!session.last_message;

  return (
    <div
      onClick={onSelect}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 8,
        padding: "8px 10px",
        borderRadius: 8,
        cursor: "pointer",
        background: isActive
          ? "rgba(0, 0, 0, 0.05)"
          : isHovered
          ? "rgba(0, 0, 0, 0.025)"
          : "transparent",
        transition: "background 0.15s ease",
        marginBottom: 2,
        position: "relative",
      }}
    >
      {/* Status checkmark icon on left */}
      <div style={{ paddingTop: 3, flexShrink: 0 }}>
        {hasMessages ? (
          <Check size={13} color="#16a34a" />
        ) : (
          <div style={{ width: 13, height: 13 }} />
        )}
      </div>

      {/* Main content: Title + Time (row 1), Snippet (row 2) */}
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 2 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6 }}>
          <span
            style={{
              fontSize: "0.81rem",
              fontWeight: isActive ? 600 : 500,
              color: isActive ? "#0f172a" : "#1e293b",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              flex: 1,
            }}
          >
            {title}
          </span>
          <span
            style={{
              fontSize: "0.71rem",
              color: "#94a3b8",
              flexShrink: 0,
            }}
          >
            {timeFormatted}
          </span>
        </div>

        <div
          style={{
            fontSize: "0.73rem",
            color: "#64748b",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            lineHeight: 1.35,
          }}
        >
          {snippet}
        </div>
      </div>

      {/* Hover action menu (3 dots) */}
      {(isHovered || menuOpen) && (
        <div
          ref={menuRef}
          onClick={(e) => e.stopPropagation()}
          style={{ position: "relative", flexShrink: 0, paddingTop: 1 }}
        >
          <button
            type="button"
            onClick={() => setMenuOpen(!menuOpen)}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: "2px",
              color: "#94a3b8",
              display: "flex",
              alignItems: "center",
              borderRadius: 4,
            }}
            title="Session options"
          >
            <MoreVertical size={13} />
          </button>
          {menuOpen && (
            <div
              style={{
                position: "absolute",
                right: 0,
                top: 20,
                background: "#ffffff",
                border: "1px solid #e2e8f0",
                borderRadius: 6,
                boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
                zIndex: 50,
                minWidth: 100,
                padding: 4,
              }}
            >
              <button
                type="button"
                onClick={(e) => {
                  setMenuOpen(false);
                  onDelete(e);
                }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  width: "100%",
                  padding: "5px 8px",
                  border: "none",
                  background: "none",
                  color: "#dc2626",
                  fontSize: "0.75rem",
                  cursor: "pointer",
                  borderRadius: 4,
                  textAlign: "left",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "#fee2e2")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
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

interface AgentChatPageProps {
  initialView?: "chat" | "customizations" | "logs";
}

export default function AgentChatPage({ initialView }: AgentChatPageProps = {}) {
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

  const isEditRoute = typeof window !== "undefined" && (window.location.pathname.endsWith("/edit") || window.location.pathname.endsWith("/customizations"));
  // View mode: chat, customizations, or logs
  const [mainView, setMainView] = useState<"chat" | "customizations" | "logs">(initialView ?? (isEditRoute ? "customizations" : "chat"));

  useEffect(() => {
    if (initialView) {
      setMainView(initialView);
    } else if (window.location.pathname.endsWith("/edit") || window.location.pathname.endsWith("/customizations")) {
      setMainView("customizations");
    }
  }, [initialView]);

  const { data: messages = [] } = useChatMessages(agentId, activeSessionId);
  const isResearchEngineAgent = (agent?.tools ?? []).some((tool) => ["fetch_research_proposal_history"].includes(tool.tool_name));
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
  // Sidebar state (resizable)
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    try {
      const saved = localStorage.getItem("agent_sidebar_width");
      if (saved) {
        const val = parseInt(saved, 10);
        if (!isNaN(val) && val >= 240 && val <= 600) return val;
      }
    } catch {}
    return 300; // Increased default width from 260 to 300
  });
  const [isResizingSidebar, setIsResizingSidebar] = useState(false);
  const resizeStartXRef = useRef(0);
  const resizeStartWidthRef = useRef(300);

  const startSidebarResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizingSidebar(true);
    resizeStartXRef.current = e.clientX;
    resizeStartWidthRef.current = sidebarWidth;
  }, [sidebarWidth]);

  useEffect(() => {
    if (!isResizingSidebar) return;

    const handleMouseMove = (e: MouseEvent) => {
      const delta = e.clientX - resizeStartXRef.current;
      const newWidth = Math.min(Math.max(resizeStartWidthRef.current + delta, 240), 600);
      setSidebarWidth(newWidth);
    };

    const handleMouseUp = (e: MouseEvent) => {
      setIsResizingSidebar(false);
      const delta = e.clientX - resizeStartXRef.current;
      const finalWidth = Math.min(Math.max(resizeStartWidthRef.current + delta, 240), 600);
      try {
        localStorage.setItem("agent_sidebar_width", String(finalWidth));
      } catch {}
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isResizingSidebar]);

  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [visibleSessionLimit, setVisibleSessionLimit] = useState(15);
  const [agentMenuOpen, setAgentMenuOpen] = useState(false);
  const agentMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (agentMenuRef.current && !agentMenuRef.current.contains(e.target as Node)) {
        setAgentMenuOpen(false);
      }
    }
    if (agentMenuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [agentMenuOpen]);

  const filteredSessions = useMemo(() => {
    if (!searchQuery.trim()) return sessions;
    const q = searchQuery.toLowerCase().trim();
    return sessions.filter((s) =>
      (s.title && s.title.toLowerCase().includes(q)) ||
      (s.last_message && s.last_message.toLowerCase().includes(q))
    );
  }, [sessions, searchQuery]);

  const visibleSessions = useMemo(() => {
    return filteredSessions.slice(0, visibleSessionLimit);
  }, [filteredSessions, visibleSessionLimit]);

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
    setMainView("chat");
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
      {/* ── Collapsed Rail (Width 48px) ── */}
      {isSidebarCollapsed && (
        <div
          style={{
            width: 48,
            borderRight: "1px solid var(--color-border, #e5e7eb)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            padding: "10px 0",
            background: "#ffffff",
            flexShrink: 0,
            zIndex: 10,
          }}
        >
          {/* Top: Expand sidebar button */}
          <button
            type="button"
            onClick={() => setIsSidebarCollapsed(false)}
            title="Expand sidebar"
            style={{
              width: 34,
              height: 34,
              borderRadius: 8,
              border: "none",
              background: "transparent",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#475569",
              marginBottom: 12,
              transition: "background 0.15s ease, color 0.15s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "#f1f5f9";
              e.currentTarget.style.color = "#0f172a";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color = "#475569";
            }}
          >
            <PanelLeftOpen size={16} />
          </button>

          {/* New Chat icon */}
          <button
            type="button"
            onClick={handleNewSession}
            disabled={isCreatingSession}
            title="New chat"
            style={{
              width: 34,
              height: 34,
              borderRadius: 8,
              border: "none",
              background: "transparent",
              cursor: isCreatingSession ? "not-allowed" : "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#475569",
              marginBottom: 6,
              transition: "background 0.15s ease",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "#f1f5f9")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          >
            {isCreatingSession ? <Loader2 size={16} className="spin" /> : <SquarePen size={16} />}
          </button>

          {/* Customizations icon */}
          <button
            type="button"
            onClick={() => setMainView("customizations")}
            title="Customizations"
            style={{
              width: 34,
              height: 34,
              borderRadius: 8,
              border: "none",
              background: mainView === "customizations" ? "#f1f5f9" : "transparent",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: mainView === "customizations" ? "#2563eb" : "#475569",
              marginBottom: 6,
              transition: "background 0.15s ease",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "#f1f5f9")}
            onMouseLeave={(e) => (e.currentTarget.style.background = mainView === "customizations" ? "#f1f5f9" : "transparent")}
          >
            <SlidersHorizontal size={16} />
          </button>

          {/* Session LLM Logs icon */}
          <button
            type="button"
            onClick={() => setMainView("logs")}
            disabled={!activeSessionId}
            title={activeSessionId ? "Session LLM Logs" : "Select a session to view logs"}
            style={{
              width: 34,
              height: 34,
              borderRadius: 8,
              border: "none",
              background: mainView === "logs" ? "#f1f5f9" : "transparent",
              cursor: !activeSessionId ? "not-allowed" : "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: mainView === "logs" ? "#2563eb" : (!activeSessionId ? "#cbd5e1" : "#475569"),
              marginBottom: 6,
              transition: "background 0.15s ease",
            }}
            onMouseEnter={(e) => {
              if (activeSessionId) e.currentTarget.style.background = "#f1f5f9";
            }}
            onMouseLeave={(e) => (e.currentTarget.style.background = mainView === "logs" ? "#f1f5f9" : "transparent")}
          >
            <Terminal size={16} />
          </button>

          {/* History icon — expands the sidebar to show chat list */}
          <button
            type="button"
            onClick={() => setIsSidebarCollapsed(false)}
            title="Chats history"
            style={{
              width: 34,
              height: 34,
              borderRadius: 8,
              border: "none",
              background: "transparent",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#475569",
              marginBottom: 6,
              transition: "background 0.15s ease",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "#f1f5f9")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          >
            <History size={16} />
          </button>

          {/* Spacer */}
          <div style={{ flex: 1 }} />

          {/* Bottom: Options (⋮) */}
          <div style={{ position: "relative" }} ref={agentMenuRef}>
            <button
              type="button"
              onClick={() => setAgentMenuOpen(!agentMenuOpen)}
              title="More options"
              style={{
                width: 34,
                height: 34,
                borderRadius: 8,
                border: "none",
                background: "transparent",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#64748b",
                transition: "background 0.15s ease",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "#f1f5f9")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <MoreVertical size={16} />
            </button>
            {agentMenuOpen && (
              <div
                style={{
                  position: "absolute",
                  left: "100%",
                  bottom: 0,
                  marginLeft: 6,
                  background: "#ffffff",
                  border: "1px solid #e2e8f0",
                  borderRadius: 8,
                  boxShadow: "0 4px 16px rgba(0,0,0,0.1)",
                  zIndex: 60,
                  minWidth: 160,
                  padding: 4,
                }}
              >
                <button
                  type="button"
                  onClick={() => {
                    setAgentMenuOpen(false);
                    setMainView("customizations");
                  }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    width: "100%",
                    padding: "7px 10px",
                    border: "none",
                    background: "transparent",
                    color: "#1e293b",
                    fontSize: "0.78rem",
                    cursor: "pointer",
                    borderRadius: 4,
                    textAlign: "left",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "#f8fafc")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                >
                  <Settings2 size={13} />
                  Agent Settings
                </button>
                {activeSessionId && (
                  <button
                    type="button"
                    onClick={() => {
                      setAgentMenuOpen(false);
                      setMainView("logs");
                    }}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      width: "100%",
                      padding: "7px 10px",
                      border: "none",
                      background: "transparent",
                      color: "#1e293b",
                      fontSize: "0.78rem",
                      cursor: "pointer",
                      borderRadius: 4,
                      textAlign: "left",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "#f8fafc")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  >
                    <Terminal size={13} />
                    Session LLM Logs
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Expanded Sessions Sidebar (Resizable) ── */}
      {!isSidebarCollapsed && (
        <div
          style={{
            width: sidebarWidth,
            minWidth: 240,
            maxWidth: 600,
            borderRight: "1px solid var(--color-border, #e5e7eb)",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            flexShrink: 0,
            background: "#ffffff",
            position: "relative",
            userSelect: isResizingSidebar ? "none" : "auto",
          }}
        >
          {/* Header Bar */}
          <div
            style={{
              padding: "14px 14px 10px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 8,
            }}
          >
            <span
              style={{
                fontWeight: 600,
                fontSize: "0.92rem",
                color: "#0f172a",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                letterSpacing: "-0.01em",
              }}
            >
              {agent?.name ?? "Agent"}
            </span>

            <div style={{ display: "flex", alignItems: "center", gap: 2 }}>
              {/* Collapse Icon */}
              <button
                type="button"
                onClick={() => setIsSidebarCollapsed(true)}
                title="Collapse sidebar"
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  padding: "4px",
                  borderRadius: 4,
                  color: "#64748b",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  transition: "color 0.15s ease, background 0.15s ease",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = "#0f172a";
                  e.currentTarget.style.background = "#f1f5f9";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = "#64748b";
                  e.currentTarget.style.background = "none";
                }}
              >
                <PanelLeftClose size={16} />
              </button>

              {/* Options Menu (⋮) */}
              <div style={{ position: "relative" }} ref={agentMenuRef}>
                <button
                  type="button"
                  onClick={() => setAgentMenuOpen(!agentMenuOpen)}
                  title="Agent options"
                  style={{
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    padding: "4px",
                    borderRadius: 4,
                    color: "#64748b",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    transition: "color 0.15s ease, background 0.15s ease",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.color = "#0f172a";
                    e.currentTarget.style.background = "#f1f5f9";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.color = "#64748b";
                    e.currentTarget.style.background = "none";
                  }}
                >
                  <MoreVertical size={16} />
                </button>
                {agentMenuOpen && (
                  <div
                    style={{
                      position: "absolute",
                      right: 0,
                      top: 24,
                      background: "#ffffff",
                      border: "1px solid #e2e8f0",
                      borderRadius: 8,
                      boxShadow: "0 4px 16px rgba(0,0,0,0.1)",
                      zIndex: 60,
                      minWidth: 160,
                      padding: 4,
                    }}
                  >
                    <button
                      type="button"
                      onClick={() => {
                        setAgentMenuOpen(false);
                        setMainView("customizations");
                      }}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        width: "100%",
                        padding: "7px 10px",
                        border: "none",
                        background: "transparent",
                        color: "#1e293b",
                        fontSize: "0.78rem",
                        cursor: "pointer",
                        borderRadius: 4,
                        textAlign: "left",
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = "#f8fafc")}
                      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                    >
                      <Settings2 size={13} />
                      Agent Settings
                    </button>
                    {activeSessionId && (
                      <button
                        type="button"
                        onClick={() => {
                          setAgentMenuOpen(false);
                          setMainView("logs");
                        }}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          width: "100%",
                          padding: "7px 10px",
                          border: "none",
                          background: "transparent",
                          color: "#1e293b",
                          fontSize: "0.78rem",
                          cursor: "pointer",
                          borderRadius: 4,
                          textAlign: "left",
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.background = "#f8fafc")}
                        onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                      >
                        <Terminal size={13} />
                        Session LLM Logs
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Navigation Action items: New chat, Customizations, Session Logs */}
          <div style={{ padding: "0 8px 8px", display: "flex", flexDirection: "column", gap: 1 }}>
            <button
              type="button"
              onClick={handleNewSession}
              disabled={isCreatingSession}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                width: "100%",
                padding: "7px 8px",
                border: "none",
                background: "transparent",
                color: "#1e293b",
                fontSize: "0.82rem",
                fontWeight: 500,
                cursor: isCreatingSession ? "not-allowed" : "pointer",
                borderRadius: 6,
                textAlign: "left",
                transition: "background 0.15s ease",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "#f1f5f9")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              {isCreatingSession ? <Loader2 size={15} className="spin" /> : <SquarePen size={15} color="#475569" />}
              <span>New chat</span>
            </button>

            <button
              type="button"
              onClick={() => setMainView("customizations")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                width: "100%",
                padding: "7px 8px",
                border: "none",
                background: mainView === "customizations" ? "rgba(0, 0, 0, 0.05)" : "transparent",
                color: mainView === "customizations" ? "#0f172a" : "#1e293b",
                fontSize: "0.82rem",
                fontWeight: mainView === "customizations" ? 600 : 500,
                cursor: "pointer",
                borderRadius: 6,
                textAlign: "left",
                transition: "background 0.15s ease",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "#f1f5f9")}
              onMouseLeave={(e) => (e.currentTarget.style.background = mainView === "customizations" ? "rgba(0, 0, 0, 0.05)" : "transparent")}
            >
              <SlidersHorizontal size={15} color={mainView === "customizations" ? "#2563eb" : "#475569"} />
              <span>Customizations</span>
            </button>

            {activeSessionId && (
              <button
                type="button"
                onClick={() => setMainView("logs")}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  width: "100%",
                  padding: "7px 8px",
                  border: "none",
                  background: mainView === "logs" ? "rgba(0, 0, 0, 0.05)" : "transparent",
                  color: mainView === "logs" ? "#0f172a" : "#1e293b",
                  fontSize: "0.82rem",
                  fontWeight: mainView === "logs" ? 600 : 500,
                  cursor: "pointer",
                  borderRadius: 6,
                  textAlign: "left",
                  transition: "background 0.15s ease",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "#f1f5f9")}
                onMouseLeave={(e) => (e.currentTarget.style.background = mainView === "logs" ? "rgba(0, 0, 0, 0.05)" : "transparent")}
              >
                <Terminal size={15} color={mainView === "logs" ? "#2563eb" : "#475569"} />
                <span>Session Logs</span>
              </button>
            )}
          </div>

          {/* Search chats input */}
          <div style={{ padding: "0 8px 10px" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                background: "#f1f5f9",
                borderRadius: 8,
                padding: "6px 10px",
              }}
            >
              <Search size={14} color="#94a3b8" />
              <input
                type="text"
                placeholder="Search chats"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  width: "100%",
                  border: "none",
                  outline: "none",
                  background: "transparent",
                  fontSize: "0.78rem",
                  color: "#1e293b",
                  lineHeight: 1.3,
                }}
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery("")}
                  style={{
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    padding: 0,
                    color: "#94a3b8",
                    display: "flex",
                    alignItems: "center",
                  }}
                >
                  <XIcon size={12} />
                </button>
              )}
            </div>
          </div>

          {/* Chat Sessions list */}
          <div className="sidebar-hover-scrollbar" style={{ flex: 1, padding: "0 6px 12px" }}>
            {isResearchEngineAgent && (
              <div style={{ margin: "4px 2px 10px", padding: "8px", border: "1px solid var(--color-border)", borderRadius: 8 }}>
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

            {visibleSessions.map((s) => (
              <SessionListItem
                key={s.id}
                session={s}
                isActive={activeSessionId === s.id}
                onSelect={() => selectSession(s.id)}
                onDelete={(e) => handleDeleteSession(e, s)}
              />
            ))}

            {filteredSessions.length === 0 && (
              <div style={{ padding: "24px 8px", fontSize: "0.75rem", color: "#94a3b8", textAlign: "center" }}>
                {searchQuery ? "No matching chats found" : "No chats yet"}
              </div>
            )}

            {filteredSessions.length > visibleSessionLimit && (
              <div style={{ padding: "8px 4px 4px", textAlign: "center" }}>
                <button
                  type="button"
                  onClick={() => setVisibleSessionLimit((prev) => prev + 15)}
                  style={{
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    color: "#64748b",
                    fontSize: "0.75rem",
                    fontWeight: 500,
                    padding: "4px 8px",
                    borderRadius: 4,
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = "#0f172a")}
                  onMouseLeave={(e) => (e.currentTarget.style.color = "#64748b")}
                >
                  Show more
                </button>
              </div>
            )}
          </div>

          {/* Draggable resize handle on right border */}
          <div
            onMouseDown={startSidebarResize}
            style={{
              position: "absolute",
              top: 0,
              right: -3,
              width: 6,
              height: "100%",
              cursor: "col-resize",
              zIndex: 50,
              background: isResizingSidebar ? "var(--color-primary, #2563eb)" : "transparent",
              transition: isResizingSidebar ? "none" : "background 0.2s ease",
            }}
            onMouseEnter={(e) => {
              if (!isResizingSidebar) {
                e.currentTarget.style.background = "rgba(37, 99, 235, 0.35)";
              }
            }}
            onMouseLeave={(e) => {
              if (!isResizingSidebar) {
                e.currentTarget.style.background = "transparent";
              }
            }}
          />
        </div>
      )}

      {/* ── Right-side area: Customizations vs Logs vs Chat ── */}
      {mainView === "customizations" && agentId ? (
        <AgentCustomizationsView agentId={agentId} onClose={() => setMainView("chat")} />
      ) : mainView === "logs" && agentId && activeSessionId ? (
        <SessionLlmLogsView
          agentId={agentId}
          agentName={agent?.name}
          sessionId={activeSessionId}
          onClose={() => setMainView("chat")}
        />
      ) : (
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
            {/* Chat Canvas Top-Right Action Bar */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "flex-end",
                padding: "10px 24px 0",
                flexShrink: 0,
              }}
            >
              <button
                type="button"
                onClick={() => setMainView("logs")}
                title="View LLM Call Logs for this session"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "5px 10px",
                  borderRadius: 6,
                  border: "1px solid #e2e8f0",
                  background: "#ffffff",
                  color: "#475569",
                  fontSize: "0.76rem",
                  fontWeight: 500,
                  cursor: "pointer",
                  boxShadow: "0 1px 2px rgba(0,0,0,0.03)",
                  transition: "all 0.15s ease",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "#f8fafc";
                  e.currentTarget.style.color = "#0f172a";
                  e.currentTarget.style.borderColor = "#cbd5e1";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "#ffffff";
                  e.currentTarget.style.color = "#475569";
                  e.currentTarget.style.borderColor = "#e2e8f0";
                }}
              >
                <Terminal size={13} color="#2563eb" />
                <span>LLM Logs</span>
              </button>
            </div>

            {/* Messages */}
            <div
              style={{
                flex: 1,
                overflowY: "auto",
                padding: "24px 24px 36px",
                display: "flex",
                justifyContent: "center",
              }}
            >
              <div
                style={{
                  width: "100%",
                  maxWidth: 780,
                  display: "flex",
                  flexDirection: "column",
                  gap: 20,
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
                      timelineSteps.push(st as any);
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
                        const stepIdRaw = mr?.updated_step ?? (m.tool_result.args as any)?.step_id;
                        const status = mr?.status ?? (m.tool_result.args as any)?.status;
                        if (stepIdRaw != null && status) {
                          stepStatusMap[Number(stepIdRaw)] = String(status);
                        }
                      }
                    });
                    
                    const computedSteps = steps.map((s: any, idx: number) => {
                      const id = Number(s.id ?? idx + 1);
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
                            defaultExpanded={false}
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

                      {/* In-Turn File/Asset Edit Badges */}
                      {(() => {
                        const turnEdits: TurnEditInfo[] = [];
                        const seenNames = new Set<string>();

                        turnItems.forEach((m) => {
                          if (m.role === "tool" && m.tool_result) {
                            const change = (m.tool_result as any).change;
                            if (change && change.full_name && !seenNames.has(change.full_name)) {
                              seenNames.add(change.full_name);
                              turnEdits.push({
                                change_id: change.change_id,
                                full_name: change.full_name,
                                object_type: change.object_type || "notebook",
                                additions: change.additions,
                                deletions: change.deletions,
                              });
                            } else if (
                              (m.tool_name === "create_notebook" ||
                                m.tool_name === "catalog_editor" ||
                                m.tool_name === "notebook_manager") &&
                              m.tool_result.ok
                            ) {
                              const res = m.tool_result.result as any;
                              const args = m.tool_result.args as any;
                              const fn =
                                res?.full_name ||
                                (args?.catalog_name && args?.schema_name && args?.notebook_name
                                  ? `${args.catalog_name}.${args.schema_name}.${args.notebook_name}`
                                  : null);
                              if (fn && !seenNames.has(fn)) {
                                seenNames.add(fn);
                                turnEdits.push({
                                  full_name: fn,
                                  object_type: (res?.object_type || args?.object_type || "notebook") as any,
                                });
                              }
                            }
                          }
                        });

                        if (turnEdits.length === 0) return null;
                        return (
                          <div style={{ marginTop: 8 }}>
                            <TurnEditBadge
                              edits={turnEdits}
                              agentId={agentId}
                              sessionId={activeSessionId}
                              onOpenDiff={(record) => setDiffSheetRecord(record as any)}
                            />
                          </div>
                        );
                      })()}

                      {/* Copy Button at the bottom of the entire response */}
                      {cleanFinalResponse && (
                        <div style={{ marginTop: 8, display: "flex", alignItems: "center" }}>
                          <CopyMessageButton text={cleanFinalResponse} />
                        </div>
                      )}
                    </div>
                  );
                });
              })()}
              <div ref={messagesEndRef} />
              </div>
            </div>

            {/* Unified Bottom Composer & Docked Panels */}
            {(() => {
              // 1. Check for active uncompleted plan to dock
              const createPlanMsg = [...messages].reverse().find((m) => m.role === "tool" && m.tool_name === "create_plan");
              let dockedPlanElement: React.ReactNode = null;

              if (createPlanMsg && createPlanMsg.tool_result) {
                const res = createPlanMsg.tool_result.result as any;
                const args = createPlanMsg.tool_result.args as any;
                const stepsData = args?.steps || res?.steps || [];
                const goalData = args?.goal || res?.goal || "Execution Plan";
                const planIdData = res?.plan_id || "plan";

                // Compute live step status map
                const stepStatusMap: Record<number, string> = {};
                messages.forEach((m) => {
                  if (m.role === "tool" && m.tool_name === "mark_step" && m.tool_result) {
                    const r = m.tool_result.result as any;
                    const stepIdRaw = r?.updated_step ?? (m.tool_result.args as any)?.step_id;
                    const status = r?.status ?? (m.tool_result.args as any)?.status;
                    if (stepIdRaw != null && status) {
                      stepStatusMap[Number(stepIdRaw)] = String(status);
                    }
                  }
                });
                streamingSteps.forEach((st) => {
                  if (st.type === "tool" && st.name === "mark_step" && st.result) {
                    const r = st.result as any;
                    const stepIdRaw = r?.updated_step ?? st.args?.step_id;
                    const status = r?.status ?? st.args?.status;
                    if (stepIdRaw != null && status) {
                      stepStatusMap[Number(stepIdRaw)] = String(status);
                    }
                  }
                });

                const mappedSteps = stepsData.map((s: any, idx: number) => {
                  const stepId = Number(s.id ?? idx + 1);
                  return {
                    id: stepId,
                    description: s.description ?? s.text ?? "",
                    status: stepStatusMap[stepId] || s.status || "pending",
                    verification: s.verification ?? "Automatic check",
                    corrections: s.corrections ?? [],
                    attempts: s.attempts ?? 1,
                  };
                });

                const isAllDone = mappedSteps.length > 0 && mappedSteps.every((s: any) => s.status === "done");

                if (!isAllDone) {
                  const isPlanApproved = Boolean(
                    res?.approved_at ||
                    streamingSteps.some((st) => st.type === "tool" && (st.name === "mark_step" || st.name === "get_next_step")) ||
                    messages.some((m) => {
                      if (m.role === "tool" && (m.tool_name === "mark_step" || m.tool_name === "get_next_step")) return true;
                      if (m.role === "user" && m.content) {
                        const lower = m.content.toLowerCase().trim();
                        return (
                          lower.startsWith("approved") ||
                          lower.startsWith("approve") ||
                          lower.startsWith("proceed") ||
                          lower.startsWith("go ahead") ||
                          lower.startsWith("yes") ||
                          lower.includes("approved") ||
                          lower.includes("execute the plan")
                        );
                      }
                      return false;
                    })
                  );

                  dockedPlanElement = (
                    <PlanTaskViewer
                      isDocked={true}
                      defaultExpanded={!isPlanApproved}
                      plan={{
                        plan_id: planIdData,
                        agent_id: "agent",
                        goal: goalData,
                        steps: mappedSteps,
                        approved_at: isPlanApproved ? (res?.approved_at || new Date().toISOString()) : null,
                        execution_approved_at: res?.execution_approved_at,
                      }}
                      onApprovePlan={() => sendMessage("Approved. Proceed to execute the plan.")}
                      onRejectPlan={() => sendMessage("Plan rejected. Re-evaluate the requirements and propose a different approach.")}
                      onRequestChange={(feedback) => sendMessage(`Plan changes requested: ${feedback}`)}
                    />
                  );
                }
              }

              return (
                <div
                  style={{
                    borderTop: "none",
                    padding: "0 24px 16px",
                    display: "flex",
                    justifyContent: "center",
                  }}
                >
                  <div
                    style={{
                      width: "100%",
                      maxWidth: 780,
                      display: "flex",
                      flexDirection: "column",
                      background: "#ffffff",
                      border: "1px solid var(--color-border, #e5e7eb)",
                      borderRadius: "16px",
                      overflow: "hidden",
                      boxShadow: "0 1px 3px rgba(0, 0, 0, 0.03)",
                    }}
                  >
                    {/* 1. Docked Plan (Top of Composer Card, slightly gray background) */}
                    {dockedPlanElement}

                    {/* 2. Docked Session Changes Panel (Middle/Top of Composer Card, slightly gray background) */}
                    {agentId && activeSessionId && (
                      <SessionChangesDock
                        isDocked={true}
                        agentId={agentId}
                        sessionId={activeSessionId}
                        refreshTrigger={messages.length}
                        onOpenDiff={(record) => setDiffSheetRecord(record as any)}
                      />
                    )}

                    {/* 3. Input Composer (Bottom of Composer Card, pure white background) */}
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        background: "#ffffff",
                        padding: "10px 14px",
                        gap: 8,
                      }}
                    >
                      {/* Hidden file input */}
                      <input
                        ref={fileInputRef}
                        type="file"
                        multiple
                        accept=".pdf,.docx,.xlsx,.csv,.txt,.md,.json,.png,.jpg,.jpeg,.webp,.gif,.svg,image/*"
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
      )}

      {/* G7: DiffSheet side-panel — fixed overlay outside layout */}
      <DiffSheet record={diffSheetRecord} onClose={() => setDiffSheetRecord(null)} />
    </div>
  );
}


