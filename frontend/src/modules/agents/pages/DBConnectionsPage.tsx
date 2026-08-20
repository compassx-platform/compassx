import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Database,
  Plus,
  Trash2,
  Edit2,
  Play,
  ChevronDown,
  ChevronRight,
  Loader2,
  CheckCircle2,
  XCircle,
  RefreshCw,
} from "lucide-react";
import {
  useDBConnections,
  useCreateDBConnection,
  useUpdateDBConnection,
  useDeleteDBConnection,
  useTestDBConnection,
  useReprofileDBConnection,
  useDBConnectionProfiles,
  useDBSchema,
  type DBConnection,
} from "@/modules/agents/hooks/useDBConnections";
import { useAgents } from "@/modules/agents/hooks/useAgents";
import { useToast } from "@/lib/toast";
import { useScopedNavigate } from "@/lib/appNavigation";

const DB_TYPES = [
  { value: "postgres",   label: "PostgreSQL" },
  { value: "mysql",      label: "MySQL" },
  { value: "mssql",      label: "MS SQL Server" },
  { value: "sqlite",     label: "SQLite" },
  { value: "snowflake",  label: "Snowflake" },
  { value: "bigquery",   label: "BigQuery" },
  { value: "databricks", label: "Databricks" },
  { value: "oracle",     label: "Oracle" },
];

function DBConnectionForm({
  initial,
  onSave,
  onCancel,
  isSaving,
}: {
  initial?: Partial<DBConnection>;
  onSave: (data: {
    name: string;
    db_type: string;
    host?: string;
    port?: number;
    db_name?: string;
    username?: string;
    password?: string;
    profiler_agent_id?: number;
    scoped_tables?: string[];
  }) => void;
  onCancel: () => void;
  isSaving: boolean;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [dbType, setDbType] = useState(initial?.db_type ?? "postgres");
  const [host, setHost] = useState(initial?.host ?? "");
  const [port, setPort] = useState(initial?.port?.toString() ?? "");
  const [dbName, setDbName] = useState(initial?.db_name ?? "");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [profilerAgentId, setProfilerAgentId] = useState<number | undefined>(initial?.profiler_agent_id);
  const [scopedTables, setScopedTables] = useState<string[]>(initial?.scoped_tables ?? []);

  const { data: agents = [] } = useAgents();
  const { data: schema } = useDBSchema(initial?.id ?? null, !!initial?.id);

  const needsHost = !["sqlite", "bigquery"].includes(dbType);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSave({
      name,
      db_type: dbType,
      host: host || undefined,
      port: port ? parseInt(port) : undefined,
      db_name: dbName || undefined,
      username: username || undefined,
      password: password || undefined,
      profiler_agent_id: profilerAgentId,
      scoped_tables: scopedTables,
    });
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div className="form-group">
          <label className="form-label">Name *</label>
          <input className="form-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Analytics DB" required />
        </div>
        <div className="form-group">
          <label className="form-label">Database Type *</label>
          <select className="form-input" value={dbType} onChange={(e) => setDbType(e.target.value)}>
            {DB_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </div>
      </div>
      {needsHost && (
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16 }}>
          <div className="form-group">
            <label className="form-label">Host</label>
            <input className="form-input" value={host} onChange={(e) => setHost(e.target.value)} placeholder="localhost" />
          </div>
          <div className="form-group">
            <label className="form-label">Port</label>
            <input className="form-input" type="number" value={port} onChange={(e) => setPort(e.target.value)} placeholder="5432" />
          </div>
        </div>
      )}
      <div className="form-group">
        <label className="form-label">{dbType === "sqlite" ? "File Path" : "Database Name"}</label>
        <input className="form-input" value={dbName} onChange={(e) => setDbName(e.target.value)} placeholder={dbType === "sqlite" ? "/path/to/db.sqlite" : "mydb"} />
      </div>
      {needsHost && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <div className="form-group">
            <label className="form-label">Username {initial?.id ? "(leave blank to keep)" : ""}</label>
            <input className="form-input" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="postgres" />
          </div>
          <div className="form-group">
            <label className="form-label">Password {initial?.id ? "(leave blank to keep)" : ""}</label>
            <input className="form-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 16, borderTop: "1px solid var(--color-border)", paddingTop: 16 }}>
        <div className="form-group">
          <label className="form-label">Profiler Agent</label>
          <select
            className="form-input"
            value={profilerAgentId ?? ""}
            onChange={(e) => setProfilerAgentId(e.target.value ? parseInt(e.target.value) : undefined)}
          >
            <option value="">No Profiler Agent</option>
            {agents.map((agent) => (
              <option key={agent.id} value={agent.id}>
                {agent.name}
              </option>
            ))}
          </select>
          <p style={{ fontSize: "0.7rem", marginTop: 4, color: "var(--color-text-muted)" }}>
            Select an agent to automatically profile the selected tables when connection is created/updated.
          </p>
        </div>
      </div>

      {initial?.id && (
        <div className="form-group">
          <label className="form-label" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span>Scoped Tables</span>
            <span style={{ fontSize: "0.7rem", color: "var(--color-text-muted)" }}>
              {scopedTables.length} selected
            </span>
          </label>
          {schema && Object.keys(schema).length > 0 ? (
            <div
              style={{
                border: "1px solid var(--color-border)",
                borderRadius: 6,
                padding: "8px 12px",
                maxHeight: 180,
                overflowY: "auto",
                display: "flex",
                flexDirection: "column",
                gap: 6,
                background: "var(--color-surface-hover)"
              }}
            >
              <div style={{ display: "flex", gap: 8, marginBottom: 4, borderBottom: "1px solid var(--color-border)", paddingBottom: 4 }}>
                <button
                  type="button"
                  style={{ fontSize: "0.7rem", background: "none", border: "none", color: "var(--color-primary)", cursor: "pointer", padding: 0 }}
                  onClick={() => setScopedTables(Object.keys(schema))}
                >
                  Select All
                </button>
                <span style={{ color: "var(--color-border)", fontSize: "0.7rem" }}>|</span>
                <button
                  type="button"
                  style={{ fontSize: "0.7rem", background: "none", border: "none", color: "var(--color-primary)", cursor: "pointer", padding: 0 }}
                  onClick={() => setScopedTables([])}
                >
                  Deselect All
                </button>
              </div>
              {Object.keys(schema).map((table) => {
                const isChecked = scopedTables.includes(table);
                return (
                  <label key={table} style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: "0.75rem" }}>
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => {
                        setScopedTables((prev) =>
                          isChecked ? prev.filter((t) => t !== table) : [...prev, table]
                        );
                      }}
                    />
                    <span>{table}</span>
                  </label>
                );
              })}
            </div>
          ) : (
            <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
              No tables found. Save connection successfully first to configure scoping.
            </div>
          )}
        </div>
      )}

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

