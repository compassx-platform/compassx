/**
 * DiffPreview – tabbed view of upload diff results.
 *
 * Tabs: New | Updated | Duplicate | Invalid
 * Each tab shows a compact table of staging rows.
 */

import { useState } from "react";
import { format } from "date-fns";
import type { DiffResponse, StagingRow } from "@/modules/data/hooks/useTimeseries";

interface DiffPreviewProps {
  diff: DiffResponse;
}

type TabKey = "new" | "updated" | "duplicate" | "invalid";

const TAB_CONFIG: { key: TabKey; label: string; color: string }[] = [
  { key: "new", label: "New", color: "#4ade80" },
  { key: "updated", label: "Updated", color: "#60a5fa" },
  { key: "duplicate", label: "Duplicate", color: "#94a3b8" },
  { key: "invalid", label: "Invalid", color: "#f87171" },
];

function formatTs(ts: string | null) {
  if (!ts) return "—";
  try {
    return format(new Date(ts), "yyyy-MM-dd HH:mm");
  } catch {
    return ts;
  }
}

function StagingTable({ rows, showError }: { rows: StagingRow[]; showError?: boolean }) {
  if (rows.length === 0) {
    return (
      <div
        style={{
          padding: "2rem",
          textAlign: "center",
          color: "var(--color-text-muted)",
          fontSize: 14,
        }}
      >
        No rows in this category.
      </div>
    );
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid var(--color-border)" }}>
            <th style={thStyle}>#</th>
            <th style={thStyle}>Timestamp</th>
            <th style={thStyle}>Asset</th>
            <th style={thStyle}>Tag</th>
            <th style={thStyle}>Value</th>
            {showError && <th style={thStyle}>Error</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.row_number}
              style={{ borderBottom: "1px solid var(--color-border)" }}
            >
              <td style={tdStyle}>{row.row_number}</td>
              <td style={tdStyle}>{formatTs(row.ts)}</td>
              <td style={tdStyle}>{row.asset_ref ?? "—"}</td>
              <td style={tdStyle}>{row.tag_ref ?? "—"}</td>
              <td style={tdStyle}>{row.value != null ? row.value.toLocaleString() : "—"}</td>
              {showError && (
                <td style={{ ...tdStyle, color: "#f87171", maxWidth: 300, whiteSpace: "normal" }}>
                  {row.error_message ?? "—"}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const thStyle: React.CSSProperties = {
  padding: "8px 12px",
  textAlign: "left",
  fontSize: 11,
  fontWeight: 600,
  color: "var(--color-text-muted)",
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  background: "rgba(255,255,255,0.03)",
  whiteSpace: "nowrap",
};

const tdStyle: React.CSSProperties = {
  padding: "7px 12px",
  whiteSpace: "nowrap",
};

export default function DiffPreview({ diff }: DiffPreviewProps) {
  const [activeTab, setActiveTab] = useState<TabKey>("new");

  const counts: Record<TabKey, number> = {
    new: diff.new.length,
    updated: diff.updated.length,
    duplicate: diff.duplicate.length,
    invalid: diff.invalid.length,
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      {/* Tabs */}
      <div
        style={{
          display: "flex",
          borderBottom: "1px solid var(--color-border)",
          gap: 0,
        }}
      >
        {TAB_CONFIG.map(({ key, label, color }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            style={{
              padding: "8px 16px",
              background: "transparent",
              border: "none",
              borderBottom: activeTab === key ? `2px solid ${color}` : "2px solid transparent",
              color: activeTab === key ? color : "var(--color-text-muted)",
              cursor: "pointer",
              fontSize: 13,
              fontWeight: activeTab === key ? 600 : 400,
              display: "flex",
              alignItems: "center",
              gap: 6,
              transition: "all 0.15s",
              marginBottom: -1,
            }}
          >
            {label}
            <span
              style={{
                background: activeTab === key ? color : "rgba(255,255,255,0.1)",
                color: activeTab === key ? "#000" : "var(--color-text-muted)",
                borderRadius: 10,
                padding: "1px 7px",
                fontSize: 11,
                fontWeight: 600,
              }}
            >
              {counts[key]}
            </span>
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ maxHeight: 320, overflowY: "auto" }}>
        <StagingTable
          rows={diff[activeTab]}
          showError={activeTab === "invalid" || activeTab === "duplicate"}
        />
      </div>
    </div>
  );
}
