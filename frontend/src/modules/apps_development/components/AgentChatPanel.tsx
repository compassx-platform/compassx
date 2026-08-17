import React, {
  useState,
  useEffect,
  useRef,
  useCallback,
  type KeyboardEvent,
} from "react";
import {
  Bot,
  Send,
  Square,
  Plus,
  ChevronDown,
  Wrench,
  CheckCircle,
  XCircle,
  ChevronRight,
  Trash2,
  Zap,
} from "lucide-react";
import { useAppChat, type LiveMessage, type LiveToolCall } from "../hooks/useAppChat";
import { useLLMConnections } from "../hooks/useLLMConnections";
import type { AppChatSession } from "../hooks/useAppChat";

interface Props {
  appId: string;
  branchId: string;
}

// ─── Markdown-light renderer ──────────────────────────────────────────────────
function renderMarkdown(text: string): React.ReactNode {
  // Split into paragraphs on double newlines
  const paragraphs = text.split(/\n\n+/);
  return paragraphs.map((para, i) => {
    // Code block
    if (para.startsWith("```")) {
      const lines = para.split("\n");
      const lang = lines[0].slice(3).trim();
      const code = lines.slice(1, lines[lines.length - 1] === "```" ? -1 : undefined).join("\n");
      return (
        <pre key={i} style={{ background: "var(--color-surface-hover)", borderRadius: 6, padding: "10px 12px", overflowX: "auto", margin: "6px 0", fontSize: 12, border: "1px solid var(--color-border)" }}>
          {lang && <span style={{ color: "var(--color-text-muted)", fontSize: 10, display: "block", marginBottom: 4 }}>{lang}</span>}
          <code>{code}</code>
        </pre>
      );
    }
    // Inline code + bold with line breaks
    const inline = para.split("\n").map((line, j) => {
      const parts = line.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
      return (
        <React.Fragment key={j}>
          {parts.map((part, k) => {
            if (part.startsWith("`") && part.endsWith("`"))
              return <code key={k} style={{ background: "var(--color-surface-hover)", padding: "1px 4px", borderRadius: 3, fontSize: 12 }}>{part.slice(1, -1)}</code>;
            if (part.startsWith("**") && part.endsWith("**"))
              return <strong key={k}>{part.slice(2, -2)}</strong>;
            return part;
          })}
          {j < para.split("\n").length - 1 && <br />}
        </React.Fragment>
      );
    });
    return <p key={i} style={{ margin: "4px 0" }}>{inline}</p>;
  });
}

// ─── ToolCallCard ─────────────────────────────────────────────────────────────
function ToolCallCard({ tc }: { tc: LiveToolCall }) {
  const [open, setOpen] = useState(false);

  const icons: Record<string, string> = {
    read_file: "📄",
    write_file: "✏️",
    list_files: "📁",
    delete_file: "🗑️",
    rename_file: "↔️",
  };

  const mainArg =
    (tc.args?.path as string) ||
    (tc.args?.old_path as string) ||
    (tc.args?.directory as string) ||
    "";

  return (
    <div
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 8,
        margin: "6px 0",
        fontSize: 12,
        overflow: "hidden",
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "6px 10px",
          background: "transparent",
          border: "none",
          cursor: "pointer",
          color: "var(--color-text)",
          textAlign: "left",
        }}
      >
        <span>{icons[tc.tool_name] ?? <Wrench size={12} />}</span>
        <span style={{ fontWeight: 600, color: "var(--color-primary)" }}>{tc.tool_name}</span>
        {mainArg && (
          <span style={{ color: "var(--color-text-muted)", fontFamily: "monospace" }}>
            {mainArg.length > 40 ? "…" + mainArg.slice(-38) : mainArg}
          </span>
        )}
        <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 4 }}>
          {tc.done ? (
            tc.ok ? (
              <CheckCircle size={12} color="var(--color-success)" />
            ) : (
              <XCircle size={12} color="var(--color-danger)" />
            )
          ) : (
            <div className="spin" style={{ width: 12, height: 12, border: "2px solid var(--color-border)", borderTopColor: "var(--color-primary)", borderRadius: "50%" }} />
          )}
          <ChevronRight
            size={12}
            style={{ transform: open ? "rotate(90deg)" : "none", transition: "transform 0.15s", color: "var(--color-text-muted)" }}
          />
        </span>
      </button>

      {open && tc.done && (
        <div
          style={{
            borderTop: "1px solid var(--color-border)",
            padding: "8px 10px",
            color: "var(--color-text-muted)",
            overflowX: "auto",
          }}
        >
          {tc.ok ? (
            <pre style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-all", fontSize: 11 }}>
              {tc.result?.content
                ? String(tc.result.content).slice(0, 2000) + (String(tc.result.content).length > 2000 ? "\n…(truncated)" : "")
                : JSON.stringify(tc.result, null, 2)}
            </pre>
          ) : (
            <span style={{ color: "var(--color-danger)" }}>{tc.error ?? "Tool failed"}</span>
          )}
        </div>
      )}
    </div>
  );
}

