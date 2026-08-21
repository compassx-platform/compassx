import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  useMe, useUsers, useCreateUser, useInvites, useGroups, useWorkspacesAdmin, useAuditLog,
  useSuspendUser, useReactivateUser, useCreateInvite, useRevokeInvite,
  useCreateGroup, changeAccountRole,
  type UserListItem, type InviteOut, type GroupOut, type WorkspaceAdminOut, type AuditLogItem, type InviteIn,
} from "../../lib/userManagerApi";
import { clearSession } from "../../lib/auth";
import { CompassXLogo } from "@/components/common/CompassXLogo";

const TABS = ["Users", "Invites", "Groups", "Workspaces", "Audit Log"] as const;
type Tab = typeof TABS[number];

const STATUS_COLOR: Record<string, string> = {
  active: "var(--color-success)", invited: "var(--color-warning)", suspended: "var(--color-danger)", deactivated: "var(--color-text-subtle)",
};

/* ─── Shared primitives ───────────────────────────────────────────────── */
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
  }}>{label.replace("_", " ").toUpperCase()}</span>
);

/* ─── Users Tab ──────────────────────────────────────────────────────── */
function UsersTab() {
  const { data: users = [], isLoading } = useUsers();
  const createUser = useCreateUser();
  const suspend = useSuspendUser();
  const reactivate = useReactivateUser();
  const [editingRole, setEditingRole] = useState<string | null>(null);
  const [roleMap, setRoleMap] = useState<Record<string, string>>({});

  const [showForm, setShowForm] = useState(false);
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [accountRole, setAccountRole] = useState("account_viewer");
  const [error, setError] = useState<string | null>(null);

  if (isLoading) return <Loader />;

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!email.trim() || !displayName.trim() || !password) return;
    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    try {
      await createUser.mutateAsync({
        email: email.trim(),
        display_name: displayName.trim(),
        password,
        account_role: accountRole,
      });
      setShowForm(false);
      setEmail("");
      setDisplayName("");
      setPassword("");
      setAccountRole("account_viewer");
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || "Failed to create user");
    }
  };

  const handleRoleChange = async (userId: string, roleId: string) => {
    await changeAccountRole(userId, roleId);
    setEditingRole(null);
  };

  return (
    <div>
      <div style={{ marginBottom: 16, display: "flex", justifyContent: "flex-end" }}>
        <button className="btn-primary" onClick={() => setShowForm(s => !s)}>+ Add User</button>
      </div>

      {showForm && (
        <Glass style={{ padding: 20, marginBottom: 20 }}>
          <h3 style={{ margin: "0 0 16px", fontSize: 15, fontWeight: 700 }}>Directly Provision User</h3>
          {error && (
            <div style={{ padding: "8px 12px", background: "var(--color-danger-bg)", color: "var(--color-danger)",
              borderRadius: "var(--radius)", fontSize: 13, marginBottom: 12 }}>
              {error}
            </div>
          )}
          <form onSubmit={handleCreateUser}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
              <div>
                <label className="label">Email Address</label>
                <input required className="input-field" type="email" value={email}
                  onChange={e => setEmail(e.target.value)} />
              </div>
              <div>
                <label className="label">Display Name</label>
                <input required className="input-field" type="text" value={displayName}
                  onChange={e => setDisplayName(e.target.value)} />
              </div>
              <div>
                <label className="label">Initial Password</label>
                <input required className="input-field" type="password" value={password}
                  onChange={e => setPassword(e.target.value)} />
              </div>
              <div>
                <label className="label">Account Role</label>
                <select className="input-field" value={accountRole} onChange={e => setAccountRole(e.target.value)}>
                  <option value="account_viewer">Account Viewer</option>
                  <option value="billing_admin">Billing Admin</option>
                  <option value="account_admin">Account Admin</option>
                </select>
              </div>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button type="submit" className="btn-primary" disabled={createUser.isPending}>
                {createUser.isPending ? "Creating…" : "Create User"}
              </button>
              <button type="button" className="btn-outline" onClick={() => setShowForm(false)}>Cancel</button>
            </div>
          </form>
        </Glass>
      )}
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--color-border)" }}>
              {["User", "Status", "Account Role", "Workspaces", "Last Login", "Actions"].map(h => (
                <th key={h} style={{ textAlign: "left", padding: "10px 14px", fontSize: 11, fontWeight: 700,
                  color: "var(--color-text-muted)", letterSpacing: "0.08em", textTransform: "uppercase" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {users.map((u: UserListItem) => (
              <tr key={u.id} style={{ borderBottom: "1px solid var(--color-border)" }}>
                <td style={{ padding: "12px 14px" }}>
                  <div style={{ fontWeight: 600, color: "var(--color-text)", fontSize: 14 }}>{u.display_name || u.email}</div>
                  <div style={{ fontSize: 12, color: "var(--color-text-muted)" }}>{u.email}</div>
                </td>
                <td style={{ padding: "12px 14px" }}>
                  <Badge label={u.status} color={STATUS_COLOR[u.status]} />
                </td>
                <td style={{ padding: "12px 14px" }}>
                  {editingRole === u.id ? (
                    <div style={{ display: "flex", gap: 6 }}>
                      <select className="input-field" style={{ width: "auto" }} value={roleMap[u.id] || u.account_role || ""}
                        onChange={e => setRoleMap(m => ({ ...m, [u.id]: e.target.value }))}>
                        {["account_admin", "billing_admin", "account_viewer"].map(r =>
                          <option key={r} value={r}>{r.replace("_", " ")}</option>)}
                      </select>
                      <button className="btn-primary" style={{ padding: "4px 10px", fontSize: 12 }}
                        onClick={() => handleRoleChange(u.id, roleMap[u.id] || u.account_role || "")}>Save</button>
                      <button className="btn-outline" style={{ padding: "4px 8px", fontSize: 12 }} onClick={() => setEditingRole(null)}>✕</button>
                    </div>
                  ) : (
                    <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                      {u.account_role ? <Badge label={u.account_role} /> : <span style={{ color: "var(--color-text-subtle)" }}>—</span>}
                      <button onClick={() => setEditingRole(u.id)}
                        style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer", fontSize: 12 }}>✎</button>
                    </div>
                  )}
                </td>
                <td style={{ padding: "12px 14px", color: "var(--color-text-muted)", fontSize: 13 }}>{u.workspace_count}</td>
                <td style={{ padding: "12px 14px", color: "var(--color-text-muted)", fontSize: 12 }}>
                  {u.last_login_at ? new Date(u.last_login_at).toLocaleDateString() : "Never"}
                </td>
                <td style={{ padding: "12px 14px" }}>
                  <div style={{ display: "flex", gap: 6 }}>
                    {u.status === "active" && (
                      <button className="btn-outline" style={{ fontSize: 12, padding: "4px 10px" }}
                        onClick={() => suspend.mutate(u.id)}>Suspend</button>
                    )}
                    {u.status === "suspended" && (
                      <button className="btn-primary" style={{ fontSize: 12, padding: "4px 10px" }}
                        onClick={() => reactivate.mutate(u.id)}>Reactivate</button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {users.length === 0 && <Empty message="No users yet. Invite someone to get started." />}
      </div>
    </div>
  );
}

/* ─── Invites Tab ────────────────────────────────────────────────────── */
function InvitesTab() {
  const { data: invites = [], isLoading } = useInvites();
  const create = useCreateInvite();
  const revoke = useRevokeInvite();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<InviteIn>({ email: "", target_scope: "workspace", proposed_workspace_role_id: "analyst" });

  const handleCreate = async () => {
    await create.mutateAsync(form);
    setShowForm(false);
    setForm({ email: "", target_scope: "workspace", proposed_workspace_role_id: "analyst" });
  };

  if (isLoading) return <Loader />;
  return (
    <div>
      <div style={{ marginBottom: 16, display: "flex", justifyContent: "flex-end" }}>
        <button className="btn-primary" onClick={() => setShowForm(s => !s)}>+ Invite User</button>
      </div>
      {showForm && (
        <Glass style={{ padding: 20, marginBottom: 20 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
            <div>
              <label className="label">Email</label>
              <input className="input-field" type="email" value={form.email}
                onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />
            </div>
            <div>
              <label className="label">Scope</label>
              <select className="input-field" value={form.target_scope}
                onChange={e => setForm(f => ({ ...f, target_scope: e.target.value }))}>
                <option value="workspace">Workspace</option>
                <option value="account">Account only</option>
              </select>
            </div>
            <div>
              <label className="label">Workspace Role</label>
              <select className="input-field" value={form.proposed_workspace_role_id || ""}
                onChange={e => setForm(f => ({ ...f, proposed_workspace_role_id: e.target.value }))}>
                {["workspace_admin", "analyst", "business_viewer"].map(r =>
                  <option key={r} value={r}>{r.replace(/_/g, " ")}</option>)}
              </select>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn-primary" onClick={handleCreate} disabled={create.isPending}>
              {create.isPending ? "Sending…" : "Send Invite"}
            </button>
            <button className="btn-outline" onClick={() => setShowForm(false)}>Cancel</button>
          </div>
        </Glass>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {invites.map((inv: InviteOut) => (
          <Glass key={inv.id} style={{ padding: "14px 20px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <div style={{ fontWeight: 600, color: "var(--color-text)" }}>{inv.email}</div>
              <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 2 }}>
                {inv.target_scope} · {inv.proposed_workspace_role_id || inv.proposed_account_role_id || "—"} ·
                Expires {new Date(inv.expires_at).toLocaleDateString()}
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              {inv.invite_url && (
                <button onClick={() => navigator.clipboard.writeText(inv.invite_url)}
                  style={{ background: "none", border: "none", color: "var(--color-primary)", cursor: "pointer", fontSize: 12 }}>
                  Copy Link
                </button>
              )}
              <button className="btn-danger" style={{ fontSize: 12, padding: "4px 10px" }}
                onClick={() => revoke.mutate(inv.id)}>Revoke</button>
            </div>
          </Glass>
        ))}
        {invites.length === 0 && <Empty message="No pending invites." />}
      </div>
    </div>
  );
}

/* ─── Groups Tab ─────────────────────────────────────────────────────── */
function GroupsTab() {
  const { data: groups = [], isLoading } = useGroups();
  const create = useCreateGroup();
  const [newGroupName, setNewGroupName] = useState("");
  const [expandedGroup, setExpandedGroup] = useState<string | null>(null);

  const handleCreate = async () => {
    if (!newGroupName.trim()) return;
    await create.mutateAsync(newGroupName.trim());
    setNewGroupName("");
  };

  if (isLoading) return <Loader />;
  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        <input className="input-field" value={newGroupName}
          onChange={e => setNewGroupName(e.target.value)} style={{ maxWidth: 320 }} />
        <button className="btn-primary" onClick={handleCreate}>Create Group</button>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {groups.map((g: GroupOut) => (
          <Glass key={g.id} style={{ padding: "14px 20px" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div>
                <span style={{ fontWeight: 600, color: "var(--color-text)" }}>{g.name}</span>
                <span style={{ color: "var(--color-text-muted)", fontSize: 12, marginLeft: 10 }}>{g.member_count} member{g.member_count !== 1 ? "s" : ""}</span>
              </div>
              <button className="btn-outline" style={{ fontSize: 12 }}
                onClick={() => setExpandedGroup(expandedGroup === g.id ? null : g.id)}>
                {expandedGroup === g.id ? "Hide" : "Manage"}
              </button>
            </div>
          </Glass>
        ))}
        {groups.length === 0 && <Empty message="No groups yet." />}
      </div>
    </div>
  );
}

/* ─── Workspaces Tab ─────────────────────────────────────────────────── */
function WorkspacesTab() {
  const { data: workspaces = [], isLoading } = useWorkspacesAdmin();
  const navigate = useNavigate();

  if (isLoading) return <Loader />;
  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(260px,1fr))", gap: 16 }}>
        {workspaces.map((ws: WorkspaceAdminOut) => (
          <Glass key={ws.id} style={{ padding: 20, cursor: "pointer" }}
            onClick={() => navigate(`/account/workspaces/${ws.id}/members`)}>
            <div style={{ fontWeight: 700, color: "var(--color-text)", fontSize: 16, marginBottom: 6 }}>{ws.name}</div>
            <div style={{ fontSize: 12, color: "var(--color-text-muted)" }}>{ws.slug}</div>
            <div style={{ marginTop: 12, display: "flex", gap: 8, alignItems: "center" }}>
              <Badge label={ws.status} color={ws.status === "active" ? "var(--color-success)" : "var(--color-text-subtle)"} />
              <span style={{ fontSize: 12, color: "var(--color-text-muted)" }}>{ws.member_count} members</span>
            </div>
          </Glass>
        ))}
      </div>
      {workspaces.length === 0 && <Empty message="No workspaces yet." />}
    </div>
  );
}

/* ─── Audit Log Tab ──────────────────────────────────────────────────── */
function AuditLogTab() {
  const [filters, setFilters] = useState<{ action?: string; workspace_id?: string }>({});
  const { data: logs = [], isLoading } = useAuditLog({ ...filters, limit: 100 });

  return (
    <div>
      <div style={{ display: "flex", gap: 10, marginBottom: 16 }}>
        <input className="input-field" placeholder="Filter by action…" style={{ maxWidth: 200 }}
          onChange={e => setFilters(f => ({ ...f, action: e.target.value || undefined }))} />
        <input className="input-field" placeholder="Filter by workspace ID…" style={{ maxWidth: 260 }}
          onChange={e => setFilters(f => ({ ...f, workspace_id: e.target.value || undefined }))} />
      </div>
      {isLoading ? <Loader /> : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {logs.map((log: AuditLogItem) => (
            <Glass key={log.id} style={{ padding: "10px 16px", display: "flex", alignItems: "center", gap: 16 }}>
              <div style={{ minWidth: 170, fontSize: 11, color: "var(--color-text-muted)" }}>
                {new Date(log.created_at).toLocaleString()}
              </div>
              <div style={{ flex: 1 }}>
                <span style={{ fontWeight: 600, color: "var(--color-primary)", fontSize: 13 }}>{log.action}</span>
                <span style={{ color: "var(--color-text-muted)", fontSize: 12, marginLeft: 8 }}>on {log.target_type}</span>
              </div>
              {log.workspace_id && <div style={{ fontSize: 11, color: "var(--color-text-subtle)" }}>{log.workspace_id.slice(0, 8)}…</div>}
            </Glass>
          ))}
          {logs.length === 0 && <Empty message="No audit events found." />}
        </div>
      )}
    </div>
  );
}

/* ─── Helpers ────────────────────────────────────────────────────────── */
const Loader = () => (
  <div style={{ textAlign: "center", padding: 48, color: "var(--color-text-muted)" }}>
    <div style={{ fontSize: 24, animation: "spin 1s linear infinite", display: "inline-block" }}>⟳</div>
    <p style={{ marginTop: 8 }}>Loading…</p>
  </div>
);

const Empty: React.FC<{ message: string }> = ({ message }) => (
  <div style={{ textAlign: "center", padding: 48, color: "var(--color-text-muted)" }}>
    <div style={{ fontSize: 32, marginBottom: 8 }}>📭</div>
    <p>{message}</p>
  </div>
);

/* ─── Main Page ──────────────────────────────────────────────────────── */
export default function AccountConsolePage() {
  const { data: me, isLoading } = useMe();
  const [activeTab, setActiveTab] = useState<Tab>("Users");
  const navigate = useNavigate();

  const handleLogout = () => {
    clearSession();
    navigate("/login");
  };

  const isAccountAdmin = me?.account_role === "account_admin" || me?.is_account_admin;

  if (isLoading) {
    return <div style={{ textAlign: "center", padding: 64, color: "var(--color-text-muted)" }}>Loading console…</div>;
  }

  if (me && !isAccountAdmin) {
    return (
      <div style={{ minHeight: "100vh", background: "var(--color-bg)", color: "var(--color-text)", display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
        <Glass style={{ padding: 32, maxWidth: 440, textAlign: "center" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: 18, color: "var(--color-danger)" }}>Access Restricted</h2>
          <p style={{ color: "var(--color-text-muted)", fontSize: 14, marginBottom: 20 }}>
            Account Admin privileges are required to access the Account Console.
          </p>
          <button className="btn-primary" onClick={() => navigate("/")}>Return to Application</button>
        </Glass>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--color-bg)", color: "var(--color-text)", fontFamily: "var(--font-family)" }}>
      {/* Header */}
      <div style={{ borderBottom: "1px solid var(--color-border)", padding: "0 32px",
        display: "flex", alignItems: "center", justifyContent: "space-between", height: 56, background: "var(--color-surface)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <CompassXLogo size={26} color="var(--color-primary, #1B6EF3)" />
          <span style={{ fontWeight: 700, fontSize: 16, color: "var(--color-text)" }}>
            Compass<span style={{ color: "var(--color-primary, #1B6EF3)" }}>X</span>
          </span>
          <span style={{ color: "var(--color-border)", margin: "0 4px" }}>›</span>
          <span style={{ color: "var(--color-text-muted)", fontSize: 14 }}>Account Console</span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn-outline" onClick={() => navigate("/")}>← App</button>
          <button className="btn-outline" onClick={handleLogout}>Logout</button>
        </div>
      </div>

      <div style={{ padding: "32px", maxWidth: 1200, margin: "0 auto" }}>
        {/* Page title */}
        <div style={{ marginBottom: 24 }}>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: "var(--color-text)" }}>Account Console</h1>
          <p style={{ margin: "4px 0 0", color: "var(--color-text-muted)", fontSize: 14 }}>
            Manage users, invites, groups, workspaces, and audit activity.
          </p>
        </div>

        {/* Tabs */}
        <div style={{ display: "flex", gap: 2, borderBottom: "1px solid var(--color-border)", marginBottom: 24 }}>
          {TABS.map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)} style={{
              background: "none", border: "none", cursor: "pointer",
              padding: "10px 20px", fontSize: 14, fontWeight: activeTab === tab ? 600 : 400,
              color: activeTab === tab ? "var(--color-primary)" : "var(--color-text-muted)",
              borderBottom: `2px solid ${activeTab === tab ? "var(--color-primary)" : "transparent"}`,
              transition: "all 0.15s", marginBottom: -1,
            }}>{tab}</button>
          ))}
        </div>

        {/* Tab content */}
        {activeTab === "Users"      && <UsersTab />}
        {activeTab === "Invites"    && <InvitesTab />}
        {activeTab === "Groups"     && <GroupsTab />}
        {activeTab === "Workspaces" && <WorkspacesTab />}
        {activeTab === "Audit Log"  && <AuditLogTab />}
      </div>
    </div>
  );
}
