import React, { useState } from "react";
import { useCheckpoint } from "../hooks/useCheckpoint";

interface Props {
  appId: string;
  branchId: string;
}

export default function CheckpointButton({ appId, branchId }: Props) {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const { mutate, isPending, isSuccess } = useCheckpoint(appId, branchId);

  const handleCheckpoint = () => {
    if (!message.trim()) return;
    mutate(message, {
      onSuccess: () => {
        setMessage("");
        setOpen(false);
      },
    });
  };

  return (
    <>
      <button
        id="checkpoint-btn"
        onClick={() => setOpen(true)}
        className="btn-outline"
        style={{
          borderRadius: "8px",
          padding: "6px 14px",
          fontSize: "13px",
          cursor: "pointer",
          fontWeight: 500,
        }}
      >
        💾 Checkpoint
      </button>

      {open && (
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
          onClick={(e) => e.target === e.currentTarget && setOpen(false)}
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
              Create Checkpoint
            </h3>
            <p style={{ margin: 0, fontSize: "13px", color: "var(--color-text-muted)" }}>
              Saves a versioned snapshot of the current working tree. This is separate from autosave.
            </p>
            <textarea
              id="checkpoint-message-input"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Describe your changes..."
              rows={3}
              style={{
                background: "var(--color-bg)",
                border: "1px solid var(--color-border)",
                borderRadius: "8px",
                color: "var(--color-text)",
                padding: "10px 12px",
                fontSize: "13px",
                resize: "vertical",
                outline: "none",
                fontFamily: "inherit",
              }}
              onKeyDown={(e) => e.key === "Enter" && e.metaKey && handleCheckpoint()}
            />
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
              <button
                className="btn-outline"
                onClick={() => setOpen(false)}
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
                id="checkpoint-confirm-btn"
                onClick={handleCheckpoint}
                disabled={!message.trim() || isPending}
                className="btn-primary"
                style={{
                  borderRadius: "8px",
                  padding: "7px 18px",
                  fontSize: "13px",
                  fontWeight: 600,
                  cursor: message.trim() && !isPending ? "pointer" : "not-allowed",
                  opacity: !message.trim() || isPending ? 0.5 : 1,
                }}
              >
                {isPending ? "Saving…" : "Save Checkpoint"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
