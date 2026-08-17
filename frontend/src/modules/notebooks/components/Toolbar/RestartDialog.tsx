interface Props {
  onConfirm: () => void;
  onCancel: () => void;
}

export default function RestartDialog({ onConfirm, onCancel }: Props) {
  return (
    <div className="notebook-dialog-overlay">
      <div className="notebook-dialog">
        <h3 className="notebook-dialog-title">Restart kernel?</h3>
        <p className="notebook-dialog-body">
          All variables will be lost. Cell sources are preserved.
        </p>
        <div className="notebook-dialog-actions">
          <button className="notebook-toolbar-btn" onClick={onCancel}>Cancel</button>
          <button className="notebook-toolbar-btn notebook-toolbar-btn-danger" onClick={onConfirm}>
            Restart
          </button>
        </div>
      </div>
    </div>
  );
}
