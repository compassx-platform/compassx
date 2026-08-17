import React from "react";
import { useNavigate } from "react-router-dom";
import type { AppRead } from "../lib/appsApi";

interface Props {
  app: AppRead;
  workspaceSlug: string;
  appScopeId: string;
}

export default function AppCard({ app, workspaceSlug, appScopeId }: Props) {
  const navigate = useNavigate();

  return (
    <div
      id={`app-card-${app.app_id}`}
      className="app-card"
      onClick={() =>
        navigate(`/w/${workspaceSlug}/${appScopeId}/apps_development/${app.app_id}/main`)
      }
      style={{
        background: "var(--surface-2, #1e1e2e)",
        border: "1px solid var(--border, #313244)",
        borderRadius: "12px",
        padding: "20px 24px",
        cursor: "pointer",
        transition: "border-color 0.15s, box-shadow 0.15s",
        display: "flex",
        flexDirection: "column",
        gap: "8px",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLDivElement).style.borderColor = "var(--accent, #89b4fa)";
        (e.currentTarget as HTMLDivElement).style.boxShadow = "0 0 0 1px var(--accent, #89b4fa)22";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.borderColor = "var(--border, #313244)";
        (e.currentTarget as HTMLDivElement).style.boxShadow = "none";
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <span style={{ fontSize: "20px" }}>⚡</span>
        <span
          style={{
            fontWeight: 600,
            fontSize: "15px",
            color: "var(--text-primary, #cdd6f4)",
          }}
        >
          {app.name}
        </span>
      </div>
      <div style={{ fontSize: "12px", color: "var(--text-muted, #6c7086)", fontFamily: "monospace" }}>
        {app.catalog_fqn}
      </div>
      <div style={{ display: "flex", gap: "8px", marginTop: "6px" }}>
        <span
          style={{
            fontSize: "11px",
            padding: "2px 8px",
            borderRadius: "999px",
            background: app.versioning_backend === "git" ? "#313244" : "#1e3a5f",
            color: app.versioning_backend === "git" ? "#89b4fa" : "#74c7ec",
          }}
        >
          {app.versioning_backend}
        </span>
        <span
          style={{
            fontSize: "11px",
            padding: "2px 8px",
            borderRadius: "999px",
            background: "#313244",
            color: "#a6e3a1",
          }}
        >
          max {app.max_concurrent_branches} branches
        </span>
      </div>
    </div>
  );
}
