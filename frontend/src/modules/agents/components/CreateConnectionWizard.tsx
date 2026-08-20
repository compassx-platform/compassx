import React, { useState, useEffect } from "react";
import {
  X,
  Search,
  CheckCircle2,
  XCircle,
  Loader2,
  ChevronRight,
  ChevronLeft,
  Sparkles,
  Database,
  Globe,
  Activity,
  Server,
  Key,
  ShieldCheck,
  Zap,
} from "lucide-react";
import {
  useConnectionProviders,
  useCreateCatalogConnection,
  useTestConnection,
  type ProviderMetadata,
} from "@/modules/agents/hooks/useCatalogConnections";
import { useToast } from "@/lib/toast";

interface CreateConnectionWizardProps {
  isOpen: boolean;
  onClose: () => void;
  initialProvider?: string | null;
  defaultCatalog?: string;
  defaultSchema?: string;
}

// Authentic Brand SVG Logos
export function ProviderLogo({ typeId, size = 24 }: { typeId: string; size?: number }) {
  switch (typeId) {
    case "postgres":
      return (
        <svg viewBox="0 0 128 128" width={size} height={size} style={{ flexShrink: 0 }}>
          <path
            fill="#336791"
            d="M64 5.5C31.7 5.5 5.5 31.7 5.5 64s26.2 58.5 58.5 58.5 58.5-26.2 58.5-58.5S96.3 5.5 64 5.5z"
          />
          <path
            fill="#FFFFFF"
            d="M87.2 41.5c-1.8-3.9-5-6.8-9.1-8.3-5.2-1.9-11.4-1.2-16.8 1.1-6.1 2.6-11.5 7.4-15.1 13.3-2.7 4.5-4.4 9.7-5.1 14.9-.7 5.2-.2 10.5 1.5 15.4 1.4 4.1 3.9 7.8 7.3 10.4 4.1 3.1 9.4 4.5 14.5 4.1 5.8-.5 11.2-3.4 15.3-7.6 3.6-3.7 6.1-8.4 7.2-13.5.9-4.3.7-8.8-.6-13-1.1-4.4-3.5-8.4-6.8-11.6l7.7-5.2zm-22.1 41c-3.1.2-6.2-.9-8.4-3-2.3-2.1-3.6-5.1-3.7-8.2-.1-3.7 1.3-7.4 3.7-10.2 2.7-3.1 6.6-5.2 10.7-5.7 3.3-.4 6.7.4 9.3 2.4 2.4 1.8 4 4.6 4.4 7.6.4 3.5-.6 7.1-2.8 9.9-2.9 3.5-7.8 5.7-13.2 7.2z"
          />
          <path
            fill="#336791"
            d="M62.5 59.2c-2.4.3-4.6 1.6-6.1 3.5-1.5 1.9-2.2 4.4-2.1 6.8.1 2.1 1 4.1 2.5 5.5 1.5 1.4 3.6 2.1 5.6 2 3.6-1 6.8-2.5 8.7-4.8 1.4-1.8 2.1-4.1 1.8-6.4-.3-2-1.3-3.8-2.9-5-1.9-1.3-4.4-1.8-7.5-1.6z"
          />
        </svg>
      );
    case "mysql":
      return (
        <svg viewBox="0 0 128 128" width={size} height={size} style={{ flexShrink: 0 }}>
          <rect width="128" height="128" rx="20" fill="#00618A" />
          <path
            fill="#E48E00"
            d="M98.6 78.4c-4.2-12.8-15.5-22.4-28.8-24.8 1.4-4.8 4.7-8.8 9.2-11.2-8.3 1.1-15.4 6.2-19.1 13.6-7.8 1.5-14.8 5.8-19.8 12-4.9 6.2-7.2 14.1-6.5 22 8.7 1.6 17.8.2 25.7-4 7.9-4.2 14.2-10.9 17.8-19.1 7.2 2.6 13.3 7.8 17.2 14.5 1.6.9 3.3 1.4 5.1 1.4 3.1 0 6.1-1.6 7.8-4.1.8-.1 1.2-.2 1.4-.3z"
          />
          <path
            fill="#FFFFFF"
            d="M32 94c3.8-6.1 9.4-11 16.1-14 6.7-3 14.3-3.8 21.6-2.2-4.1 6.6-9.9 11.9-16.8 15.3-6.9 3.4-14.8 4.3-22.2 2.5.4-.5.9-1.1 1.3-1.6z"
          />
        </svg>
      );
    case "mssql":
      return (
        <svg viewBox="0 0 128 128" width={size} height={size} style={{ flexShrink: 0 }}>
          <rect width="128" height="128" rx="20" fill="#CC292B" />
          <path
            fill="#FFFFFF"
            d="M64 26C45.2 26 30 31.4 30 38v52c0 6.6 15.2 12 34 12s34-5.4 34-12V38c0-6.6-15.2-12-34-12zm0 8c14.6 0 26 3.6 26 6s-11.4 6-26 6-26-3.6-26-6 11.4-6 26-6zm0 22c14.6 0 26 3.6 26 6s-11.4 6-26 6-26-3.6-26-6 11.4-6 26-6zm0 22c14.6 0 26 3.6 26 6s-11.4 6-26 6-26-3.6-26-6 11.4-6 26-6z"
          />
        </svg>
      );
    case "snowflake":
      return (
        <svg viewBox="0 0 128 128" width={size} height={size} style={{ flexShrink: 0 }}>
          <rect width="128" height="128" rx="20" fill="#29B5E8" />
          <g fill="#FFFFFF">
            <path d="M64 16v96M16 64h96M30 30l68 68M30 98l68-68" stroke="#FFFFFF" strokeWidth="8" strokeLinecap="round" />
            <circle cx="64" cy="64" r="10" />
            <circle cx="64" cy="22" r="5" />
            <circle cx="64" cy="106" r="5" />
            <circle cx="22" cy="64" r="5" />
            <circle cx="106" cy="64" r="5" />
            <circle cx="34" cy="34" r="5" />
            <circle cx="94" cy="94" r="5" />
            <circle cx="34" cy="94" r="5" />
            <circle cx="94" cy="34" r="5" />
          </g>
        </svg>
      );
    case "sqlite":
      return (
        <svg viewBox="0 0 128 128" width={size} height={size} style={{ flexShrink: 0 }}>
          <rect width="128" height="128" rx="20" fill="#003B57" />
          <path
            fill="#00ADEF"
            d="M96 32c-16 0-32 12-42 26-10 14-18 32-26 50 14-8 28-18 38-30s18-26 30-46z"
          />
          <path
            fill="#FFFFFF"
            d="M48 64c-8 12-14 26-20 40 10-6 20-14 28-24 6-8 12-18 16-28-8 3-16 7-24 12z"
          />
        </svg>
      );
    case "oracle":
      return (
        <svg viewBox="0 0 128 128" width={size} height={size} style={{ flexShrink: 0 }}>
          <rect width="128" height="128" rx="20" fill="#F80000" />
          <path
            fill="#FFFFFF"
            d="M48 40h32c13.3 0 24 10.7 24 24s-10.7 24-24 24H48c-13.3 0-24-10.7-24-24s10.7-24 24-24zm0 12c-6.6 0-12 5.4-12 12s5.4 12 12 12h32c6.6 0 12-5.4 12-12s-5.4-12-12-12H48z"
          />
        </svg>
      );
    case "bigquery":
      return (
        <svg viewBox="0 0 128 128" width={size} height={size} style={{ flexShrink: 0 }}>
          <rect width="128" height="128" rx="20" fill="#4285F4" />
          <g fill="#FFFFFF">
            <circle cx="58" cy="58" r="30" fill="none" stroke="#FFFFFF" strokeWidth="10" />
            <path d="M80 80l24 24" stroke="#FFFFFF" strokeWidth="12" strokeLinecap="round" />
            <rect x="44" y="44" width="8" height="20" rx="2" />
            <rect x="54" y="38" width="8" height="26" rx="2" />
            <rect x="64" y="50" width="8" height="14" rx="2" />
          </g>
        </svg>
      );
    case "databricks":
      return (
        <svg viewBox="0 0 128 128" width={size} height={size} style={{ flexShrink: 0 }}>
          <rect width="128" height="128" rx="20" fill="#FF3621" />
          <path
            fill="#FFFFFF"
            d="M64 24l36 20-36 20-36-20 36-20zm0 28l36 20-36 20-36-20 36-20zm0 28l36 20-36 20-36-20 36-20z"
          />
        </svg>
      );
    case "rest_api":
      return (
        <svg viewBox="0 0 128 128" width={size} height={size} style={{ flexShrink: 0 }}>
          <rect width="128" height="128" rx="20" fill="#10B981" />
          <path
            fill="none"
            stroke="#FFFFFF"
            strokeWidth="8"
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M52 44H40a20 20 0 000 40h12m24 0h12a20 20 0 000-40H76m-32 20h40"
          />
        </svg>
      );
    case "loki":
      return (
        <svg viewBox="0 0 128 128" width={size} height={size} style={{ flexShrink: 0 }}>
          <rect width="128" height="128" rx="20" fill="#F46800" />
          <path
            fill="#FFFFFF"
            d="M36 32h56v14H36zm0 25h56v14H36zm0 25h40v14H36z"
            rx="4"
          />
          <circle cx="88" cy="89" r="7" fill="#FFFFFF" />
        </svg>
      );
    case "prometheus":
      return (
        <svg viewBox="0 0 128 128" width={size} height={size} style={{ flexShrink: 0 }}>
          <rect width="128" height="128" rx="20" fill="#E6522C" />
          <path
            fill="#FFFFFF"
            d="M64 24c-12 18-20 28-20 44 0 11 9 20 20 20s20-9 20-20c0-16-8-26-20-44zm0 50c-3.3 0-6-2.7-6-6 0-5.3 4-10.3 6-15 2 4.7 6 9.7 6 15 0 3.3-2.7 6-6 6zm-28 22h56v8H36z"
          />
        </svg>
      );
    default:
      return (
        <svg viewBox="0 0 128 128" width={size} height={size} style={{ flexShrink: 0 }}>
          <rect width="128" height="128" rx="20" fill="#64748B" />
          <path
            fill="none"
            stroke="#FFFFFF"
            strokeWidth="8"
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M32 44h64v20H32zm0 28h64v20H32zm16-38v-8m32 8v-8"
          />
        </svg>
      );
  }
}

