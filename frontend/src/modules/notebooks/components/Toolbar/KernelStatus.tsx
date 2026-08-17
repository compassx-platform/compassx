import { useNotebookStore } from '../../store/notebookStore';

const STATUS_LABELS: Record<string, string> = {
  idle: 'Idle',
  busy: 'Busy',
  dead: 'Dead',
  connecting: 'Connecting…',
  unknown: 'Unknown',
};

export default function KernelStatus() {
  const status = useNotebookStore((s) => s.kernelStatus);
  const kernelInfo = useNotebookStore((s) => s.kernelInfo);

  const label = kernelInfo
    ? `${kernelInfo.name}${kernelInfo.version ? ` ${kernelInfo.version}` : ''}`
    : 'Python 3';

  return (
    <div className={`notebook-kernel-status notebook-kernel-status-${status}`} title={`Kernel: ${label}`}>
      <span className="notebook-kernel-dot" />
      <span className="notebook-kernel-text">{label} · {STATUS_LABELS[status] ?? status}</span>
    </div>
  );
}
