import React from "react";
import { useNavigate } from "react-router-dom";
import { clearSession } from "../../lib/auth";
import { useMe } from "../../lib/userManagerApi";

export default function NoWorkspacePage() {
  const navigate = useNavigate();
  const { data: me } = useMe();
  const isAccountAdmin = me?.account_role === "account_admin" || me?.is_account_admin;

  const handleLogout = () => {
    clearSession();
    navigate("/login");
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "var(--color-bg)",
        color: "var(--color-text)",
        fontFamily: "var(--font-family)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
        boxSizing: "border-box",
      }}
    >
      <div
        className="glass"
        style={{
          width: "100%",
          maxWidth: "440px",
          borderRadius: "var(--radius-lg)",
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          padding: "40px 32px",
          textAlign: "center",
          boxShadow: "var(--shadow-md)",
        }}
      >
        <div
          style={{
            width: "56px",
            height: "56px",
            borderRadius: "var(--radius-lg)",
            background: isAccountAdmin ? "var(--color-primary-bg, rgba(99, 102, 241, 0.1))" : "var(--color-danger-bg)",
            border: `1px solid ${isAccountAdmin ? "var(--color-primary, #6366f1)" : "var(--color-danger)"}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "24px",
            margin: "0 auto 20px",
          }}
        >
          {isAccountAdmin ? "📁" : "🔒"}
        </div>

        <h1 style={{ margin: "0 0 8px", fontSize: "20px", fontWeight: 700, color: "var(--color-text)" }}>
          {isAccountAdmin ? "No Workspace Found" : "No Workspace Access"}
        </h1>
        <p
          style={{
            margin: "0 0 24px",
            color: "var(--color-text-muted)",
            fontSize: "14px",
            lineHeight: 1.5,
          }}
        >
          {isAccountAdmin
            ? "You don't have any workspaces yet. Create your first workspace to start using Compass."
            : "You don't have access to any workspaces yet. Please contact your account administrator to get workspace access."}
        </p>

        <div style={{ display: "flex", gap: "12px", justifyContent: "center" }}>
          {isAccountAdmin && (
            <button
              onClick={() => navigate("/workspace/create")}
              className="btn-primary"
              style={{ padding: "10px 20px" }}
            >
              + Create Workspace
            </button>
          )}
          <button
            onClick={handleLogout}
            className="btn-outline"
            style={{ padding: "10px 20px" }}
          >
            Log Out
          </button>
        </div>
      </div>
    </div>
  );
}
