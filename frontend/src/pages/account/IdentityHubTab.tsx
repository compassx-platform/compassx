import React from "react";
import { Tab } from "./AccountConsolePage";

interface IdentityHubTabProps {
  onSelectTab: (tab: Tab) => void;
  userCount: number;
  groupCount: number;
  spCount: number;
}

export const IdentityHubTab: React.FC<IdentityHubTabProps> = ({
  onSelectTab,
  userCount,
  groupCount,
  spCount,
}) => {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div>
        <h2 style={{ fontSize: 18, fontWeight: 700, margin: "0 0 6px", color: "var(--color-text)" }}>
          Identity and Access
        </h2>
        <p style={{ margin: 0, color: "var(--color-text-muted)", fontSize: 14 }}>
          Management and platform permissions for users, groups, and automated service identities.
        </p>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {/* Users Section */}
        <div
          className="glass"
          style={{
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-lg)",
            padding: "20px 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: 16, fontWeight: 700, color: "var(--color-text)" }}>Users</span>
              <span
                style={{
                  fontSize: 11,
                  padding: "2px 8px",
                  borderRadius: 999,
                  background: "var(--color-primary-bg, rgba(27, 110, 243, 0.1))",
                  color: "var(--color-primary, #1B6EF3)",
                  fontWeight: 600,
                }}
              >
                {userCount} total
              </span>
            </div>
            <div style={{ fontSize: 13, color: "var(--color-text-muted)", marginTop: 4 }}>
              Manage users, invite team members, configure account roles, and set platform entitlements.
            </div>
          </div>
          <button className="btn-primary" onClick={() => onSelectTab("Users")} style={{ minWidth: 100 }}>
            Manage
          </button>
        </div>

        {/* Groups Section */}
        <div
          className="glass"
          style={{
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-lg)",
            padding: "20px 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: 16, fontWeight: 700, color: "var(--color-text)" }}>Groups</span>
              <span
                style={{
                  fontSize: 11,
                  padding: "2px 8px",
                  borderRadius: 999,
                  background: "var(--color-primary-bg, rgba(27, 110, 243, 0.1))",
                  color: "var(--color-primary, #1B6EF3)",
                  fontWeight: 600,
                }}
              >
                {groupCount} total
              </span>
            </div>
            <div style={{ fontSize: 13, color: "var(--color-text-muted)", marginTop: 4 }}>
              Manage team groups, nested parent-child hierarchies, and delegated group administrators.
            </div>
          </div>
          <button className="btn-primary" onClick={() => onSelectTab("Groups")} style={{ minWidth: 100 }}>
            Manage
          </button>
        </div>

        {/* Service Principals Section */}
        <div
          className="glass"
          style={{
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-lg)",
            padding: "20px 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: 16, fontWeight: 700, color: "var(--color-text)" }}>Service Principals</span>
              <span
                style={{
                  fontSize: 11,
                  padding: "2px 8px",
                  borderRadius: 999,
                  background: "var(--color-primary-bg, rgba(27, 110, 243, 0.1))",
                  color: "var(--color-primary, #1B6EF3)",
                  fontWeight: 600,
                }}
              >
                {spCount} total
              </span>
            </div>
            <div style={{ fontSize: 13, color: "var(--color-text-muted)", marginTop: 4 }}>
              Identities for use with automated tools, running pipelines, CI/CD, and M2M OAuth applications.
            </div>
          </div>
          <button className="btn-primary" onClick={() => onSelectTab("Service Principals")} style={{ minWidth: 100 }}>
            Manage
          </button>
        </div>
      </div>
    </div>
  );
};
