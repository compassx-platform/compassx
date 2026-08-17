import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  GitBranch,
  Plus,
  Trash2,
  Edit2,
  Play,
  Loader2,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import {
  useGitConnections,
  useCreateGitConnection,
  useUpdateGitConnection,
  useDeleteGitConnection,
  useTestGitConnection,
  type GitConnection,
} from "@/modules/agents/hooks/useGitConnections";
import { useToast } from "@/lib/toast";
import { useScopedNavigate } from "@/lib/appNavigation";

const PROVIDERS = [
  { value: "github",       label: "GitHub" },
  { value: "azure_devops", label: "Azure DevOps" },
];

type FormPayload = {
  name: string;
  provider: string;
  organization: string;
  default_project: string;
  base_url: string;
  pat: string;
};

function GitConnectionForm({
  initial,
  onSave,
  onCancel,
  isSaving,
}: {
  initial?: Partial<GitConnection>;
  onSave: (data: Omit<FormPayload, "pat"> & { pat?: string }) => void;
  onCancel: () => void;
  isSaving: boolean;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [provider, setProvider] = useState(initial?.provider ?? "github");
  const [organization, setOrganization] = useState(initial?.organization ?? "");
  const [defaultProject, setDefaultProject] = useState(initial?.default_project ?? "");
  const [baseUrl, setBaseUrl] = useState(initial?.base_url ?? "");
  const [pat, setPat] = useState("");

  const isAdo = provider === "azure_devops";

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSave({
      name,
      provider,
      organization: organization || '',
      default_project: defaultProject || '',
      base_url: baseUrl || '',
      pat: pat || undefined,
    });
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div className="form-group">
          <label className="form-label">Name *</label>
          <input
            className="form-input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. IpPlatform ADO"
            required
          />
        </div>
        <div className="form-group">
          <label className="form-label">Provider *</label>
          <select
            className="form-input"
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            disabled={!!initial?.id}   // can't change provider on edit
          >
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
        </div>
      </div>

      {isAdo && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <div className="form-group">
            <label className="form-label">Organization *</label>
            <input
              className="form-input"
              value={organization}
              onChange={(e) => setOrganization(e.target.value)}
              placeholder="e.g. IpPlatform"
              required={isAdo}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Default Project</label>
            <input
              className="form-input"
              value={defaultProject}
              onChange={(e) => setDefaultProject(e.target.value)}
              placeholder="e.g. IDCC"
            />
          </div>
        </div>
      )}

      <div className="form-group">
        <label className="form-label">Base URL <span style={{ fontWeight: 400, color: "var(--color-text-muted)" }}>(optional — for self-hosted)</span></label>
        <input
          className="form-input"
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
          placeholder={isAdo ? "https://dev.azure.com/MyOrg" : "https://github.mycompany.com"}
        />
      </div>

      <div className="form-group">
        <label className="form-label">
          Personal Access Token {initial?.id ? "(leave blank to keep existing)" : "*"}
        </label>
        <input
          className="form-input"
          type="password"
          value={pat}
          onChange={(e) => setPat(e.target.value)}
          placeholder={initial?.pat_configured ? "Enter new PAT to replace…" : "Paste your PAT…"}
          required={!initial?.id}
          autoComplete="new-password"
        />
        <div style={{ fontSize: "0.7rem", color: "var(--color-text-muted)", marginTop: 4 }}>
          {isAdo
            ? "Azure DevOps: Code (Read & Write) scope required."
            : "GitHub: repo scope required for private repos."}
          {" "}Stored encrypted — never shown again.
        </div>
      </div>

      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
        <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={isSaving || !name}>
          {isSaving ? <Loader2 size={14} className="spin" /> : null}
          {initial?.id ? "Update" : "Create"}
        </button>
      </div>
    </form>
  );
}

