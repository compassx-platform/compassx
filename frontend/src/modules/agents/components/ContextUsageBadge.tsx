import React, { useState, useRef, useEffect } from "react";
import {
  Minimize2,
  FileText,
  CheckCircle2,
  X as XIcon,
} from "lucide-react";
import { useSessionContext } from "@/modules/agents/hooks/useChat";

interface ContextUsageBadgeProps {
  agentId: number;
  sessionId: number;
  onCompact?: () => void;
  isCompactLoading?: boolean;
}

function formatTokens(tokens: number): string {
  if (tokens >= 1_000_000) {
    return `${(tokens / 1_000_000).toFixed(1)}M`;
  }
  if (tokens >= 1_000) {
    return `${(tokens / 1_000).toFixed(1)}k`;
  }
  return tokens.toLocaleString();
}

export function ContextUsageBadge({
  agentId,
  sessionId,
  onCompact,
  isCompactLoading,
}: ContextUsageBadgeProps) {
  const { data: contextData, isLoading } = useSessionContext(agentId, sessionId);
  const [isOpen, setIsOpen] = useState(false);
  const [popoverCoords, setPopoverCoords] = useState<{ bottom: number; right: number } | null>(null);
  const [showSummaryModal, setShowSummaryModal] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);

  const togglePopover = () => {
    if (!isOpen && popoverRef.current) {
      const rect = popoverRef.current.getBoundingClientRect();
      setPopoverCoords({
        bottom: window.innerHeight - rect.top + 8,
        right: Math.max(16, window.innerWidth - rect.right - 10),
      });
      setIsOpen(true);
    } else {
      setIsOpen(false);
    }
  };

  // Close popover on outside click and update on scroll/resize
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        const popoverEl = document.getElementById("context-donut-popover");
        if (popoverEl && popoverEl.contains(e.target as Node)) {
          return;
        }
        setIsOpen(false);
      }
    }
    function handleScrollOrResize() {
      if (isOpen && popoverRef.current) {
        const rect = popoverRef.current.getBoundingClientRect();
        setPopoverCoords({
          bottom: window.innerHeight - rect.top + 8,
          right: Math.max(16, window.innerWidth - rect.right - 10),
        });
      }
    }
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      window.addEventListener("scroll", handleScrollOrResize, true);
      window.addEventListener("resize", handleScrollOrResize);
      return () => {
        document.removeEventListener("mousedown", handleClickOutside);
        window.removeEventListener("scroll", handleScrollOrResize, true);
        window.removeEventListener("resize", handleScrollOrResize);
      };
    }
  }, [isOpen]);

  if (isLoading && !contextData) {
    return (
      <div
        style={{
          width: 15,
          height: 15,
          borderRadius: "50%",
          border: "2px solid #e2e8f0",
          borderTopColor: "#94a3b8",
          animation: "spin 1s linear infinite",
          opacity: 0.6,
        }}
        title="Calculating context..."
      />
    );
  }

  if (!contextData) return null;

  const {
    total_tokens,
    context_window,
    high_watermark,
    usage_percent,
    total_turns,
    retained_turns,
    has_summary,
    summary,
    model_name,
  } = contextData;

  // Donut SVG geometry
  const size = 15;
  const strokeWidth = 2.2;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const normalizedPercent = Math.min(Math.max(usage_percent, 0), 100);
  const strokeDashoffset = circumference - (normalizedPercent / 100) * circumference;

  // Muted color logic
  const isHigh = usage_percent >= 85;
  const isWarning = usage_percent >= 60 && usage_percent < 85;

  const strokeColor = isHigh
    ? "#8b5cf6"
    : isWarning
    ? "#d97706"
    : "#94a3b8";

  const trackColor = "#e2e8f0";

  return (
    <div
      style={{
        position: "relative",
        display: "inline-flex",
        alignItems: "center",
      }}
      ref={popoverRef}
    >
      {/* Small Donut Circle Trigger */}
      <button
        type="button"
        onClick={togglePopover}
        title={`Context: ${formatTokens(total_tokens)} / ${formatTokens(context_window)} (${usage_percent}%)`}
        style={{
          background: "none",
          border: "none",
          padding: 2,
          margin: 0,
          cursor: "pointer",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          borderRadius: "50%",
          outline: "none",
          opacity: 0.85,
          transition: "opacity 0.15s ease, transform 0.15s ease",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.opacity = "1";
          e.currentTarget.style.transform = "scale(1.1)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.opacity = "0.85";
          e.currentTarget.style.transform = "scale(1)";
        }}
      >
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          style={{ transform: "rotate(-90deg)", display: "block" }}
        >
          {/* Background Track */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={trackColor}
            strokeWidth={strokeWidth}
          />
          {/* Progress Arc */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={strokeColor}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            style={{ transition: "stroke-dashoffset 0.3s ease" }}
          />
        </svg>
      </button>

      {/* Upward Compact Popover Card using Viewport Positioning (Immune to parent overflow: hidden) */}
      {isOpen && popoverCoords && (
        <div
          id="context-donut-popover"
          style={{
            position: "fixed",
            bottom: popoverCoords.bottom,
            right: popoverCoords.right,
            width: 270,
            background: "#ffffff",
            borderRadius: 8,
            border: "1px solid #e2e8f0",
            boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.12), 0 8px 10px -6px rgba(0, 0, 0, 0.06)",
            padding: "12px 14px",
            zIndex: 99999,
            fontSize: "0.76rem",
            color: "#1e293b",
            textAlign: "left",
          }}
        >
          {/* Header */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 8,
              borderBottom: "1px solid #f1f5f9",
              paddingBottom: 6,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              {/* Donut in header */}
              <svg
                width={13}
                height={13}
                viewBox={`0 0 ${size} ${size}`}
                style={{ transform: "rotate(-90deg)" }}
              >
                <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={trackColor} strokeWidth={strokeWidth} />
                <circle
                  cx={size / 2}
                  cy={size / 2}
                  r={radius}
                  fill="none"
                  stroke={strokeColor}
                  strokeWidth={strokeWidth}
                  strokeDasharray={circumference}
                  strokeDashoffset={strokeDashoffset}
                  strokeLinecap="round"
                />
              </svg>
              <span style={{ fontWeight: 600, color: "#334155" }}>Context Usage</span>
            </div>

            <span
              style={{
                fontSize: "0.68rem",
                padding: "1px 5px",
                borderRadius: 4,
                background: "#f1f5f9",
                color: "#64748b",
                fontFamily: "monospace",
              }}
            >
              {model_name || "LLM"}
            </span>
          </div>

          {/* Metrics */}
          <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between", color: "#64748b" }}>
              <span>Tokens:</span>
              <span style={{ fontWeight: 600, color: "#0f172a" }}>
                {total_tokens.toLocaleString()} / {formatTokens(context_window)} ({usage_percent}%)
              </span>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", color: "#64748b" }}>
              <span>History:</span>
              <span style={{ color: "#334155" }}>
                Last {retained_turns} raw ({total_turns} total turns)
              </span>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", color: "#64748b" }}>
              <span>Auto-compact:</span>
              <span style={{ color: "#334155" }}>
                at {formatTokens(high_watermark)} tokens (85%)
              </span>
            </div>
          </div>

          {/* Summary status pill if present */}
          {has_summary && summary && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "4px 6px",
                borderRadius: 4,
                background: "#f5f3ff",
                border: "1px solid #ede9fe",
                marginBottom: 8,
                fontSize: "0.72rem",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 4, color: "#6d28d9" }}>
                <CheckCircle2 size={11} color="#7c3aed" />
                <span>Memory summary active</span>
              </div>
              <button
                type="button"
                onClick={() => {
                  setShowSummaryModal(true);
                  setIsOpen(false);
                }}
                style={{
                  background: "none",
                  border: "none",
                  padding: 0,
                  color: "#7c3aed",
                  cursor: "pointer",
                  textDecoration: "underline",
                  fontSize: "0.7rem",
                  fontWeight: 500,
                }}
              >
                View
              </button>
            </div>
          )}

          {/* Manual Compact Button */}
          <div style={{ display: "flex", justifyContent: "flex-end", paddingTop: 4, borderTop: "1px solid #f1f5f9" }}>
            <button
              type="button"
              onClick={() => {
                setIsOpen(false);
                if (onCompact) onCompact();
              }}
              disabled={isCompactLoading || total_turns <= 3}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                padding: "3px 8px",
                borderRadius: 4,
                border: "1px solid #e2e8f0",
                background: "#f8fafc",
                color: total_turns <= 3 ? "#94a3b8" : "#475569",
                fontSize: "0.7rem",
                fontWeight: 500,
                cursor: total_turns <= 3 ? "not-allowed" : "pointer",
              }}
              title={total_turns <= 3 ? "Need >3 turns to compact" : "Compact turns older than last 3 into summary"}
            >
              <Minimize2 size={10} color="#6366f1" />
              <span>Compact now</span>
            </button>
          </div>
        </div>
      )}

      {/* Summary Viewer Modal */}
      {showSummaryModal && summary && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(15, 23, 42, 0.4)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 10000,
            padding: 20,
          }}
          onClick={() => setShowSummaryModal(false)}
        >
          <div
            style={{
              width: "100%",
              maxWidth: 580,
              maxHeight: "80vh",
              background: "#ffffff",
              borderRadius: 10,
              boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1)",
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div
              style={{
                padding: "14px 18px",
                borderBottom: "1px solid #e2e8f0",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <FileText size={15} color="#7c3aed" />
                <span style={{ fontWeight: 600, fontSize: "0.9rem", color: "#0f172a" }}>
                  Distilled Conversation Summary
                </span>
              </div>
              <button
                type="button"
                onClick={() => setShowSummaryModal(false)}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  color: "#64748b",
                  padding: 2,
                }}
              >
                <XIcon size={16} />
              </button>
            </div>

            {/* Modal Content */}
            <div
              style={{
                padding: "16px 18px",
                overflowY: "auto",
                fontSize: "0.8rem",
                lineHeight: 1.6,
                color: "#334155",
                whiteSpace: "pre-wrap",
                fontFamily: "system-ui, -apple-system, sans-serif",
              }}
            >
              {summary}
            </div>

            {/* Modal Footer */}
            <div
              style={{
                padding: "10px 18px",
                borderTop: "1px solid #e2e8f0",
                display: "flex",
                justifyContent: "flex-end",
                background: "#f8fafc",
              }}
            >
              <button
                type="button"
                onClick={() => setShowSummaryModal(false)}
                style={{
                  padding: "5px 12px",
                  borderRadius: 5,
                  border: "1px solid #cbd5e1",
                  background: "#ffffff",
                  color: "#334155",
                  fontSize: "0.76rem",
                  fontWeight: 500,
                  cursor: "pointer",
                }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
