import React, { useState, useEffect, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ArrowLeft,
  Search,
  CheckCircle2,
  XCircle,
  Loader2,
  ChevronDown,
  ChevronRight,
  Eye,
  EyeOff,
  Zap,
} from "lucide-react";
import { useScopedNavigate } from "@/lib/appNavigation";
import {
  useConnectionProviders,
  useCreateCatalogConnection,
  useTestConnection,
  useCatalogs,
  type ProviderMetadata,
} from "@/modules/agents/hooks/useCatalogConnections";
import { ProviderLogo } from "@/modules/agents/components/CreateConnectionWizard";
import { useToast } from "@/lib/toast";

export default function CreateConnectionPage() {
  const navigate = useScopedNavigate();
  const [searchParams] = useSearchParams();
  const toast = useToast();

  const initialProviderParam = searchParams.get("provider");
  const initialCatalogParam = searchParams.get("catalog") || "";
  const initialSchemaParam = searchParams.get("schema") || "";

  const { data: providers = [], isLoading: isLoadingProviders } = useConnectionProviders();
  const { data: catalogs = [], isLoading: isLoadingCatalogs } = useCatalogs();
  const createConn = useCreateCatalogConnection();
  const testConn = useTestConnection();

  const [step, setStep] = useState<1 | 2 | 3>(1);

  // Step 1 state: Name, Type dropdown, optional Catalog & Schema location
  const [connName, setConnName] = useState<string>("");
  const [selectedTypeId, setSelectedTypeId] = useState<string>("");
  const [catalogName, setCatalogName] = useState<string>(initialCatalogParam);
  const [schemaName, setSchemaName] = useState<string>(initialSchemaParam);
  const [description, setDescription] = useState<string>("");

  // Custom Dropdown Open State
  const [isTypeDropdownOpen, setIsTypeDropdownOpen] = useState(false);
  const [dropdownSearch, setDropdownSearch] = useState("");

  // Step 2 state: Dynamic Config & Auth values + password visibility
  const [configValues, setConfigValues] = useState<Record<string, any>>({});
  const [authValues, setAuthValues] = useState<Record<string, any>>({});
  const [showPasswordMap, setShowPasswordMap] = useState<Record<string, boolean>>({});

  // Step 3 state: Live Test outcome
  const [testResult, setTestResult] = useState<{
    tested: boolean;
    success: boolean;
    message: string;
    latency_ms: number;
  } | null>(null);

  // Selected Provider object
  const selectedProvider = useMemo(() => {
    return providers.find((p) => p.type_id === selectedTypeId) || null;
  }, [providers, selectedTypeId]);

  // Selected Catalog object & schemas
  const activeCatalog = useMemo(() => {
    if (!catalogName) return null;
    return catalogs.find((c) => c.name.toLowerCase() === catalogName.toLowerCase()) || null;
  }, [catalogs, catalogName]);

  const availableSchemas = useMemo(() => {
    return activeCatalog?.schemas || [];
  }, [activeCatalog]);

  // Handle URL param initialization or default selection
  useEffect(() => {
    if (providers.length > 0 && !selectedTypeId) {
      const match = initialProviderParam
        ? providers.find((p) => p.type_id === initialProviderParam)
        : providers[0];
      if (match) {
        handleSelectProviderType(match.type_id);
      }
    }
  }, [initialProviderParam, providers]);

  function handleSelectProviderType(typeId: string) {
    setSelectedTypeId(typeId);
    setIsTypeDropdownOpen(false);
    setDropdownSearch("");

    const provider = providers.find((p) => p.type_id === typeId);
    if (provider) {
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
    }
  }

  function togglePasswordVisibility(fieldName: string) {
    setShowPasswordMap((prev) => ({
      ...prev,
      [fieldName]: !prev[fieldName],
    }));
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
    if (!selectedProvider) {
      toast.error("Please select a connection type.");
      return;
    }
    if (!connName.trim()) {
      toast.error("Connection name is required.");
      return;
    }

    try {
      await createConn.mutateAsync({
        catalog: catalogName.trim() || undefined,
        schema: schemaName.trim() || undefined,
        name: connName.trim(),
        connector_type: selectedProvider.type_id,
        category: selectedProvider.category,
        description: description.trim() || undefined,
        config: configValues,
        auth_config: authValues,
        status: "active",
      });

      toast.success(`Connection "${connName}" created successfully!`);
      navigate("/connections");
    } catch (err: any) {
      toast.error(err.message || "Failed to save connection");
    }
  }

  // Filtered providers for dropdown search
  const filteredDropdownProviders = providers.filter(
    (p) =>
      !dropdownSearch.trim() ||
      p.name.toLowerCase().includes(dropdownSearch.toLowerCase()) ||
      p.category.toLowerCase().includes(dropdownSearch.toLowerCase()) ||
      p.type_id.toLowerCase().includes(dropdownSearch.toLowerCase())
  );

  const displayScope = catalogName && schemaName ? `${catalogName}.${schemaName}.${connName || "name"}` : (connName || "name");

  return (
    <div style={{ maxWidth: 760, margin: "24px auto", padding: "0 16px 60px" }}>
      {/* Back Button */}
      <button
        type="button"
        className="btn btn-secondary"
        onClick={() => navigate("/connections")}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          marginBottom: 16,
          fontSize: "0.82rem",
          padding: "6px 12px",
          color: "#475569",
        }}
      >
        <ArrowLeft size={14} /> Back to Connections
      </button>

      {/* Stepper Progress Bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 20px",
          background: "#ffffff",
          borderRadius: 8,
          border: "1px solid #e2e8f0",
          marginBottom: 18,
          boxShadow: "0 1px 2px rgba(0, 0, 0, 0.02)",
        }}
      >
        <div
          onClick={() => setStep(1)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            cursor: "pointer",
            color: step === 1 ? "#2563eb" : step > 1 ? "#059669" : "#64748b",
            fontWeight: step === 1 ? 600 : 500,
            fontSize: "0.84rem",
          }}
        >
          <span
            style={{
              width: 22,
              height: 22,
              borderRadius: "50%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "0.75rem",
              fontWeight: 700,
              background: step === 1 ? "#eff6ff" : step > 1 ? "#ecfdf5" : "#f1f5f9",
              color: step === 1 ? "#2563eb" : step > 1 ? "#059669" : "#64748b",
              border: `1px solid ${step === 1 ? "#bfdbfe" : step > 1 ? "#a7f3d0" : "#e2e8f0"}`,
            }}
          >
            {step > 1 ? "✓" : "1"}
          </span>
          <span>1. Connection details</span>
        </div>

        <ChevronRight size={14} color="#cbd5e1" />

        <div
          onClick={() => {
            if (connName.trim() && selectedTypeId) setStep(2);
          }}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            cursor: connName.trim() && selectedTypeId ? "pointer" : "default",
            color: step === 2 ? "#2563eb" : step > 2 ? "#059669" : "#64748b",
            fontWeight: step === 2 ? 600 : 500,
            fontSize: "0.84rem",
          }}
        >
          <span
            style={{
              width: 22,
              height: 22,
              borderRadius: "50%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "0.75rem",
              fontWeight: 700,
              background: step === 2 ? "#eff6ff" : step > 2 ? "#ecfdf5" : "#f1f5f9",
              color: step === 2 ? "#2563eb" : step > 2 ? "#059669" : "#64748b",
              border: `1px solid ${step === 2 ? "#bfdbfe" : step > 2 ? "#a7f3d0" : "#e2e8f0"}`,
            }}
          >
            {step > 2 ? "✓" : "2"}
          </span>
          <span>2. Authentication & settings</span>
        </div>

        <ChevronRight size={14} color="#cbd5e1" />

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            color: step === 3 ? "#2563eb" : "#64748b",
            fontWeight: step === 3 ? 600 : 500,
            fontSize: "0.84rem",
          }}
        >
          <span
            style={{
              width: 22,
              height: 22,
              borderRadius: "50%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "0.75rem",
              fontWeight: 700,
              background: step === 3 ? "#eff6ff" : "#f1f5f9",
              color: step === 3 ? "#2563eb" : "#64748b",
              border: `1px solid ${step === 3 ? "#bfdbfe" : "#e2e8f0"}`,
            }}
          >
            3
          </span>
          <span>3. Review & test</span>
        </div>
      </div>

      {/* Main Clean Card */}
      <div
        style={{
          background: "#ffffff",
          borderRadius: 8,
          border: "1px solid #e2e8f0",
          boxShadow: "0 1px 3px rgba(0, 0, 0, 0.03)",
          overflow: "hidden",
        }}
      >
        {/* Step Header Inside Card */}
        <div
          style={{
            background: "#fbfcfd",
            padding: "24px 32px 20px",
            borderBottom: "1px solid #f1f5f9",
          }}
        >
          <div style={{ fontSize: "0.82rem", fontWeight: 500, color: "#64748b", marginBottom: 6 }}>
            Step {step}
          </div>
          <h2 style={{ margin: 0, fontSize: "1.28rem", fontWeight: 600, color: "#0f172a", letterSpacing: "-0.01em" }}>
            {step === 1 && "Connection details"}
            {step === 2 && "Authentication"}
            {step === 3 && "Review & Test"}
          </h2>
        </div>

        {/* Step Content */}
        <div style={{ padding: "32px" }}>
          {/* ── STEP 1: Details & Type ── */}
          {step === 1 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
              {/* Connection Name */}
              <div>
                <label style={{ display: "block", fontSize: "0.86rem", fontWeight: 600, color: "#1e293b", marginBottom: 2 }}>
                  Connection name*
                </label>
                <p style={{ margin: "0 0 8px", fontSize: "0.80rem", color: "#64748b", lineHeight: 1.4 }}>
                  Unique identifier used to reference this connection.
                </p>
                <input
                  className="form-input"
                  placeholder="e.g. pg_analytics, stripe_api, prod_loki"
                  value={connName}
                  onChange={(e) => setConnName(e.target.value)}
                  autoFocus
                  required
                  style={{
                    width: "100%",
                    padding: "9px 12px",
                    borderRadius: 6,
                    border: "1px solid #cbd5e1",
                    fontSize: "0.88rem",
                  }}
                />
              </div>

              {/* Connection Type Dropdown */}
              <div style={{ position: "relative" }}>
                <label style={{ display: "block", fontSize: "0.86rem", fontWeight: 600, color: "#1e293b", marginBottom: 2 }}>
                  Connection type*
                </label>
                <p style={{ margin: "0 0 8px", fontSize: "0.80rem", color: "#64748b", lineHeight: 1.4 }}>
                  The source database, API provider, or observability service to connect.
                </p>

                {/* Dropdown Trigger */}
                <div
                  onClick={() => setIsTypeDropdownOpen(!isTypeDropdownOpen)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "9px 12px",
                    borderRadius: 6,
                    border: "1px solid #cbd5e1",
                    background: "#ffffff",
                    cursor: "pointer",
                    minHeight: 40,
                  }}
                >
                  {selectedProvider ? (
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <ProviderLogo typeId={selectedProvider.type_id} size={20} />
                      <span style={{ fontWeight: 500, fontSize: "0.88rem", color: "#0f172a" }}>
                        {selectedProvider.name}
                      </span>
                      <span
                        style={{
                          fontSize: "0.68rem",
                          textTransform: "uppercase",
                          padding: "1px 6px",
                          borderRadius: 4,
                          background: "#f1f5f9",
                          color: "#64748b",
                          fontWeight: 600,
                        }}
                      >
                        {selectedProvider.category}
                      </span>
                    </div>
                  ) : (
                    <span style={{ color: "#94a3b8", fontSize: "0.88rem" }}>
                      Select a connection type...
                    </span>
                  )}
                  <ChevronDown size={16} color="#64748b" />
                </div>

                {/* Dropdown Menu */}
                {isTypeDropdownOpen && (
                  <div
                    style={{
                      position: "absolute",
                      top: "100%",
                      left: 0,
                      right: 0,
                      marginTop: 4,
                      background: "#ffffff",
                      borderRadius: 8,
                      border: "1px solid #e2e8f0",
                      boxShadow: "0 10px 25px rgba(0,0,0,0.12)",
                      zIndex: 100,
                      maxHeight: 320,
                      display: "flex",
                      flexDirection: "column",
                      overflow: "hidden",
                    }}
                  >
                    <div style={{ padding: "8px 10px", borderBottom: "1px solid #e2e8f0" }}>
                      <div className="search-bar-wrapper" style={{ width: "100%" }}>
                        <Search size={13} className="search-icon" />
                        <input
                          className="search-input"
                          placeholder="Search type (Postgres, REST, Loki...)"
                          value={dropdownSearch}
                          onChange={(e) => setDropdownSearch(e.target.value)}
                          autoFocus
                          onClick={(e) => e.stopPropagation()}
                        />
                      </div>
                    </div>

                    <div style={{ overflowY: "auto", padding: "4px 0" }}>
                      {isLoadingProviders ? (
                        <div style={{ padding: 16, textAlign: "center" }}>
                          <Loader2 className="spin" size={18} />
                        </div>
                      ) : filteredDropdownProviders.length === 0 ? (
                        <div style={{ padding: "12px 16px", fontSize: "0.82rem", color: "#64748b" }}>
                          No connection types matching "{dropdownSearch}"
                        </div>
                      ) : (
                        filteredDropdownProviders.map((p) => (
                          <div
                            key={p.type_id}
                            onClick={() => handleSelectProviderType(p.type_id)}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between",
                              padding: "8px 14px",
                              cursor: "pointer",
                              background: p.type_id === selectedTypeId ? "#eff6ff" : "transparent",
                              transition: "background 0.1s ease",
                            }}
                            onMouseEnter={(e) => {
                              if (p.type_id !== selectedTypeId) e.currentTarget.style.background = "#f8fafc";
                            }}
                            onMouseLeave={(e) => {
                              if (p.type_id !== selectedTypeId) e.currentTarget.style.background = "transparent";
                            }}
                          >
                            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                              <ProviderLogo typeId={p.type_id} size={20} />
                              <span style={{ fontSize: "0.88rem", fontWeight: p.type_id === selectedTypeId ? 600 : 400, color: "#0f172a" }}>
                                {p.name}
                              </span>
                            </div>

                            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                              {p.is_popular && (
                                <span style={{ fontSize: "0.62rem", padding: "1px 5px", borderRadius: 4, background: "#FEF3C7", color: "#92400E", fontWeight: 600 }}>
                                  POPULAR
                                </span>
                              )}
                              <span style={{ fontSize: "0.7rem", textTransform: "uppercase", color: "#64748b" }}>
                                {p.category}
                              </span>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Destination Catalog */}
              <div>
                <label style={{ display: "block", fontSize: "0.86rem", fontWeight: 600, color: "#1e293b", marginBottom: 2 }}>
                  Catalog
                </label>
                <p style={{ margin: "0 0 8px", fontSize: "0.80rem", color: "#64748b", lineHeight: 1.4 }}>
                  Catalog location in the data catalog. Leave unselected for account-level connection.
                </p>
                <select
                  className="form-input"
                  value={catalogName}
                  onChange={(e) => {
                    const val = e.target.value;
                    setCatalogName(val);
                    if (!val) {
                      setSchemaName("");
                    } else {
                      const matched = catalogs.find((c) => c.name === val);
                      if (matched && matched.schemas.length > 0) {
                        setSchemaName(matched.schemas[0].name);
                      } else {
                        setSchemaName("");
                      }
                    }
                  }}
                  style={{
                    width: "100%",
                    padding: "9px 12px",
                    borderRadius: 6,
                    border: "1px solid #cbd5e1",
                    fontSize: "0.88rem",
                  }}
                >
                  <option value="">-- None (Account-Level Connection) --</option>
                  {catalogs.map((cat) => (
                    <option key={cat.name} value={cat.name}>
                      {cat.name} ({cat.catalog_type || "catalog"})
                    </option>
                  ))}
                </select>
              </div>

              {/* Destination Schema */}
              <div>
                <label style={{ display: "block", fontSize: "0.86rem", fontWeight: 600, color: "#1e293b", marginBottom: 2 }}>
                  Schema
                </label>
                <p style={{ margin: "0 0 8px", fontSize: "0.80rem", color: "#64748b", lineHeight: 1.4 }}>
                  Schema namespace inside the selected catalog.
                </p>
                <select
                  className="form-input"
                  value={schemaName}
                  onChange={(e) => setSchemaName(e.target.value)}
                  disabled={!catalogName}
                  style={{
                    width: "100%",
                    padding: "9px 12px",
                    borderRadius: 6,
                    border: "1px solid #cbd5e1",
                    fontSize: "0.88rem",
                    backgroundColor: !catalogName ? "#f8fafc" : "#ffffff",
                  }}
                >
                  <option value="">-- None --</option>
                  {availableSchemas.map((sch) => (
                    <option key={sch.name} value={sch.name}>
                      {sch.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Description */}
              <div>
                <label style={{ display: "block", fontSize: "0.86rem", fontWeight: 600, color: "#1e293b", marginBottom: 2 }}>
                  Description
                </label>
                <p style={{ margin: "0 0 8px", fontSize: "0.80rem", color: "#64748b", lineHeight: 1.4 }}>
                  Optional comment or purpose of this connection.
                </p>
                <textarea
                  className="form-input"
                  rows={2}
                  placeholder="e.g. Production analytics database replica"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "9px 12px",
                    borderRadius: 6,
                    border: "1px solid #cbd5e1",
                    fontSize: "0.88rem",
                  }}
                />
              </div>
            </div>
          )}

          {/* ── STEP 2: Authentication & Connection Settings ── */}
          {step === 2 && selectedProvider && (
            <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
              {/* Dynamic Config Fields */}
              {selectedProvider.config_fields.map((f) => (
                <div key={f.name}>
                  <label style={{ display: "block", fontSize: "0.86rem", fontWeight: 600, color: "#1e293b", marginBottom: 2 }}>
                    {f.label}{f.required && "*"}
                  </label>
                  <p style={{ margin: "0 0 8px", fontSize: "0.80rem", color: "#64748b", lineHeight: 1.4 }}>
                    {f.help_text || (f.name === "host" ? "Host name of the foreign server without scheme (i.e. no 'jdbc://' or 'https://' prefix)." : f.name === "port" ? `Port of the foreign instance, default to ${f.default || 5432}.` : f.name === "database" ? "Initial database name on the foreign instance." : `Configuration value for ${f.label.toLowerCase()}.`)}
                  </p>
                  {f.type === "textarea" ? (
                    <textarea
                      className="form-input"
                      rows={3}
                      placeholder={f.placeholder}
                      value={configValues[f.name] || ""}
                      onChange={(e) => setConfigValues({ ...configValues, [f.name]: e.target.value })}
                      style={{ width: "100%", padding: "9px 12px", borderRadius: 6, border: "1px solid #cbd5e1", fontSize: "0.88rem" }}
                    />
                  ) : f.type === "select" ? (
                    <select
                      className="form-input"
                      value={configValues[f.name] || ""}
                      onChange={(e) => setConfigValues({ ...configValues, [f.name]: e.target.value })}
                      style={{ width: "100%", padding: "9px 12px", borderRadius: 6, border: "1px solid #cbd5e1", fontSize: "0.88rem" }}
                    >
                      {(f.options || []).map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  ) : f.type === "boolean" ? (
                    <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: "0.85rem", color: "#1e293b", marginTop: 4 }}>
                      <input
                        type="checkbox"
                        checked={Boolean(configValues[f.name])}
                        onChange={(e) => setConfigValues({ ...configValues, [f.name]: e.target.checked })}
                      />
                      {f.label}
                    </label>
                  ) : (
                    <input
                      type={f.type === "number" ? "number" : "text"}
                      className="form-input"
                      placeholder={f.placeholder}
                      value={configValues[f.name] ?? ""}
                      onChange={(e) => setConfigValues({ ...configValues, [f.name]: f.type === "number" ? Number(e.target.value) : e.target.value })}
                      required={f.required}
                      style={{ width: "100%", padding: "9px 12px", borderRadius: 6, border: "1px solid #cbd5e1", fontSize: "0.88rem" }}
                    />
                  )}
                </div>
              ))}

              {/* Dynamic Auth Fields */}
              {selectedProvider.auth_fields.map((f) => (
                <div key={f.name}>
                  <label style={{ display: "block", fontSize: "0.86rem", fontWeight: 600, color: "#1e293b", marginBottom: 2 }}>
                    {f.label}{f.required && "*"}
                  </label>
                  <p style={{ margin: "0 0 8px", fontSize: "0.80rem", color: "#64748b", lineHeight: 1.4 }}>
                    {f.help_text || (f.name === "username" ? "User identity used to access the foreign instance." : f.name === "password" ? "Password of the foreign instance." : `Credentials for ${f.label.toLowerCase()}.`)}
                  </p>
                  {f.type === "password" ? (
                    <div style={{ position: "relative" }}>
                      <input
                        type={showPasswordMap[f.name] ? "text" : "password"}
                        className="form-input"
                        placeholder={f.placeholder || "password123"}
                        value={authValues[f.name] || ""}
                        onChange={(e) => setAuthValues({ ...authValues, [f.name]: e.target.value })}
                        required={f.required}
                        style={{
                          width: "100%",
                          padding: "9px 38px 9px 12px",
                          borderRadius: 6,
                          border: "1px solid #cbd5e1",
                          fontSize: "0.88rem",
                        }}
                      />
                      <button
                        type="button"
                        onClick={() => togglePasswordVisibility(f.name)}
                        style={{
                          position: "absolute",
                          right: 10,
                          top: "50%",
                          transform: "translateY(-50%)",
                          background: "none",
                          border: "none",
                          cursor: "pointer",
                          color: "#64748b",
                          padding: 4,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                        title={showPasswordMap[f.name] ? "Hide password" : "Show password"}
                      >
                        {showPasswordMap[f.name] ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                  ) : f.type === "textarea" ? (
                    <textarea
                      className="form-input"
                      rows={3}
                      placeholder={f.placeholder}
                      value={authValues[f.name] || ""}
                      onChange={(e) => setAuthValues({ ...authValues, [f.name]: e.target.value })}
                      style={{ width: "100%", padding: "9px 12px", borderRadius: 6, border: "1px solid #cbd5e1", fontSize: "0.88rem" }}
                    />
                  ) : f.type === "select" ? (
                    <select
                      className="form-input"
                      value={authValues[f.name] || ""}
                      onChange={(e) => setAuthValues({ ...authValues, [f.name]: e.target.value })}
                      style={{ width: "100%", padding: "9px 12px", borderRadius: 6, border: "1px solid #cbd5e1", fontSize: "0.88rem" }}
                    >
                      {(f.options || []).map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      className="form-input"
                      placeholder={f.placeholder || (f.name === "username" ? "username" : "")}
                      value={authValues[f.name] || ""}
                      onChange={(e) => setAuthValues({ ...authValues, [f.name]: e.target.value })}
                      required={f.required}
                      style={{ width: "100%", padding: "9px 12px", borderRadius: 6, border: "1px solid #cbd5e1", fontSize: "0.88rem" }}
                    />
                  )}
                </div>
              ))}
            </div>
          )}

          {/* ── STEP 3: Review & Test ── */}
          {step === 3 && selectedProvider && (
            <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
              {/* Summary Box */}
              <div
                style={{
                  padding: "16px 20px",
                  borderRadius: 6,
                  background: "#f8fafc",
                  border: "1px solid #e2e8f0",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
                  <ProviderLogo typeId={selectedProvider.type_id} size={28} />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: "0.95rem", color: "#0f172a" }}>
                      {displayScope}
                    </div>
                    <div style={{ fontSize: "0.78rem", color: "#64748b" }}>
                      {selectedProvider.name} • {catalogName && schemaName ? `Catalog: ${catalogName}.${schemaName}` : "Account Level"}
                    </div>
                  </div>
                </div>
                {description && (
                  <div style={{ fontSize: "0.82rem", color: "#475569", marginTop: 6 }}>
                    {description}
                  </div>
                )}
              </div>

              {/* Live Test Box */}
              <div
                style={{
                  padding: "18px 20px",
                  borderRadius: 6,
                  border: "1px solid #e2e8f0",
                  background: "#ffffff",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: "0.88rem", color: "#0f172a" }}>
                      Test Connectivity
                    </div>
                    <div style={{ fontSize: "0.78rem", color: "#64748b" }}>
                      Validate network access and credentials before saving.
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={handleRunLiveTest}
                    disabled={testConn.isPending}
                    style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 12px", fontSize: "0.82rem" }}
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

        {/* Card Footer Actions */}
        <div
          style={{
            padding: "16px 32px",
            background: "#fbfcfd",
            borderTop: "1px solid #f1f5f9",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            {step > 1 && (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setStep((s) => (s - 1) as any)}
                style={{ fontSize: "0.85rem", padding: "7px 14px" }}
              >
                Back
              </button>
            )}
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => navigate("/connections")}
              style={{ fontSize: "0.85rem", padding: "7px 14px" }}
            >
              Cancel
            </button>

            {step < 3 ? (
              <button
                type="button"
                className="btn btn-primary"
                disabled={step === 1 && (!connName.trim() || !selectedTypeId)}
                onClick={() => {
                  if (step === 1) {
                    if (!connName.trim()) {
                      toast.error("Please enter a connection name.");
                      return;
                    }
                    if (!selectedTypeId) {
                      toast.error("Please select a connection type.");
                      return;
                    }
                  }
                  setStep((s) => (s + 1) as any);
                }}
                style={{ fontSize: "0.85rem", padding: "7px 16px" }}
              >
                Next
              </button>
            ) : (
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleFinishCreate}
                disabled={createConn.isPending}
                style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.85rem", padding: "7px 16px" }}
              >
                {createConn.isPending && <Loader2 size={14} className="spin" />}
                {createConn.isPending ? "Creating..." : "Create"}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
