import React, { useState, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  User, Users, Bot, Shield, Search, ArrowLeft, Plus, Check, Trash2, Edit3, X, Copy, Mail, Key
} from "lucide-react";
import {
  useMe,
  useWorkspaceMembers,
  useCandidatePrincipals,
  useAssignWorkspacePrincipal,
  useInviteToWorkspace,
  useCreateWorkspaceUser,
  useUpdateMemberRole,
  useRemoveWorkspaceMember,
  type WorkspaceMemberOut,
  type CandidatePrincipalOut,
} from "../../lib/userManagerApi";

const WORKSPACE_ROLES = [
  { id: "workspace_admin", label: "Workspace Admin", desc: "Full administrative control over this workspace" },
  { id: "analyst", label: "Analyst", desc: "Can develop, execute notebooks, create jobs & queries" },
  { id: "business_viewer", label: "Business Viewer", desc: "View-only access to published dashboards & assets" },
];

const Glass: React.FC<React.PropsWithChildren<{ className?: string; style?: React.CSSProperties; onClick?: () => void }>> =
  ({ children, className = "", style, onClick }) => (
    <div
      className={`glass ${className}`}
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-lg, 10px)",
        ...style,
      }}
      onClick={onClick}
    >
      {children}
    </div>
  );

type FilterType = "all" | "user" | "group" | "service_principal";
type AddModalTab = "directory" | "create" | "invite";

