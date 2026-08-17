import React from "react";
import type { BranchRead } from "../lib/appsApi";

interface Props {
  branches: BranchRead[];
  activeBranchId: string;
  onSwitch: (branchId: string) => void;
  onNewBranch: () => void;
}

export default function BranchSelector({ branches, activeBranchId, onSwitch, onNewBranch }: Props) {
  const [open, setOpen] = React.useState(false);
  const active = branches.find((b) => b.branch_id === activeBranchId);

  return (
    <div style={{ position: "relative" }}>
      <button
        id="branch-selector-btn"
        onClick={() => setOpen((o) => !o)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          background: "var(--surface-2, #1e1e2e)",
          border: "1px solid var(--border, #313244)",
          borderRadius: "8px",
          color: "var(--text-primary, #cdd6f4)",
          padding: "6px 12px",
          fontSize: "13px",
          cursor: "pointer",
          whiteSpace: "nowrap",
        }}
      >
        <span>⎇</span>
        <span>{active?.name ?? "Select branch"}</span>
        <span style={{ opacity: 0.5 }}>▾</span>
      </button>

      {open && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 4px)",
            left: 0,
            zIndex: 200,
            background: "var(--surface-2, #1e1e2e)",
            border: "1px solid var(--border, #313244)",
            borderRadius: "8px",
            minWidth: "200px",
            boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
            overflow: "hidden",
          }}
        >
          {branches.map((b) => (
            <div
              key={b.branch_id}
              id={`branch-option-${b.branch_id}`}
              onClick={() => { onSwitch(b.branch_id); setOpen(false); }}
              style={{
                padding: "10px 16px",
                cursor: "pointer",
                fontSize: "13px",
                color: b.branch_id === activeBranchId ? "var(--accent, #89b4fa)" : "var(--text-primary, #cdd6f4)",
                background: b.branch_id === activeBranchId ? "rgba(137,180,250,0.08)" : "transparent",
                fontWeight: b.branch_id === activeBranchId ? 600 : 400,
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(137,180,250,0.06)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = b.branch_id === activeBranchId ? "rgba(137,180,250,0.08)" : "transparent")}
            >
              {b.branch_id === activeBranchId && <span style={{ marginRight: 6 }}>✓</span>}
              {b.name}
            </div>
          ))}
          <div style={{ borderTop: "1px solid var(--border, #313244)" }}>
            <div
              id="branch-selector-new"
              onClick={() => { onNewBranch(); setOpen(false); }}
              style={{
                padding: "10px 16px",
                cursor: "pointer",
                fontSize: "13px",
                color: "var(--accent, #89b4fa)",
              }}
            >
              + New branch
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
