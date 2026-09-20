import React, { useRef, useState, useEffect } from "react";
import { ChevronDown, Check, Users, User, Shield } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useMyGroups, type MyGroupOut } from "@/lib/userManagerApi";
import { useSessionRoleStore } from "@/lib/sessionRoleStore";

export const RoleSwitcherDropdown: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement | null>(null);
  const qc = useQueryClient();

  const { data: myGroups = [] } = useMyGroups();
  const { activeRole, setActiveRole, clearActiveRole } = useSessionRoleStore();

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  const handleSelectRole = (group: MyGroupOut | null) => {
    if (group) {
      setActiveRole({ id: group.id, name: group.name });
    } else {
      clearActiveRole();
    }
    setIsOpen(false);
    // Invalidate queries to refresh data under assumed session context
    qc.invalidateQueries();
  };

  const displayText = activeRole ? `Role: ${activeRole.name}` : "Personal Context";

  return (
    <div ref={dropdownRef} style={{ position: "relative" }}>
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "5px 10px",
          borderRadius: 6,
          border: activeRole
            ? "1px solid var(--color-primary, #1B6EF3)"
            : "1px solid var(--color-border)",
          background: activeRole
            ? "var(--color-primary-bg, rgba(27, 110, 243, 0.08))"
            : "transparent",
          color: activeRole ? "var(--color-primary, #1B6EF3)" : "var(--color-text)",
          cursor: "pointer",
          fontSize: "0.82rem",
          fontWeight: 500,
          transition: "all 0.15s ease",
        }}
        title="Switch active execution role"
      >
        {activeRole ? <Shield size={13} /> : <User size={13} style={{ opacity: 0.7 }} />}
        <span style={{ maxWidth: 140, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {displayText}
        </span>
        <ChevronDown size={12} style={{ opacity: 0.6 }} />
      </button>

      {isOpen && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 6px)",
            right: 0,
            width: 240,
            background: "var(--color-surface, #1e2024)",
            border: "1px solid var(--color-border)",
            borderRadius: 8,
            boxShadow: "0 8px 24px rgba(0,0,0,0.25)",
            zIndex: 1000,
            padding: 4,
          }}
        >
          <div style={{ padding: "6px 10px", fontSize: 11, fontWeight: 700, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Execution Context
          </div>

          {/* Personal (Default) */}
          <button
            type="button"
            onClick={() => handleSelectRole(null)}
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "7px 10px",
              borderRadius: 6,
              border: "none",
              background: !activeRole ? "rgba(255,255,255,0.06)" : "transparent",
              color: "var(--color-text)",
              cursor: "pointer",
              textAlign: "left",
              fontSize: "0.84rem",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <User size={14} style={{ opacity: 0.7 }} />
              <div>
                <div style={{ fontWeight: !activeRole ? 600 : 400 }}>Personal (Default)</div>
                <div style={{ fontSize: 11, color: "var(--color-text-muted)" }}>All direct & ambient access</div>
              </div>
            </div>
            {!activeRole && <Check size={14} style={{ color: "var(--color-primary, #1B6EF3)" }} />}
          </button>

          {/* Assumable Groups Section */}
          {myGroups.length > 0 && (
            <>
              <div style={{ height: 1, background: "var(--color-border)", margin: "4px 0" }} />
              <div style={{ padding: "6px 10px", fontSize: 11, fontWeight: 700, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Assumable Roles & Groups
              </div>

              {myGroups.map((g: MyGroupOut) => {
                const isSelected = activeRole?.id === g.id;
                return (
                  <button
                    key={g.id}
                    type="button"
                    onClick={() => handleSelectRole(g)}
                    style={{
                      width: "100%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "7px 10px",
                      borderRadius: 6,
                      border: "none",
                      background: isSelected ? "rgba(255,255,255,0.06)" : "transparent",
                      color: "var(--color-text)",
                      cursor: "pointer",
                      textAlign: "left",
                      fontSize: "0.84rem",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <Users size={14} style={{ opacity: 0.7 }} />
                      <div>
                        <div style={{ fontWeight: isSelected ? 600 : 400 }}>{g.name}</div>
                        <div style={{ fontSize: 11, color: "var(--color-text-muted)" }}>
                          {g.member_count} member{g.member_count !== 1 ? "s" : ""}
                        </div>
                      </div>
                    </div>
                    {isSelected && <Check size={14} style={{ color: "var(--color-primary, #1B6EF3)" }} />}
                  </button>
                );
              })}
            </>
          )}
        </div>
      )}
    </div>
  );
};
