import React, { useState } from "react";
import {
  useServicePrincipals,
  useCreateServicePrincipal,
  useUpdateServicePrincipal,
  useDeleteServicePrincipal,
  useServicePrincipalSecrets,
  useGenerateSPSecret,
  useRevokeSPSecret,
  type ServicePrincipalOut,
  type SecretGenerateOut,
  type SecretMetadataOut,
} from "../../lib/userManagerApi";

const Glass: React.FC<React.PropsWithChildren<{ className?: string; style?: React.CSSProperties; onClick?: () => void }>> =
  ({ children, className = "", style, onClick }) => (
    <div className={`glass ${className}`} style={{
      background: "var(--color-surface)",
      border: "1px solid var(--color-border)",
      borderRadius: "var(--radius-lg)",
      ...style,
    }} onClick={onClick}>{children}</div>
  );

const Badge: React.FC<{ label: string; color?: string }> = ({ label, color = "var(--color-primary)" }) => (
  <span style={{
    display: "inline-block", padding: "2px 10px", borderRadius: 999,
    fontSize: 11, fontWeight: 600, letterSpacing: "0.04em",
    background: `${color}22`, color, border: `1px solid ${color}44`,
  }}>{label.toUpperCase()}</span>
);

export const ServicePrincipalsTab: React.FC = () => {
  const { data: sps = [], isLoading } = useServicePrincipals();
  const createSp = useCreateServicePrincipal();
  const updateSp = useUpdateServicePrincipal();
  const deleteSp = useDeleteServicePrincipal();

  const [search, setSearch] = useState("");
  const [showAddForm, setShowAddForm] = useState(false);
  const [newDisplayName, setNewDisplayName] = useState("");
  const [expandedSpId, setExpandedSpId] = useState<string | null>(null);

  const filteredSps = sps.filter((sp) =>
    sp.display_name.toLowerCase().includes(search.toLowerCase()) ||
    sp.application_id.toLowerCase().includes(search.toLowerCase())
  );

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDisplayName.trim()) return;
    await createSp.mutateAsync(newDisplayName.trim());
    setNewDisplayName("");
    setShowAddForm(false);
  };

  if (isLoading) {
    return <div style={{ textAlign: "center", padding: 32, color: "var(--color-text-muted)" }}>Loading service principals…</div>;
  }

  return (
    <div>
      {/* Top Header Controls */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <input
            className="input-field"
            placeholder="Search service principals…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ width: 280 }}
          />
          <span style={{ fontSize: 13, color: "var(--color-text-muted)" }}>
            {filteredSps.length} total
          </span>
        </div>
        <button className="btn-primary" onClick={() => setShowAddForm((s) => !s)}>
          + Add service principal
        </button>
      </div>

      {/* Inline Creation Form */}
      {showAddForm && (
        <Glass style={{ padding: 20, marginBottom: 20 }}>
          <h3 style={{ margin: "0 0 12px", fontSize: 15, fontWeight: 700 }}>Add Service Principal</h3>
          <form onSubmit={handleCreate} style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <input
              className="input-field"
              placeholder="Display Name (e.g. etl-pipeline-runner)"
              value={newDisplayName}
              onChange={(e) => setNewDisplayName(e.target.value)}
              style={{ flex: 1 }}
              required
            />
            <button className="btn-primary" type="submit" disabled={createSp.isPending}>
              {createSp.isPending ? "Creating…" : "Create"}
            </button>
            <button className="btn-outline" type="button" onClick={() => setShowAddForm(false)}>
              Cancel
            </button>
          </form>
        </Glass>
      )}

      {/* Service Principals List */}
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {filteredSps.map((sp: ServicePrincipalOut) => {
          const isExpanded = expandedSpId === sp.id;
          return (
            <Glass key={sp.id} style={{ padding: "16px 20px" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                  <span
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: "50%",
                      background: sp.is_active ? "var(--color-success, #22C55E)" : "var(--color-danger, #EF4444)",
                    }}
                    title={sp.is_active ? "Active" : "Inactive"}
                  />
                  <div>
                    <div style={{ fontWeight: 600, color: "var(--color-text)", fontSize: 15 }}>
                      {sp.display_name}
                    </div>
                    <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2, display: "flex", gap: 8, alignItems: "center" }}>
                      <span>App ID: <code style={{ fontSize: 11 }}>{sp.application_id}</code></span>
                      <button
                        onClick={() => navigator.clipboard.writeText(sp.application_id)}
                        style={{ background: "none", border: "none", color: "var(--color-primary)", cursor: "pointer", fontSize: 11 }}
                      >
                        Copy
                      </button>
                      <span>·</span>
                      <span>{sp.secret_count} active secret{sp.secret_count !== 1 ? "s" : ""}</span>
                    </div>
                  </div>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <button
                    className="btn-outline"
                    style={{ fontSize: 13, padding: "6px 14px" }}
                    onClick={() => setExpandedSpId(isExpanded ? null : sp.id)}
                  >
                    {isExpanded ? "Close" : "Manage"}
                  </button>
                </div>
              </div>

              {/* Expanded Detail Panel */}
              {isExpanded && (
                <div style={{ marginTop: 20, paddingTop: 16, borderTop: "1px solid var(--color-border)" }}>
                  <ServicePrincipalDetailView
                    sp={sp}
                    onDelete={async () => {
                      if (window.confirm(`Delete service principal "${sp.display_name}"?`)) {
                        await deleteSp.mutateAsync(sp.id);
                        setExpandedSpId(null);
                      }
                    }}
                    onToggleActive={async () => {
                      await updateSp.mutateAsync({ spId: sp.id, payload: { is_active: !sp.is_active } });
                    }}
                  />
                </div>
              )}
            </Glass>
          );
        })}

        {filteredSps.length === 0 && (
          <div style={{ textAlign: "center", padding: 48, color: "var(--color-text-muted)" }}>
            No service principals found.
          </div>
        )}
      </div>
    </div>
  );
};

