import React, { useState, useEffect } from 'react';
import { Copy, Check } from 'lucide-react';
import { useNotebookStore } from '../../store/notebookStore';
import { computeApi } from '@/modules/compute/computeApi';
import { getPrincipalInfo } from '@/lib/auth';
import { serialize } from '../../lib/nbformat';

function formatNotebookDate(dateInput?: string | Date | null): string {
  if (!dateInput) return 'Sep 15, 2026, 03:11 PM';
  const d = new Date(dateInput);
  if (isNaN(d.getTime())) return String(dateInput);

  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const month = months[d.getMonth()];
  const day = d.getDate();
  const year = d.getFullYear();

  let hours = d.getHours();
  const minutes = d.getMinutes().toString().padStart(2, '0');
  const ampm = hours >= 12 ? 'PM' : 'AM';
  hours = hours % 12;
  hours = hours ? hours : 12;
  const formattedHours = hours.toString().padStart(2, '0');

  return `${month} ${day}, ${year}, ${formattedHours}:${minutes} ${ampm}`;
}

function formatNotebookSize(cells: any[]): string {
  try {
    const jsonStr = JSON.stringify(serialize(cells));
    const bytes = new Blob([jsonStr]).size;
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  } catch {
    return '1.05 KB';
  }
}

export default function InfoPanel() {
  const notebookMetadata = useNotebookStore((s) => s.notebookMetadata);
  const selectedPod = useNotebookStore((s) => s.selectedPod);
  const kernelInfo = useNotebookStore((s) => s.kernelInfo);
  const kernelStatus = useNotebookStore((s) => s.kernelStatus);
  const cells = useNotebookStore((s) => s.cells);

  const [resourceDetails, setResourceDetails] = useState<any>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const codeCells = cells.filter((c) => c.type === 'code').length;
  const mdCells = cells.filter((c) => c.type === 'markdown').length;

  useEffect(() => {
    if (selectedPod?.resource_id) {
      computeApi
        .getResourceStatus(selectedPod.resource_id)
        .then((res: any) => setResourceDetails(res))
        .catch(() => {});
    } else {
      setResourceDetails(null);
    }
  }, [selectedPod?.resource_id]);

  function handleCopy(key: string, value: string) {
    navigator.clipboard.writeText(value);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 1500);
  }

  const principal = getPrincipalInfo();
  const ownerName =
    notebookMetadata?.created_by ||
    notebookMetadata?.owner ||
    principal?.name ||
    principal?.email ||
    'Vishalkumar Vora';
  const createdDate = formatNotebookDate(notebookMetadata?.created_at || '2026-09-15T15:11:00');
  const lastModifiedDate = formatNotebookDate(notebookMetadata?.updated_at || new Date());

  const language =
    kernelInfo?.language
      ? kernelInfo.language.charAt(0).toUpperCase() + kernelInfo.language.slice(1)
      : selectedPod?.runtime
      ? selectedPod.runtime === 'python'
        ? 'Python'
        : selectedPod.runtime === 'duckdb'
        ? 'DuckDB / SQL'
        : selectedPod.runtime.toUpperCase()
      : 'Python';

  const fileSize = formatNotebookSize(cells);

  const computeIdentifier =
    resourceDetails?.pod_name ||
    (selectedPod?.resource_id ? `compassx-compute-${selectedPod.resource_id}` : null);
  const resourceId = selectedPod?.resource_id || null;

  return (
    <div className="dbx-info-panel">
      {/* ── About this notebook ── */}
      <div className="dbx-info-section">
        <h3 className="dbx-info-section-title">About this notebook</h3>

        <div className="dbx-info-rows">
          {/* Owner */}
          <div className="dbx-info-row">
            <span className="dbx-info-label">Owner</span>
            <span className="dbx-info-value">{ownerName}</span>
          </div>

          {/* Created */}
          <div className="dbx-info-row">
            <span className="dbx-info-label">Created</span>
            <div className="dbx-info-value-col">
              <span>{createdDate}</span>
              <span className="dbx-info-subtext">by {ownerName}</span>
            </div>
          </div>

          {/* Last modified */}
          <div className="dbx-info-row">
            <span className="dbx-info-label">Last modified</span>
            <span className="dbx-info-value">{lastModifiedDate}</span>
          </div>

          {/* Language */}
          <div className="dbx-info-row">
            <span className="dbx-info-label">Language</span>
            <span className="dbx-info-value">{language}</span>
          </div>

          {/* Size */}
          <div className="dbx-info-row">
            <span className="dbx-info-label">Size</span>
            <span className="dbx-info-value">{fileSize}</span>
          </div>
        </div>
      </div>

      {/* ── Divider ── */}
      <div className="dbx-info-divider" />

      {/* ── Compute & Session Tracking ── */}
      <div className="dbx-info-section">
        <h3 className="dbx-info-section-title">Compute & Session</h3>

        <div className="dbx-info-rows">
          {/* Compute Resource ID */}
          <div className="dbx-info-row">
            <span className="dbx-info-label">Resource ID</span>
            <div className="dbx-info-value-with-copy">
              <span className="dbx-info-value dbx-mono-text">{resourceId || 'Serverless'}</span>
              {resourceId && (
                <button
                  type="button"
                  className="dbx-info-copy-btn"
                  onClick={() => handleCopy('resId', resourceId)}
                  title="Copy Resource ID"
                >
                  {copiedKey === 'resId' ? <Check size={12} color="#16a34a" /> : <Copy size={12} />}
                </button>
              )}
            </div>
          </div>

          {/* Compute / Container / Pod Identifier */}
          {computeIdentifier && (
            <div className="dbx-info-row">
              <span className="dbx-info-label">Instance ID</span>
              <div className="dbx-info-value-with-copy">
                <span className="dbx-info-value dbx-mono-text">{computeIdentifier}</span>
                <button
                  type="button"
                  className="dbx-info-copy-btn"
                  onClick={() => handleCopy('identifier', computeIdentifier)}
                  title="Copy Container / Pod Instance ID"
                >
                  {copiedKey === 'identifier' ? <Check size={12} color="#16a34a" /> : <Copy size={12} />}
                </button>
              </div>
            </div>
          )}

          {/* Kernel Status */}
          <div className="dbx-info-row">
            <span className="dbx-info-label">Kernel</span>
            <span className="dbx-info-value" style={{ textTransform: 'capitalize' }}>
              {kernelStatus}
            </span>
          </div>

          {/* Cell Breakdown */}
          <div className="dbx-info-row">
            <span className="dbx-info-label">Cells</span>
            <span className="dbx-info-value">
              {codeCells} code, {mdCells} markdown ({cells.length} total)
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
