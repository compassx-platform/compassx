/**
 * Shown after login when the account admin has no workspaces yet.
 * Forces creation of the first workspace before accessing the app.
 */
import { useState, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, CompassIcon, FolderPlus } from "lucide-react";
import { useCreateWorkspace } from "@/lib/workspaceApi";
import { useMe } from "@/lib/userManagerApi";
import { useQueryClient } from "@tanstack/react-query";

const STORAGE_BACKENDS = ["minio", "s3", "azure"] as const;

export default function CreateWorkspacePage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: me, isLoading: loadingMe } = useMe();
  const { mutateAsync, isPending, error } = useCreateWorkspace();

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [backend, setBackend] = useState<"minio" | "s3" | "azure">("minio");
  const [endpoint, setEndpoint] = useState("");
  const [bucket, setBucket] = useState("");
  const [accessKey, setAccessKey] = useState("");
  const [secretKey, setSecretKey] = useState("");
  const [prefix, setPrefix] = useState("");

  const isAccountAdmin = me?.account_role === "account_admin" || me?.is_account_admin;

  if (loadingMe) {
    return <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", background: "var(--color-bg)" }}><Loader2 className="animate-spin" /></div>;
  }

  if (me && !isAccountAdmin) {
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
    let storage_config: Record<string, string>;
    if (backend === "minio") {
      storage_config = { endpoint, bucket, access_key: accessKey, secret_key: secretKey, prefix };
    } else if (backend === "s3") {
      storage_config = { bucket, region: endpoint, access_key: accessKey, secret_key: secretKey, prefix };
    } else {
      storage_config = { container: bucket, account_name: endpoint, account_key: accessKey, prefix };
    }

    const ws = await mutateAsync({ name, slug, storage_backend: backend, storage_config });
    await qc.invalidateQueries({ queryKey: ["my-workspaces"] });
    navigate(`/w/${ws.slug}/platform`);
  }

  const errMsg = error
    ? (error as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? "Failed to create workspace."
    : null;

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--color-bg)" }}>
      <div style={{ width: 480, background: "var(--color-surface)", border: "1px solid var(--color-border)", borderRadius: 16, padding: "40px 36px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 28 }}>
          <div style={{ width: 36, height: 36, borderRadius: 10, background: "var(--color-primary)", display: "grid", placeItems: "center", color: "#fff" }}>
            <CompassIcon size={18} />
          </div>
          <span style={{ fontWeight: 700, fontSize: "1.125rem" }}>Compass</span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
          <FolderPlus size={18} />
          <h1 style={{ fontSize: "1.2rem", fontWeight: 700 }}>Create your first workspace</h1>
        </div>
        <p style={{ color: "var(--color-text-muted)", fontSize: "0.85rem", marginBottom: 28 }}>
          A workspace groups your data, notebooks, and agents. You need at least one to get started.
        </p>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Workspace name</label>
            <input className="form-input" value={name} onChange={e => handleNameChange(e.target.value)} placeholder="Engineering" required autoFocus />
          </div>
          <div className="form-group">
            <label className="form-label">URL slug</label>
            <input className="form-input" value={slug} onChange={e => setSlug(e.target.value)} placeholder="engineering" required pattern="[a-z0-9-]+" />
            <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>Will be used in URL: /w/{slug || "..."}/</span>
          </div>

          <div className="form-group">
            <label className="form-label">Storage backend</label>
            <select className="form-input" value={backend} onChange={e => setBackend(e.target.value as typeof backend)}>
              {STORAGE_BACKENDS.map(b => <option key={b} value={b}>{b.toUpperCase()}</option>)}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">{backend === "azure" ? "Account name" : backend === "s3" ? "Region" : "Endpoint"}</label>
            <input className="form-input" value={endpoint} onChange={e => setEndpoint(e.target.value)} placeholder={backend === "minio" ? "http://minio:9000" : backend === "s3" ? "us-east-1" : "myaccount"} required />
          </div>
          <div className="form-group">
            <label className="form-label">{backend === "azure" ? "Container" : "Bucket"}</label>
            <input className="form-input" value={bucket} onChange={e => setBucket(e.target.value)} placeholder={backend === "azure" ? "compassx-data" : "compassx-engineering"} required />
          </div>
          <div className="form-group">
            <label className="form-label">{backend === "azure" ? "Account key" : "Access key"}</label>
            <input className="form-input" type="password" value={accessKey} onChange={e => setAccessKey(e.target.value)} required />
          </div>
          {backend !== "azure" && (
            <div className="form-group">
              <label className="form-label">Secret key</label>
              <input className="form-input" type="password" value={secretKey} onChange={e => setSecretKey(e.target.value)} required />
            </div>
          )}
          <div className="form-group">
            <label className="form-label">Path prefix <span style={{ color: "var(--color-text-muted)" }}>(optional)</span></label>
            <input className="form-input" value={prefix} onChange={e => setPrefix(e.target.value)} placeholder="engineering/" />
          </div>

          {errMsg && (
            <div style={{ padding: "10px 14px", borderRadius: 8, background: "rgba(185,28,28,0.1)", color: "#b91c1c", fontSize: "0.8rem", marginBottom: 16 }}>
              {errMsg}
            </div>
          )}

          <button type="submit" className="btn btn-primary" style={{ width: "100%", justifyContent: "center" }} disabled={isPending || !name || !slug}>
            {isPending ? <Loader2 size={15} className="spin" /> : null}
            {isPending ? "Creating…" : "Create workspace"}
          </button>
        </form>
      </div>
    </div>
  );
}
