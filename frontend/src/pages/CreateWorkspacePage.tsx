/**
 * Create Workspace Page.
 * Supports zero-friction creation using Account-Managed Storage (default)
 * or connecting Custom Storage (MinIO, S3, Azure Blob).
 */
import { useState, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, CompassIcon, FolderPlus, Database, ChevronDown, ChevronUp, CheckCircle2 } from "lucide-react";
import { useCreateWorkspace } from "@/lib/workspaceApi";
import { useMe } from "@/lib/userManagerApi";
import { isLoggedIn } from "@/lib/auth";
import { useQueryClient } from "@tanstack/react-query";

const STORAGE_BACKENDS = ["minio", "s3", "azure"] as const;

export default function CreateWorkspacePage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: me, isLoading: loadingMe } = useMe();
  const { mutateAsync, isPending, error } = useCreateWorkspace();

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [useCustomStorage, setUseCustomStorage] = useState(false);

  // Custom storage state
  const [backend, setBackend] = useState<"minio" | "s3" | "azure">("minio");
  const [endpoint, setEndpoint] = useState("");
  const [bucket, setBucket] = useState("");
  const [accessKey, setAccessKey] = useState("");
  const [secretKey, setSecretKey] = useState("");
  const [prefix, setPrefix] = useState("");

  const isAccountAdmin = me?.account_role === "account_admin" || me?.is_account_admin;

  if (loadingMe) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", background: "var(--color-bg)" }}>
        <Loader2 className="animate-spin" />
      </div>
    );
  }

  if (!isLoggedIn() || !me) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", background: "var(--color-bg)" }}>
        <div className="glass" style={{ padding: 32, maxWidth: 440, textAlign: "center", borderRadius: "var(--radius-lg)", background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: 18, color: "var(--color-danger)" }}>Authentication Required</h2>
          <p style={{ color: "var(--color-text-muted)", fontSize: 14, marginBottom: 20 }}>
            You must be logged in as an Account Administrator to create workspaces.
          </p>
          <button className="btn-primary" onClick={() => navigate("/login")}>Go to Login</button>
        </div>
      </div>
    );
  }

  if (!isAccountAdmin) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", background: "var(--color-bg)" }}>
        <div className="glass" style={{ padding: 32, maxWidth: 440, textAlign: "center", borderRadius: "var(--radius-lg)", background: "var(--color-surface)", border: "1px solid var(--color-border)" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: 18, color: "var(--color-danger)" }}>Access Restricted</h2>
          <p style={{ color: "var(--color-text-muted)", fontSize: 14, marginBottom: 20 }}>
            Only Account Administrators are authorized to create new workspaces.
          </p>
          <button className="btn-primary" onClick={() => navigate("/")}>Return to Application</button>
        </div>
      </div>
    );
  }

  function deriveSlug(n: string) {
    return n.toLowerCase().replace(/[^a-z0-9-]/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "");
  }

  function handleNameChange(v: string) {
    setName(v);
    setSlug(deriveSlug(v));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();

    let payload: { name: string; slug: string; storage_backend: string; storage_config: Record<string, string> };

    if (!useCustomStorage) {
      payload = {
        name: name.trim(),
        slug: slug.trim(),
        storage_backend: "managed",
        storage_config: {},
      };
    } else {
      let storage_config: Record<string, string>;
      if (backend === "minio") {
        storage_config = { endpoint, bucket, access_key: accessKey, secret_key: secretKey, prefix };
      } else if (backend === "s3") {
        storage_config = { bucket, region: endpoint, access_key: accessKey, secret_key: secretKey, prefix };
      } else {
        storage_config = { container: bucket, account_name: endpoint, account_key: accessKey, prefix };
      }
      payload = {
        name: name.trim(),
        slug: slug.trim(),
        storage_backend: backend,
        storage_config,
      };
    }

    const ws = await mutateAsync(payload);
    await qc.invalidateQueries({ queryKey: ["my-workspaces"] });
    navigate(`/w/${ws.slug}/platform`);
  }

  const errMsg = error
    ? (error as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? "Failed to create workspace."
    : null;

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--color-bg)", padding: "24px" }}>
      <div style={{ width: "100%", maxWidth: 500, background: "var(--color-surface)", border: "1px solid var(--color-border)", borderRadius: 16, padding: "36px 32px", boxShadow: "var(--shadow-md)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 24 }}>
          <div style={{ width: 36, height: 36, borderRadius: 10, background: "var(--color-primary)", display: "grid", placeItems: "center", color: "#fff" }}>
            <CompassIcon size={18} />
          </div>
          <span style={{ fontWeight: 700, fontSize: "1.125rem" }}>Compass</span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
          <FolderPlus size={20} />
          <h1 style={{ fontSize: "1.25rem", fontWeight: 700, margin: 0 }}>Create a Workspace</h1>
        </div>
        <p style={{ color: "var(--color-text-muted)", fontSize: "0.875rem", marginBottom: 24 }}>
          Workspaces organize your notebooks, SQL warehouse queries, catalogs, and AI agents.
        </p>

        <form onSubmit={handleSubmit}>
          <div className="form-group" style={{ marginBottom: 16 }}>
            <label className="form-label" style={{ fontWeight: 600, fontSize: "0.85rem", marginBottom: 6, display: "block" }}>Workspace Name</label>
            <input className="form-input" value={name} onChange={e => handleNameChange(e.target.value)} placeholder="e.g. Engineering, Marketing, Analytics" required autoFocus />
          </div>

          <div className="form-group" style={{ marginBottom: 20 }}>
            <label className="form-label" style={{ fontWeight: 600, fontSize: "0.85rem", marginBottom: 6, display: "block" }}>URL Slug</label>
            <input className="form-input" value={slug} onChange={e => setSlug(e.target.value)} placeholder="engineering" required pattern="[a-z0-9-]+" />
            <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", display: "block", marginTop: 4 }}>
              Accessible via: /w/{slug || "..."}/
            </span>
          </div>

          {/* Managed Storage Default Badge */}
          {!useCustomStorage && (
            <div style={{
              display: "flex",
              alignItems: "flex-start",
              gap: 12,
              padding: "12px 14px",
              borderRadius: "var(--radius)",
              background: "var(--color-surface-hover, rgba(255,255,255,0.03))",
              border: "1px solid var(--color-border)",
              marginBottom: 20,
            }}>
              <CheckCircle2 size={18} style={{ color: "var(--color-success, #10b981)", marginTop: 2, flexShrink: 0 }} />
              <div>
                <div style={{ fontWeight: 600, fontSize: "0.85rem" }}>Account Managed Storage (Default)</div>
                <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginTop: 2 }}>
                  Automatically stores workspace assets in your platform's managed storage under <code style={{ fontSize: "0.72rem" }}>workspaces/{slug || "slug"}/</code>. Zero setup required.
                </div>
              </div>
            </div>
          )}

          {/* Collapsible Custom Storage Option */}
          <div style={{ marginBottom: 24, borderTop: "1px solid var(--color-border)", paddingTop: 16 }}>
            <button
              type="button"
              onClick={() => setUseCustomStorage(!useCustomStorage)}
              style={{
                background: "transparent",
                border: "none",
                color: "var(--color-text-muted)",
                cursor: "pointer",
                padding: "4px 0",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                width: "100%",
                fontSize: "0.85rem",
              }}
            >
              <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <Database size={15} />
                {useCustomStorage ? "Using Custom Storage" : "Use Custom Storage (Advanced)"}
              </span>
              {useCustomStorage ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>

            {useCustomStorage && (
              <div style={{ marginTop: 16, padding: "16px", borderRadius: "var(--radius)", border: "1px solid var(--color-border)", background: "rgba(0,0,0,0.1)" }}>
                <div className="form-group" style={{ marginBottom: 12 }}>
                  <label className="form-label" style={{ fontSize: "0.8rem", marginBottom: 4, display: "block" }}>Storage Backend</label>
                  <select className="form-input" value={backend} onChange={e => setBackend(e.target.value as typeof backend)}>
                    {STORAGE_BACKENDS.map(b => <option key={b} value={b}>{b.toUpperCase()}</option>)}
                  </select>
                </div>

                <div className="form-group" style={{ marginBottom: 12 }}>
                  <label className="form-label" style={{ fontSize: "0.8rem", marginBottom: 4, display: "block" }}>{backend === "azure" ? "Account Name" : backend === "s3" ? "Region" : "Endpoint"}</label>
                  <input className="form-input" value={endpoint} onChange={e => setEndpoint(e.target.value)} placeholder={backend === "minio" ? "http://minio:9000" : backend === "s3" ? "us-east-1" : "myaccount"} required={useCustomStorage} />
                </div>
                <div className="form-group" style={{ marginBottom: 12 }}>
                  <label className="form-label" style={{ fontSize: "0.8rem", marginBottom: 4, display: "block" }}>{backend === "azure" ? "Container" : "Bucket"}</label>
                  <input className="form-input" value={bucket} onChange={e => setBucket(e.target.value)} placeholder={backend === "azure" ? "compassx-data" : "compassx-engineering"} required={useCustomStorage} />
                </div>
                <div className="form-group" style={{ marginBottom: 12 }}>
                  <label className="form-label" style={{ fontSize: "0.8rem", marginBottom: 4, display: "block" }}>{backend === "azure" ? "Account Key" : "Access Key"}</label>
                  <input className="form-input" type="password" value={accessKey} onChange={e => setAccessKey(e.target.value)} required={useCustomStorage} />
                </div>
                {backend !== "azure" && (
                  <div className="form-group" style={{ marginBottom: 12 }}>
                    <label className="form-label" style={{ fontSize: "0.8rem", marginBottom: 4, display: "block" }}>Secret Key</label>
                    <input className="form-input" type="password" value={secretKey} onChange={e => setSecretKey(e.target.value)} required={useCustomStorage} />
                  </div>
                )}
                <div className="form-group" style={{ marginBottom: 4 }}>
                  <label className="form-label" style={{ fontSize: "0.8rem", marginBottom: 4, display: "block" }}>Path Prefix <span style={{ color: "var(--color-text-muted)" }}>(optional)</span></label>
                  <input className="form-input" value={prefix} onChange={e => setPrefix(e.target.value)} placeholder="engineering/" />
                </div>
              </div>
            )}
          </div>

          {errMsg && (
            <div style={{ padding: "10px 14px", borderRadius: 8, background: "rgba(185,28,28,0.1)", color: "#b91c1c", fontSize: "0.8rem", marginBottom: 16 }}>
              {errMsg}
            </div>
          )}

          <div style={{ display: "flex", gap: 12 }}>
            <button
              type="button"
              className="btn-outline"
              style={{ flex: 1, justifyContent: "center" }}
              onClick={() => navigate(-1)}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              style={{ flex: 2, justifyContent: "center" }}
              disabled={isPending || !name || !slug}
            >
              {isPending ? <Loader2 size={15} className="spin" /> : null}
              {isPending ? "Creating…" : "Create Workspace"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
