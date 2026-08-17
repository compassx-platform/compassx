import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useApps, useCreateApp } from "../hooks/useApps";
import { useWorkspaceContext } from "@/lib/workspaceContext";
import { Table, type TableColumn } from "@/components/common/Table";
import { Play, Plus } from "lucide-react";
import type { AppRead } from "../lib/appsApi";

/**
 * Apps list page — route: /w/:workspaceSlug/:appId/apps_development
 *
 * Lists all apps in the current workspace using the shared Table component.
 */
export default function AppsListPage() {
  const { workspaceSlug, appId: appScopeId } = useParams<{
    workspaceSlug: string;
    appId: string;
  }>();

  const workspaceCtx = useWorkspaceContext();
  const workspaceId = workspaceCtx.id;
  const navigate = useNavigate();

  const { data: apps = [], isLoading, error } = useApps(workspaceId);
  const { mutate: createApp, isPending: creating } = useCreateApp();

  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState("");
  const [newFqn, setNewFqn] = useState("");

  const handleCreate = () => {
    if (!newName.trim() || !newFqn.trim()) return;
    createApp(
      {
        name: newName.trim(),
        catalog_fqn: newFqn.trim(),
        workspace_id: workspaceId,
        versioning_backend: "native",
      },
      {
        onSuccess: () => {
          setShowNew(false);
          setNewName("");
          setNewFqn("");
        },
      },
    );
  };

  const columns: TableColumn<AppRead>[] = [
    {
      key: "name",
      header: "Name",
      render: (row) => <span style={{ fontWeight: 600 }}>{row.name}</span>,
    },
    {
      key: "catalog_fqn",
      header: "Catalog FQN",
      render: (row) => <code style={{ fontSize: "12px" }}>{row.catalog_fqn}</code>,
    },
    {
      key: "versioning_backend",
      header: "Versioning",
      render: (row) => (
        <span className={`badge ${row.versioning_backend === "git" ? "badge-open" : "badge-closed"}`}>
          {row.versioning_backend}
        </span>
      ),
    },
    {
      key: "created_at",
      header: "Created At",
      render: (row) => new Date(row.created_at).toLocaleString(),
    },
  ];

  const primaryAction = {
    label: "Open",
    icon: Play,
    onClick: (row: AppRead) => {
      navigate(`/w/${workspaceSlug}/${appScopeId}/apps_development/${row.app_id}/main`);
    },
  };

  return (
    <div className="page-section animate-fade-in">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">⚡ Apps</h1>
          <p className="page-subtitle">
            FastAPI + React apps — build, branch, publish
          </p>
        </div>
        <button
          id="new-app-btn"
          className="btn-primary"
          onClick={() => setShowNew(true)}
        >
          <Plus size={15} /> Add App
        </button>
      </div>

      {/* Apps Table */}
      <Table
        columns={columns}
        rows={apps}
        keyExtractor={(row) => row.app_id}
        primaryAction={primaryAction}
        loading={isLoading}
        error={!!error}
        errorState={<div className="table-empty error">Failed to load apps: {String(error)}</div>}
        emptyState={
          <div className="table-empty">
            No apps yet. Create your first app to get started.
          </div>
        }
      />

      {/* New App Modal */}
      {showNew && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.4)",
            zIndex: 1000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
          onClick={(e) => e.target === e.currentTarget && setShowNew(false)}
        >
          <div
            className="glass"
            style={{
              borderRadius: "12px",
              padding: "24px",
              width: "460px",
              display: "flex",
              flexDirection: "column",
              gap: "16px",
              background: "var(--color-surface)",
              color: "var(--color-text)",
            }}
          >
            <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 600 }}>
              Create New App
            </h3>
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <label className="label">App Name</label>
              <input
                id="new-app-name-input"
                className="form-input"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="my-awesome-app"
              />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <label className="label">
                Catalog FQN <span style={{ opacity: 0.6 }}>(catalog.schema.app_name)</span>
              </label>
              <input
                id="new-app-fqn-input"
                className="form-input"
                value={newFqn}
                onChange={(e) => setNewFqn(e.target.value)}
                placeholder="main.development.my_awesome_app"
              />
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "4px" }}>
              <button
                className="btn-outline"
                onClick={() => setShowNew(false)}
              >
                Cancel
              </button>
              <button
                id="create-app-confirm-btn"
                className="btn-primary"
                onClick={handleCreate}
                disabled={!newName.trim() || !newFqn.trim() || creating}
              >
                {creating ? "Creating…" : "Create App"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
