import React, { useState } from "react";
import { usePublish } from "../hooks/usePublish";

interface Props {
  appId: string;
  branchId: string;
  headCommitId: string | null;
}

export default function PublishButton({ appId, branchId, headCommitId }: Props) {
  const [confirming, setConfirming] = useState(false);
  const { mutate, isPending, isSuccess } = usePublish(appId);

  const handlePublish = () => {
    if (!headCommitId) return;
    mutate(
      { commitId: headCommitId, sourceBranchId: branchId },
      { onSuccess: () => setConfirming(false) },
    );
  };

  if (!headCommitId) {
    return (
      <button
        id="publish-btn"
        disabled
        className="btn-outline"
        style={{
          borderRadius: "8px",
          color: "var(--color-text-muted)",
          padding: "6px 14px",
          fontSize: "13px",
          cursor: "not-allowed",
          opacity: 0.5,
        }}
      >
        🚀 Publish
      </button>
    );
  }

  return (
    <>
      <button
        id="publish-btn"
        onClick={() => setConfirming(true)}
        style={{
          background: "var(--color-success)",
          border: "none",
          borderRadius: "8px",
          color: "#ffffff",
          padding: "6px 16px",
          fontSize: "13px",
          fontWeight: 600,
          cursor: "pointer",
        }}
      >
        🚀 Publish
      </button>

      {confirming && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.4)",
            zIndex: 1000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
          onClick={(e) => e.target === e.currentTarget && setConfirming(false)}
        >
          <div
            className="glass"
            style={{
              background: "var(--color-surface)",
              color: "var(--color-text)",
              borderRadius: "12px",
              padding: "28px",
              width: "440px",
              display: "flex",
              flexDirection: "column",
              gap: "16px",
            }}
          >
            <h3 style={{ margin: 0, color: "var(--color-text)", fontSize: "16px" }}>
              Publish to Production
            </h3>
            <p style={{ margin: 0, fontSize: "13px", color: "var(--color-text-muted)" }}>
              This will provision a new production pod and switch traffic to commit{" "}
              <code style={{ fontFamily: "monospace", color: "var(--color-primary)" }}>
                {headCommitId.slice(0, 8)}
              </code>
              . The prior production pod will be kept warm for 10 minutes for instant rollback.
            </p>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
              <button
                className="btn-outline"
                onClick={() => setConfirming(false)}
                style={{
                  borderRadius: "8px",
                  padding: "7px 16px",
                  fontSize: "13px",
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                id="publish-confirm-btn"
                onClick={handlePublish}
                disabled={isPending}
                style={{
                  background: "var(--color-success)",
                  border: "none",
                  borderRadius: "8px",
                  color: "#ffffff",
                  padding: "7px 18px",
                  fontSize: "13px",
                  fontWeight: 600,
                  cursor: isPending ? "not-allowed" : "pointer",
                  opacity: isPending ? 0.6 : 1,
                }}
              >
                {isPending ? "Publishing…" : "Confirm Publish"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