/* ─── Detail View (Sub-tabs: Configurations + Secrets) ────────────────────────── */

interface DetailViewProps {
  sp: ServicePrincipalOut;
  onDelete: () => Promise<void>;
  onToggleActive: () => Promise<void>;
}

const ServicePrincipalDetailView: React.FC<DetailViewProps> = ({ sp, onDelete, onToggleActive }) => {
  const [subTab, setSubTab] = useState<"Configurations" | "Secrets">("Configurations");
  const { data: secrets = [], isLoading: loadingSecrets } = useServicePrincipalSecrets(sp.id);
  const generateSecret = useGenerateSPSecret(sp.id);
  const revokeSecret = useRevokeSPSecret(sp.id);

  const [generatedResult, setGeneratedResult] = useState<SecretGenerateOut | null>(null);
  const [expiryDays, setExpiryDays] = useState(90);

  const handleGenerateSecret = async () => {
    const res = await generateSecret.mutateAsync(expiryDays);
    setGeneratedResult(res);
  };

  return (
    <div>
      {/* Sub-tab Switcher */}
      <div style={{ display: "flex", gap: 16, borderBottom: "1px solid var(--color-border)", marginBottom: 16 }}>
        {(["Configurations", "Secrets"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setSubTab(tab)}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: "8px 4px",
              fontSize: 13,
              fontWeight: subTab === tab ? 600 : 400,
              color: subTab === tab ? "var(--color-primary)" : "var(--color-text-muted)",
              borderBottom: `2px solid ${subTab === tab ? "var(--color-primary)" : "transparent"}`,
              marginBottom: -1,
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Sub-tab: Configurations */}
      {subTab === "Configurations" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <label className="label" style={{ fontSize: 12 }}>Application ID</label>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
              <input className="input-field" readOnly value={sp.application_id} style={{ maxWidth: 380 }} />
              <button
                className="btn-outline"
                onClick={() => navigator.clipboard.writeText(sp.application_id)}
                style={{ fontSize: 12 }}
              >
                Copy ID
              </button>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 13 }}>
              <input type="checkbox" checked={sp.is_active} onChange={onToggleActive} />
              Active
            </label>
          </div>

          <div style={{ paddingTop: 8 }}>
            <button className="btn-danger" style={{ fontSize: 12, padding: "6px 14px" }} onClick={onDelete}>
              Delete Service Principal
            </button>
          </div>
        </div>
      )}

      {/* Sub-tab: Secrets */}
      {subTab === "Secrets" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 13, color: "var(--color-text-muted)" }}>
              OAuth credentials for authenticating automated pipelines and background workers.
            </span>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <select
                className="input-field"
                value={expiryDays}
                onChange={(e) => setExpiryDays(Number(e.target.value))}
                style={{ fontSize: 12, padding: "4px 8px" }}
              >
                <option value={30}>Expires in 30 days</option>
                <option value={90}>Expires in 90 days</option>
                <option value={365}>Expires in 1 year</option>
                <option value={0}>Never expires</option>
              </select>
              <button className="btn-primary" style={{ fontSize: 12 }} onClick={handleGenerateSecret} disabled={generateSecret.isPending}>
                {generateSecret.isPending ? "Generating…" : "+ Generate Secret"}
              </button>
            </div>
          </div>

          {/* Newly Generated Secret Alert */}
          {generatedResult && (
            <div
              style={{
                background: "rgba(34, 197, 94, 0.08)",
                border: "1px solid rgba(34, 197, 94, 0.3)",
                borderRadius: "var(--radius)",
                padding: "16px 20px",
              }}
            >
              <div style={{ color: "var(--color-success, #22C55E)", fontWeight: 700, fontSize: 13, marginBottom: 4 }}>
                Secret Generated Successfully
              </div>
              <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginBottom: 12 }}>
                Please copy this secret now. You will not be able to see it again.
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <input
                  className="input-field"
                  readOnly
                  value={generatedResult.client_secret}
                  style={{ flex: 1, fontFamily: "monospace", fontSize: 12 }}
                />
                <button
                  className="btn-primary"
                  style={{ fontSize: 12 }}
                  onClick={() => navigator.clipboard.writeText(generatedResult.client_secret)}
                >
                  Copy Secret
                </button>
                <button
                  className="btn-outline"
                  style={{ fontSize: 12 }}
                  onClick={() => setGeneratedResult(null)}
                >
                  Dismiss
                </button>
              </div>
            </div>
          )}

          {/* Active Secrets Table */}
          {loadingSecrets ? (
            <div style={{ fontSize: 13, color: "var(--color-text-muted)" }}>Loading secrets…</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {secrets.map((sec: SecretMetadataOut) => (
                <div
                  key={sec.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "10px 14px",
                    background: "var(--color-bg)",
                    border: "1px solid var(--color-border)",
                    borderRadius: "var(--radius)",
                  }}
                >
                  <div>
                    <code style={{ fontSize: 13, fontWeight: 600 }}>{sec.secret_prefix}</code>
                    <div style={{ fontSize: 11, color: "var(--color-text-muted)", marginTop: 2 }}>
                      Created {new Date(sec.created_at).toLocaleDateString()} ·{" "}
                      {sec.expires_at ? `Expires ${new Date(sec.expires_at).toLocaleDateString()}` : "Never expires"}
                    </div>
                  </div>
                  <button
                    className="btn-danger"
                    style={{ fontSize: 11, padding: "4px 10px" }}
                    onClick={() => revokeSecret.mutate(sec.id)}
                    disabled={revokeSecret.isPending}
                  >
                    Revoke
                  </button>
                </div>
              ))}
              {secrets.length === 0 && (
                <div style={{ fontSize: 13, color: "var(--color-text-muted)", padding: "12px 0" }}>
                  No active secrets generated for this service principal.
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