export function CreateConnectionWizard({
  isOpen,
  onClose,
  initialProvider,
  defaultCatalog = "main",
  defaultSchema = "default",
}: CreateConnectionWizardProps) {
  const toast = useToast();
  const { data: providers = [], isLoading: isLoadingProviders } = useConnectionProviders();
  const createConn = useCreateCatalogConnection();
  const testConn = useTestConnection();

  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);
  const [selectedProvider, setSelectedProvider] = useState<ProviderMetadata | null>(null);

  // Filter state for Step 1
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Step 2 state: Identity & Catalog location
  const [catalogName, setCatalogName] = useState<string>(defaultCatalog);
  const [schemaName, setSchemaName] = useState<string>(defaultSchema);
  const [connName, setConnName] = useState<string>("");
  const [description, setDescription] = useState<string>("");

  // Step 3 state: Dynamic Config & Auth values
  const [configValues, setConfigValues] = useState<Record<string, any>>({});
  const [authValues, setAuthValues] = useState<Record<string, any>>({});

  // Step 4 state: Live Test outcome
  const [testResult, setTestResult] = useState<{
    tested: boolean;
    success: boolean;
    message: string;
    latency_ms: number;
  } | null>(null);

  // Pre-select provider if passed via props
  useEffect(() => {
    if (initialProvider && providers.length > 0) {
      const match = providers.find((p) => p.type_id === initialProvider);
      if (match) {
        handleSelectProvider(match);
      }
    }
  }, [initialProvider, providers]);

  function handleSelectProvider(provider: ProviderMetadata) {
    setSelectedProvider(provider);
    // Initialize default config fields
    const initialCfg: Record<string, any> = {};
    provider.config_fields.forEach((f) => {
      if (f.default !== undefined) initialCfg[f.name] = f.default;
    });
    setConfigValues(initialCfg);

    // Initialize default auth fields
    const initialAuth: Record<string, any> = {};
    provider.auth_fields.forEach((f) => {
      if (f.default !== undefined) initialAuth[f.name] = f.default;
    });
    setAuthValues(initialAuth);

    setTestResult(null);
    setStep(2);
  }

  function handleRunLiveTest() {
    if (!selectedProvider) return;
    setTestResult(null);
    testConn.mutate(
      {
        connector_type: selectedProvider.type_id,
        config: configValues,
        auth_config: authValues,
      },
      {
        onSuccess: (data) => {
          setTestResult({
            tested: true,
            success: data.success,
            message: data.message,
            latency_ms: data.latency_ms,
          });
          if (data.success) {
            toast.success(`Connection test passed (${data.latency_ms}ms)`);
          } else {
            toast.error(data.message);
          }
        },
        onError: (err: any) => {
          setTestResult({
            tested: true,
            success: false,
            message: err.message || "Failed to reach server",
            latency_ms: 0,
          });
          toast.error("Test connection failed");
        },
      }
    );
  }

  async function handleFinishCreate() {
    if (!selectedProvider) return;
    if (!connName.trim()) {
      toast.error("Connection name is required.");
      return;
    }

    try {
      await createConn.mutateAsync({
        catalog: catalogName.trim() || "main",
        schema: schemaName.trim() || "default",
        name: connName.trim(),
        connector_type: selectedProvider.type_id,
        category: selectedProvider.category,
        description: description.trim() || undefined,
        config: configValues,
        auth_config: authValues,
        status: "active",
      });

      toast.success(`Catalog Connection "${connName}" created successfully!`);
      onClose();
    } catch (err: any) {
      toast.error(err.message || "Failed to save connection");
    }
  }

  if (!isOpen) return null;

  const filteredProviders = providers.filter((p) => {
    const matchesCat = categoryFilter === "all" || p.category === categoryFilter;
    const matchesSearch =
      !searchQuery.trim() ||
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.description.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCat && matchesSearch;
  });

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0, 0, 0, 0.5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1100,
        backdropFilter: "blur(3px)",
      }}
    >
      <div
        style={{
          backgroundColor: "var(--color-bg-surface, #ffffff)",
          color: "var(--color-text-primary, #1e293b)",
          width: "100%",
          maxWidth: 680,
          maxHeight: "90vh",
          display: "flex",
          flexDirection: "column",
          borderRadius: 10,
          boxShadow: "0 20px 40px rgba(0, 0, 0, 0.2)",
          border: "1px solid var(--color-border, #e2e8f0)",
          overflow: "hidden",
        }}
      >
        {/* Header with Step Indicator */}
        <div
          style={{
            padding: "16px 24px",
            borderBottom: "1px solid var(--color-border, #e2e8f0)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "var(--color-bg-subtle, #f8fafc)",
          }}
        >
          <div>
            <h2 style={{ margin: 0, fontSize: "1.15rem", fontWeight: 600 }}>Create Catalog Connection</h2>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6, fontSize: "0.8rem", color: "var(--color-text-muted, #64748b)" }}>
              <span style={{ color: step >= 1 ? "var(--color-primary, #2563eb)" : undefined, fontWeight: step === 1 ? 600 : 400 }}>1. Provider</span>
              <ChevronRight size={12} />
              <span style={{ color: step >= 2 ? "var(--color-primary, #2563eb)" : undefined, fontWeight: step === 2 ? 600 : 400 }}>2. Catalog & Name</span>
              <ChevronRight size={12} />
              <span style={{ color: step >= 3 ? "var(--color-primary, #2563eb)" : undefined, fontWeight: step === 3 ? 600 : 400 }}>3. Configuration</span>
              <ChevronRight size={12} />
              <span style={{ color: step >= 4 ? "var(--color-primary, #2563eb)" : undefined, fontWeight: step === 4 ? 600 : 400 }}>4. Test & Save</span>
            </div>
          </div>
          <button type="button" className="ghost-icon-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px" }}>
          {/* ── STEP 1: Select Provider ── */}
          {step === 1 && (
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                <div className="search-bar-wrapper" style={{ flex: 1 }}>
                  <Search size={14} className="search-icon" />
                  <input
                    className="search-input"
                    placeholder="Search databases, APIs, Loki..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    autoFocus
                  />
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  {["all", "database", "api", "observability"].map((cat) => (
                    <button
                      key={cat}
                      type="button"
                      onClick={() => setCategoryFilter(cat)}
                      style={{
                        padding: "6px 12px",
                        borderRadius: 6,
                        border: "1px solid",
                        fontSize: "0.8rem",
                        cursor: "pointer",
                        borderColor: categoryFilter === cat ? "var(--color-primary, #2563eb)" : "var(--color-border, #e2e8f0)",
                        background: categoryFilter === cat ? "var(--color-primary-light, #eff6ff)" : "transparent",
                        color: categoryFilter === cat ? "var(--color-primary, #2563eb)" : "inherit",
                        fontWeight: categoryFilter === cat ? 600 : 400,
                      }}
                    >
                      {cat === "all" ? "All" : cat === "database" ? "Databases" : cat === "api" ? "REST APIs" : "Observability"}
                    </button>
                  ))}
                </div>
              </div>

              {isLoadingProviders ? (
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: 40 }}>
                  <Loader2 className="spin" size={24} />
                </div>
              ) : (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }}>
                  {filteredProviders.map((p) => (
                    <div
                      key={p.type_id}
                      onClick={() => handleSelectProvider(p)}
                      style={{
                        padding: "14px 16px",
                        borderRadius: 8,
                        border: "1px solid var(--color-border, #e2e8f0)",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "flex-start",
                        gap: 12,
                        transition: "all 0.15s ease",
                        background: "var(--color-bg-surface, #ffffff)",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = "var(--color-primary, #2563eb)";
                        e.currentTarget.style.boxShadow = "0 4px 12px rgba(37,99,235,0.08)";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = "var(--color-border, #e2e8f0)";
                        e.currentTarget.style.boxShadow = "none";
                      }}
                    >
                      <ProviderLogo typeId={p.type_id} size={32} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <span style={{ fontWeight: 600, fontSize: "0.92rem" }}>{p.name}</span>
                          {p.is_popular && (
                            <span
                              style={{
                                fontSize: "0.65rem",
                                padding: "1px 5px",
                                borderRadius: 4,
                                background: "#FEF3C7",
                                color: "#92400E",
                                fontWeight: 600,
                              }}
                            >
                              POPULAR
                            </span>
                          )}
                        </div>
                        <p style={{ margin: "4px 0 0", fontSize: "0.78rem", color: "var(--color-text-muted, #64748b)", lineHeight: 1.35 }}>
                          {p.description}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── STEP 2: Catalog, Schema & Connection Name ── */}
          {step === 2 && selectedProvider && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 14px", background: "var(--color-bg-subtle, #f8fafc)", borderRadius: 8, border: "1px solid var(--color-border, #e2e8f0)" }}>
                <ProviderLogo typeId={selectedProvider.type_id} size={28} />
                <div>
                  <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>{selectedProvider.name}</div>
                  <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>Category: {selectedProvider.category.toUpperCase()}</div>
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                <div className="form-group">
                  <label className="form-label">Destination Catalog</label>
                  <input className="form-input" value={catalogName} onChange={(e) => setCatalogName(e.target.value)} required />
                </div>
                <div className="form-group">
                  <label className="form-label">Destination Schema</label>
                  <input className="form-input" value={schemaName} onChange={(e) => setSchemaName(e.target.value)} required />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">
                  Connection Identifier <span style={{ color: "var(--color-danger, #ef4444)" }}>*</span>
                </label>
                <input
                  className="form-input"
                  placeholder="e.g. pg_analytics, loki_prod, stripe_api"
                  value={connName}
                  onChange={(e) => setConnName(e.target.value)}
                  autoFocus
                  required
                />
                <p style={{ margin: "4px 0 0", fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
                  Fully Qualified Name: <code>{catalogName || "catalog"}.{schemaName || "schema"}.{connName || "name"}</code>
                </p>
              </div>

              <div className="form-group">
                <label className="form-label">Description</label>
                <textarea
                  className="form-input"
                  rows={2}
                  placeholder="Optional notes or purpose of this connection"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>
            </div>
          )}

          {/* ── STEP 3: Connection Configuration & Auth Fields ── */}
          {step === 3 && selectedProvider && (
            <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
              {/* Configuration Section */}
              <div>
                <h4 style={{ margin: "0 0 12px", fontSize: "0.9rem", fontWeight: 600, display: "flex", alignItems: "center", gap: 6 }}>
                  <Server size={14} /> Connection Settings
                </h4>
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  {selectedProvider.config_fields.map((f) => (
                    <div key={f.name} className="form-group">
                      <label className="form-label">
                        {f.label} {f.required && <span style={{ color: "var(--color-danger, #ef4444)" }}>*</span>}
                      </label>
                      {f.type === "textarea" ? (
                        <textarea
                          className="form-input"
                          rows={3}
                          placeholder={f.placeholder}
                          value={configValues[f.name] || ""}
                          onChange={(e) => setConfigValues({ ...configValues, [f.name]: e.target.value })}
                        />
                      ) : f.type === "select" ? (
                        <select
                          className="form-input"
                          value={configValues[f.name] || ""}
                          onChange={(e) => setConfigValues({ ...configValues, [f.name]: e.target.value })}
                        >
                          {(f.options || []).map((opt) => (
                            <option key={opt.value} value={opt.value}>
                              {opt.label}
                            </option>
                          ))}
                        </select>
                      ) : f.type === "boolean" ? (
                        <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: "0.85rem" }}>
                          <input
                            type="checkbox"
                            checked={Boolean(configValues[f.name])}
                            onChange={(e) => setConfigValues({ ...configValues, [f.name]: e.target.checked })}
                          />
                          {f.help_text || f.label}
                        </label>
                      ) : (
                        <input
                          type={f.type === "number" ? "number" : "text"}
                          className="form-input"
                          placeholder={f.placeholder}
                          value={configValues[f.name] ?? ""}
                          onChange={(e) => setConfigValues({ ...configValues, [f.name]: f.type === "number" ? Number(e.target.value) : e.target.value })}
                          required={f.required}
                        />
                      )}
                      {f.help_text && f.type !== "boolean" && (
                        <p style={{ margin: "4px 0 0", fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
                          {f.help_text}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Authentication Section */}
              {selectedProvider.auth_fields.length > 0 && (
                <div style={{ paddingTop: 14, borderTop: "1px solid var(--color-border, #e2e8f0)" }}>
                  <h4 style={{ margin: "0 0 12px", fontSize: "0.9rem", fontWeight: 600, display: "flex", alignItems: "center", gap: 6 }}>
                    <Key size={14} /> Authentication & Secrets <span style={{ fontSize: "0.75rem", fontWeight: 400, color: "#10B981" }}>(Encrypted at Rest)</span>
                  </h4>
                  <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                    {selectedProvider.auth_fields.map((f) => (
                      <div key={f.name} className="form-group">
                        <label className="form-label">
                          {f.label} {f.required && <span style={{ color: "var(--color-danger, #ef4444)" }}>*</span>}
                        </label>
                        {f.type === "select" ? (
                          <select
                            className="form-input"
                            value={authValues[f.name] || ""}
                            onChange={(e) => setAuthValues({ ...authValues, [f.name]: e.target.value })}
                          >
                            {(f.options || []).map((opt) => (
                              <option key={opt.value} value={opt.value}>
                                {opt.label}
                              </option>
                            ))}
                          </select>
                        ) : f.type === "textarea" ? (
                          <textarea
                            className="form-input"
                            rows={3}
                            placeholder={f.placeholder}
                            value={authValues[f.name] || ""}
                            onChange={(e) => setAuthValues({ ...authValues, [f.name]: e.target.value })}
                          />
                        ) : (
                          <input
                            type={f.type === "password" ? "password" : "text"}
                            className="form-input"
                            placeholder={f.placeholder}
                            value={authValues[f.name] || ""}
                            onChange={(e) => setAuthValues({ ...authValues, [f.name]: e.target.value })}
                            required={f.required}
                          />
                        )}
                        {f.help_text && (
                          <p style={{ margin: "4px 0 0", fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
                            {f.help_text}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── STEP 4: Live Test & Summary ── */}
          {step === 4 && selectedProvider && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ padding: 14, borderRadius: 8, background: "var(--color-bg-subtle, #f8fafc)", border: "1px solid var(--color-border, #e2e8f0)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                  <ProviderLogo typeId={selectedProvider.type_id} size={28} />
                  <div>
                    <b style={{ fontSize: "0.95rem" }}>{catalogName}.{schemaName}.{connName}</b>
                    <div style={{ fontSize: "0.78rem", color: "var(--color-text-muted)" }}>{selectedProvider.name} • {selectedProvider.category}</div>
                  </div>
                </div>
                {description && <div style={{ fontSize: "0.8rem", color: "var(--color-text-muted)", marginTop: 4 }}>{description}</div>}
              </div>

              {/* Test Action Card */}
              <div style={{ padding: 16, borderRadius: 8, border: "1px solid var(--color-border, #e2e8f0)", background: "#ffffff" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>Test Connectivity</div>
                    <div style={{ fontSize: "0.78rem", color: "var(--color-text-muted)" }}>Validate network access and credentials before saving</div>
                  </div>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={handleRunLiveTest}
                    disabled={testConn.isPending}
                    style={{ display: "flex", alignItems: "center", gap: 6 }}
                  >
                    {testConn.isPending ? <Loader2 size={14} className="spin" /> : <Zap size={14} color="#F59E0B" />}
                    {testConn.isPending ? "Testing..." : "Test Connection"}
                  </button>
                </div>

                {testResult && (
                  <div
                    style={{
                      padding: "10px 14px",
                      borderRadius: 6,
                      fontSize: "0.82rem",
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      background: testResult.success ? "#E8F5E9" : "#FFEBEE",
                      color: testResult.success ? "#2E7D32" : "#C62828",
                      border: `1px solid ${testResult.success ? "#A5D6A7" : "#FFCDD2"}`,
                    }}
                  >
                    {testResult.success ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
                    <span style={{ flex: 1 }}>{testResult.message}</span>
                    {testResult.latency_ms > 0 && <span>({testResult.latency_ms}ms)</span>}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer Controls */}
        <div
          style={{
            padding: "14px 24px",
            borderTop: "1px solid var(--color-border, #e2e8f0)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "var(--color-bg-subtle, #f8fafc)",
          }}
        >
          <div>
            {step > 1 && (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setStep((s) => (s - 1) as any)}
                style={{ display: "flex", alignItems: "center", gap: 6 }}
              >
                <ChevronLeft size={14} /> Back
              </button>
            )}
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>

            {step < 4 ? (
              <button
                type="button"
                className="btn btn-primary"
                disabled={step === 1 && !selectedProvider}
                onClick={() => {
                  if (step === 2 && !connName.trim()) {
                    toast.error("Please provide a connection identifier.");
                    return;
                  }
                  setStep((s) => (s + 1) as any);
                }}
                style={{ display: "flex", alignItems: "center", gap: 6 }}
              >
                Next <ChevronRight size={14} />
              </button>
            ) : (
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleFinishCreate}
                disabled={createConn.isPending}
                style={{ display: "flex", alignItems: "center", gap: 6 }}
              >
                {createConn.isPending && <Loader2 size={14} className="spin" />}
                {createConn.isPending ? "Creating..." : "Create Connection"}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
