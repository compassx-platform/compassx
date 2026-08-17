import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Cpu,
  Plus,
  Trash2,
  Edit2,
  Wifi,
  Loader2,
  CheckCircle2,
  XCircle,
  BrainCircuit,
  Layers,
} from "lucide-react";
import {
  useLLMConnections,
  useCreateLLMConnection,
  useUpdateLLMConnection,
  useDeleteLLMConnection,
  usePingLLMConnection,
  useSetEmbeddingLLMConnection,
  type LLMConnection,
} from "@/modules/agents/hooks/useLLMConnections";
import { useToast } from "@/lib/toast";
import { useScopedNavigate } from "@/lib/appNavigation";

const PROVIDERS = [
  { value: "anthropic", label: "Anthropic" },
  { value: "openai",    label: "OpenAI" },
  { value: "azure",     label: "Azure OpenAI" },
  { value: "gemini",    label: "Google Gemini API" },
  { value: "litellm",   label: "LiteLLM (proxy)" },
  { value: "ollama",    label: "Ollama (local)" },
  { value: "compatible", label: "OpenAI-compatible" },
];

const MODEL_PLACEHOLDERS: Record<string, string> = {
  anthropic: "e.g. claude-opus-4-6",
  openai: "e.g. gpt-4o",
  azure: "e.g. gpt-4o",
  gemini: "e.g. gemini-2.5-flash",
  litellm: "e.g. anthropic/claude-3-7-sonnet",
  ollama: "e.g. llama3.1",
  compatible: "e.g. gpt-4o-mini",
};

const API_KEY_PLACEHOLDERS: Record<string, string> = {
  anthropic: "sk-ant-…",
  openai: "sk-…",
  azure: "Azure API key",
  gemini: "AIza…",
  litellm: "proxy key",
  ollama: "optional",
  compatible: "API key",
};

const PROVIDER_HELP: Record<string, string> = {
  openai: "Optional. Leave blank to use OpenAI's default API endpoint, or set this for a compatible proxy.",
  gemini: "Uses the direct Google Gemini Models API with an AI Studio API key.",
  litellm: "Connects to an existing LiteLLM proxy; the app does not host LiteLLM itself.",
};

