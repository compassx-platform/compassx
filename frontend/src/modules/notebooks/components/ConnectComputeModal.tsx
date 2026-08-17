import { Cpu } from 'lucide-react';

interface Props {
  onConnectDefault: () => void;
  onSelectCompute: () => void;
  onDismiss: () => void;
}

export default function ConnectComputeModal({ onConnectDefault, onSelectCompute, onDismiss }: Props) {
  return (
    <div className="notebook-connect-modal-backdrop" onClick={onDismiss}>
      <div
        className="notebook-connect-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="connect-modal-title"
      >
        <div className="notebook-connect-modal__icon">
          <Cpu size={24} />
        </div>
        <h3 id="connect-modal-title" className="notebook-connect-modal__title">
          Connect to compute
        </h3>
        <p className="notebook-connect-modal__body">
          This notebook is not connected to a compute resource. Select a resource to execute cells.
        </p>
        <div className="notebook-connect-modal__actions">
          <button
            className="notebook-connect-modal__btn notebook-connect-modal__btn--primary"
            onClick={onConnectDefault}
          >
            Use default compute
          </button>
          <button
            className="notebook-connect-modal__btn notebook-connect-modal__btn--secondary"
            onClick={onSelectCompute}
          >
            Select compute
          </button>
        </div>
        <button
          className="notebook-connect-modal__dismiss"
          onClick={onDismiss}
          aria-label="Dismiss"
        >
          Later
        </button>
      </div>
    </div>
  );
}
