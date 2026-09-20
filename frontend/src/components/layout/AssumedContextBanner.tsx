import React from "react";
import { Shield, X } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useSessionRoleStore } from "@/lib/sessionRoleStore";
import { useMe } from "@/lib/userManagerApi";

export const AssumedContextBanner: React.FC = () => {
  const { activeRole, clearActiveRole } = useSessionRoleStore();
  const { data: me } = useMe();
  const qc = useQueryClient();

  if (!activeRole) {
    return null;
  }

  const handleExit = () => {
    clearActiveRole();
    qc.invalidateQueries();
  };

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "6px 16px",
        background: "rgba(27, 110, 243, 0.08)",
        borderBottom: "1px solid rgba(27, 110, 243, 0.2)",
        color: "var(--color-text)",
        fontSize: "0.82rem",
        lineHeight: 1.4,
        zIndex: 50,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, overflow: "hidden" }}>
        <Shield size={14} style={{ color: "var(--color-primary, #1B6EF3)", flexShrink: 0 }} />
        <div style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          <span>Operating as </span>
          <strong style={{ color: "var(--color-primary, #1B6EF3)" }}>{activeRole.name}</strong>
          <span style={{ opacity: 0.7 }}> — Permissions scoped strictly to this group</span>
          {me?.email && (
            <span style={{ opacity: 0.6, marginLeft: 6 }}>
              (audited as {me.email})
            </span>
          )}
        </div>
      </div>

      <button
        type="button"
        onClick={handleExit}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 4,
          padding: "3px 8px",
          borderRadius: 4,
          border: "1px solid var(--color-border)",
          background: "var(--color-surface, #ffffff)",
          color: "var(--color-text)",
          cursor: "pointer",
          fontSize: "0.78rem",
          fontWeight: 500,
          flexShrink: 0,
          marginLeft: 12,
        }}
        title="Exit assumed role and return to personal context"
      >
        <span>Switch to Personal Context</span>
        <X size={12} style={{ opacity: 0.7 }} />
      </button>
    </div>
  );
};