function LLMConnectionForm({
  initial,
  onSave,
  onCancel,
  isSaving,
}: Readonly<{
  initial?: Partial<LLMConnection>;
  onSave: (data: {
    name: string;
    provider: string;
    model_name: string;
    api_key?: string;
    base_url?: string;
    use_for_memory?: boolean;
    use_for_embedding?: boolean;
    input_cost_per_1k_tokens?: number;
    output_cost_per_1k_tokens?: number;
    cost_currency?: string;
  }) => void;
  onCancel: () => void;
  isSaving: boolean;
}>) {
  const [name, setName] = useState(initial?.name ?? "");
  const [provider, setProvider] = useState(initial?.provider ?? "anthropic");
  const [modelName, setModelName] = useState(initial?.model_name ?? "");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState(initial?.base_url ?? "");
  const [useForMemory, setUseForMemory] = useState(initial?.use_for_memory ?? false);
  const [useForEmbedding, setUseForEmbedding] = useState(initial?.use_for_embedding ?? false);
  const [inputCost, setInputCost] = useState(initial?.input_cost_per_1k_tokens?.toString() ?? "");
  const [outputCost, setOutputCost] = useState(initial?.output_cost_per_1k_tokens?.toString() ?? "");
  const [costCurrency, setCostCurrency] = useState(initial?.cost_currency ?? "USD");
  
  const showBaseUrl = provider === "openai" || provider === "azure" || provider === "ollama" || provider === "litellm" || provider === "compatible";

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSave({
      name,
      provider,
      model_name: modelName,
      api_key: apiKey || undefined,
      base_url: baseUrl || undefined,
      use_for_memory: useForMemory,
      use_for_embedding: useForEmbedding,
      input_cost_per_1k_tokens: inputCost !== "" ? Number(inputCost) : undefined,
      output_cost_per_1k_tokens: outputCost !== "" ? Number(outputCost) : undefined,
      cost_currency: costCurrency || undefined,
    });
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div className="form-group">
          <label className="form-label" htmlFor="llm-connection-name">Name *</label>
          <input id="llm-connection-name" className="form-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. GPT-4o Production" required />
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="llm-connection-provider">Provider *</label>
          <select id="llm-connection-provider" className="form-input" value={provider} onChange={(e) => setProvider(e.target.value)}>
            {PROVIDERS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div className="form-group">
          <label className="form-label" htmlFor="llm-connection-model">Model Name *</label>
          <input id="llm-connection-model" className="form-input" value={modelName} onChange={(e) => setModelName(e.target.value)} placeholder={MODEL_PLACEHOLDERS[provider] ?? "e.g. claude-opus-4-6"} required />
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="llm-connection-api-key">API Key {initial?.id ? "(leave blank to keep current)" : ""}</label>
          <input
            id="llm-connection-api-key"
            className="form-input"
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={initial?.api_key_masked ?? API_KEY_PLACEHOLDERS[provider] ?? "sk-…"}
          />
        </div>
      </div>
      {PROVIDER_HELP[provider] && (
        <div style={{ fontSize: "0.8rem", color: "var(--color-text-muted)" }}>
          {PROVIDER_HELP[provider]}
        </div>
      )}
      {showBaseUrl && (
        <div className="form-group">
          <label className="form-label" htmlFor="llm-connection-base-url">
            Base URL {provider === "openai" ? "(optional override)" : provider === "litellm" ? "(LiteLLM proxy endpoint)" : ""}
          </label>
          <input
            id="llm-connection-base-url"
            className="form-input"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder={provider === "openai" ? "https://api.openai.com/v1" : provider === "litellm" ? "http://localhost:4000" : "https://…"}
          />
        </div>
      )}
      
      <div style={{ borderTop: "1px solid var(--color-border-subtle)", paddingTop: 16, marginTop: 8 }}>
        <h4 style={{ fontSize: "0.95rem", fontWeight: 600, marginBottom: 12, color: "var(--color-text-primary)" }}>Token Cost Configuration (Optional)</h4>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
          <div className="form-group">
            <label className="form-label" htmlFor="llm-connection-input-cost">Input Cost per 1K Tokens</label>
            <input
              id="llm-connection-input-cost"
              className="form-input"
              type="number"
              step="0.00001"
              min="0"
              value={inputCost}
              onChange={(e) => setInputCost(e.target.value)}
              placeholder="e.g. 0.0015"
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="llm-connection-output-cost">Output Cost per 1K Tokens</label>
            <input
              id="llm-connection-output-cost"
              className="form-input"
              type="number"
              step="0.00001"
              min="0"
              value={outputCost}
              onChange={(e) => setOutputCost(e.target.value)}
              placeholder="e.g. 0.006"
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="llm-connection-currency">Currency</label>
            <select
              id="llm-connection-currency"
              className="form-input"
              value={costCurrency}
              onChange={(e) => setCostCurrency(e.target.value)}
            >
              <option value="USD">USD ($)</option>
              <option value="INR">INR (₹)</option>
              <option value="EUR">EUR (€)</option>
              <option value="GBP">GBP (£)</option>
            </select>
          </div>
        </div>
      </div>

      <div className="form-group" style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <input
          id="llm-connection-memory"
          type="checkbox"
          checked={useForMemory}
          onChange={(e) => setUseForMemory(e.target.checked)}
          style={{ width: "auto", cursor: "pointer" }}
        />
        <label className="form-label" htmlFor="llm-connection-memory" style={{ marginBottom: 0, cursor: "pointer", userSelect: "none" }}>
          <BrainCircuit size={13} style={{ display: "inline", marginRight: 4, verticalAlign: "middle" }} />
          Use for Memory Extraction
        </label>
      </div>
      <div className="form-group" style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <input
          id="llm-connection-embedding"
          type="checkbox"
          checked={useForEmbedding}
          onChange={(e) => setUseForEmbedding(e.target.checked)}
          style={{ width: "auto", cursor: "pointer" }}
        />
        <label className="form-label" htmlFor="llm-connection-embedding" style={{ marginBottom: 0, cursor: "pointer", userSelect: "none" }}>
          <Layers size={13} style={{ display: "inline", marginRight: 4, verticalAlign: "middle" }} />
          Use for Catalog Embeddings
          <span style={{ marginLeft: 6, fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
            (model must produce 1536-dim vectors, e.g. text-embedding-3-small)
          </span>
        </label>
      </div>
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
        <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={isSaving || !name || !modelName}>
          {isSaving ? <Loader2 size={14} className="spin" /> : null}
          {initial?.id ? "Update" : "Create"}
        </button>
      </div>
    </form>
  );
}

export default function LLMConnectionsPage() {
  const navigate = useScopedNavigate();
  const [searchParams] = useSearchParams();
  const { data: connections = [], isLoading } = useLLMConnections();
  const createMutation = useCreateLLMConnection();
  const updateMutation = useUpdateLLMConnection();
  const deleteMutation = useDeleteLLMConnection();
  const pingMutation = usePingLLMConnection();
  const setEmbeddingMutation = useSetEmbeddingLLMConnection();
  const toast = useToast();

  const [showForm, setShowForm] = useState(true);
  const [editing, setEditing] = useState<LLMConnection | null>(null);
  const [pingStatus, setPingStatus] = useState<Record<number, "ok" | "fail" | "pinging">>({});
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

  async function handleDelete(conn: LLMConnection) {
    if (!confirm(`Delete "${conn.name}"?`)) return;
    try {
      await deleteMutation.mutateAsync({ connId: conn.id });
      toast.success("Connection deleted");
    } catch {
      toast.error("Failed to delete connection");
    }
  }

  async function handlePing(conn: LLMConnection) {
    setPingStatus((s) => ({ ...s, [conn.id]: "pinging" }));
    try {
      const result = await pingMutation.mutateAsync({ connId: conn.id });
      setPingStatus((s) => ({ ...s, [conn.id]: result.success ? "ok" : "fail" }));
      if (result.success) toast.success(result.message); else toast.error(result.message);
    } catch {
      setPingStatus((s) => ({ ...s, [conn.id]: "fail" }));
      toast.error("Ping failed");
    }
  }

  async function handleSetEmbedding(conn: LLMConnection) {
    try {
      await setEmbeddingMutation.mutateAsync({ connId: conn.id });
      toast.success(`"${conn.name}" set as embedding model`);
    } catch {
      toast.error("Failed to set embedding connection");
    }
  }

  function renderPingIcon(status: "ok" | "fail" | "pinging" | undefined) {
    if (status === "pinging") {
      return <Loader2 size={14} className="spin" />;
    }
    if (status === "ok") {
      return <CheckCircle2 size={14} color="#2E7D32" />;
    }
    if (status === "fail") {
      return <XCircle size={14} color="#D32F2F" />;
    }
    return <Wifi size={14} />;
  }

  let content;
  if (isLoading) {
    content = <div className="table-empty"><Loader2 size={20} className="spin" /> Loading…</div>;
  } else if (connections.length === 0) {
    content = (
      <div className="table-empty">
        <Cpu size={32} style={{ opacity: 0.3, marginBottom: 8 }} />
        <div>No LLM connections yet.</div>
      </div>
    );
  } else {
    content = (
      <table className="admin-table">
        <thead>
          <tr>
            <th style={{ width: "20%" }}>Name</th>
            <th style={{ width: "11%" }}>Provider</th>
            <th style={{ width: "22%" }}>Model</th>
            <th style={{ width: "14%" }}>Cost (In / Out per 1K)</th>
            <th style={{ width: "10%" }}>API Key</th>
            <th style={{ width: "13%" }}>Roles</th>
            <th style={{ width: "10%" }} />
          </tr>
        </thead>
        <tbody>
          {connections.map((conn) => (
            <tr key={conn.id}>
              <td style={{ fontWeight: 500, fontSize: "0.875rem" }}>{conn.name}</td>
              <td style={{ fontSize: "0.8rem", color: "var(--color-text-muted)", textTransform: "capitalize" }}>{conn.provider}</td>
              <td style={{ fontSize: "0.8rem", fontFamily: "monospace" }}>{conn.model_name}</td>
              <td style={{ fontSize: "0.8rem" }}>
                {conn.input_cost_per_1k_tokens !== undefined && conn.input_cost_per_1k_tokens !== null && conn.output_cost_per_1k_tokens !== undefined && conn.output_cost_per_1k_tokens !== null ? (
                  <span>
                    {conn.cost_currency ?? "USD"} {conn.input_cost_per_1k_tokens} / {conn.output_cost_per_1k_tokens}
                  </span>
                ) : (
                  <span style={{ color: "var(--color-text-muted)", fontStyle: "italic" }}>Not set</span>
                )}
              </td>
              <td style={{ fontSize: "0.75rem", fontFamily: "monospace", color: "var(--color-text-muted)" }}>
                {conn.api_key_masked ?? "—"}
              </td>
              <td>
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  {conn.use_for_memory && (
                    <span style={{
                      display: "inline-flex", alignItems: "center", gap: 4,
                      fontSize: "0.7rem", fontWeight: 600, padding: "2px 7px",
                      borderRadius: 99, background: "var(--color-accent-subtle, rgba(99,102,241,0.12))",
                      color: "var(--color-accent, #6366f1)",
                    }}>
                      <BrainCircuit size={10} /> Memory
                    </span>
                  )}
                  {conn.use_for_embedding && (
                    <span style={{
                      display: "inline-flex", alignItems: "center", gap: 4,
                      fontSize: "0.7rem", fontWeight: 600, padding: "2px 7px",
                      borderRadius: 99, background: "rgba(16,185,129,0.12)",
                      color: "#10b981",
                    }}>
                      <Layers size={10} /> Embeddings
                    </span>
                  )}
                </div>
              </td>
              <td>
                <div className="row-actions">
                  <button
                    className="btn-icon"
                    title="Ping"
                    onClick={() => handlePing(conn)}
                    disabled={pingStatus[conn.id] === "pinging"}
                  >
                    {renderPingIcon(pingStatus[conn.id])}
                  </button>
                  {!conn.use_for_embedding && (
                    <button
                      className="btn-icon"
                      title="Set as embedding model"
                      onClick={() => handleSetEmbedding(conn)}
                      disabled={setEmbeddingMutation.isPending}
                    >
                      <Layers size={14} />
                    </button>
                  )}
                  <button className="btn-icon" title="Edit" onClick={() => { setEditing(conn); setShowForm(false); }}>
                    <Edit2 size={14} />
                  </button>
                  <button className="btn-icon btn-icon-danger" title="Delete" onClick={() => handleDelete(conn)}>
                    <Trash2 size={14} />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  return (
    <div className="page-section">
      <div className="page-header">
        <div>
          <h1 className="page-title">LLM Connections</h1>
          <p className="page-subtitle">Configure language model providers for agents.</p>
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
            {editing ? `Edit: ${editing.name}` : "New LLM Connection"}
          </div>
          <LLMConnectionForm
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
          {content}
        </div>
      )}
    </div>
  );
}
