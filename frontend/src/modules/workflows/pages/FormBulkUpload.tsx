/**
 * FormBulkUpload — upload CSV/Excel, preview rows in an editable grid, then commit.
 */
import { useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { useScopedNavigate } from '@/lib/appNavigation';
import {
  Upload,
  Download,
  CheckCircle,
  AlertCircle,
  FileText,
  X,
} from 'lucide-react';
import api from '@/lib/api';

// ── Types ──────────────────────────────────────────────────────────────────────

interface PreviewField {
  id: string;
  label: string;
  type: string;
}

interface PreviewRow {
  _row: number;
  asset_id?: string;
  [key: string]: string | number | undefined;
}

interface PreviewResult {
  fields: PreviewField[];
  rows: PreviewRow[];
  errors: { row: number; message: string }[];
}

interface CommitResult {
  created: number;
  errors: { row: number | string; message: string }[];
}

// ── Component ──────────────────────────────────────────────────────────────────

export default function FormBulkUpload() {
  const { formId } = useParams<{ formId: string }>();
  const navigate = useScopedNavigate();

  const [step, setStep] = useState<'upload' | 'preview' | 'done'>('upload');

  // Upload step state
  const [dragOver, setDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Preview step state
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [editedRows, setEditedRows] = useState<PreviewRow[]>([]);
  const [committing, setCommitting] = useState(false);
  const [commitError, setCommitError] = useState<string | null>(null);

  // Done step state
  const [commitResult, setCommitResult] = useState<CommitResult | null>(null);

  // ── Template download ────────────────────────────────────────────────────────

  const handleDownloadTemplate = async (format: 'csv' | 'xlsx') => {
    try {
      const resp = await api.get(`/forms/${formId}/bulk-template?format=${format}`, {
        responseType: 'blob',
      });
      const url = URL.createObjectURL(resp.data as Blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${formId}_template.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // silent – browser will show network error
    }
  };

  // ── File selection ───────────────────────────────────────────────────────────

  const acceptFile = (file: File) => {
    if (!file.name.match(/\.(csv|xlsx|xls)$/i)) {
      setUploadError('Only .csv and .xlsx files are supported.');
      return;
    }
    setSelectedFile(file);
    setUploadError(null);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) acceptFile(file);
  };

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) acceptFile(file);
  };

  // ── Upload & parse ───────────────────────────────────────────────────────────

  const handleUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    setUploadError(null);
    try {
      const fd = new FormData();
      fd.append('file', selectedFile);
      const { data } = await api.post<PreviewResult>(
        `/forms/${formId}/bulk-preview`,
        fd,
        { headers: { 'Content-Type': 'multipart/form-data' } },
      );
      setPreview(data);
      setEditedRows(data.rows.map((r) => ({ ...r })));
      setStep('preview');
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Failed to parse file.';
      setUploadError(msg);
    } finally {
      setUploading(false);
    }
  };

  // ── Inline cell edit ─────────────────────────────────────────────────────────

  const handleCellEdit = (rowIdx: number, key: string, value: string) => {
    setEditedRows((prev) => {
      const next = [...prev];
      next[rowIdx] = { ...next[rowIdx], [key]: value };
      return next;
    });
  };

  const handleDeleteRow = (rowIdx: number) => {
    setEditedRows((prev) => prev.filter((_, i) => i !== rowIdx));
  };

  // ── Commit ───────────────────────────────────────────────────────────────────

  const handleCommit = async () => {
    setCommitting(true);
    setCommitError(null);
    try {
      const { data } = await api.post<CommitResult>(`/forms/${formId}/bulk-commit`, {
        rows: editedRows,
      });
      setCommitResult(data);
      setStep('done');
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Commit failed.';
      setCommitError(msg);
    } finally {
      setCommitting(false);
    }
  };

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <div className="animate-fade-in" style={{ maxWidth: 1100, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: '1.75rem' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 600, marginBottom: 2 }}>
          Bulk Upload
        </h1>
        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>
          Form: <code style={{ fontFamily: 'monospace' }}>{formId}</code>
        </p>
      </div>

      {/* Step indicator */}
      <StepIndicator step={step} />

      {/* ── Step 1: Upload ── */}
      {step === 'upload' && (
        <div className="glass" style={{ borderRadius: 'var(--radius)', padding: '2rem' }}>
          {/* Template download */}
          <div style={{ marginBottom: '1.75rem' }}>
            <p style={{ fontWeight: 600, marginBottom: '0.6rem' }}>
              1. Download the template
            </p>
            <div style={{ display: 'flex', gap: 10 }}>
              <button
                className="btn-outline"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.85rem' }}
                onClick={() => handleDownloadTemplate('csv')}
              >
                <Download size={14} /> Download CSV
              </button>
              <button
                className="btn-outline"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.85rem' }}
                onClick={() => handleDownloadTemplate('xlsx')}
              >
                <Download size={14} /> Download Excel
              </button>
            </div>
            <p style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem', marginTop: '0.5rem' }}>
              Row 1 = column headers &nbsp;·&nbsp; Row 2 = field hints (delete before uploading if you edit manually)
            </p>
          </div>

          <hr style={{ border: 'none', borderTop: '1px solid var(--color-border)', marginBottom: '1.75rem' }} />

          {/* Drop zone */}
          <p style={{ fontWeight: 600, marginBottom: '0.6rem' }}>2. Upload your filled file</p>
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
            style={{
              border: `2px dashed ${dragOver ? 'var(--color-primary)' : 'var(--color-border)'}`,
              borderRadius: 'var(--radius)',
              padding: '2.5rem',
              textAlign: 'center',
              cursor: 'pointer',
              background: dragOver ? 'rgba(99,102,241,0.05)' : 'transparent',
              transition: 'all 0.15s',
            }}
          >
            <Upload size={32} style={{ color: 'var(--color-text-muted)', marginBottom: '0.75rem', opacity: 0.6 }} />
            {selectedFile ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                <FileText size={16} style={{ color: 'var(--color-primary)' }} />
                <span style={{ fontWeight: 500 }}>{selectedFile.name}</span>
                <button
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)', padding: 0 }}
                  onClick={(e) => { e.stopPropagation(); setSelectedFile(null); }}
                >
                  <X size={14} />
                </button>
              </div>
            ) : (
              <>
                <p style={{ fontWeight: 500, marginBottom: 4 }}>Drag & drop or click to select</p>
                <p style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem' }}>
                  Supports .csv and .xlsx
                </p>
              </>
            )}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.xlsx,.xls"
            style={{ display: 'none' }}
            onChange={onFileChange}
          />

          {uploadError && (
            <div style={{ marginTop: '1rem', color: 'var(--color-danger)', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: 6 }}>
              <AlertCircle size={14} /> {uploadError}
            </div>
          )}

          <div style={{ marginTop: '1.5rem', display: 'flex', justifyContent: 'flex-end' }}>
            <button
              className="btn-primary"
              disabled={!selectedFile || uploading}
              onClick={handleUpload}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
            >
              {uploading ? 'Parsing…' : 'Preview Rows →'}
            </button>
          </div>
        </div>
      )}

      {/* ── Step 2: Preview & Edit ── */}
      {step === 'preview' && preview && (
        <div>
          {/* Parse errors banner */}
          {preview.errors.length > 0 && (
            <div
              className="glass"
              style={{
                borderRadius: 'var(--radius)',
                padding: '1rem 1.25rem',
                marginBottom: '1rem',
                borderLeft: '3px solid var(--color-warning, #f59e0b)',
                background: 'rgba(245,158,11,0.06)',
              }}
            >
              <p style={{ fontWeight: 600, marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: 6 }}>
                <AlertCircle size={15} style={{ color: 'var(--color-warning, #f59e0b)' }} />
                {preview.errors.length} validation warning{preview.errors.length > 1 ? 's' : ''}
              </p>
              <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.82rem', color: 'var(--color-text-muted)' }}>
                {preview.errors.slice(0, 10).map((e, i) => (
                  <li key={i}>{e.message}</li>
                ))}
                {preview.errors.length > 10 && <li>…and {preview.errors.length - 10} more</li>}
              </ul>
            </div>
          )}

          <div className="glass" style={{ borderRadius: 'var(--radius)', overflow: 'hidden' }}>
            {/* Table toolbar */}
            <div style={{ padding: '0.9rem 1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--color-border)' }}>
              <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>
                {editedRows.length} row{editedRows.length !== 1 ? 's' : ''} to import
              </span>
              <div style={{ display: 'flex', gap: 10 }}>
                <button
                  className="btn-outline"
                  style={{ fontSize: '0.8rem', padding: '0.3rem 0.7rem' }}
                  onClick={() => { setStep('upload'); setSelectedFile(null); setPreview(null); }}
                >
                  ← Re-upload
                </button>
                <button
                  className="btn-primary"
                  disabled={editedRows.length === 0 || committing}
                  onClick={handleCommit}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.85rem' }}
                >
                  {committing ? 'Saving…' : `Commit ${editedRows.length} Record${editedRows.length !== 1 ? 's' : ''}`}
                </button>
              </div>
            </div>

            {commitError && (
              <div style={{ padding: '0.75rem 1.25rem', background: 'rgba(239,68,68,0.07)', color: 'var(--color-danger)', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: 6 }}>
                <AlertCircle size={14} /> {commitError}
              </div>
            )}

            {/* Editable grid */}
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
                <thead>
                  <tr style={{ background: 'var(--color-surface)', borderBottom: '2px solid var(--color-border)' }}>
                    <th style={{ ...thStyle, width: 36 }}>#</th>
                    <th style={thStyle}>asset_id</th>
                    {preview.fields.map((f) => (
                      <th key={f.id} style={thStyle} title={f.type}>
                        {f.label}
                        {f.type !== 'text' && (
                          <span style={{ marginLeft: 4, fontSize: '0.7rem', color: 'var(--color-text-muted)', fontWeight: 400 }}>
                            ({f.type})
                          </span>
                        )}
                      </th>
                    ))}
                    <th style={{ ...thStyle, width: 40 }} />
                  </tr>
                </thead>
                <tbody>
                  {editedRows.map((row, rowIdx) => (
                    <tr
                      key={rowIdx}
                      style={{ borderBottom: '1px solid var(--color-border)' }}
                    >
                      <td style={{ ...tdStyle, color: 'var(--color-text-muted)', textAlign: 'center' }}>
                        {row._row}
                      </td>
                      {/* asset_id cell */}
                      <EditableCell
                        value={String(row.asset_id ?? '')}
                        onChange={(v) => handleCellEdit(rowIdx, 'asset_id', v)}
                      />
                      {/* field cells */}
                      {preview.fields.map((f) => (
                        <EditableCell
                          key={f.id}
                          value={String(row[f.id] ?? '')}
                          onChange={(v) => handleCellEdit(rowIdx, f.id, v)}
                        />
                      ))}
                      {/* delete row */}
                      <td style={{ ...tdStyle, textAlign: 'center' }}>
                        <button
                          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)', padding: 2 }}
                          title="Remove row"
                          onClick={() => handleDeleteRow(rowIdx)}
                        >
                          <X size={13} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ── Step 3: Done ── */}
      {step === 'done' && commitResult && (
        <div className="glass" style={{ borderRadius: 'var(--radius)', padding: '2.5rem', textAlign: 'center' }}>
          <CheckCircle size={48} style={{ color: 'var(--color-success, #22c55e)', marginBottom: '1rem' }} />
          <h2 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: '0.5rem' }}>
            {commitResult.created} record{commitResult.created !== 1 ? 's' : ''} created
          </h2>
          {commitResult.errors.length > 0 && (
            <div style={{ marginTop: '1rem', textAlign: 'left', maxWidth: 560, margin: '1rem auto 0' }}>
              <p style={{ fontWeight: 600, color: 'var(--color-danger)', marginBottom: '0.4rem', display: 'flex', alignItems: 'center', gap: 6 }}>
                <AlertCircle size={14} /> {commitResult.errors.length} row{commitResult.errors.length > 1 ? 's' : ''} failed
              </p>
              <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.82rem', color: 'var(--color-text-muted)' }}>
                {commitResult.errors.map((e, i) => (
                  <li key={i}>Row {e.row}: {e.message}</li>
                ))}
              </ul>
            </div>
          )}
          <div style={{ marginTop: '2rem', display: 'flex', gap: 12, justifyContent: 'center' }}>
            <button
              className="btn-outline"
              onClick={() => { setStep('upload'); setSelectedFile(null); setPreview(null); setCommitResult(null); }}
            >
              Upload Another File
            </button>
            <button
              className="btn-primary"
              onClick={() => navigate(`/entities/${formId}/records`)}
            >
              View Records
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Editable Cell ──────────────────────────────────────────────────────────────

function EditableCell({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  const commit = () => {
    setEditing(false);
    onChange(draft);
  };

  if (editing) {
    return (
      <td style={tdStyle}>
        <input
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => { if (e.key === 'Enter') commit(); if (e.key === 'Escape') { setDraft(value); setEditing(false); } }}
          style={{
            width: '100%',
            background: 'var(--color-surface)',
            border: '1px solid var(--color-primary)',
            borderRadius: 4,
            padding: '0.2rem 0.4rem',
            fontSize: '0.82rem',
            color: 'var(--color-text)',
            outline: 'none',
            minWidth: 80,
          }}
        />
      </td>
    );
  }

  return (
    <td
      style={{ ...tdStyle, cursor: 'text' }}
      onClick={() => { setDraft(value); setEditing(true); }}
      title="Click to edit"
    >
      {value || <span style={{ color: 'var(--color-text-muted)', fontStyle: 'italic' }}>—</span>}
    </td>
  );
}

// ── Step Indicator ─────────────────────────────────────────────────────────────

function StepIndicator({ step }: { step: 'upload' | 'preview' | 'done' }) {
  const steps = [
    { key: 'upload', label: 'Upload File' },
    { key: 'preview', label: 'Preview & Edit' },
    { key: 'done', label: 'Done' },
  ];
  const activeIdx = steps.findIndex((s) => s.key === step);

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 0, marginBottom: '1.5rem' }}>
      {steps.map((s, i) => {
        const isActive = i === activeIdx;
        const isDone = i < activeIdx;
        return (
          <div key={s.key} style={{ display: 'flex', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div
                style={{
                  width: 26,
                  height: 26,
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.78rem',
                  fontWeight: 700,
                  background: isDone
                    ? 'var(--color-success, #22c55e)'
                    : isActive
                    ? 'var(--color-primary)'
                    : 'var(--color-border)',
                  color: isDone || isActive ? '#fff' : 'var(--color-text-muted)',
                  transition: 'all 0.2s',
                }}
              >
                {isDone ? <CheckCircle size={13} /> : i + 1}
              </div>
              <span
                style={{
                  fontSize: '0.85rem',
                  fontWeight: isActive ? 600 : 400,
                  color: isActive ? 'var(--color-text)' : 'var(--color-text-muted)',
                }}
              >
                {s.label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div style={{ width: 32, height: 1, background: 'var(--color-border)', margin: '0 8px' }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────────

const thStyle: React.CSSProperties = {
  padding: '0.6rem 0.9rem',
  textAlign: 'left',
  fontWeight: 600,
  color: 'var(--color-text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  fontSize: '0.72rem',
  whiteSpace: 'nowrap',
};

const tdStyle: React.CSSProperties = {
  padding: '0.5rem 0.9rem',
  color: 'var(--color-text)',
  verticalAlign: 'middle',
};
