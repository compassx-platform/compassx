import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMe, useMyWorkspaces, setDefaultWorkspace, fetchEntryPoint, type WorkspaceMembershipOut } from "../../lib/userManagerApi";

export default function WorkspacePickerPage() {
  const navigate = useNavigate();
  const { data: me } = useMe();
  const { data: workspaces = [], isLoading, error } = useMyWorkspaces();
  const [selectedWorkspace, setSelectedWorkspace] = useState<string | null>(null);
  const [makeDefault, setMakeDefault] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const isAccountAdmin = me?.account_role === "account_admin" || me?.is_account_admin;

  const handleContinue = async () => {
    if (!selectedWorkspace) return;

    setSubmitting(true);
    try {
      await setDefaultWorkspace(selectedWorkspace);
      try {
        localStorage.setItem("compassx_last_workspace", selectedWorkspace);
      } catch {}
      const selectedWsObj = workspaces.find(w => w.workspace_id === selectedWorkspace);
      const targetSlug = selectedWsObj?.workspace_slug || selectedWorkspace;

      const ep = await fetchEntryPoint(selectedWorkspace);
      if (ep.route && ep.route.startsWith("/w/")) {
        navigate(ep.route);
      } else {
        navigate(`/w/${targetSlug}/platform`);
      }
    } catch (err) {
      console.error("Failed to select workspace", err);
    } finally {
      setSubmitting(false);
    }
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
          maxWidth: "600px",
          borderRadius: "var(--radius-lg)",
          padding: "36px",
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          boxShadow: "var(--shadow-md)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "28px" }}>
          <div>
            <h1
              style={{
                margin: "0 0 6px",
                fontSize: "24px",
                fontWeight: 700,
                color: "var(--color-text)",
              }}
            >
              Select a Workspace
            </h1>
            <p style={{ margin: 0, color: "var(--color-text-muted)", fontSize: "14px" }}>
              Choose where you want to work today.
            </p>
          </div>
          {isAccountAdmin && (
            <button
              className="btn-outline"
              onClick={() => navigate("/workspace/create")}
              style={{ fontSize: "13px", padding: "8px 14px" }}
            >
              + Create Workspace
            </button>
          )}
        </div>

        {error && (
          <div
            style={{
              marginBottom: "20px",
              padding: "12px 16px",
              background: "var(--color-danger-bg)",
              border: "1px solid var(--color-danger)",
              borderRadius: "var(--radius)",
              color: "var(--color-danger)",
              fontSize: "13px",
            }}
          >
            Failed to load workspaces. Please try refreshing.
          </div>
        )}

        {isLoading ? (
          <div style={{ textAlign: "center", padding: "48px 0", color: "var(--color-text-muted)" }}>
            Loading workspaces…
          </div>
        ) : workspaces.length === 0 ? (
          <div
            style={{
              textAlign: "center",
              padding: "48px 24px",
              background: "var(--color-bg)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius)",
            }}
          >
            <div style={{ fontSize: "36px", marginBottom: "8px" }}>🏢</div>
            <h3 style={{ margin: "0 0 6px", color: "var(--color-text)", fontSize: "16px" }}>
              No Workspaces Found
            </h3>
            <p style={{ margin: 0, color: "var(--color-text-muted)", fontSize: "13px" }}>
              You don't have access to any workspaces yet. Contact your admin.
            </p>
          </div>
        ) : (
          <>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
                gap: "14px",
                marginBottom: "28px",
              }}
            >
              {workspaces.map((ws: WorkspaceMembershipOut) => {
                const isSelected = selectedWorkspace === ws.workspace_id;
                return (
                  <div
                    key={ws.workspace_id}
                    onClick={() => setSelectedWorkspace(ws.workspace_id)}
                    style={{
                      padding: "18px",
                      borderRadius: "var(--radius)",
                      border: `1px solid ${isSelected ? "var(--color-primary)" : "var(--color-border)"}`,
                      background: isSelected
                        ? "var(--color-primary-bg)"
                        : "var(--color-surface)",
                      cursor: "pointer",
                      transition: "all 0.15s",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: "10px",
                      }}
                    >
                      <span style={{ fontWeight: 600, fontSize: "15px", color: "var(--color-text)" }}>
                        {ws.workspace_name || ws.workspace_id.slice(0, 8)}
                      </span>
                      {isSelected && (
                        <span style={{ color: "var(--color-primary)", fontWeight: 800, fontSize: "16px" }}>
                          ✓
                        </span>
                      )}
                    </div>
                    <span
                      style={{
                        fontSize: "11px",
                        fontWeight: 600,
                        padding: "3px 8px",
                        borderRadius: "4px",
                        background: "var(--color-bg)",
                        color: "var(--color-text-muted)",
                      }}
                    >
                      {ws.role_id.replace(/_/g, " ")}
                    </span>
                  </div>
                );
              })}
            </div>

            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                paddingTop: "20px",
                borderTop: "1px solid var(--color-border)",
              }}
            >
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  cursor: "pointer",
                  color: "var(--color-text)",
                  fontSize: "13px",
                }}
              >
                <input
                  type="checkbox"
                  checked={makeDefault}
                  onChange={(e) => setMakeDefault(e.target.checked)}
                  style={{ accentColor: "var(--color-primary)", width: "16px", height: "16px" }}
                />
                Make this my default workspace
              </label>

              <button
                onClick={handleContinue}
                disabled={!selectedWorkspace || submitting}
                className="btn-primary"
                style={{
                  padding: "10px 24px",
                  fontSize: "14px",
                }}
              >
                {submitting ? "Loading…" : "Continue →"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
