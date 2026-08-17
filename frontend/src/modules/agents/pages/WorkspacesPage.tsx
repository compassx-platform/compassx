import { useState } from "react";
import { useScopedNavigate } from "@/lib/appNavigation";
import {
  Layers,
  Plus,
  Search,
  Trash2,
  Settings2,
  ChevronRight,
  Loader2,
  Bot,
} from "lucide-react";
import {
  useWorkspaces,
  useCreateWorkspace,
  useDeleteWorkspace,
} from "@/modules/agents/hooks/useWorkspace";
import { useWorkspaceStore } from "@/modules/agents/stores/workspaceStore";
import { useToast } from "@/lib/toast";

function CreateWorkspaceModal({ onClose }: { onClose: () => void }) {
  const { mutateAsync, isPending } = useCreateWorkspace();
  const toast = useToast();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      await mutateAsync({ name: name.trim(), description: description.trim() || undefined });
      toast.success(`Workspace "${name}" created`);
      onClose();
    } catch {
      toast.error("Failed to create workspace");
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">New Workspace</h2>
        </div>
        <form onSubmit={handleSubmit} className="modal-body">
          <div className="form-group">
            <label className="form-label">Name *</label>
            <input
              className="form-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Data Engineering"
              autoFocus
            />
          </div>
          <div className="form-group">
            <label className="form-label">Description</label>
            <textarea
              className="form-input"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What is this workspace for?"
            />
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={isPending || !name.trim()}>
              {isPending ? <Loader2 size={14} className="spin" /> : <Plus size={14} />}
              Create Workspace
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function WorkspacesPage() {
  const navigate = useScopedNavigate();
  const { data: workspaces, isLoading, error } = useWorkspaces();
  const deleteMutation = useDeleteWorkspace();
  const toast = useToast();
  const { setActiveWorkspace } = useWorkspaceStore();
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);

  const filtered = (workspaces ?? []).filter((w) => {
    const q = search.trim().toLowerCase();
    return !q || w.name.toLowerCase().includes(q) || (w.description ?? "").toLowerCase().includes(q);
  });

  function handleOpen(id: number) {
    setActiveWorkspace(id);
    navigate(`/agents/workspaces/${id}/agents`);
  }

  async function handleDelete(e: React.MouseEvent, id: number, name: string) {
    e.stopPropagation();
    if (!confirm(`Delete workspace "${name}"? This will delete all agents, connections, and data.`)) return;
    try {
      await deleteMutation.mutateAsync(id);
      toast.success(`Workspace "${name}" deleted`);
    } catch {
      toast.error("Failed to delete workspace");
    }
  }

  return (
    <div className="page-section">
      <div className="page-header">
        <div>
          <h1 className="page-title">Workspaces</h1>
          <p className="page-subtitle">Organize agents, connections, and context into isolated environments.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
          <Plus size={15} /> New Workspace
        </button>
      </div>

      <div className="search-bar-wrapper">
        <Search size={14} className="search-icon" />
        <input
          className="search-input"
          placeholder="Search workspaces…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="admin-table-wrap">
        {isLoading ? (
          <div className="table-empty"><Loader2 size={20} className="spin" /> Loading…</div>
        ) : error ? (
          <div className="table-empty error">Failed to load workspaces.</div>
        ) : filtered.length === 0 ? (
          <div className="table-empty">
            <Layers size={32} style={{ opacity: 0.3, marginBottom: 8 }} />
            <div>No workspaces yet.</div>
            <button className="btn btn-secondary" style={{ marginTop: 12 }} onClick={() => setShowCreate(true)}>
              <Plus size={14} /> Create your first workspace
            </button>
          </div>
        ) : (
          <table className="admin-table">
            <thead>
              <tr>
                <th style={{ width: "40%" }}>Name</th>
                <th style={{ width: "20%" }}>Created by</th>
                <th style={{ width: "15%" }}>Created</th>
                <th style={{ width: "15%" }} />
                <th style={{ width: "10%" }} />
              </tr>
            </thead>
            <tbody>
              {filtered.map((ws) => (
                <tr
                  key={ws.id}
                  className="table-row-clickable"
                  onClick={() => handleOpen(ws.id)}
                >
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <Layers size={14} color="var(--color-primary)" style={{ flexShrink: 0 }} />
                      <div>
                        <div style={{ fontWeight: 500, fontSize: "0.875rem" }}>{ws.name}</div>
                        {ws.description && (
                          <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginTop: 1 }}>
                            {ws.description}
                          </div>
                        )}
                      </div>
                    </div>
                  </td>
                  <td style={{ fontSize: "0.8rem", color: "var(--color-text-muted)" }}>
                    {ws.created_by ?? "—"}
                  </td>
                  <td style={{ fontSize: "0.8rem", color: "var(--color-text-muted)" }}>
                    {new Date(ws.created_at).toLocaleDateString()}
                  </td>
                  <td>
                    <div style={{ display: "flex", gap: 8 }}>
                      <button
                        className="btn btn-secondary"
                        style={{ fontSize: "0.75rem", padding: "3px 10px", height: "auto" }}
                        onClick={(e) => { e.stopPropagation(); handleOpen(ws.id); }}
                      >
                        <Bot size={12} /> Open Agents
                        <ChevronRight size={12} />
                      </button>
                    </div>
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <div className="row-actions">
                      <button
                        className="btn-icon"
                        title="Settings"
                        onClick={(e) => { e.stopPropagation(); navigate(`/agents/workspaces/${ws.id}/settings`); }}
                      >
                        <Settings2 size={14} />
                      </button>
                      <button
                        className="btn-icon btn-icon-danger"
                        title="Delete"
                        onClick={(e) => handleDelete(e, ws.id, ws.name)}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showCreate && <CreateWorkspaceModal onClose={() => setShowCreate(false)} />}
    </div>
  );
}