// ─── MessageBubble ────────────────────────────────────────────────────────────
function MessageBubble({ msg }: { msg: LiveMessage }) {
  const isUser = msg.role === "user";
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: isUser ? "flex-end" : "flex-start",
        gap: 4,
      }}
    >
      {!isUser && (
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
          <div
            style={{
              width: 20,
              height: 20,
              background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
              borderRadius: 6,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <Zap size={11} color="white" />
          </div>
          <span style={{ fontSize: 11, fontWeight: 600, color: "var(--color-text-muted)" }}>
            CompassX AI
          </span>
        </div>
      )}

      {/* Tool calls */}
      {msg.toolCalls.length > 0 && (
        <div style={{ width: "100%" }}>
          {msg.toolCalls.map((tc) => (
            <ToolCallCard key={tc.id} tc={tc} />
          ))}
        </div>
      )}

      {/* Text content */}
      {(msg.content || msg.isStreaming) && (
        <div
          style={{
            maxWidth: "88%",
            padding: isUser ? "8px 12px" : "10px 12px",
            borderRadius: isUser ? "14px 14px 4px 14px" : "4px 14px 14px 14px",
            background: isUser
              ? "linear-gradient(135deg, #6366f1, #4f46e5)"
              : "var(--color-surface)",
            color: isUser ? "#fff" : "var(--color-text)",
            fontSize: 13,
            lineHeight: 1.6,
            border: isUser ? "none" : "1px solid var(--color-border)",
          }}
        >
          {isUser ? (
            msg.content
          ) : (
            <>
              {renderMarkdown(msg.content)}
              {msg.isStreaming && (
                <span
                  style={{
                    display: "inline-block",
                    width: 2,
                    height: "1em",
                    background: "var(--color-primary)",
                    marginLeft: 2,
                    animation: "blink 1s step-end infinite",
                    verticalAlign: "text-bottom",
                  }}
                />
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ─── SessionItem ──────────────────────────────────────────────────────────────
function SessionItem({
  session,
  active,
  onSelect,
  onDelete,
}: {
  session: AppChatSession;
  active: boolean;
  onSelect: () => void;
  onDelete: () => void;
}) {
  const [hover, setHover] = useState(false);
  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        padding: "5px 10px",
        borderRadius: 6,
        cursor: "pointer",
        background: active ? "var(--color-primary-bg)" : hover ? "var(--color-surface-hover)" : "transparent",
        color: active ? "var(--color-primary)" : "var(--color-text)",
        fontSize: 12,
      }}
      onClick={onSelect}
    >
      <Bot size={13} style={{ flexShrink: 0, opacity: 0.7 }} />
      <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {session.title ?? "New conversation"}
      </span>
      {hover && (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onDelete(); }}
          style={{ background: "transparent", border: "none", cursor: "pointer", padding: 2, color: "var(--color-danger)", borderRadius: 4, display: "flex" }}
        >
          <Trash2 size={11} />
        </button>
      )}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function AgentChatPanel({ appId, branchId }: Props) {
  const [llmConnectionId, setLlmConnectionId] = useState<number | null>(null);
  const [input, setInput] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const { connections } = useLLMConnections();
  const {
    sessions,
    activeSessionId,
    messages,
    liveMessages,
    isStreaming,
    loadingMessages,
    sendMessage,
    stopStreaming,
    newSession,
    switchSession,
    removeSession,
    setLiveMessages,
  } = useAppChat(appId, branchId, llmConnectionId);

  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [liveMessages, messages]);

  // Auto-pick first LLM connection
  useEffect(() => {
    if (connections.length > 0 && llmConnectionId === null) {
      const fallback = connections.find((c) => c.is_fallback) ?? connections[0];
      setLlmConnectionId(fallback.id);
    }
  }, [connections, llmConnectionId]);

  // When switching sessions, seed liveMessages from persisted messages
  useEffect(() => {
    if (!loadingMessages && messages.length > 0) {
      const live: LiveMessage[] = messages
        .filter((m) => m.role === "user" || m.role === "assistant")
        .map((m) => ({
          role: m.role as "user" | "assistant",
          content: m.content ?? "",
          isStreaming: false,
          toolCalls: [],
        }));
      setLiveMessages(live);
    } else if (!loadingMessages && messages.length === 0) {
      setLiveMessages([]);
    }
  }, [messages, loadingMessages, setLiveMessages]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isStreaming) return;
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "38px";
    }
    await sendMessage(text);
  }, [input, isStreaming, sendMessage]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    // Auto-grow
    e.target.style.height = "38px";
    e.target.style.height = Math.min(e.target.scrollHeight, 140) + "px";
  };

  const activeSessions = sessions;

  return (
    <div
      id="agent-chat-panel"
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        background: "var(--color-bg)",
        position: "relative",
      }}
    >
      {/* ── Session sidebar overlay ── */}
      {sidebarOpen && (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            zIndex: 10,
            background: "var(--color-bg)",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div style={{ padding: "12px 12px 8px", borderBottom: "1px solid var(--color-border)", display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 600, flex: 1 }}>Conversations</span>
            <button
              type="button"
              onClick={async () => { await newSession(); setSidebarOpen(false); }}
              style={{ background: "var(--color-primary)", color: "#fff", border: "none", borderRadius: 6, padding: "4px 10px", fontSize: 12, cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}
            >
              <Plus size={12} /> New
            </button>
            <button
              type="button"
              onClick={() => setSidebarOpen(false)}
              style={{ background: "transparent", border: "1px solid var(--color-border)", borderRadius: 6, padding: "4px 8px", fontSize: 12, cursor: "pointer", color: "var(--color-text-muted)" }}
            >
              Close
            </button>
          </div>
          <div style={{ flex: 1, overflowY: "auto", padding: "6px" }}>
            {activeSessions.length === 0 ? (
              <div style={{ padding: "20px", textAlign: "center", color: "var(--color-text-muted)", fontSize: 12 }}>
                No conversations yet
              </div>
            ) : (
              activeSessions.map((s) => (
                <SessionItem
                  key={s.id}
                  session={s}
                  active={s.id === activeSessionId}
                  onSelect={() => { switchSession(s.id); setSidebarOpen(false); }}
                  onDelete={() => removeSession(s.id)}
                />
              ))
            )}
          </div>
        </div>
      )}

      {/* ── Header ── */}
      <div
        style={{
          padding: "8px 12px",
          borderBottom: "1px solid var(--color-border)",
          display: "flex",
          alignItems: "center",
          gap: 8,
          flexShrink: 0,
          background: "var(--color-surface)",
        }}
      >
        <div
          style={{
            width: 24,
            height: 24,
            background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
            borderRadius: 7,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <Zap size={13} color="white" />
        </div>
        <span style={{ fontSize: 13, fontWeight: 700, color: "var(--color-text)" }}>
          CompassX AI
        </span>

        {/* LLM Connection picker */}
        {connections.length > 0 && (
          <select
            id="llm-connection-select"
            value={llmConnectionId ?? ""}
            onChange={(e) => setLlmConnectionId(Number(e.target.value) || null)}
            style={{
              marginLeft: "auto",
              background: "var(--color-surface-hover)",
              border: "1px solid var(--color-border)",
              borderRadius: 6,
              padding: "3px 6px",
              fontSize: 11,
              color: "var(--color-text)",
              cursor: "pointer",
              maxWidth: 140,
            }}
          >
            {connections.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        )}

        {/* Session list button */}
        <button
          type="button"
          id="sessions-list-btn"
          onClick={() => setSidebarOpen(true)}
          title="View conversations"
          style={{
            background: "transparent",
            border: "1px solid var(--color-border)",
            borderRadius: 6,
            padding: "3px 7px",
            cursor: "pointer",
            color: "var(--color-text-muted)",
            display: "flex",
            alignItems: "center",
            gap: 3,
            fontSize: 11,
          }}
        >
          <ChevronDown size={11} />
          {sessions.length > 0 && sessions.length}
        </button>

        {/* New session */}
        <button
          type="button"
          id="new-chat-session-btn"
          onClick={newSession}
          title="New conversation"
          style={{
            background: "transparent",
            border: "1px solid var(--color-border)",
            borderRadius: 6,
            padding: "3px 6px",
            cursor: "pointer",
            color: "var(--color-text-muted)",
            display: "flex",
          }}
        >
          <Plus size={13} />
        </button>
      </div>

      {/* ── Message list ── */}
      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "12px",
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}
      >
        {loadingMessages && (
          <div style={{ textAlign: "center", color: "var(--color-text-muted)", fontSize: 12, padding: 20 }}>
            Loading conversation…
          </div>
        )}

        {!loadingMessages && liveMessages.length === 0 && (
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 12,
              padding: 24,
              textAlign: "center",
            }}
          >
            <div
              style={{
                width: 48,
                height: 48,
                background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                borderRadius: 14,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Zap size={24} color="white" />
            </div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700, color: "var(--color-text)", marginBottom: 6 }}>
                CompassX AI
              </div>
              <div style={{ fontSize: 12, color: "var(--color-text-muted)", lineHeight: 1.6 }}>
                Ask me to build features, fix bugs, refactor code, or explain how anything works.
                I can read and edit any file in your workspace.
              </div>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, justifyContent: "center" }}>
              {[
                "Add a dark mode toggle",
                "Create a REST API endpoint",
                "Fix TypeScript errors",
                "Explain how auth works",
              ].map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => { setInput(prompt); textareaRef.current?.focus(); }}
                  style={{
                    background: "var(--color-surface)",
                    border: "1px solid var(--color-border)",
                    borderRadius: 8,
                    padding: "5px 10px",
                    fontSize: 11,
                    cursor: "pointer",
                    color: "var(--color-text)",
                    transition: "all 0.15s",
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--color-primary)"; e.currentTarget.style.color = "var(--color-primary)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--color-border)"; e.currentTarget.style.color = "var(--color-text)"; }}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        {liveMessages.map((msg, i) => (
          <MessageBubble key={i} msg={msg} />
        ))}
      </div>

      {/* ── Composer ── */}
      <div
        style={{
          padding: "10px 12px",
          borderTop: "1px solid var(--color-border)",
          background: "var(--color-surface)",
          flexShrink: 0,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "flex-end",
            gap: 8,
            background: "var(--color-bg)",
            border: "1px solid var(--color-border)",
            borderRadius: 10,
            padding: "6px 8px 6px 12px",
            transition: "border-color 0.15s",
          }}
          onFocus={() => {}}
        >
          <textarea
            ref={textareaRef}
            id="chat-composer"
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder="Ask CompassX AI to build, fix, or explain…"
            disabled={isStreaming}
            rows={1}
            style={{
              flex: 1,
              background: "transparent",
              border: "none",
              outline: "none",
              resize: "none",
              fontSize: 13,
              color: "var(--color-text)",
              lineHeight: 1.5,
              height: "38px",
              minHeight: "38px",
              maxHeight: "140px",
              padding: 0,
              fontFamily: "inherit",
            }}
          />
          <div style={{ display: "flex", alignItems: "center", gap: 4, flexShrink: 0 }}>
            {isStreaming ? (
              <button
                type="button"
                id="stop-stream-btn"
                onClick={stopStreaming}
                style={{
                  background: "var(--color-danger)",
                  color: "#fff",
                  border: "none",
                  borderRadius: 7,
                  width: 32,
                  height: 32,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Square size={13} fill="white" />
              </button>
            ) : (
              <button
                type="button"
                id="send-message-btn"
                onClick={handleSend}
                disabled={!input.trim()}
                style={{
                  background: input.trim() ? "linear-gradient(135deg, #6366f1, #4f46e5)" : "var(--color-surface-hover)",
                  color: input.trim() ? "#fff" : "var(--color-text-muted)",
                  border: "none",
                  borderRadius: 7,
                  width: 32,
                  height: 32,
                  cursor: input.trim() ? "pointer" : "default",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  transition: "all 0.15s",
                }}
              >
                <Send size={13} />
              </button>
            )}
          </div>
        </div>
        <div style={{ fontSize: 10, color: "var(--color-text-muted)", marginTop: 5, paddingLeft: 2 }}>
          Enter to send · Shift+Enter for new line
        </div>
      </div>

      <style>{`
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
        @keyframes spin { to { transform: rotate(360deg); } }
        .spin { animation: spin 0.8s linear infinite; }
      `}</style>
    </div>
  );
}

