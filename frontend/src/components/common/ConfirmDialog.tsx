import { AlertCircle, X } from "lucide-react";

interface Props {
  title: string;
  message: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  isDestructive?: boolean;
  isLoading?: boolean;
  hideConfirm?: boolean;
}

export default function ConfirmDialog({
  title,
  message,
  confirmLabel,
  onConfirm,
  onCancel,
  isDestructive = true,
  isLoading = false,
  hideConfirm = false,
}: Props) {
  return (
    <div className="modal-backdrop" onClick={onCancel} style={{ zIndex: 100 }}>
      <div
        className="modal-panel"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        style={{
          width: "min(460px, calc(100vw - 2rem))",
          borderRadius: "10px",
          overflow: "hidden",
          boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
          background: "var(--color-surface, #ffffff)",
          border: "1px solid var(--color-border, #e2e8f0)",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "16px 20px 12px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span
              aria-hidden="true"
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 32,
                height: 32,
                borderRadius: "50%",
                backgroundColor: isDestructive ? "rgba(239, 68, 68, 0.1)" : "rgba(37, 99, 235, 0.1)",
                color: isDestructive ? "var(--color-danger, #ef4444)" : "var(--color-primary, #2563eb)",
                flexShrink: 0,
              }}
            >
              <AlertCircle size={18} />
            </span>
            <h3
              id="confirm-dialog-title"
              style={{
                margin: 0,
                fontSize: "15px",
                fontWeight: 600,
                color: "var(--color-text, #1e293b)",
              }}
            >
              {title}
            </h3>
          </div>
          <button
            type="button"
            className="btn-icon"
            aria-label="Close"
            onClick={onCancel}
            style={{
              background: "transparent",
              border: "none",
              cursor: "pointer",
              padding: "4px",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: "4px",
              color: "var(--color-text-muted, #64748b)",
            }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: "0 20px 20px 62px" }}>
          <p
            style={{
              margin: 0,
              color: "var(--color-text-muted, #64748b)",
              fontSize: "13px",
              lineHeight: 1.5,
            }}
          >
            {message}
          </p>
        </div>

        {/* Footer */}
        <div
          className="modal-footer"
          style={{
            display: "flex",
            justifyContent: "flex-end",
            alignItems: "center",
            gap: 10,
            padding: "12px 20px",
            borderTop: "1px solid var(--color-border, #e2e8f0)",
            background: "var(--color-surface-secondary, #f8fafc)",
          }}
        >
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onCancel}
            disabled={isLoading}
            style={{
              height: "32px",
              padding: "0 14px",
              fontSize: "12px",
              fontWeight: 500,
              borderRadius: "6px",
              cursor: "pointer",
            }}
          >
            {hideConfirm ? "Close" : "Cancel"}
          </button>
          {!hideConfirm && (
            <button
              type="button"
              className={`btn ${isDestructive ? "btn-danger" : "btn-primary"}`}
              onClick={onConfirm}
              disabled={isLoading}
              style={{
                height: "32px",
                padding: "0 14px",
                fontSize: "12px",
                fontWeight: 500,
                borderRadius: "6px",
                cursor: "pointer",
                background: isDestructive ? "var(--color-danger, #ef4444)" : "var(--color-primary, #2563eb)",
                color: "#ffffff",
                border: "none",
              }}
            >
              {isLoading ? `${confirmLabel}...` : confirmLabel}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
