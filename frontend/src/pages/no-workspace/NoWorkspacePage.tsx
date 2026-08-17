import React from "react";
import { useNavigate } from "react-router-dom";
import { clearSession } from "../../lib/auth";

export default function NoWorkspacePage() {
  const navigate = useNavigate();

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
          maxWidth: "420px",
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
            background: "var(--color-danger-bg)",
            border: "1px solid var(--color-danger)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "24px",
            margin: "0 auto 20px",
          }}
        >
          🔒
        </div>

        <h1 style={{ margin: "0 0 8px", fontSize: "20px", fontWeight: 700, color: "var(--color-text)" }}>
          No Workspace Access
        </h1>
        <p
          style={{
            margin: "0 0 24px",
            color: "var(--color-text-muted)",
            fontSize: "14px",
            lineHeight: 1.5,
          }}
        >
          You don't have access to any workspaces yet. Please contact your account
          administrator to get workspace access.
        </p>

        <button
          onClick={handleLogout}
          className="btn-outline"
          style={{ padding: "10px 24px" }}
        >
          Log Out
        </button>
      </div>
    </div>
  );
}
