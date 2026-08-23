import React, { useState, useMemo, useEffect, useRef } from "react";
import {
  Terminal,
  Loader2,
  RefreshCw,
  MessageSquare,
  Eye,
  Search,
  X,
  Copy,
  Check,
  ChevronRight,
  ChevronLeft,
  Wrench,
  Sparkles,
  Bot,
  Code2,
  FileCode,
  MessageCircle,
  Cpu,
  ArrowRight,
} from "lucide-react";
import {
  useLlmCallLogs,
  useLlmCallLogDetail,
  type LlmCallLogListItem,
  type LlmCallLogDetail,
} from "@/modules/agents/hooks/useLlmCalls";
import { AppTable, type AppTableColumn } from "@/components/common/AppTable";

interface SessionLlmLogsViewProps {
  agentId: number;
  agentName?: string;
  sessionId: number;
  onClose: () => void;
}

export const SessionLlmLogsView: React.FC<SessionLlmLogsViewProps> = ({
  agentId,
  agentName,
  sessionId,
  onClose,
}) => {
  const [selectedCallId, setSelectedCallId] = useState<number | null>(null);
  const [searchFilter, setSearchFilter] = useState("");

  const {
    data: logs = [],
    isLoading,
    isFetching,
    refetch,
  } = useLlmCallLogs({
    agent_id: agentId,
    session_id: sessionId,
    limit: 100,
  });

  const totalInputTokens = logs.reduce((acc, log) => acc + (log.input_tokens || 0), 0);
  const totalOutputTokens = logs.reduce((acc, log) => acc + (log.output_tokens || 0), 0);
  const totalTokens = totalInputTokens + totalOutputTokens;

  // Sort calls in increasing sequence order
  const sortedLogs = useMemo(() => {
    return [...logs].sort((a, b) => a.call_sequence_number - b.call_sequence_number);
  }, [logs]);

  const filteredLogs = useMemo(() => {
    if (!searchFilter.trim()) return sortedLogs;
    const q = searchFilter.toLowerCase();
    return sortedLogs.filter((log) => (
      log.model.toLowerCase().includes(q) ||
      (log.summary && log.summary.toLowerCase().includes(q)) ||
      String(log.call_sequence_number).includes(q)
    ));
  }, [sortedLogs, searchFilter]);

  const columns: AppTableColumn<LlmCallLogListItem>[] = useMemo(
    () => [
      {
        key: "seq",
        header: "Seq #",
        width: "70px",
        render: (log) => (
          <span style={{ fontWeight: 600, color: "#0f172a" }}>
            #{log.call_sequence_number}
          </span>
        ),
      },
      {
        key: "summary",
        header: "Response / Tool Summary",
        render: (log) => (
          <span
            style={{
              color: "var(--color-text, #334155)",
              fontSize: "0.78rem",
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}
          >
            {log.summary || "-"}
          </span>
        ),
      },
      {
        key: "model",
        header: "Model",
        width: "150px",
        render: (log) => (
          <code
            style={{
              fontSize: "0.75rem",
              background: "var(--color-bg-light, #f1f5f9)",
              padding: "2px 6px",
              borderRadius: 4,
              color: "var(--color-text, #0f172a)",
            }}
          >
            {log.model}
          </code>
        ),
      },
      {
        key: "tokens",
        header: "Tokens (I / O)",
        width: "130px",
        render: (log) => (
          <span style={{ fontSize: "0.76rem", color: "var(--color-text-muted, #64748b)" }}>
            {(log.input_tokens ?? 0).toLocaleString()} / {(log.output_tokens ?? 0).toLocaleString()}
          </span>
        ),
      },
      {
        key: "created_at",
        header: "Time",
        width: "80px",
        render: (log) => (
          <span style={{ fontSize: "0.74rem", color: "var(--color-text-muted, #64748b)" }}>
            {new Date(log.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </span>
        ),
      },
      {
        key: "actions",
        header: "",
        width: "45px",
        align: "right",
        render: (log) => (
          <button
            type="button"
            className="btn-icon"
            onClick={(e) => {
              e.stopPropagation();
              setSelectedCallId(log.id);
            }}
            title="Inspect Call"
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 26,
              height: 26,
              borderRadius: 4,
              border: "none",
              background: "transparent",
              cursor: "pointer",
              color: "#64748b",
            }}
          >
            <Eye size={13} />
          </button>
        ),
      },
    ],
    []
  );

  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        height: "100%",
        background: "#ffffff",
        overflow: "hidden",
      }}
    >
      {/* Clean Single-Row Top Toolbar */}
      <div
        style={{
          padding: "10px 20px 0",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          flexShrink: 0,
          background: "#ffffff",
        }}
      >
        {/* Left: Session Badge & Token Metrics */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0, flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <Terminal size={14} color="#2563eb" />
            <span style={{ fontSize: "0.82rem", fontWeight: 600, color: "#0f172a" }}>
              Session #{sessionId} Logs
            </span>
          </div>

          <div style={{ height: 12, width: 1, background: "#e2e8f0" }} />

          <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.75rem", color: "#64748b" }}>
            <span><strong>{logs.length}</strong> calls</span>
            <span>·</span>
            <span><strong>{totalTokens.toLocaleString()}</strong> tokens ({totalInputTokens.toLocaleString()} in / {totalOutputTokens.toLocaleString()} out)</span>
          </div>
        </div>

        {/* Right: Search, Refresh, and Clean Chat button */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
          {logs.length > 0 && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                background: "#f1f5f9",
                borderRadius: 6,
                padding: "3px 8px",
                width: 170,
              }}
            >
              <Search size={12} color="#94a3b8" />
              <input
                type="text"
                placeholder="Filter calls…"
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                style={{
                  border: "none",
                  background: "transparent",
                  fontSize: "0.74rem",
                  outline: "none",
                  width: "100%",
                }}
              />
            </div>
          )}

          {/* Icon-only Refresh button */}
          <button
            type="button"
            onClick={() => refetch()}
            disabled={isFetching}
            title={isFetching ? "Refreshing…" : "Refresh logs"}
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 28,
              height: 28,
              borderRadius: 6,
              border: "1px solid #e2e8f0",
              background: "#ffffff",
              color: "#475569",
              cursor: isFetching ? "not-allowed" : "pointer",
              boxShadow: "0 1px 2px rgba(0,0,0,0.03)",
              transition: "all 0.15s ease",
            }}
            onMouseEnter={(e) => {
              if (!isFetching) {
                e.currentTarget.style.background = "#f8fafc";
                e.currentTarget.style.color = "#0f172a";
                e.currentTarget.style.borderColor = "#cbd5e1";
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "#ffffff";
              e.currentTarget.style.color = "#475569";
              e.currentTarget.style.borderColor = "#e2e8f0";
            }}
          >
            <RefreshCw size={13} className={isFetching ? "spin" : ""} color="#64748b" />
          </button>

          {/* Clean Chat button matching the top-right chat canvas button */}
          <button
            type="button"
            onClick={onClose}
            title="Chat"
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
            <MessageSquare size={13} color="#2563eb" />
            <span>Chat</span>
          </button>
        </div>
      </div>

      {/* Main Content Area: Standard AppTable */}
      <div style={{ flex: 1, overflowY: "auto", padding: "16px 20px 32px" }}>
        <AppTable<LlmCallLogListItem>
          columns={columns}
          rows={filteredLogs}
          rowKey={(log) => log.id}
          isLoading={isLoading}
          onRowClick={(log) => setSelectedCallId(log.id)}
          emptyText={
            <div style={{ padding: "40px 0", textAlign: "center", color: "#94a3b8" }}>
              <Terminal size={32} style={{ opacity: 0.25, margin: "0 auto 8px" }} />
              <div style={{ fontSize: "0.85rem", fontWeight: 500, color: "#64748b" }}>
                {searchFilter ? "No matching calls found" : "No LLM calls recorded for this session yet"}
              </div>
            </div>
          }
        />
      </div>

      {/* Side Sheet: Chronological Execution Timeline Inspector */}
      {selectedCallId && (
        <LlmCallDetailSheet
          callId={selectedCallId}
          allLogs={sortedLogs}
          onSelectCallId={setSelectedCallId}
          onClose={() => setSelectedCallId(null)}
        />
      )}
    </div>
  );
};