export default function WorkspaceMembersPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const navigate = useNavigate();

  const { data: me } = useMe();
  const { data: members = [], isLoading } = useWorkspaceMembers(workspaceId!);
  const { data: candidates = [] } = useCandidatePrincipals(workspaceId!);

  const assignPrincipal = useAssignWorkspacePrincipal(workspaceId!);
  const invite = useInviteToWorkspace(workspaceId!);
  const createUser = useCreateWorkspaceUser(workspaceId!);
  const updateRole = useUpdateMemberRole(workspaceId!);
  const remove = useRemoveWorkspaceMember(workspaceId!);

  const [activeFilter, setActiveFilter] = useState<FilterType>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [showAddModal, setShowAddModal] = useState(false);
  const [modalTab, setModalTab] = useState<AddModalTab>("directory");

  // Assignment from directory state
  const [selectedPrincipal, setSelectedPrincipal] = useState<CandidatePrincipalOut | null>(null);
  const [assignRole, setAssignRole] = useState("analyst");
  const [directorySearch, setDirectorySearch] = useState("");

  // Create user state
  const [createEmail, setCreateEmail] = useState("");
  const [createDisplayName, setCreateDisplayName] = useState("");
  const [createPassword, setCreatePassword] = useState("");
  const [createRole, setCreateRole] = useState("analyst");

  // Invite state
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("analyst");

  // Edit role inline state
  const [editingAssignmentId, setEditingAssignmentId] = useState<string | null>(null);
  const [roleMap, setRoleMap] = useState<Record<string, string>>({});

  const [notification, setNotification] = useState<{ type: "success" | "info"; message: string; url?: string } | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  // Permission checks
  const isAccountAdmin = Boolean(me?.account_role === "account_admin" || me?.is_account_admin);
  const currentMember = members.find((m) => m.principal_id === me?.id || m.user_id === me?.id);
  const isWsAdmin = Boolean(isAccountAdmin || currentMember?.role_id === "workspace_admin");

  // Counts
  const counts = useMemo(() => {
    return {
      all: members.length,
      user: members.filter((m) => m.principal_type === "user").length,
      group: members.filter((m) => m.principal_type === "group").length,
      service_principal: members.filter((m) => m.principal_type === "service_principal").length,
    };
  }, [members]);

  // Filtered members
  const filteredMembers = useMemo(() => {
    return members.filter((m) => {
      if (activeFilter !== "all" && m.principal_type !== activeFilter) return false;
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      return (
        m.display_name?.toLowerCase().includes(q) ||
        m.email?.toLowerCase().includes(q) ||
        m.client_id?.toLowerCase().includes(q) ||
        m.role_id.toLowerCase().includes(q)
      );
    });
  }, [members, activeFilter, searchQuery]);

  // Filtered candidates for directory search
  const filteredCandidates = useMemo(() => {
    if (!directorySearch.trim()) return candidates;
    const q = directorySearch.toLowerCase();
    return candidates.filter(
      (c) =>
        c.display_name.toLowerCase().includes(q) ||
        c.email_or_client_id?.toLowerCase().includes(q) ||
        c.type.toLowerCase().includes(q)
    );
  }, [candidates, directorySearch]);

  const handleAssignDirectoryPrincipal = async () => {
    if (!selectedPrincipal || !workspaceId) return;
    setFormError(null);
    try {
      await assignPrincipal.mutateAsync({
        principal_id: selectedPrincipal.id,
        principal_type: selectedPrincipal.type,
        role_id: assignRole,
      });
      setNotification({
        type: "success",
        message: `✓ Assigned ${selectedPrincipal.display_name} (${selectedPrincipal.type.replace("_", " ")}) to workspace`,
      });
      setSelectedPrincipal(null);
      setDirectorySearch("");
      setShowAddModal(false);
    } catch (err: any) {
      setFormError(err.response?.data?.detail || err.message || "Failed to assign principal");
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
      setNotification({
        type: "success",
        message: `✓ Created user ${createEmail.trim()} and granted workspace access`,
      });
      setCreateEmail("");
      setCreateDisplayName("");
      setCreatePassword("");
      setShowAddModal(false);
    } catch (err: any) {
      setFormError(err.response?.data?.detail || err.message || "Failed to create user");
    }
  };

  const handleInvite = async () => {
    if (!inviteEmail.trim() || !workspaceId) return;
    setFormError(null);
    try {
      const res = await invite.mutateAsync({
        emailOrUserId: inviteEmail.trim(),
        roleId: inviteRole,
      });
      if (res.type === "invited") {
        setNotification({
          type: "info",
          message: `✓ Invitation link generated for ${inviteEmail.trim()}`,
          url: res.invite_url,
        });
      } else {
        setNotification({
          type: "success",
          message: `✓ Added ${inviteEmail.trim()} directly to workspace`,
        });
      }
      setInviteEmail("");
      setShowAddModal(false);
    } catch (err: any) {
      setFormError(err.response?.data?.detail || err.message || "Failed to send invite");
    }
  };

  const handleRoleUpdate = async (principalId: string, assignmentId: string) => {
    const nextRole = roleMap[assignmentId];
    if (nextRole && workspaceId) {
      await updateRole.mutateAsync({ principalId, roleId: nextRole });
    }
    setEditingAssignmentId(null);
  };

  const getPrincipalIcon = (type: string) => {
    switch (type) {
      case "user":
        return <User size={15} style={{ color: "var(--color-primary, #1B6EF3)" }} />;
      case "group":
        return <Users size={15} style={{ color: "var(--color-text-muted)" }} />;
      case "service_principal":
        return <Bot size={15} style={{ color: "var(--color-text-muted)" }} />;
      default:
        return <Shield size={15} />;
    }
  };

  return (
    <div style={{ minHeight: "100vh", background: "var(--color-bg)", color: "var(--color-text)" }}>
      {/* Top Header */}
      <div
        style={{
          borderBottom: "1px solid var(--color-border)",
          padding: "0 28px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          height: 56,
          background: "var(--color-surface)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button
            onClick={() => navigate(-1)}
            style={{
              background: "none",
              border: "none",
              color: "var(--color-text-muted)",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 4,
              fontSize: "0.86rem",
            }}
          >
            <ArrowLeft size={16} />
            <span>Back</span>
          </button>
          <div style={{ height: 18, width: 1, background: "var(--color-border)" }} />
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontWeight: 700, fontSize: 16 }}>Workspace Permissions & Identity</span>
            {workspaceId && (
              <span
                style={{
                  fontSize: 11,
                  padding: "2px 8px",
                  borderRadius: 6,
                  background: "var(--color-surface-hover, rgba(255,255,255,0.05))",
                  border: "1px solid var(--color-border)",
                  color: "var(--color-text-muted)",
                }}
              >
                WS: {workspaceId.slice(0, 8)}…
              </span>
            )}
          </div>
        </div>

        {isWsAdmin && (
          <button
            className="btn-primary"
            onClick={() => {
              setShowAddModal(true);
              setFormError(null);
            }}
            style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.84rem", padding: "6px 14px" }}
          >
            <Plus size={15} />
            <span>Assign to Workspace</span>
          </button>
        )}
      </div>

      <div style={{ padding: "28px", maxWidth: 1200, margin: "0 auto" }}>
        {/* Notification Alert */}
        {notification && (
          <Glass
            style={{
              padding: "12px 18px",
              marginBottom: 20,
              borderColor: "var(--color-primary, #1B6EF3)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <Check size={16} style={{ color: "var(--color-primary, #1B6EF3)" }} />
              <div>
                <span style={{ fontWeight: 600, fontSize: "0.86rem" }}>{notification.message}</span>
                {notification.url && (
                  <div style={{ marginTop: 4, display: "flex", gap: 8, alignItems: "center" }}>
                    <code style={{ fontSize: 12, color: "var(--color-text-muted)" }}>{notification.url}</code>
                    <button
                      onClick={() => navigator.clipboard.writeText(notification.url!)}
                      style={{
                        background: "none",
                        border: "none",
                        color: "var(--color-primary)",
                        cursor: "pointer",
                        fontSize: 12,
                        display: "flex",
                        alignItems: "center",
                        gap: 4,
                      }}
                    >
                      <Copy size={12} />
                      <span>Copy</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
            <button
              onClick={() => setNotification(null)}
              style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer" }}
            >
              <X size={14} />
            </button>
          </Glass>
        )}

        {/* Toolbar: Tabs & Search */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 16,
            marginBottom: 20,
            flexWrap: "wrap",
          }}
        >
          {/* Filter Pills */}
          <div style={{ display: "flex", gap: 6 }}>
            {(
              [
                { id: "all", label: "All Identities", count: counts.all },
                { id: "user", label: "Users", count: counts.user },
                { id: "group", label: "Groups", count: counts.group },
                { id: "service_principal", label: "Service Principals", count: counts.service_principal },
              ] as const
            ).map((tab) => {
              const isActive = activeFilter === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveFilter(tab.id)}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "6px 12px",
                    borderRadius: 8,
                    fontSize: "0.82rem",
                    fontWeight: isActive ? 600 : 500,
                    border: isActive ? "1px solid var(--color-primary, #1B6EF3)" : "1px solid var(--color-border)",
                    background: isActive ? "rgba(27, 110, 243, 0.08)" : "transparent",
                    color: isActive ? "var(--color-primary, #1B6EF3)" : "var(--color-text-muted)",
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                >
                  <span>{tab.label}</span>
                  <span
                    style={{
                      fontSize: 11,
                      padding: "1px 6px",
                      borderRadius: 999,
                      background: isActive ? "rgba(27, 110, 243, 0.2)" : "rgba(255,255,255,0.06)",
                    }}
                  >
                    {tab.count}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Search bar */}
          <div style={{ position: "relative", minWidth: 260 }}>
            <Search
              size={14}
              style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", opacity: 0.5 }}
            />
            <input
              type="text"
              className="input-field"
              placeholder="Search by name, email, or role…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ paddingLeft: 32, height: 34, fontSize: "0.82rem" }}
            />
          </div>
        </div>

        {/* Members Table */}
        {isLoading ? (
          <div style={{ textAlign: "center", padding: 60, color: "var(--color-text-muted)" }}>
            <div style={{ fontSize: 24, animation: "spin 1s linear infinite", display: "inline-block" }}>⟳</div>
            <p style={{ marginTop: 8 }}>Loading workspace identities…</p>
          </div>
        ) : (
          <Glass style={{ overflow: "hidden" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--color-border)", background: "rgba(255,255,255,0.02)" }}>
                  <th
                    style={{
                      textAlign: "left",
                      padding: "12px 20px",
                      fontSize: 11,
                      fontWeight: 700,
                      color: "var(--color-text-muted)",
                      letterSpacing: "0.06em",
                      textTransform: "uppercase",
                    }}
                  >
                    Identity
                  </th>
                  <th
                    style={{
                      textAlign: "left",
                      padding: "12px 20px",
                      fontSize: 11,
                      fontWeight: 700,
                      color: "var(--color-text-muted)",
                      letterSpacing: "0.06em",
                      textTransform: "uppercase",
                    }}
                  >
                    Type
                  </th>
                  <th
                    style={{
                      textAlign: "left",
                      padding: "12px 20px",
                      fontSize: 11,
                      fontWeight: 700,
                      color: "var(--color-text-muted)",
                      letterSpacing: "0.06em",
                      textTransform: "uppercase",
                    }}
                  >
                    Workspace Role
                  </th>
                  <th
                    style={{
                      textAlign: "left",
                      padding: "12px 20px",
                      fontSize: 11,
                      fontWeight: 700,
                      color: "var(--color-text-muted)",
                      letterSpacing: "0.06em",
                      textTransform: "uppercase",
                    }}
                  >
                    Granted
                  </th>
                  {isWsAdmin && (
                    <th
                      style={{
                        textAlign: "right",
                        padding: "12px 20px",
                        fontSize: 11,
                        fontWeight: 700,
                        color: "var(--color-text-muted)",
                        letterSpacing: "0.06em",
                        textTransform: "uppercase",
                      }}
                    >
                      Actions
                    </th>
                  )}
                </tr>
              </thead>
              <tbody>
                {filteredMembers.map((m: WorkspaceMemberOut) => {
                  const isEditing = editingAssignmentId === m.assignment_id;
                  return (
                    <tr
                      key={m.assignment_id}
                      style={{ borderBottom: "1px solid var(--color-border)", transition: "background 0.12s ease" }}
                    >
                      {/* Identity */}
                      <td style={{ padding: "14px 20px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <div
                            style={{
                              width: 32,
                              height: 32,
                              borderRadius: "50%",
                              background: "rgba(255,255,255,0.06)",
                              border: "1px solid var(--color-border)",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              flexShrink: 0,
                            }}
                          >
                            {getPrincipalIcon(m.principal_type)}
                          </div>
                          <div style={{ minWidth: 0, overflow: "hidden" }}>
                            <div style={{ fontWeight: 600, color: "var(--color-text)", fontSize: "0.88rem" }}>
                              {m.display_name || m.email || m.principal_id.slice(0, 8)}
                            </div>
                            {m.email && m.display_name && (
                              <div style={{ fontSize: 12, color: "var(--color-text-muted)" }}>{m.email}</div>
                            )}
                            {m.client_id && (
                              <div style={{ fontSize: 11, color: "var(--color-text-muted)", fontFamily: "monospace" }}>
                                OAuth ID: {m.client_id}
                              </div>
                            )}
                            {m.principal_type === "group" && m.member_count !== undefined && (
                              <div style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                                {m.member_count} direct member{m.member_count !== 1 ? "s" : ""}
                              </div>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Type */}
                      <td style={{ padding: "14px 20px" }}>
                        <span
                          style={{
                            display: "inline-block",
                            padding: "2px 8px",
                            borderRadius: 6,
                            fontSize: 11,
                            fontWeight: 600,
                            background: "rgba(255,255,255,0.06)",
                            border: "1px solid var(--color-border)",
                            color: "var(--color-text-muted)",
                            textTransform: "uppercase",
                            letterSpacing: "0.04em",
                          }}
                        >
                          {m.principal_type.replace("_", " ")}
                        </span>
                      </td>

                      {/* Role */}
                      <td style={{ padding: "14px 20px" }}>
                        {isWsAdmin && isEditing ? (
                          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                            <select
                              className="input-field"
                              style={{ width: "auto", height: 30, fontSize: "0.8rem", padding: "2px 8px" }}
                              value={roleMap[m.assignment_id] || m.role_id}
                              onChange={(e) =>
                                setRoleMap((r) => ({ ...r, [m.assignment_id]: e.target.value }))
                              }
                            >
                              {WORKSPACE_ROLES.map((r) => (
                                <option key={r.id} value={r.id}>
                                  {r.label}
                                </option>
                              ))}
                            </select>
                            <button
                              className="btn-primary"
                              style={{ padding: "4px 8px", fontSize: 11, height: 30 }}
                              onClick={() => handleRoleUpdate(m.principal_id, m.assignment_id)}
                            >
                              Save
                            </button>
                            <button
                              className="btn-outline"
                              style={{ padding: "4px 8px", fontSize: 11, height: 30 }}
                              onClick={() => setEditingAssignmentId(null)}
                            >
                              ✕
                            </button>
                          </div>
                        ) : (
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <span
                              style={{
                                display: "inline-block",
                                padding: "3px 10px",
                                borderRadius: 999,
                                fontSize: 11,
                                fontWeight: 600,
                                background:
                                  m.role_id === "workspace_admin"
                                    ? "var(--color-success-bg, rgba(34, 197, 94, 0.1))"
                                    : "var(--color-primary-bg, rgba(27, 110, 243, 0.08))",
                                color:
                                  m.role_id === "workspace_admin"
                                    ? "var(--color-success, #22c55e)"
                                    : "var(--color-primary, #1B6EF3)",
                                border:
                                  m.role_id === "workspace_admin"
                                    ? "1px solid var(--color-success, #22c55e)"
                                    : "1px solid var(--color-primary, #1B6EF3)",
                              }}
                            >
                              {m.role_id.replace(/_/g, " ").toUpperCase()}
                            </span>
                            {m.is_default && (
                              <span style={{ fontSize: 10, color: "var(--color-warning, #f59e0b)" }}>★ Default</span>
                            )}
                            {isWsAdmin && (
                              <button
                                onClick={() => {
                                  setEditingAssignmentId(m.assignment_id);
                                  setRoleMap((r) => ({ ...r, [m.assignment_id]: m.role_id }));
                                }}
                                style={{
                                  background: "none",
                                  border: "none",
                                  color: "var(--color-text-muted)",
                                  cursor: "pointer",
                                  padding: 2,
                                  opacity: 0.7,
                                }}
                                title="Change role"
                              >
                                <Edit3 size={13} />
                              </button>
                            )}
                          </div>
                        )}
                      </td>

                      {/* Granted date */}
                      <td style={{ padding: "14px 20px", fontSize: 12, color: "var(--color-text-muted)" }}>
                        {new Date(m.granted_at).toLocaleDateString()}
                      </td>

                      {/* Actions */}
                      {isWsAdmin && (
                        <td style={{ padding: "14px 20px", textAlign: "right" }}>
                          <button
                            className="btn-danger"
                            style={{
                              fontSize: 12,
                              padding: "4px 8px",
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 4,
                            }}
                            onClick={() => remove.mutate(m.principal_id)}
                            title="Revoke workspace access"
                          >
                            <Trash2 size={12} />
                            <span>Remove</span>
                          </button>
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {filteredMembers.length === 0 && (
              <div style={{ textAlign: "center", padding: 48, color: "var(--color-text-muted)" }}>
                <p>No identities found matching the filter.</p>
              </div>
            )}
          </Glass>
        )}
      </div>

      {/* Databricks-Style "Add / Assign to Workspace" Modal */}
      {showAddModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 9999,
            backdropFilter: "blur(4px)",
          }}
        >
          <Glass style={{ width: 560, maxHeight: "90vh", overflow: "hidden", display: "flex", flexDirection: "column" }}>
            {/* Modal Header */}
            <div
              style={{
                padding: "16px 20px",
                borderBottom: "1px solid var(--color-border)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <div style={{ fontWeight: 700, fontSize: 16 }}>Grant Workspace Access</div>
              <button
                onClick={() => setShowAddModal(false)}
                style={{ background: "none", border: "none", color: "var(--color-text-muted)", cursor: "pointer" }}
              >
                <X size={16} />
              </button>
            </div>

            {/* Modal Navigation Tabs */}
            <div
              style={{
                display: "flex",
                borderBottom: "1px solid var(--color-border)",
                padding: "0 20px",
                background: "rgba(255,255,255,0.02)",
              }}
            >
              {[
                { id: "directory", label: "Select from Account Directory", icon: Users },
                { id: "create", label: "Directly Provision User", icon: User },
                { id: "invite", label: "Invite by Email", icon: Mail },
              ].map((tab) => {
                const isActive = modalTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => {
                      setModalTab(tab.id as AddModalTab);
                      setFormError(null);
                    }}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      padding: "10px 14px",
                      fontSize: "0.82rem",
                      fontWeight: isActive ? 600 : 500,
                      border: "none",
                      borderBottom: isActive ? "2px solid var(--color-primary, #1B6EF3)" : "2px solid transparent",
                      background: "transparent",
                      color: isActive ? "var(--color-primary, #1B6EF3)" : "var(--color-text-muted)",
                      cursor: "pointer",
                    }}
                  >
                    <tab.icon size={13} />
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Modal Body */}
            <div style={{ padding: 20, overflowY: "auto", flex: 1 }}>
              {formError && (
                <div
                  style={{
                    padding: "8px 12px",
                    background: "var(--color-danger-bg, rgba(239, 68, 68, 0.1))",
                    color: "var(--color-danger, #ef4444)",
                    borderRadius: 6,
                    fontSize: 13,
                    marginBottom: 16,
                  }}
                >
                  {formError}
                </div>
              )}

              {/* Mode 1: Assign from Account Directory */}
              {modalTab === "directory" && (
                <div>
                  <label className="label" style={{ marginBottom: 6, display: "block" }}>
                    Select Account User, Group, or Service Principal
                  </label>
                  <div style={{ position: "relative", marginBottom: 12 }}>
                    <Search
                      size={14}
                      style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", opacity: 0.5 }}
                    />
                    <input
                      type="text"
                      className="input-field"
                      placeholder="Search account directory…"
                      value={directorySearch}
                      onChange={(e) => setDirectorySearch(e.target.value)}
                      style={{ paddingLeft: 32, fontSize: "0.84rem" }}
                    />
                  </div>

                  {/* Candidate List Box */}
                  <div
                    style={{
                      maxHeight: 180,
                      overflowY: "auto",
                      border: "1px solid var(--color-border)",
                      borderRadius: 8,
                      marginBottom: 16,
                      background: "var(--color-surface)",
                    }}
                  >
                    {filteredCandidates.map((c: CandidatePrincipalOut) => {
                      const isSelected = selectedPrincipal?.id === c.id;
                      return (
                        <div
                          key={c.id}
                          onClick={() => setSelectedPrincipal(c)}
                          style={{
                            padding: "8px 12px",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            borderBottom: "1px solid var(--color-border)",
                            background: isSelected ? "rgba(27, 110, 243, 0.1)" : "transparent",
                            cursor: "pointer",
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            {getPrincipalIcon(c.type)}
                            <div>
                              <div style={{ fontWeight: isSelected ? 600 : 400, fontSize: "0.84rem" }}>
                                {c.display_name}
                              </div>
                              <div style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                                {c.details || c.email_or_client_id}
                              </div>
                            </div>
                          </div>
                          {isSelected && <Check size={14} style={{ color: "var(--color-primary, #1B6EF3)" }} />}
                        </div>
                      );
                    })}
                    {filteredCandidates.length === 0 && (
                      <div style={{ padding: "16px", textAlign: "center", fontSize: 12, color: "var(--color-text-muted)" }}>
                        No unassigned account identities found.
                      </div>
                    )}
                  </div>

                  {/* Workspace Role Selector */}
                  <div style={{ marginBottom: 18 }}>
                    <label className="label" style={{ marginBottom: 6, display: "block" }}>
                      Assigned Workspace Role
                    </label>
                    <select
                      className="input-field"
                      value={assignRole}
                      onChange={(e) => setAssignRole(e.target.value)}
                      style={{ width: "100%" }}
                    >
                      {WORKSPACE_ROLES.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.label} — {r.desc}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
                    <button type="button" className="btn-outline" onClick={() => setShowAddModal(false)}>
                      Cancel
                    </button>
                    <button
                      type="button"
                      className="btn-primary"
                      disabled={!selectedPrincipal || assignPrincipal.isPending}
                      onClick={handleAssignDirectoryPrincipal}
                    >
                      {assignPrincipal.isPending ? "Assigning…" : "Assign to Workspace"}
                    </button>
                  </div>
                </div>
              )}

              {/* Mode 2: Direct Provision User */}
              {modalTab === "create" && (
                <form onSubmit={handleCreateUser}>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
                    <div>
                      <label className="label">Email Address</label>
                      <input
                        required
                        className="input-field"
                        type="email"
                        value={createEmail}
                        onChange={(e) => setCreateEmail(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="label">Display Name</label>
                      <input
                        required
                        className="input-field"
                        type="text"
                        value={createDisplayName}
                        onChange={(e) => setCreateDisplayName(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="label">Initial Password</label>
                      <input
                        required
                        className="input-field"
                        type="password"
                        value={createPassword}
                        onChange={(e) => setCreatePassword(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="label">Workspace Role</label>
                      <select
                        className="input-field"
                        value={createRole}
                        onChange={(e) => setCreateRole(e.target.value)}
                      >
                        {WORKSPACE_ROLES.map((r) => (
                          <option key={r.id} value={r.id}>
                            {r.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
                    <button type="button" className="btn-outline" onClick={() => setShowAddModal(false)}>
                      Cancel
                    </button>
                    <button type="submit" className="btn-primary" disabled={createUser.isPending}>
                      {createUser.isPending ? "Creating…" : "Create & Add User"}
                    </button>
                  </div>
                </form>
              )}

              {/* Mode 3: Invite by Email */}
              {modalTab === "invite" && (
                <div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
                    <div>
                      <label className="label">User Email Address</label>
                      <input
                        className="input-field"
                        type="email"
                        placeholder="user@example.com"
                        value={inviteEmail}
                        onChange={(e) => setInviteEmail(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="label">Workspace Role</label>
                      <select
                        className="input-field"
                        value={inviteRole}
                        onChange={(e) => setInviteRole(e.target.value)}
                      >
                        {WORKSPACE_ROLES.map((r) => (
                          <option key={r.id} value={r.id}>
                            {r.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
                    <button type="button" className="btn-outline" onClick={() => setShowAddModal(false)}>
                      Cancel
                    </button>
                    <button
                      type="button"
                      className="btn-primary"
                      disabled={!inviteEmail.trim() || invite.isPending}
                      onClick={handleInvite}
                    >
                      {invite.isPending ? "Generating…" : "Generate Invite"}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </Glass>
        </div>
      )}
    </div>
  );
}