function SchemaViewer({ connId }: { connId: number }) {
  const [enabled, setEnabled] = useState(false);
  const { data: schema, isLoading } = useDBSchema(connId, enabled);
  const [openTables, setOpenTables] = useState<Set<string>>(new Set());

  function toggleTable(t: string) {
    setOpenTables((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });
  }

  return (
    <div style={{ marginTop: 8 }}>
      {!enabled ? (
        <button
          className="btn btn-secondary"
          style={{ fontSize: "0.75rem" }}
          onClick={() => setEnabled(true)}
        >
          Browse Schema
        </button>
      ) : isLoading ? (
        <div style={{ fontSize: "0.75rem", display: "flex", gap: 6, alignItems: "center", color: "var(--color-text-muted)" }}>
          <Loader2 size={12} className="spin" /> Loading schema…
        </div>
      ) : !schema || Object.keys(schema).length === 0 ? (
        <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>No tables found.</div>
      ) : (
        <div
          style={{
            border: "1px solid var(--color-border)",
            borderRadius: 6,
            overflow: "hidden",
            maxHeight: 280,
            overflowY: "auto",
            fontSize: "0.75rem",
          }}
        >
          {Object.entries(schema).map(([table, cols]) => (
            <div key={table}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "5px 8px",
                  cursor: "pointer",
                  background: "var(--color-surface-hover)",
                  borderBottom: "1px solid var(--color-border)",
                }}
                onClick={() => toggleTable(table)}
              >
                {openTables.has(table) ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                <Database size={11} color="var(--color-primary)" />
                <span style={{ fontWeight: 500 }}>{table}</span>
                <span style={{ marginLeft: "auto", color: "var(--color-text-muted)" }}>{cols.length} cols</span>
              </div>
              {openTables.has(table) && (
                <div style={{ padding: "4px 24px" }}>
                  {cols.map((col) => (
                    <div key={col} style={{ padding: "2px 0", color: "var(--color-text-muted)" }}>
                      {col}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ProfilesViewer({ connId }: { connId: number }) {
  const [enabled, setEnabled] = useState(false);
  const { data: profiles, isLoading } = useDBConnectionProfiles(connId, enabled);
  const [openProfiles, setOpenProfiles] = useState<Set<string>>(new Set());

  function toggleProfile(t: string) {
    setOpenProfiles((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });
  }

  return (
    <div style={{ marginTop: 8 }}>
      {!enabled ? (
        <button
          className="btn btn-secondary"
          style={{ fontSize: "0.75rem" }}
          onClick={() => setEnabled(true)}
        >
          View Data Profiles
        </button>
      ) : isLoading ? (
        <div style={{ fontSize: "0.75rem", display: "flex", gap: 6, alignItems: "center", color: "var(--color-text-muted)" }}>
          <Loader2 size={12} className="spin" /> Loading profiles…
        </div>
      ) : !profiles || profiles.length === 0 ? (
        <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>No profiling data available. Trigger a reprofile to generate.</div>
      ) : (
        <div
          style={{
            border: "1px solid var(--color-border)",
            borderRadius: 6,
            overflow: "hidden",
            maxHeight: 350,
            overflowY: "auto",
            fontSize: "0.75rem",
          }}
        >
          {profiles.map((p) => (
            <div key={p.id} style={{ borderBottom: "1px solid var(--color-border)" }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "6px 8px",
                  cursor: "pointer",
                  background: "var(--color-surface-hover)",
                }}
                onClick={() => toggleProfile(p.table_name)}
              >
                {openProfiles.has(p.table_name) ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                <span style={{ fontWeight: 600 }}>{p.table_name}</span>
                <span style={{ color: "var(--color-text-muted)" }}>· {p.row_count ?? "unknown"} rows</span>
                {p.detected_layer && (
                  <span
                    style={{
                      marginLeft: "auto",
                      padding: "2px 6px",
                      borderRadius: 4,
                      background: "rgba(var(--color-primary-rgb), 0.1)",
                      color: "var(--color-primary)",
                      fontSize: "0.65rem",
                      fontWeight: 600,
                    }}
                  >
                    {p.detected_layer}
                  </span>
                )}
              </div>
              {openProfiles.has(p.table_name) && (
                <div style={{ padding: "8px 12px", background: "var(--color-surface)", display: "flex", flexDirection: "column", gap: 8 }}>
                  <div>
                    <div style={{ fontWeight: 500, marginBottom: 4 }}>Columns & Stats:</div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 4, paddingLeft: 8 }}>
                      {p.columns.map((c: any) => (
                        <div key={c.name} style={{ color: "var(--color-text-muted)" }}>
                          <strong>{c.name}</strong> ({c.type}) {c.nullable ? "NULL" : "NOT NULL"}
                          {c.null_rate !== undefined && ` · Null Rate: ${(c.null_rate * 100).toFixed(1)}%`}
                          {c.distinct_count !== undefined && ` · Distinct: ${c.distinct_count}`}
                        </div>
                      ))}
                    </div>
                  </div>
                  {p.candidate_relationships && p.candidate_relationships.length > 0 && (
                    <div>
                      <div style={{ fontWeight: 500, marginBottom: 4 }}>Candidate Relationships:</div>
                      <div style={{ display: "flex", flexDirection: "column", gap: 4, paddingLeft: 8, color: "var(--color-text-muted)" }}>
                        {p.candidate_relationships.map((r: any, idx: number) => (
                          <div key={idx}>
                            {r.from_col} → {r.to_table}.{r.to_col} (Overlap: {(r.overlap_ratio * 100).toFixed(1)}%)
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {p.prior_art_references && p.prior_art_references.length > 0 && (
                    <div>
                      <div style={{ fontWeight: 500, marginBottom: 4 }}>Prior-Art References:</div>
                      <div style={{ display: "flex", flexDirection: "column", gap: 4, paddingLeft: 8, color: "var(--color-text-muted)" }}>
                        {p.prior_art_references.map((r: any, idx: number) => (
                          <div key={idx}>
                            Found in {r.source_type} <strong>{r.source_name}</strong> ({r.relevance_note})
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {p.unresolved_ambiguities && p.unresolved_ambiguities.length > 0 && (
                    <div>
                      <div style={{ fontWeight: 500, marginBottom: 4, color: "#D32F2F" }}>Unresolved Ambiguities:</div>
                      <div style={{ display: "flex", flexDirection: "column", gap: 4, paddingLeft: 8, color: "#D32F2F" }}>
                        {p.unresolved_ambiguities.map((a: string, idx: number) => (
                          <div key={idx}>• {a}</div>
                        ))}
                      </div>
                    </div>
                  )}
                  <div style={{ fontSize: "0.65rem", color: "var(--color-text-muted)", borderTop: "1px dashed var(--color-border)", paddingTop: 4 }}>
                    Last Profiled: {new Date(p.last_profiled_at).toLocaleString()}
                    {p.profiled_by_agent_run_id && ` · Run ID: ${p.profiled_by_agent_run_id}`}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function DBConnectionsPage() {
  const navigate = useScopedNavigate();
  const [searchParams] = useSearchParams();
  const { data: connections = [], isLoading } = useDBConnections();
  const createMutation = useCreateDBConnection();
  const updateMutation = useUpdateDBConnection();
  const deleteMutation = useDeleteDBConnection();
  const testMutation = useTestDBConnection();
  const reprofileMutation = useReprofileDBConnection();
  const toast = useToast();

  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<DBConnection | null>(null);
  const [testStatus, setTestStatus] = useState<Record<number, "ok" | "fail" | "testing">>({});
  const [expandedSchema, setExpandedSchema] = useState<number | null>(null);
  const [reprofilingConn, setReprofilingConn] = useState<number | null>(null);
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

  async function handleDelete(conn: DBConnection) {
    if (!confirm(`Delete "${conn.name}"?`)) return;
    try {
      await deleteMutation.mutateAsync({ connId: conn.id });
      toast.success("Connection deleted");
    } catch {
      toast.error("Failed to delete");
    }
  }

  async function handleTest(conn: DBConnection) {
    setTestStatus((s) => ({ ...s, [conn.id]: "testing" }));
    try {
      const result = await testMutation.mutateAsync({ connId: conn.id });
      setTestStatus((s) => ({ ...s, [conn.id]: result.success ? "ok" : "fail" }));
      if (result.success) toast.success(result.message); else toast.error(result.message);
    } catch {
      setTestStatus((s) => ({ ...s, [conn.id]: "fail" }));
      toast.error("Test failed");
    }
  }

  async function handleReprofile(connId: number) {
    setReprofilingConn(connId);
    try {
      const res = await reprofileMutation.mutateAsync({ connId });
      toast.success(res.message || "Reprofile started");
    } catch {
      toast.error("Failed to trigger reprofile");
    } finally {
      setReprofilingConn(null);
    }
  }

  return (
    <div className="page-section connections-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">DB Connections</h1>
          <p className="page-subtitle">Connect databases the agents can query.</p>
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
            {editing ? `Edit: ${editing.name}` : "New DB Connection"}
          </div>
          <DBConnectionForm
            key={editing?.id ?? "new"}
            initial={editing ?? undefined}
            onSave={handleSave}
            onCancel={() => {
              setEditing(null);
              setShowForm(false);
              navigate("/connections");
            }}
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
            <Database size={32} style={{ opacity: 0.3, marginBottom: 8 }} />
            <div>No DB connections yet.</div>
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
                  <Database size={14} color="var(--color-primary)" />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 500, fontSize: "0.875rem" }}>{conn.name}</div>
                    <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
                      {conn.db_type} {conn.host ? `· ${conn.host}:${conn.port ?? ""}` : ""} {conn.db_name ? `/ {conn.db_name}` : ""}
                      {conn.profiler_agent_id && ` · Profiled by Agent #${conn.profiler_agent_id}`}
                      {conn.scoped_tables && conn.scoped_tables.length > 0 && ` · ${conn.scoped_tables.length} tables scoped`}
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
                        <Loader2 size={13} className="spin" />
                      ) : testStatus[conn.id] === "ok" ? (
                        <CheckCircle2 size={13} style={{ color: "var(--color-success)" }} />
                      ) : testStatus[conn.id] === "fail" ? (
                        <XCircle size={13} style={{ color: "var(--color-danger)" }} />
                      ) : (
                        <Play size={13} />
                      )}
                    </button>
                    {conn.profiler_agent_id && (
                      <button
                        className="btn-icon"
                        title="Reprofile connection"
                        onClick={() => handleReprofile(conn.id)}
                        disabled={reprofilingConn === conn.id}
                      >
                        {reprofilingConn === conn.id ? (
                          <Loader2 size={14} className="spin" />
                        ) : (
                          <RefreshCw size={14} />
                        )}
                      </button>
                    )}
                    <button
                      className="btn-icon"
                      title="Browse schema & profiles"
                      onClick={() => setExpandedSchema(expandedSchema === conn.id ? null : conn.id)}
                    >
                      {expandedSchema === conn.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </button>
                    <button className="btn-icon" title="Edit" onClick={() => { setEditing(conn); setShowForm(false); }}>
                      <Edit2 size={14} />
                    </button>
                    <button className="btn-icon btn-icon-danger" title="Delete" onClick={() => handleDelete(conn)}>
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
                {expandedSchema === conn.id && (
                  <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 12 }}>
                    <SchemaViewer connId={conn.id} />
                    <ProfilesViewer connId={conn.id} />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
      )}
    </div>
  );
}
