import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useApp } from "../hooks/useApps";
import { useBranches, useCreateBranch } from "../hooks/useBranches";
import { useFiles, useWriteFile } from "../hooks/useFiles";
import { FilePlus } from "lucide-react";
import BranchSelector from "../components/BranchSelector";
import CheckpointButton from "../components/CheckpointButton";
import PublishButton from "../components/PublishButton";
import FileTree from "../components/FileTree";
import MonacoEditor from "../components/MonacoEditor";
import LivePreviewPane from "../components/LivePreviewPane";
import TerminalPanel from "../components/TerminalPanel";
import AgentChatPanel from "../components/AgentChatPanel";

type SidePanel = "preview" | "agent";
type BottomPanel = "terminal" | null;

/**
 * App editor page — full IDE layout.
 *
 * Route: /w/:workspaceSlug/:appId/apps_development/:compassAppId/:branchId
 *
 * Layout:
 *   ┌─────────────────────────────────────────────────────────┐
 *   │  Top bar: BranchSelector | Checkpoint | Publish         │
 *   ├──────────┬──────────────────────────────┬───────────────┤
 *   │ FileTree │      Monaco Editor           │ Preview/Agent │
 *   │  (left)  │      (main pane)             │ (right panel) │
 *   ├──────────┴──────────────────────────────┴───────────────┤
 *   │  Terminal (bottom, gated by terminal_enabled)           │
 *   └─────────────────────────────────────────────────────────┘
 */
