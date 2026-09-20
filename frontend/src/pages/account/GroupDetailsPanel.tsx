import React, { useState } from "react";
import {
  useGroupMembers,
  useParentGroups,
  useAddParentGroup,
  useRemoveParentGroup,
  useGroupManagers,
  useAddGroupManager,
  useRemoveGroupManager,
  useUsers,
  useGroups,
  type GroupOut,
  type GroupMemberOut,
  type GroupManagerOut,
  type UserListItem,
} from "../../lib/userManagerApi";

interface GroupDetailsPanelProps {
  group: GroupOut;
  onAddMember: (userId: string) => Promise<void>;
  onRemoveMember: (userId: string) => Promise<void>;
}

export const GroupDetailsPanel: React.FC<GroupDetailsPanelProps> = ({
  group,
  onAddMember,
  onRemoveMember,
}) => {
  const [subTab, setSubTab] = useState<"Members" | "Parent groups" | "Managers">("Members");

  const { data: members = [], isLoading: loadingMembers } = useGroupMembers(group.id);
  const { data: parentGroups = [], isLoading: loadingParents } = useParentGroups(group.id);
  const { data: managers = [], isLoading: loadingManagers } = useGroupManagers(group.id);
  const { data: allUsers = [] } = useUsers();
  const { data: allGroups = [] } = useGroups();

  const addParent = useAddParentGroup(group.id);
  const removeParent = useRemoveParentGroup(group.id);
  const addManager = useAddGroupManager(group.id);
  const removeManager = useRemoveGroupManager(group.id);

  const [selectedUserId, setSelectedUserId] = useState("");
  const [selectedParentGroupId, setSelectedParentGroupId] = useState("");
  const [selectedManagerId, setSelectedManagerId] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleAddMember = async () => {
    if (!selectedUserId) return;
    setErrorMsg(null);
    try {
      await onAddMember(selectedUserId);
      setSelectedUserId("");
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || "Failed to add member");
    }
  };

  const handleAddParent = async () => {
    if (!selectedParentGroupId) return;
    setErrorMsg(null);
    try {
      await addParent.mutateAsync(selectedParentGroupId);
      setSelectedParentGroupId("");
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || "Failed to add parent group");
    }
  };

  const handleAddManager = async () => {
    if (!selectedManagerId) return;
    setErrorMsg(null);
    try {
      await addManager.mutateAsync(selectedManagerId);
      setSelectedManagerId("");
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || "Failed to add manager");
    }
  };

  const availableParentGroups = allGroups.filter((g) => g.id !== group.id);

  return (
    <div>
      {/* Sub-tab Navigation */}
      <div style={{ display: "flex", gap: 16, borderBottom: "1px solid var(--color-border)", marginBottom: 16 }}>
        {(["Members", "Parent groups", "Managers"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => {
              setSubTab(tab);
              setErrorMsg(null);
            }}
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

      {errorMsg && (
        <div
          style={{
            padding: "8px 12px",
            background: "var(--color-danger-bg, rgba(239, 68, 68, 0.1))",
            color: "var(--color-danger, #EF4444)",
            borderRadius: "var(--radius)",
            fontSize: 12,
            marginBottom: 12,
          }}
        >
          {errorMsg}
        </div>
      )}

      {/* ── Sub-tab: Members ───────────────────────────────────────────────── */}
      {subTab === "Members" && (
        <div>
          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            <select
              className="input-field"
              value={selectedUserId}
              onChange={(e) => setSelectedUserId(e.target.value)}
              style={{ maxWidth: 320 }}
            >
              <option value="">Select user to add…</option>
              {allUsers.map((u: UserListItem) => (
                <option key={u.id} value={u.id}>
                  {u.email} ({u.display_name || "No name"})
                </option>
              ))}
            </select>
            <button className="btn-primary" onClick={handleAddMember} disabled={!selectedUserId}>
              Add Member
            </button>
          </div>

          {loadingMembers ? (
            <div style={{ fontSize: 13, color: "var(--color-text-muted)" }}>Loading members…</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {members.map((m: GroupMemberOut) => (
                <div
                  key={m.user_id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "8px 12px",
                    background: "var(--color-bg)",
                    border: "1px solid var(--color-border)",
                    borderRadius: "var(--radius)",
                  }}
                >
                  <div>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>{m.email}</span>
                    {m.display_name && (
                      <span style={{ fontSize: 12, color: "var(--color-text-muted)", marginLeft: 8 }}>
                        ({m.display_name})
                      </span>
                    )}
                  </div>
                  <button
                    className="btn-danger"
                    style={{ fontSize: 11, padding: "2px 8px" }}
                    onClick={() => onRemoveMember(m.user_id)}
                  >
                    Remove
                  </button>
                </div>
              ))}
              {members.length === 0 && (
                <div style={{ fontSize: 13, color: "var(--color-text-muted)" }}>No members in this group.</div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Sub-tab: Parent Groups (Nesting) ───────────────────────────────── */}
      {subTab === "Parent groups" && (
        <div>
          <p style={{ fontSize: 12, color: "var(--color-text-muted)", margin: "0 0 12px" }}>
            Nesting this group under a parent container group causes all members to automatically inherit permissions
            granted to the parent group.
          </p>

          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            <select
              className="input-field"
              value={selectedParentGroupId}
              onChange={(e) => setSelectedParentGroupId(e.target.value)}
              style={{ maxWidth: 320 }}
            >
              <option value="">Select parent group…</option>
              {availableParentGroups.map((g: GroupOut) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </select>
            <button
              className="btn-primary"
              onClick={handleAddParent}
              disabled={!selectedParentGroupId || addParent.isPending}
            >
              {addParent.isPending ? "Adding…" : "+ Add to Parent Group"}
            </button>
          </div>

          {loadingParents ? (
            <div style={{ fontSize: 13, color: "var(--color-text-muted)" }}>Loading parent groups…</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {parentGroups.map((pg: GroupOut) => (
                <div
                  key={pg.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "8px 12px",
                    background: "var(--color-bg)",
                    border: "1px solid var(--color-border)",
                    borderRadius: "var(--radius)",
                  }}
                >
                  <div>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>{pg.name}</span>
                    <span style={{ fontSize: 11, color: "var(--color-text-muted)", marginLeft: 8 }}>
                      (Parent Container)
                    </span>
                  </div>
                  <button
                    className="btn-danger"
                    style={{ fontSize: 11, padding: "2px 8px" }}
                    onClick={() => removeParent.mutate(pg.id)}
                    disabled={removeParent.isPending}
                  >
                    Remove
                  </button>
                </div>
              ))}
              {parentGroups.length === 0 && (
                <div style={{ fontSize: 13, color: "var(--color-text-muted)" }}>
                  This group is not nested under any parent group.
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Sub-tab: Managers (Delegation) ─────────────────────────────────── */}
      {subTab === "Managers" && (
        <div>
          <p style={{ fontSize: 12, color: "var(--color-text-muted)", margin: "0 0 12px" }}>
            Designated managers can add and remove group members without requiring full Account Admin privileges.
          </p>

          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            <select
              className="input-field"
              value={selectedManagerId}
              onChange={(e) => setSelectedManagerId(e.target.value)}
              style={{ maxWidth: 320 }}
            >
              <option value="">Select user to designate as manager…</option>
              {allUsers.map((u: UserListItem) => (
                <option key={u.id} value={u.id}>
                  {u.email} ({u.display_name || "No name"})
                </option>
              ))}
            </select>
            <button
              className="btn-primary"
              onClick={handleAddManager}
              disabled={!selectedManagerId || addManager.isPending}
            >
              {addManager.isPending ? "Assigning…" : "+ Assign Manager"}
            </button>
          </div>

          {loadingManagers ? (
            <div style={{ fontSize: 13, color: "var(--color-text-muted)" }}>Loading managers…</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {managers.map((m: GroupManagerOut) => (
                <div
                  key={m.user_id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "8px 12px",
                    background: "var(--color-bg)",
                    border: "1px solid var(--color-border)",
                    borderRadius: "var(--radius)",
                  }}
                >
                  <div>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>{m.email}</span>
                    <span style={{ fontSize: 11, color: "var(--color-text-muted)", marginLeft: 8 }}>
                      Assigned {new Date(m.assigned_at).toLocaleDateString()}
                    </span>
                  </div>
                  <button
                    className="btn-danger"
                    style={{ fontSize: 11, padding: "2px 8px" }}
                    onClick={() => removeManager.mutate(m.user_id)}
                    disabled={removeManager.isPending}
                  >
                    Remove
                  </button>
                </div>
              ))}
              {managers.length === 0 && (
                <div style={{ fontSize: 13, color: "var(--color-text-muted)" }}>
                  No delegated managers assigned to this group.
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