// ── Copy Button Helper ─────────────────────────────────────────────────────────

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      title="Copy to clipboard"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: "2px 6px",
        borderRadius: 4,
        border: "1px solid #e2e8f0",
        background: "#ffffff",
        color: copied ? "#16a34a" : "#64748b",
        fontSize: "0.7rem",
        cursor: "pointer",
        transition: "all 0.15s ease",
      }}
    >
      {copied ? <Check size={11} /> : <Copy size={11} />}
      <span>{copied ? "Copied" : "Copy"}</span>
    </button>
  );
}

// ── Side Sheet: Chronological Tree Timeline for a Call ────────────────────────

interface LlmCallDetailSheetProps {
  callId: number;
  allLogs: LlmCallLogListItem[];
  onSelectCallId: (id: number) => void;
  onClose: () => void;
}

function LlmCallDetailSheet({
  callId,
  allLogs,
  onSelectCallId,
  onClose,
}: LlmCallDetailSheetProps) {
  const { data: detail, isLoading, error } = useLlmCallLogDetail(callId);
  const [rawView, setRawView] = useState(false);
  const sheetRef = useRef<HTMLDivElement>(null);

  // Find index and sibling calls for easy multi-call stepping
  const currentIndex = allLogs.findIndex((l) => l.id === callId);
  const prevLog = currentIndex > 0 ? allLogs[currentIndex - 1] : null;
  const nextLog = currentIndex < allLogs.length - 1 ? allLogs[currentIndex + 1] : null;

  // Optional: fetch next call detail if nextLog exists so we can display tool execution results seamlessly
  const { data: nextCallDetail } = useLlmCallLogDetail(nextLog?.id ?? 0);

  // Expanded nodes inside the chronological timeline - collapsed by default
  const [expandedItems, setExpandedItems] = useState<Record<string, boolean>>({});

  useEffect(() => {
    // Reset all nodes to collapsed whenever inspecting a different call
    setExpandedItems({});
  }, [callId]);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const toggleItem = (key: string) => {
    setExpandedItems((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const formatJsonOrText = (val: any) => {
    if (!val) return "";
    if (typeof val === "string") return val;
    try {
      return JSON.stringify(val, null, 2);
    } catch {
      return String(val);
    }
  };

  const messageCount = detail?.message_history?.length ?? 0;
  const hasToolCalls = (detail?.response_tool_calls?.length ?? 0) > 0;
  const hasSkills = (detail?.skills_injected?.length ?? 0) > 0;
  const toolsCount = detail?.tools_available?.length ?? 0;

  // Filter input messages to exclude this call's own response/tool outputs if present in legacy logs
  const inputMessages = useMemo(() => {
    if (!detail?.message_history) return [];
    const toolCallIds = new Set((detail.response_tool_calls || []).map((tc: any) => tc.id));
    return detail.message_history.filter((m: any) => {
      if (m.role === "assistant" && m.tool_calls && m.tool_calls.some((tc: any) => toolCallIds.has(tc.id))) {
        return false;
      }
      if (m.role === "tool" && toolCallIds.has(m.tool_call_id)) {
        return false;
      }
      return true;
    });
  }, [detail]);

  const expandAll = () => {
    const next: Record<string, boolean> = {
      context: true,
      prompt: true,
      llm: true,
      response: true,
    };
    if (detail?.response_tool_calls) {
      detail.response_tool_calls.forEach((_: any, i: number) => {
        next[`tool-${i}`] = true;
      });
    }
    setExpandedItems(next);
  };

  const collapseAll = () => {
    setExpandedItems({});
  };

  // Helper to find tool result from nextCallDetail's or detail's message_history
  const findToolResult = (toolCallId?: string, toolName?: string) => {
    if (nextCallDetail?.message_history) {
      const match = nextCallDetail.message_history.find((m: any) => (
        m.role === "tool" &&
        ((toolCallId && m.tool_call_id === toolCallId) || (toolName && (m.name === toolName || m.tool_name === toolName)))
      ));
      if (match) return match.content || match.tool_result;
    }
    if (detail?.message_history) {
      const match = detail.message_history.find((m: any) => (
        m.role === "tool" &&
        ((toolCallId && m.tool_call_id === toolCallId) || (toolName && (m.name === toolName || m.tool_name === toolName)))
      ));
      if (match) return match.content || match.tool_result;
    }
    return null;
  };

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0, 0, 0, 0.35)",
          zIndex: 400,
          backdropFilter: "blur(2px)",
          animation: "llmFadeIn 0.2s ease",
        }}
      />

      {/* Side Sheet Panel */}
      <div
        ref={sheetRef}
        role="dialog"
        aria-modal="true"
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          bottom: 0,
          width: "min(680px, 95vw)",
          background: "#ffffff",
          borderLeft: "1px solid #e2e8f0",
          zIndex: 401,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          animation: "llmSlideIn 0.22s cubic-bezier(0.22, 1, 0.36, 1)",
          boxShadow: "-6px 0 28px rgba(0,0,0,0.1)",
        }}
      >
        {/* Header Bar with Call Navigation */}
        <div
          style={{
            padding: "12px 18px",
            borderBottom: "1px solid #f1f5f9",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "#ffffff",
            flexShrink: 0,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
            {/* Step through calls (Prev / Next) */}
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <button
                type="button"
                disabled={!prevLog}
                onClick={() => prevLog && onSelectCallId(prevLog.id)}
                title={prevLog ? `Go to Call #${prevLog.call_sequence_number}` : "No previous call"}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 22,
                  height: 22,
                  borderRadius: 4,
                  border: "1px solid #e2e8f0",
                  background: prevLog ? "#ffffff" : "#f8fafc",
                  color: prevLog ? "#0f172a" : "#cbd5e1",
                  cursor: prevLog ? "pointer" : "not-allowed",
                }}
              >
                <ChevronLeft size={13} />
              </button>

              <span style={{ fontSize: "0.88rem", fontWeight: 600, color: "#0f172a" }}>
                Call #{detail?.call_sequence_number ?? callId}
              </span>

              <button
                type="button"
                disabled={!nextLog}
                onClick={() => nextLog && onSelectCallId(nextLog.id)}
                title={nextLog ? `Go to Call #${nextLog.call_sequence_number}` : "No next call"}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 22,
                  height: 22,
                  borderRadius: 4,
                  border: "1px solid #e2e8f0",
                  background: nextLog ? "#ffffff" : "#f8fafc",
                  color: nextLog ? "#0f172a" : "#cbd5e1",
                  cursor: nextLog ? "pointer" : "not-allowed",
                }}
              >
                <ChevronRight size={13} />
              </button>
            </div>

            {detail && (
              <code
                style={{
                  fontSize: "0.72rem",
                  background: "#f1f5f9",
                  padding: "2px 6px",
                  borderRadius: 4,
                  color: "#475569",
                }}
              >
                {detail.model}
              </code>
            )}
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {detail && (
              <button
                type="button"
                onClick={() => setRawView(!rawView)}
                style={{
                  fontSize: "0.72rem",
                  padding: "3px 8px",
                  borderRadius: 4,
                  border: "1px solid #e2e8f0",
                  background: rawView ? "#eff6ff" : "#ffffff",
                  color: rawView ? "#2563eb" : "#475569",
                  cursor: "pointer",
                  fontWeight: 500,
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                }}
              >
                <Code2 size={12} />
                <span>{rawView ? "Timeline View" : "Raw JSON"}</span>
              </button>
            )}

            <button
              type="button"
              onClick={onClose}
              title="Close (Esc)"
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 26,
                height: 26,
                borderRadius: 4,
                border: "none",
                background: "transparent",
                cursor: "pointer",
                color: "#64748b",
                transition: "background 0.15s ease",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "#f1f5f9")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <X size={15} />
            </button>
          </div>
        </div>

        {/* Minimal Metrics Sub-row */}
        {detail && (
          <div
            style={{
              padding: "6px 18px",
              background: "#fafafa",
              borderBottom: "1px solid #f1f5f9",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              fontSize: "0.74rem",
              color: "#64748b",
              flexShrink: 0,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <span>
                Tokens: <strong>{(detail.input_tokens ?? 0) + (detail.output_tokens ?? 0)}</strong> ({detail.input_tokens ?? 0} in / {detail.output_tokens ?? 0} out)
              </span>
              <span>·</span>
              <span>Finish: <strong>{detail.finish_reason || "stop"}</strong></span>
            </div>
            <span style={{ fontSize: "0.72rem", color: "#94a3b8" }}>
              {new Date(detail.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
          </div>
        )}

        {/* Body: Chronological Connected Timeline Tree */}
        <div style={{ flex: 1, overflowY: "auto", padding: "16px 18px 30px" }}>
          {isLoading ? (
            <div style={{ padding: 60, display: "flex", justifyContent: "center", alignItems: "center", gap: 8, color: "#64748b" }}>
              <Loader2 size={18} className="spin" />
              <span style={{ fontSize: "0.82rem" }}>Loading call details…</span>
            </div>
          ) : error || !detail ? (
            <div style={{ padding: 40, textAlign: "center", color: "#dc2626", fontSize: "0.82rem" }}>
              Failed to load LLM call log details.
            </div>
          ) : rawView ? (
            /* RAW JSON VIEW */
            <div style={{ border: "1px solid #e2e8f0", borderRadius: 8, overflow: "hidden" }}>
              <div style={{ padding: "8px 12px", background: "#f8fafc", borderBottom: "1px solid #f1f5f9", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "#334155" }}>Raw LLM Call Payload</span>
                <CopyButton text={JSON.stringify(detail, null, 2)} />
              </div>
              <pre
                style={{
                  margin: 0,
                  padding: 14,
                  fontSize: "0.74rem",
                  lineHeight: 1.45,
                  color: "#0f172a",
                  background: "#fafafa",
                  overflowX: "auto",
                  maxHeight: "calc(100vh - 180px)",
                }}
              >
                {JSON.stringify(detail, null, 2)}
              </pre>
            </div>
          ) : (
            /* ── CHRONOLOGICAL EXECUTION TIMELINE (Flow: Input -> System/Skills -> LLM Call -> Response -> Tool Execution) ── */
            <div>
              {/* Expand / Collapse all controls */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 8, marginBottom: 10 }}>
                <button
                  type="button"
                  onClick={expandAll}
                  style={{
                    background: "none",
                    border: "none",
                    color: "#64748b",
                    fontSize: "0.72rem",
                    cursor: "pointer",
                    padding: "2px 4px",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = "#0f172a")}
                  onMouseLeave={(e) => (e.currentTarget.style.color = "#64748b")}
                >
                  Expand all
                </button>
                <span style={{ color: "#cbd5e1" }}>·</span>
                <button
                  type="button"
                  onClick={collapseAll}
                  style={{
                    background: "none",
                    border: "none",
                    color: "#64748b",
                    fontSize: "0.72rem",
                    cursor: "pointer",
                    padding: "2px 4px",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = "#0f172a")}
                  onMouseLeave={(e) => (e.currentTarget.style.color = "#64748b")}
                >
                  Collapse all
                </button>
              </div>

              {/* Vertical Tree Structure */}
              <div style={{ position: "relative", paddingLeft: 8 }}>
                {/* Continuous vertical connector line */}
                <div
                  style={{
                    position: "absolute",
                    left: 18,
                    top: 14,
                    bottom: 14,
                    width: 1,
                    background: "#e2e8f0",
                  }}
                />

                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  
                  {/* ── STEP 1: USER MESSAGE & CONVERSATION HISTORY (Input provided) ── */}
                  <TimelineTreeNode
                    id="context"
                    isExpanded={!!expandedItems.context}
                    onToggle={() => toggleItem("context")}
                    icon={<MessageCircle size={13} />}
                    iconBg="#f0fdf4"
                    iconBorder="#bbf7d0"
                    iconColor="#16a34a"
                    title="input_messages"
                    subtitle="was received"
                    rightExtra={
                      <span style={{ fontSize: "0.7rem", color: "#94a3b8" }}>
                        {inputMessages.length} turn(s)
                      </span>
                    }
                  >
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      {inputMessages.length > 0 ? (
                        inputMessages.map((msg, i) => {
                          const isUser = msg.role === "user";
                          const isAsst = msg.role === "assistant";
                          const isTool = msg.role === "tool";

                          let roleTag = "SYSTEM";
                          let tagBg = "#f1f5f9";
                          let tagColor = "#475569";

                          if (isUser) {
                            roleTag = "USER";
                            tagBg = "#eff6ff";
                            tagColor = "#2563eb";
                          } else if (isAsst) {
                            roleTag = "ASSISTANT";
                            tagBg = "#f0fdf4";
                            tagColor = "#16a34a";
                          } else if (isTool) {
                            roleTag = `TOOL RESULT: ${msg.tool_name || msg.name || ""}`;
                            tagBg = "#fff7ed";
                            tagColor = "#c2410c";
                          }

                          const textContent = msg.tool_result
                            ? formatJsonOrText(msg.tool_result)
                            : msg.tool_calls
                            ? formatJsonOrText(msg.tool_calls)
                            : formatJsonOrText(msg.content);

                          return (
                            <div key={i} style={{ border: "1px solid #e2e8f0", borderRadius: 6, background: isUser ? "#f8fafc" : "#ffffff", overflow: "hidden" }}>
                              <div style={{ padding: "4px 8px", background: "#fafafa", borderBottom: "1px solid #f1f5f9", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                                <span style={{ fontSize: "0.66rem", fontWeight: 700, padding: "1px 4px", borderRadius: 3, background: tagBg, color: tagColor }}>
                                  {roleTag}
                                </span>
                                <CopyButton text={textContent} />
                              </div>
                              <div style={{ padding: "6px 8px", fontSize: "0.74rem", color: "#1e293b", lineHeight: 1.45 }}>
                                {msg.tool_result ? (
                                  <pre style={{ margin: 0, fontSize: "0.7rem", whiteSpace: "pre-wrap", overflowX: "auto", color: "#334155" }}>
                                    {formatJsonOrText(msg.tool_result)}
                                  </pre>
                                ) : msg.tool_calls ? (
                                  <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                                    {msg.tool_calls.map((tc: any, j: number) => (
                                      <div key={j} style={{ background: "#f8fafc", padding: 5, borderRadius: 4, border: "1px solid #e2e8f0" }}>
                                        <div style={{ fontWeight: 600, fontSize: "0.7rem", color: "#0f172a" }}>
                                          Called: {tc.name || tc.function?.name || "tool"}
                                        </div>
                                        <pre style={{ margin: "2px 0 0", fontSize: "0.68rem", overflowX: "auto", color: "#334155" }}>
                                          {formatJsonOrText(tc.arguments !== undefined ? tc.arguments : tc.function?.arguments)}
                                        </pre>
                                      </div>
                                    ))}
                                  </div>
                                ) : (
                                  <div style={{ whiteSpace: "pre-wrap" }}>
                                    {formatJsonOrText(msg.content) || "*(Empty message)*"}
                                  </div>
                                )}
                              </div>
                            </div>
                          );
                        })
                      ) : (
                        <div style={{ padding: "10px 0", textAlign: "center", color: "#94a3b8", fontSize: "0.72rem" }}>
                          No input history.
                        </div>
                      )}
                    </div>
                  </TimelineTreeNode>

                  {/* ── STEP 2: SYSTEM PROMPT, CONTEXT & SKILLS INJECTION ── */}
                  <TimelineTreeNode
                    id="prompt"
                    isExpanded={!!expandedItems.prompt}
                    onToggle={() => toggleItem("prompt")}
                    icon={<FileCode size={13} />}
                    iconBg="#faf5ff"
                    iconBorder="#e9d5ff"
                    iconColor="#9333ea"
                    title="system_prompt & skills"
                    subtitle="were injected"
                    rightExtra={
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        {hasSkills && (
                          <span style={{ fontSize: "0.68rem", padding: "1px 5px", borderRadius: 8, background: "#ede9fe", color: "#7c3aed" }}>
                            {detail.skills_injected.length} skills
                          </span>
                        )}
                        {toolsCount > 0 && (
                          <span style={{ fontSize: "0.68rem", color: "#94a3b8" }}>
                            {toolsCount} tools
                          </span>
                        )}
                        {detail.system_prompt_base && <CopyButton text={detail.system_prompt_base} />}
                      </div>
                    }
                  >
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      <div>
                        <div style={{ fontSize: "0.7rem", fontWeight: 600, color: "#64748b", marginBottom: 3 }}>BASE SYSTEM PROMPT</div>
                        <pre style={{ margin: 0, padding: 10, fontSize: "0.73rem", background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 6, whiteSpace: "pre-wrap", color: "#0f172a", maxHeight: 180, overflowY: "auto" }}>
                          {detail.system_prompt_base || "(Empty system prompt)"}
                        </pre>
                      </div>

                      {hasSkills && (
                        <div>
                          <div style={{ fontSize: "0.7rem", fontWeight: 600, color: "#64748b", marginBottom: 3 }}>INJECTED SKILLS</div>
                          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                            {detail.skills_injected.map((sk: any, i: number) => (
                              <div key={i} style={{ border: "1px solid #e2e8f0", borderRadius: 4, padding: 6, background: "#fafafa" }}>
                                <div style={{ fontSize: "0.72rem", fontWeight: 600, color: "#1e293b" }}>{sk.name}</div>
                                {sk.body && (
                                  <pre style={{ margin: "2px 0 0", fontSize: "0.68rem", whiteSpace: "pre-wrap", color: "#475569", maxHeight: 80, overflowY: "auto" }}>
                                    {sk.body}
                                  </pre>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </TimelineTreeNode>

                  {/* ── STEP 3: SEND CALL TO LLM ── */}
                  <TimelineTreeNode
                    id="llm"
                    isExpanded={!!expandedItems.llm}
                    onToggle={() => toggleItem("llm")}
                    icon={<Bot size={13} />}
                    iconBg="#f0f9ff"
                    iconBorder="#bae6fd"
                    iconColor="#0284c7"
                    title="llm"
                    subtitle="was called"
                    rightExtra={
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <code style={{ fontSize: "0.7rem", color: "#64748b", background: "#f1f5f9", padding: "1px 5px", borderRadius: 3 }}>
                          {detail.model}
                        </code>
                        <span style={{ fontSize: "0.72rem", color: "#94a3b8" }}>
                          {(detail.input_tokens ?? 0) + (detail.output_tokens ?? 0)} tok
                        </span>
                      </div>
                    }
                  >
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: "0.74rem", color: "#64748b" }}>
                        <span>Model: <strong style={{ color: "#0f172a" }}>{detail.model}</strong></span>
                        <span>·</span>
                        <span>Input: <strong>{detail.input_tokens ?? 0}</strong> tok</span>
                        <span>·</span>
                        <span>Output: <strong>{detail.output_tokens ?? 0}</strong> tok</span>
                        <span>·</span>
                        <span>Finish: <strong>{detail.finish_reason || "stop"}</strong></span>
                      </div>
                    </div>
                  </TimelineTreeNode>

                  {/* ── STEP 4: LLM RESPONSE / OUTPUT (If final text generated) ── */}
                  {detail.response_text && (
                    <TimelineTreeNode
                      id="response"
                      isExpanded={!!expandedItems.response}
                      onToggle={() => toggleItem("response")}
                      icon={<Sparkles size={13} />}
                      iconBg="#f0fdf4"
                      iconBorder="#bbf7d0"
                      iconColor="#16a34a"
                      title="llm response"
                      subtitle="was generated"
                      rightExtra={
                        <CopyButton text={detail.response_text} />
                      }
                    >
                      <div style={{ fontSize: "0.78rem", lineHeight: 1.5, color: "#0f172a", whiteSpace: "pre-wrap" }}>
                        {detail.response_text}
                      </div>
                    </TimelineTreeNode>
                  )}

                  {/* ── STEP 5+: REQUESTED TOOL EXECUTION & RESULTS ── */}
                  {hasToolCalls &&
                    detail.response_tool_calls.map((tc: any, i: number) => {
                      const toolName = tc.function?.name || tc.name || "tool";
                      const argsRaw = tc.function?.arguments || tc.arguments;
                      const argsFormatted = formatJsonOrText(argsRaw);
                      const nodeKey = `tool-${i}`;
                      
                      // Look up tool result from next call or execution log
                      const toolResult = findToolResult(tc.id, toolName);
                      const resultFormatted = toolResult ? formatJsonOrText(toolResult) : null;

                      return (
                        <TimelineTreeNode
                          key={i}
                          id={nodeKey}
                          isExpanded={!!expandedItems[nodeKey]}
                          onToggle={() => toggleItem(nodeKey)}
                          icon={<Wrench size={12} />}
                          iconBg="#fff1f2"
                          iconBorder="#fecdd3"
                          iconColor="#e11d48"
                          title={toolName}
                          subtitle="was executed"
                          rightExtra={
                            <CopyButton text={argsFormatted} />
                          }
                        >
                          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                            {/* Arguments */}
                            <div>
                              <div style={{ fontSize: "0.68rem", fontWeight: 600, color: "#64748b", marginBottom: 3 }}>
                                INPUT PARAMETERS
                              </div>
                              <pre style={{ margin: 0, padding: 8, background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: 6, fontSize: "0.7rem", color: "#0f172a", overflowX: "auto" }}>
                                {argsFormatted || "(No arguments)"}
                              </pre>
                            </div>

                            {/* Tool Execution Result */}
                            {resultFormatted && (
                              <div>
                                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 3 }}>
                                  <span style={{ fontSize: "0.68rem", fontWeight: 600, color: "#166534" }}>
                                    EXECUTION RESULT (Available in Call #{nextLog?.call_sequence_number ?? (detail.call_sequence_number + 1)})
                                  </span>
                                  <CopyButton text={resultFormatted} />
                                </div>
                                <pre style={{ margin: 0, padding: 8, background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 6, fontSize: "0.7rem", color: "#14532d", overflowX: "auto", maxHeight: 160, overflowY: "auto" }}>
                                  {resultFormatted}
                                </pre>
                              </div>
                            )}

                            {/* Pointer to Next Call */}
                            {nextLog && (
                              <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", marginTop: 2 }}>
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    onSelectCallId(nextLog.id);
                                  }}
                                  style={{
                                    display: "inline-flex",
                                    alignItems: "center",
                                    gap: 4,
                                    background: "none",
                                    border: "none",
                                    color: "#2563eb",
                                    fontSize: "0.72rem",
                                    fontWeight: 500,
                                    cursor: "pointer",
                                  }}
                                >
                                  <span>Inspect Call #{nextLog.call_sequence_number}</span>
                                  <ArrowRight size={12} />
                                </button>
                              </div>
                            )}
                          </div>
                        </TimelineTreeNode>
                      );
                    })}

                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes llmFadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes llmSlideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }
      `}</style>
    </>
  );
}

// ── Reusable Timeline Tree Node Component ─────────────────────────────────────

interface TimelineTreeNodeProps {
  id: string;
  isExpanded: boolean;
  onToggle: () => void;
  icon: React.ReactNode;
  iconBg: string;
  iconBorder: string;
  iconColor: string;
  title: string;
  subtitle: string;
  rightExtra?: React.ReactNode;
  children: React.ReactNode;
}

function TimelineTreeNode({
  isExpanded,
  onToggle,
  icon,
  iconBg,
  iconBorder,
  iconColor,
  title,
  subtitle,
  rightExtra,
  children,
}: TimelineTreeNodeProps) {
  return (
    <div style={{ position: "relative", zIndex: 1 }}>
      {/* Node Header Row */}
      <div
        onClick={onToggle}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "5px 6px",
          borderRadius: 6,
          cursor: "pointer",
          transition: "background 0.12s ease",
          background: isExpanded ? "#f8fafc" : "transparent",
        }}
        onMouseEnter={(e) => {
          if (!isExpanded) e.currentTarget.style.background = "#f8fafc";
        }}
        onMouseLeave={(e) => {
          if (!isExpanded) e.currentTarget.style.background = "transparent";
        }}
      >
        {/* Left: Chevron + Icon Badge + Text */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
          <div
            style={{
              width: 16,
              height: 16,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#94a3b8",
              transition: "transform 0.15s ease",
              transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)",
            }}
          >
            <ChevronRight size={13} />
          </div>

          <div
            style={{
              width: 22,
              height: 22,
              borderRadius: 5,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: iconBg,
              border: `1px solid ${iconBorder}`,
              color: iconColor,
              flexShrink: 0,
            }}
          >
            {icon}
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 5, fontSize: "0.8rem" }}>
            <span style={{ fontWeight: 600, color: "#0f172a" }}>{title}</span>
            <span style={{ color: "#64748b", fontWeight: 400 }}>{subtitle}</span>
          </div>
        </div>

        {/* Right side controls */}
        {rightExtra && (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {rightExtra}
          </div>
        )}
      </div>

      {/* Expanded Inline Detail Box */}
      {isExpanded && (
        <div
          style={{
            marginLeft: 42,
            marginRight: 4,
            marginTop: 4,
            marginBottom: 6,
            padding: "8px 12px",
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            borderRadius: 6,
            boxShadow: "0 1px 2px rgba(0,0,0,0.02)",
            fontSize: "0.76rem",
          }}
        >
          {children}
        </div>
      )}
    </div>
  );
}