export default function AppEditorPage() {
  const { workspaceSlug, appId: appScopeId, compassAppId, branchId: urlBranchId } =
    useParams<{
      workspaceSlug: string;
      appId: string;
      compassAppId: string;
      branchId: string;
    }>();

  const navigate = useNavigate();

  const { data: app } = useApp(compassAppId ?? "");
  const { data: branches = [] } = useBranches(compassAppId ?? "");
  const { mutate: createBranch } = useCreateBranch(compassAppId ?? "");

  const [activeBranchId, setActiveBranchId] = useState<string>(urlBranchId || "main");
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [sidePanel, setSidePanel] = useState<SidePanel>("preview");
  const [bottomPanel, setBottomPanel] = useState<BottomPanel>(null);

  useEffect(() => {
    if (urlBranchId) {
      setActiveBranchId(urlBranchId);
    }
  }, [urlBranchId]);

  useEffect(() => {
    if (branches.length > 0 && activeBranchId === "main") {
      const mainBranch = branches.find((b) => b.name === "main");
      if (mainBranch) {
        setActiveBranchId(mainBranch.branch_id);
        navigate(`/w/${workspaceSlug}/${appScopeId}/apps_development/${compassAppId}/${mainBranch.branch_id}`, { replace: true });
      }
    }
  }, [branches, activeBranchId, workspaceSlug, appScopeId, compassAppId, navigate]);

  const { data: fileTree } = useFiles(compassAppId ?? "", activeBranchId);
  const { mutate: createFile } = useWriteFile(compassAppId ?? "", activeBranchId);

  const activeBranch = branches.find((b) => b.branch_id === activeBranchId);

  const handleNewFile = () => {
    const path = prompt("Enter new file path (e.g. backend/utils.py):");
    if (!path) return;
    createFile(
      { path, content: "" },
      {
        onSuccess: () => {
          setSelectedFile(path);
        },
      }
    );
  };

  // Resolve pod info for terminal gating + preview URL
  // In a real implementation this would come from a usePod hook; using defaults here
  const terminalEnabled = true; // TODO: from active pod record
  const previewUrl = `/pods/app-${compassAppId}-branch-${activeBranchId}`;

  const isUuid = (str: string) =>
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(str);

  const handleNewBranch = () => {
    const name = prompt("New branch name:");
    if (!name) return;
    const fromId = isUuid(activeBranchId) ? activeBranchId : null;
    createBranch(
      { name, from_branch_id: fromId },
      {
        onSuccess: (b) => {
          setActiveBranchId(b.branch_id);
          navigate(`/w/${workspaceSlug}/${appScopeId}/apps_development/${compassAppId}/${b.branch_id}`);
        },
      },
    );
  };

  return (
    <div
      style={{
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        background: "var(--color-bg)",
        color: "var(--color-text)",
        overflow: "hidden",
      }}
    >
      {/* ── Top bar ── */}
      <div
        id="editor-topbar"
        style={{
          height: "44px",
          display: "flex",
          alignItems: "center",
          gap: "10px",
          padding: "0 14px",
          borderBottom: "1px solid var(--color-border)",
          flexShrink: 0,
          background: "var(--color-surface)",
        }}
      >
        <span style={{ fontWeight: 700, fontSize: "14px", color: "var(--color-primary)", marginRight: 4 }}>
          ⚡ {app?.name ?? "…"}
        </span>

        <BranchSelector
          branches={branches}
          activeBranchId={activeBranchId}
          onSwitch={(id) => {
            setActiveBranchId(id);
            navigate(`/w/${workspaceSlug}/${appScopeId}/apps_development/${compassAppId}/${id}`);
          }}
          onNewBranch={handleNewBranch}
        />

        <div style={{ flex: 1 }} />

        <CheckpointButton appId={compassAppId ?? ""} branchId={activeBranchId} />
        <PublishButton
          appId={compassAppId ?? ""}
          branchId={activeBranchId}
          headCommitId={activeBranch?.head_commit_id ?? null}
        />

        {/* Side panel toggles */}
        <div style={{ display: "flex", gap: "4px", marginLeft: "8px" }}>
          <button
            id="toggle-preview-btn"
            onClick={() => setSidePanel("preview")}
            style={{
              background: sidePanel === "preview" ? "var(--color-primary-bg)" : "transparent",
              border: "1px solid var(--color-border)",
              borderRadius: "6px",
              color: sidePanel === "preview" ? "var(--color-primary)" : "var(--color-text-muted)",
              padding: "4px 10px",
              fontSize: "12px",
              cursor: "pointer",
            }}
          >
            Preview
          </button>
          <button
            id="toggle-agent-btn"
            onClick={() => setSidePanel("agent")}
            style={{
              background: sidePanel === "agent" ? "var(--color-primary-bg)" : "transparent",
              border: "1px solid var(--color-border)",
              borderRadius: "6px",
              color: sidePanel === "agent" ? "var(--color-primary)" : "var(--color-text-muted)",
              padding: "4px 10px",
              fontSize: "12px",
              cursor: "pointer",
            }}
          >
            Pi Agent
          </button>
          {terminalEnabled && (
            <button
              id="toggle-terminal-btn"
              onClick={() => setBottomPanel(bottomPanel === "terminal" ? null : "terminal")}
              style={{
                background: bottomPanel === "terminal" ? "var(--color-primary-bg)" : "transparent",
                border: "1px solid var(--color-border)",
                borderRadius: "6px",
                color: bottomPanel === "terminal" ? "var(--color-primary)" : "var(--color-text-muted)",
                padding: "4px 10px",
                fontSize: "12px",
                cursor: "pointer",
              }}
            >
              Terminal
            </button>
          )}
        </div>
      </div>

      {/* ── Main area ── */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* File tree — left panel */}
        <div
          id="editor-file-tree"
          style={{
            width: "220px",
            flexShrink: 0,
            borderRight: "1px solid var(--color-border)",
            display: "flex",
            flexDirection: "column",
            background: "var(--color-surface)",
          }}
        >
          {/* File tree header */}
          <div
            style={{
              padding: "10px 14px",
              borderBottom: "1px solid var(--color-border)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexShrink: 0,
            }}
          >
            <span style={{ fontWeight: 600, fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.5px", color: "var(--color-text-muted)" }}>
              Workspace Files
            </span>
            <button
              id="new-file-btn"
              onClick={handleNewFile}
              title="New File"
              style={{
                background: "transparent",
                border: "none",
                color: "var(--color-text-muted)",
                cursor: "pointer",
                padding: "2px",
                display: "flex",
                alignItems: "center",
                borderRadius: "4px",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.color = "var(--color-primary)"; e.currentTarget.style.background = "var(--color-surface-hover)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = "var(--color-text-muted)"; e.currentTarget.style.background = "transparent"; }}
            >
              <FilePlus size={16} />
            </button>
          </div>

          <div style={{ flex: 1, overflowY: "auto" }}>
            <FileTree
              files={fileTree?.files ?? []}
              selectedPath={selectedFile}
              onSelect={setSelectedFile}
            />
          </div>
        </div>

        {/* Editor — main pane */}
        <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
          {/* Bottom panel (terminal) */}
          <div style={{ flex: 1, overflow: "hidden" }}>
            {selectedFile ? (
              <MonacoEditor
                appId={compassAppId ?? ""}
                branchId={activeBranchId}
                path={selectedFile}
              />
            ) : (
              <div
                style={{
                  height: "100%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "var(--color-text-muted)",
                  fontSize: "14px",
                }}
              >
                Select a file to edit
              </div>
            )}
          </div>

          {bottomPanel === "terminal" && (
            <div
              id="editor-terminal"
              style={{
                height: "220px",
                flexShrink: 0,
                borderTop: "1px solid var(--color-border)",
              }}
            >
              <TerminalPanel
                appId={compassAppId ?? ""}
                branchId={activeBranchId}
                enabled={terminalEnabled}
              />
            </div>
          )}
        </div>

        {/* Right panel — Preview or Agent */}
        <div
          id="editor-right-panel"
          style={{
            width: "380px",
            flexShrink: 0,
            borderLeft: "1px solid var(--color-border)",
            overflow: "hidden",
          }}
        >
          {sidePanel === "preview" ? (
            <LivePreviewPane previewUrl={previewUrl} />
          ) : (
            <AgentChatPanel
              appId={compassAppId ?? ""}
              branchId={activeBranchId}
            />
          )}
        </div>
      </div>
    </div>
  );
}