export default function GitConnectionsPage() {
  const navigate = useScopedNavigate();
  const [searchParams] = useSearchParams();
  const { data: connections = [], isLoading } = useGitConnections();
  const createMutation = useCreateGitConnection();
  const updateMutation = useUpdateGitConnection();
  const deleteMutation = useDeleteGitConnection();
  const testMutation = useTestGitConnection();
  const toast = useToast();

  const [showForm, setShowForm] = useState(true);
  const [editing, setEditing] = useState<GitConnection | null>(null);
  const [testStatus, setTestStatus] = useState<Record<number, "ok" | "fail" | "testing">>({});
  const editId = Number(searchParams.get("edit"));

  useEffect(() => {
    if (!editId || Number.isNaN(editId)) return;
    const connection = connections.find((conn) => conn.id === editId);
    if (!connection || editing?.id === connection.id) return;
    setEditing(connection);
    setShowForm(false);
  }, [connections, editId, editing?.id]);

  async function handleSave(data: Parameters<typeof createMutation.mutateAsync>[0]["payload"]) {
    try {
      if (editing) {
        await updateMutation.mutateAsync({ connId: editing.id, payload: data });
        toast.success("Connection updated");
        setEditing(null);
        navigate("/connections");
      } else {
        await createMutation.mutateAsync({ payload: data });
        toast.success("Connection created");
        navigate("/connections");
      }
    } catch {
      toast.error("Failed to save connection");
    }
  }

  async function handleDelete(conn: GitConnection) {
    if (!confirm(`Delete "${conn.name}"?`)) return;
    try {
      await deleteMutation.mutateAsync({ connId: conn.id });
      toast.success("Connection deleted");
    } catch {
      toast.error("Failed to delete");
    }
  }

  async function handleTest(conn: GitConnection) {
    setTestStatus((s) => ({ ...s, [conn.id]: "testing" }));
    try {
      const result = await testMutation.mutateAsync({ connId: conn.id });
      setTestStatus((s) => ({ ...s, [conn.id]: result.success ? "ok" : "fail" }));
      if (result.success) toast.success(result.message);
      else toast.error(result.message);
    } catch {
      setTestStatus((s) => ({ ...s, [conn.id]: "fail" }));
      toast.error("Test failed");
    }
  }

  return (
    <div className="page-section">
      <div className="page-header">
        <div>
          <h1 className="page-title">Git Connections</h1>
          <p className="page-subtitle">Connect GitHub or Azure DevOps so agents can read and review code.</p>
        </div>
        {!showForm && !editing && (
          <button className="btn btn-primary" onClick={() => setShowForm(true)}>
            <Plus size={15} /> Add Connection
          </button>
        )}
      </div>

      {(showForm || editing) && (
        <div
          style={{
            padding: "20px 24px",
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: 8,
            marginBottom: 20,
          }}
        >
          <div style={{ fontWeight: 600, fontSize: "0.9rem", marginBottom: 16 }}>
            {editing ? `Edit: ${editing.name}` : "New Git Connection"}
          </div>
          <GitConnectionForm
            key={editing?.id ?? "new"}
            initial={editing ?? undefined}
            onSave={handleSave}
            onCancel={() => navigate("/connections")}
            isSaving={createMutation.isPending || updateMutation.isPending}
          />
        </div>
      )}

      {!showForm && !editing && (
      <div className="admin-table-wrap">
        {isLoading ? (
          <div className="table-empty"><Loader2 size={20} className="spin" /> Loading…</div>
        ) : connections.length === 0 ? (
          <div className="table-empty">
            <GitBranch size={32} style={{ opacity: 0.3, marginBottom: 8 }} />
            <div>No Git connections yet.</div>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {connections.map((conn) => (
              <div
                key={conn.id}
                style={{
                  padding: "14px 18px",
                  background: "var(--color-surface)",
                  border: "1px solid var(--color-border)",
                  borderRadius: 8,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <GitBranch size={14} color="var(--color-primary)" />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 500, fontSize: "0.875rem", display: "flex", alignItems: "center", gap: 8 }}>
                      {conn.name}
                      <span
                        style={{
                          fontSize: "0.65rem",
                          fontWeight: 600,
                          padding: "2px 6px",
                          borderRadius: 4,
                          background: conn.provider === "github" ? "rgba(36,41,47,0.1)" : "rgba(0,120,212,0.1)",
                          color: conn.provider === "github" ? "#24292f" : "rgb(0,120,212)",
                          textTransform: "uppercase",
                          letterSpacing: "0.05em",
                        }}
                      >
                        {conn.provider === "azure_devops" ? "Azure DevOps" : "GitHub"}
                      </span>
                      {conn.pat_configured && (
                        <span style={{ fontSize: "0.7rem", color: "var(--color-success, #38a169)" }}>
                          ✓ PAT
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
                      {conn.organization ? `${conn.organization}` : ""}
                      {conn.default_project ? ` / ${conn.default_project}` : ""}
                      {conn.base_url ? ` · ${conn.base_url}` : ""}
                    </div>
                  </div>
                  <div className="row-actions">
                    <button
                      className="btn-icon"
                      title="Test connection"
                      onClick={() => handleTest(conn)}
                      disabled={testStatus[conn.id] === "testing"}
                    >
                      {testStatus[conn.id] === "testing" ? (
                        <Loader2 size={14} className="spin" />
                      ) : testStatus[conn.id] === "ok" ? (
                        <CheckCircle2 size={14} color="#2E7D32" />
                      ) : testStatus[conn.id] === "fail" ? (
                        <XCircle size={14} color="#D32F2F" />
                      ) : (
                        <Play size={14} />
                      )}
                    </button>
                    <button
                      className="btn-icon"
                      title="Edit"
                      onClick={() => { setEditing(conn); setShowForm(false); }}
                    >
                      <Edit2 size={14} />
                    </button>
                    <button
                      className="btn-icon btn-icon-danger"
                      title="Delete"
                      onClick={() => handleDelete(conn)}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      )}
    </div>
  );
}

