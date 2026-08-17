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
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-labelledby="confirm-dialog-title">
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button type="button" className="btn-icon" aria-label="Close" onClick={onCancel}>
            <X size={18} />
          </button>
        </div>
        <div style={{ padding: "4px 0 8px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
            <span aria-hidden="true" style={{ display: "inline-flex", color: "var(--color-danger, #dc2626)" }}>
              <AlertCircle size={18} />
            </span>
            <h3 id="confirm-dialog-title" style={{ margin: 0 }}>{title}</h3>
          </div>
          <p style={{ margin: 0, color: "var(--color-text-muted)" }}>{message}</p>
        </div>
        <div className="modal-footer">
          <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={isLoading}>
            {hideConfirm ? "Close" : "Cancel"}
          </button>
          {!hideConfirm && (
            <button type="button" className={`btn ${isDestructive ? "btn-danger" : "btn-primary"}`} onClick={onConfirm} disabled={isLoading}>
              {isLoading ? `${confirmLabel}...` : confirmLabel}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
