import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  useMe, useWorkspaceMembers, useInviteToWorkspace, useCreateWorkspaceUser,
  useUpdateMemberRole, useRemoveWorkspaceMember,
  type WorkspaceMemberOut,
} from "../../lib/userManagerApi";

const WORKSPACE_ROLES = ["workspace_admin", "analyst", "business_viewer"];

const Glass: React.FC<React.PropsWithChildren<{ style?: React.CSSProperties }>> =
  ({ children, style }) => (
    <div className="glass" style={{
      background: "var(--color-surface)", border: "1px solid var(--color-border)",
      borderRadius: "var(--radius-lg)", ...style,
    }}>{children}</div>
  );

export default function WorkspaceMembersPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const navigate = useNavigate();

  const { data: me } = useMe();
  const { data: members = [], isLoading } = useWorkspaceMembers(workspaceId!);
  const invite      = useInviteToWorkspace(workspaceId!);
  const createUser  = useCreateWorkspaceUser(workspaceId!);
  const updateRole  = useUpdateMemberRole(workspaceId!);
  const remove      = useRemoveWorkspaceMember(workspaceId!);

  const [showInvite, setShowInvite] = useState(false);
  const [addMode, setAddMode] = useState<"invite" | "create">("invite");

  // Permission checks
  const isAccountAdmin = me?.account_role === "account_admin" || me?.is_account_admin;
  const currentMember = members.find(m => m.user_id === me?.id);
  const isWsAdmin = Boolean(isAccountAdmin || currentMember?.role_id === "workspace_admin");

  // Invite / existing user form state
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("analyst");

  // Create user form state
  const [createEmail, setCreateEmail] = useState("");
  const [createDisplayName, setCreateDisplayName] = useState("");
  const [createPassword, setCreatePassword] = useState("");
  const [createRole, setCreateRole] = useState("analyst");

  const [editingRole, setEditingRole] = useState<string | null>(null);
  const [roleMap, setRoleMap] = useState<Record<string, string>>({});
  const [inviteResult, setInviteResult] = useState<{ url?: string; type?: string; message?: string } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const handleInvite = async () => {
    if (!inviteEmail.trim()) return;
    setFormError(null);
    try {
      const result = await invite.mutateAsync({ emailOrUserId: inviteEmail.trim(), roleId: inviteRole });
      setInviteResult(result);
      setInviteEmail("");
      setShowInvite(false);
    } catch (err: any) {
      setFormError(err.response?.data?.detail || err.message || "Failed to add member");
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (!createEmail.trim() || !createDisplayName.trim() || !createPassword) return;
    if (createPassword.length < 8) {
      setFormError("Password must be at least 8 characters");
      return;
    }

    try {
      await createUser.mutateAsync({
        email: createEmail.trim(),
        display_name: createDisplayName.trim(),
        password: createPassword,
        role_id: createRole,
      });
      setInviteResult({ type: "created", message: `✓ User ${createEmail.trim()} created and added to workspace` });
      setCreateEmail("");
      setCreateDisplayName("");
      setCreatePassword("");
      setCreateRole("analyst");
      setShowInvite(false);
    } catch (err: any) {
      setFormError(err.response?.data?.detail || err.message || "Failed to create user");
    }
  };

  const handleRoleUpdate = async (userId: string) => {
    await updateRole.mutateAsync({ userId, roleId: roleMap[userId] });
    setEditingRole(null);
  };

  const tableHeaders = isWsAdmin ? ["Member", "Type", "Role", "Actions"] : ["Member", "Type", "Role"];

  return (
    <div style={{ minHeight: "100vh", background: "var(--color-bg)", color: "var(--color-text)",
      fontFamily: "var(--font-family)", padding: 0 }}>

      {/* Header */}
      <div style={{ borderBottom: "1px solid var(--color-border)", padding: "0 32px",
        display: "flex", alignItems: "center", justifyContent: "space-between", height: 56, background: "var(--color-surface)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button onClick={() => navigate(-1)}
            style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer", fontSize: 18 }}>←</button>
          <span style={{ fontWeight: 700, fontSize: 16 }}>Workspace Members</span>
          {workspaceId && <span style={{ fontSize: 12, color: "var(--color-text-subtle)" }}>{workspaceId.slice(0, 8)}…</span>}
        </div>
        {isWsAdmin && (
          <button className="btn-primary" onClick={() => { setShowInvite(s => !s); setFormError(null); }}>+ Add Member</button>
        )}
      </div>

      <div style={{ padding: "32px", maxWidth: 1200, margin: "0 auto" }}>
        {/* Result notification */}
        {inviteResult && (
          <Glass style={{ padding: "14px 20px", marginBottom: 20, borderColor: "var(--color-primary)" }}>
            {inviteResult.type === "invited" ? (
              <div>
                <span style={{ color: "var(--color-primary)", fontWeight: 600 }}>✓ Invite created!</span>
                {inviteResult.url && (
                  <div style={{ marginTop: 6, display: "flex", gap: 8, alignItems: "center" }}>
                    <code style={{ fontSize: 12, color: "var(--color-text-muted)", wordBreak: "break-all" }}>{inviteResult.url}</code>
                    <button onClick={() => navigator.clipboard.writeText(inviteResult.url!)}
                      style={{ background: "none", border: "none", color: "var(--color-primary)", cursor: "pointer", fontSize: 12, whiteSpace: "nowrap" }}>
                      Copy Link
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <span style={{ color: "var(--color-success)", fontWeight: 600 }}>
                {inviteResult.message || "✓ User added to workspace"}
              </span>
            )}
            <button onClick={() => setInviteResult(null)}
              style={{ float: "right", background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer" }}>✕</button>
          </Glass>
        )}

        {/* Add / Create form — Workspace Admin Only */}
        {isWsAdmin && showInvite && (
          <Glass style={{ padding: 20, marginBottom: 24 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div style={{ display: "flex", gap: 6 }}>
                <button
                  type="button"
                  className={addMode === "invite" ? "btn-primary" : "btn-outline"}
                  style={{ fontSize: 12, padding: "4px 12px" }}
                  onClick={() => { setAddMode("invite"); setFormError(null); }}
                >
                  Invite / Add Existing
                </button>
                <button
                  type="button"
                  className={addMode === "create" ? "btn-primary" : "btn-outline"}
                  style={{ fontSize: 12, padding: "4px 12px" }}
                  onClick={() => { setAddMode("create"); setFormError(null); }}
                >
                  Directly Create User
                </button>
              </div>
              <button onClick={() => setShowInvite(false)} style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer" }}>✕</button>
            </div>

            {formError && (
              <div style={{ padding: "8px 12px", background: "var(--color-danger-bg)", color: "var(--color-danger)",
                borderRadius: "var(--radius)", fontSize: 13, marginBottom: 16 }}>
                {formError}
              </div>
            )}

            {addMode === "invite" ? (
              <div style={{ display: "grid", gridTemplateColumns: "1fr auto auto", gap: 10, alignItems: "end" }}>
                <div>
                  <label className="label">Email or User ID</label>
                  <input className="input-field" value={inviteEmail}
                    onChange={e => setInviteEmail(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && handleInvite()} />
                </div>
                <div>
                  <label className="label">Role</label>
                  <select className="input-field" value={inviteRole} onChange={e => setInviteRole(e.target.value)}>
                    {WORKSPACE_ROLES.map(r => <option key={r} value={r}>{r.replace(/_/g, " ")}</option>)}
                  </select>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button className="btn-primary" onClick={handleInvite} disabled={invite.isPending}>
                    {invite.isPending ? "Adding…" : "Add"}
                  </button>
                  <button className="btn-outline" onClick={() => setShowInvite(false)}>Cancel</button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleCreateUser}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
                  <div>
                    <label className="label">Email Address</label>
                    <input required className="input-field" type="email" value={createEmail}
                      onChange={e => setCreateEmail(e.target.value)} />
                  </div>
                  <div>
                    <label className="label">Display Name</label>
                    <input required className="input-field" type="text" value={createDisplayName}
                      onChange={e => setCreateDisplayName(e.target.value)} />
                  </div>
                  <div>
                    <label className="label">Initial Password</label>
                    <input required className="input-field" type="password" value={createPassword}
                      onChange={e => setCreatePassword(e.target.value)} />
                  </div>
                  <div>
                    <label className="label">Workspace Role</label>
                    <select className="input-field" value={createRole} onChange={e => setCreateRole(e.target.value)}>
                      {WORKSPACE_ROLES.map(r => <option key={r} value={r}>{r.replace(/_/g, " ")}</option>)}
                    </select>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button type="submit" className="btn-primary" disabled={createUser.isPending}>
                    {createUser.isPending ? "Creating…" : "Create & Add User"}
                  </button>
                  <button type="button" className="btn-outline" onClick={() => setShowInvite(false)}>Cancel</button>
                </div>
              </form>
            )}
          </Glass>
        )}

        {/* Members table */}
        {isLoading ? (
          <div style={{ textAlign: "center", padding: 48, color: "var(--color-text-muted)" }}>Loading members…</div>
        ) : (
          <Glass style={{ overflow: "hidden" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--color-border)" }}>
                  {tableHeaders.map(h => (
                    <th key={h} style={{ textAlign: "left", padding: "12px 20px", fontSize: 11,
                      fontWeight: 700, color: "var(--color-text-muted)", letterSpacing: "0.08em", textTransform: "uppercase" as const }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {members.map((m: WorkspaceMemberOut) => (
                  <tr key={m.assignment_id} style={{ borderBottom: "1px solid var(--color-border)" }}>
                    <td style={{ padding: "14px 20px" }}>
                      <div style={{ fontWeight: 600, color: "var(--color-text)" }}>{m.display_name || m.email || m.user_id?.slice(0, 8)}</div>
                      {m.email && <div style={{ fontSize: 12, color: "var(--color-text-muted)" }}>{m.email}</div>}
                    </td>
                    <td style={{ padding: "14px 20px" }}>
                      <span style={{ fontSize: 12, color: "var(--color-text-muted)" }}>{m.principal_type}</span>
                    </td>
                    <td style={{ padding: "14px 20px" }}>
                      {isWsAdmin && editingRole === m.assignment_id ? (
                        <div style={{ display: "flex", gap: 6 }}>
                          <select className="input-field" style={{ width: "auto" }}
                            value={roleMap[m.assignment_id] || m.role_id}
                            onChange={e => setRoleMap(r => ({ ...r, [m.assignment_id]: e.target.value }))}>
                            {WORKSPACE_ROLES.map(r => <option key={r} value={r}>{r.replace(/_/g, " ")}</option>)}
                          </select>
                          <button className="btn-primary" style={{ padding: "4px 10px", fontSize: 12 }}
                            onClick={() => handleRoleUpdate(m.user_id!)}>Save</button>
                          <button className="btn-outline" style={{ padding: "4px 8px", fontSize: 12 }}
                            onClick={() => setEditingRole(null)}>✕</button>
                        </div>
                      ) : (
                        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                          <span style={{
                            display: "inline-block", padding: "3px 10px", borderRadius: 999,
                            fontSize: 11, fontWeight: 600, background: "var(--color-primary-bg)",
                            color: "var(--color-primary)", border: "1px solid var(--color-primary)",
                          }}>{m.role_id.replace(/_/g, " ")}</span>
                          {m.is_default && <span style={{ fontSize: 10, color: "var(--color-warning)" }}>★ default</span>}
                          {isWsAdmin && m.user_id && (
                            <button onClick={() => { setEditingRole(m.assignment_id); setRoleMap(r => ({ ...r, [m.assignment_id]: m.role_id })); }}
                              style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer", fontSize: 12 }}>✎</button>
                          )}
                        </div>
                      )}
                    </td>
                    {isWsAdmin && (
                      <td style={{ padding: "14px 20px" }}>
                        {m.user_id && (
                          <button className="btn-danger" style={{ fontSize: 12, padding: "4px 10px" }}
                            onClick={() => remove.mutate(m.user_id!)}>Remove</button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
            {members.length === 0 && (
              <div style={{ textAlign: "center", padding: 48, color: "var(--color-text-muted)" }}>
                <p>No members in this workspace.</p>
              </div>
            )}
          </Glass>
        )}
      </div>
    </div>
  );
}
