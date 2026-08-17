import { useMemo, useState, type FormEvent } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { Eye, FileSpreadsheet, Upload, X } from 'lucide-react';
import { useScopedNavigate } from '@/lib/appNavigation';
import api from '@/lib/api';
import { extractApiError, useToast } from '@/lib/toast';
import { AppTable, type AppTableColumn } from '@/components/common/AppTable';
import {
  useAssetImportFiles,
  useAssetImportFilePreview,
  useAssetImportJob,
  useAssetImportJobs,
  useAssetHierarchyMappingSummary,
  useAssetTypeMatchSummary,
  useCreateAssetImportJob,
  type ImportFileSummary,
  type ImportJob,
} from '@/modules/asset_manager/hooks/useAssetImport';

export default function AssetImportPage({ startNew = false }: { startNew?: boolean } = {}) {
  const navigate = useScopedNavigate();
  const { jobId: routeJobId } = useParams<{ jobId?: string }>();
  const toast = useToast();
  const queryClient = useQueryClient();
  const createJob = useCreateAssetImportJob();
  const [newJobId, setNewJobId] = useState<string>();
  const jobId = routeJobId ?? newJobId;
  const [name, setName] = useState('Asset import');
  const [industry, setIndustry] = useState('generic');
  const [flowError, setFlowError] = useState<string | null>(null);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [previewFileId, setPreviewFileId] = useState<string | undefined>();
  const [selectedAssetTypeColumn, setSelectedAssetTypeColumn] = useState('');
  const [selectedParentAssetColumn, setSelectedParentAssetColumn] = useState('');
  const { data: jobs = [], isLoading: jobsLoading } = useAssetImportJobs();
  const { data: selectedJob } = useAssetImportJob(jobId);
  const { data: selectedFiles = [], isLoading: filesLoading } = useAssetImportFiles(jobId);
  const { data: filePreview, isLoading: previewLoading } = useAssetImportFilePreview(jobId, previewFileId);
  const showImportFlow = startNew || Boolean(routeJobId);
  const previewSheet = filePreview?.sheets?.[0];
  const availableColumns = useMemo(() => {
    const columns = selectedFiles.flatMap((file) => file.column_names ?? []);
    return Array.from(new Set(columns));
  }, [selectedFiles]);
  const detectedAssetTypeColumn = useMemo(() => (
    availableColumns.find((column) => column.trim().toLowerCase() === 'asset_type') ?? ''
  ), [availableColumns]);
  const assetTypeColumn = detectedAssetTypeColumn || selectedAssetTypeColumn;
  const needsAssetTypeColumnSelection = selectedFiles.length > 0 && !detectedAssetTypeColumn;
  const { data: assetTypeMatch, isLoading: assetTypeMatchLoading } = useAssetTypeMatchSummary(jobId, assetTypeColumn);
  const detectedParentAssetColumn = useMemo(() => (
    availableColumns.find((column) => {
      const normalized = column.trim().toLowerCase().replace(/\s+/g, '_');
      return ['parent_asset', 'parent_asset_name', 'parent_equipment_name', 'parent'].includes(normalized);
    }) ?? ''
  ), [availableColumns]);
  const parentAssetColumn = detectedParentAssetColumn || selectedParentAssetColumn;
  const { data: hierarchyMapping, isLoading: hierarchyMappingLoading } = useAssetHierarchyMappingSummary(
    jobId,
    assetTypeColumn,
    parentAssetColumn,
  );
  const needsParentAssetColumnSelection = Boolean(
    assetTypeColumn
    && hierarchyMapping?.parent_column_required
    && !detectedParentAssetColumn
    && !selectedParentAssetColumn
  );

  const jobColumns: AppTableColumn<ImportJob>[] = useMemo(() => [
    { key: 'name', header: 'Job', render: (job) => <span style={{ fontWeight: 600 }}>{job.name}</span> },
    { key: 'status', header: 'Status', render: (job) => job.status },
    { key: 'stage', header: 'Stage', render: (job) => job.stage },
    { key: 'records', header: 'Records', render: (job) => `${job.imported_records || 0}/${job.total_records || job.parsed_records || 0}` },
    { key: 'updated', header: 'Updated', render: (job) => job.updated_at ? new Date(job.updated_at).toLocaleString() : '-' },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      className: 'app-table-actions',
      render: (job) => (
        <button className="ghost-icon-btn" title="Open import" onClick={() => navigate(`/assets/import/${job.import_job_id}`)}>
          Open
        </button>
      ),
    },
  ], [navigate]);
  const fileColumns: AppTableColumn<ImportFileSummary>[] = useMemo(() => [
    { key: 'file_name', header: 'File', render: (file) => <span style={{ fontWeight: 600 }}>{file.file_name}</span> },
    { key: 'status', header: 'Status', render: (file) => file.status },
    { key: 'sheet', header: 'Sheet', render: (file) => file.active_sheet ?? '-' },
    { key: 'size', header: 'Size', render: (file) => `${file.file_size_kb} KB` },
    { key: 'uploaded', header: 'Uploaded', render: (file) => file.uploaded_at ? new Date(file.uploaded_at).toLocaleString() : '-' },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      className: 'app-table-actions',
      render: (file) => (
        <button className="ghost-icon-btn" title="Preview data" onClick={() => setPreviewFileId(file.file_id)}>
          <Eye size={15} />
        </button>
      ),
    },
  ], []);

  async function ensureJob(file: File) {
    if (jobId) return jobId;
    const ext = file.name.split('.').pop()?.toLowerCase() || 'csv';
    const job = await createJob.mutateAsync({ name, industry_tag: industry, source_format: ext });
    setNewJobId(job.import_job_id);
    navigate(`/assets/import/${job.import_job_id}`);
    return job.import_job_id;
  }

  async function handleFile(file: File) {
    try {
      setFlowError(null);
      const targetJobId = await ensureJob(file);
      const form = new FormData();
      form.append('file', file);
      await api.post(`/asset-imports/${targetJobId}/files`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setUploadFile(null);
      setShowUploadModal(false);
      queryClient.invalidateQueries({ queryKey: ['asset-imports'] });
      queryClient.invalidateQueries({ queryKey: ['asset-imports', targetJobId] });
      queryClient.invalidateQueries({ queryKey: ['asset-imports', targetJobId, 'files'] });
    } catch (e: unknown) {
      notifyError(e, 'Upload failed');
    }
  }

  function notifyError(error: unknown, fallback: string) {
    const message = extractApiError(error) || fallback;
    setFlowError(message);
    toast.error(message);
  }

  async function submitUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!uploadFile) return;
    await handleFile(uploadFile);
  }

  return (
    <div className="page-section asset-page" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="db-page-header asset-import-header">
        <div className="asset-import-breadcrumb" aria-label="Breadcrumb">
          <button type="button" onClick={() => navigate('/assets')} className="asset-breadcrumb-link">Assets</button>
          <span>/</span>
          <button type="button" onClick={() => navigate('/assets/import')} className="asset-breadcrumb-link">Bulk Upload</button>
          {selectedJob && (
            <>
              <span>/</span>
              <span className="asset-breadcrumb-current">{selectedJob.name}</span>
            </>
          )}
        </div>
        <div className="asset-import-title-row">
          <div className="asset-import-title">
            <FileSpreadsheet size={22} color="var(--color-primary)" />
            <div>
              <h1 className="db-page-title">Import Assets</h1>
              <div className="asset-summary-bar" style={{ marginTop: 4 }}>
                <span>Upload</span>
                <span>Map</span>
                <span>Dry run</span>
                <span>Approve</span>
                <span>Import</span>
              </div>
            </div>
          </div>
          {!showImportFlow && (
            <button className="btn btn-primary" onClick={() => navigate('/assets/import/new')}>
              <Upload size={14} /> Start new import
            </button>
          )}
        </div>
      </div>

      {flowError && (
        <div
          role="alert"
          style={{
            padding: '10px 12px',
            border: '1px solid rgba(239,68,68,0.35)',
            borderRadius: 6,
            background: 'rgba(239,68,68,0.08)',
            color: 'var(--color-danger)',
            fontSize: 13,
            whiteSpace: 'pre-wrap',
          }}
        >
          {flowError}
        </div>
      )}

      {!showImportFlow && (
        <>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
              {jobs.length} import job{jobs.length === 1 ? '' : 's'}
            </div>
          </div>
          <AppTable
            columns={jobColumns}
            rows={jobs}
            rowKey={(job) => job.import_job_id}
            onRowClick={(job) => navigate(`/assets/import/${job.import_job_id}`)}
            emptyText="No asset import jobs yet."
            isLoading={jobsLoading}
          />
        </>
      )}

      {showImportFlow && (
        <section className="asset-form-section asset-import-flat-section">
          <div className="asset-section-header">
            <div>
              <h3 className="asset-form-section-title">1. Files</h3>
              <p className="asset-section-subtitle">Upload CSV or Excel files for this import.</p>
            </div>
            <button className="btn btn-primary" onClick={() => setShowUploadModal(true)}>
              <Upload size={14} /> Upload file
            </button>
          </div>
          <AppTable
            columns={fileColumns}
            rows={selectedFiles}
            rowKey={(file) => file.file_id}
            emptyText="No files uploaded yet."
            isLoading={filesLoading}
          />
          {selectedFiles.length > 0 && (
            <div className="asset-import-detection-card">
              <div className="asset-import-detection-header">
                <div>
                  <h3 className="asset-form-section-title">2. Asset type column</h3>
                  <p className="asset-section-subtitle">
                    {detectedAssetTypeColumn
                      ? `Detected "${detectedAssetTypeColumn}" as the asset type column.`
                      : 'We could not find an asset_type column. Select the column that contains asset type values.'}
                  </p>
                </div>
                {needsAssetTypeColumnSelection ? (
                  <select
                    className="form-input asset-import-column-select"
                    value={selectedAssetTypeColumn}
                    onChange={(event) => setSelectedAssetTypeColumn(event.target.value)}
                  >
                    <option value="">Select asset type column</option>
                    {availableColumns.map((column) => <option key={column} value={column}>{column}</option>)}
                  </select>
                ) : (
                  <span className="asset-import-detected-pill">{assetTypeColumn}</span>
                )}
              </div>
              {assetTypeColumn && (
                <div className="asset-import-match-summary">
                  {assetTypeMatchLoading && <div className="asset-section-subtitle">Matching rows with asset types...</div>}
                  {!assetTypeMatchLoading && assetTypeMatch && (
                    <>
                      <div className="asset-import-match-stats">
                        <span><strong>{assetTypeMatch.matched_rows}</strong> matched</span>
                        <span><strong>{assetTypeMatch.unmatched_rows}</strong> unmatched</span>
                        <span><strong>{assetTypeMatch.total_rows}</strong> total rows</span>
                      </div>
                      <div className="asset-import-match-grid">
                        <div>
                          <h4>Matched asset types</h4>
                          {assetTypeMatch.matched_types.length > 0 ? (
                            <ul>
                              {assetTypeMatch.matched_types.map((type) => (
                                <li key={type.asset_type_id}>
                                  <span>{type.name}</span>
                                  <strong>{type.matched_rows}</strong>
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <p>No asset type names matched.</p>
                          )}
                        </div>
                        <div>
                          <h4>Unmatched values</h4>
                          {assetTypeMatch.unmatched_values.length > 0 ? (
                            <ul>
                              {assetTypeMatch.unmatched_values.map((item) => (
                                <li key={item.value}>
                                  <span>{item.value}</span>
                                  <strong>{item.rows}</strong>
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <p>All rows matched asset types.</p>
                          )}
                        </div>
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          )}
          {assetTypeColumn && hierarchyMapping && (
            <div className="asset-import-detection-card">
              <div className="asset-import-detection-header">
                <div>
                  <h3 className="asset-form-section-title">3. Parent asset mapping</h3>
                  <p className="asset-section-subtitle">
                    {hierarchyMapping.parent_column_required
                      ? 'Non-root asset types need a parent asset. Match parent values from the file with existing assets.'
                      : 'Only root asset types are present, so parent asset mapping is not required.'}
                  </p>
                </div>
                {hierarchyMapping.parent_column_required && (
                  detectedParentAssetColumn ? (
                    <span className="asset-import-detected-pill">{detectedParentAssetColumn}</span>
                  ) : (
                    <select
                      className="form-input asset-import-column-select"
                      value={selectedParentAssetColumn}
                      onChange={(event) => setSelectedParentAssetColumn(event.target.value)}
                    >
                      <option value="">Select parent asset column</option>
                      {availableColumns.map((column) => <option key={column} value={column}>{column}</option>)}
                    </select>
                  )
                )}
              </div>
              {needsParentAssetColumnSelection && (
                <div className="asset-section-subtitle">Select the parent asset column to calculate parent matches.</div>
              )}
              {hierarchyMappingLoading && <div className="asset-section-subtitle">Preparing hierarchy order...</div>}
              {!hierarchyMappingLoading && !needsParentAssetColumnSelection && (
                <div className="asset-import-hierarchy-steps">
                  {hierarchyMapping.steps.map((step, index) => (
                    <div className="asset-import-hierarchy-step" key={step.asset_type_id}>
                      <div className="asset-import-step-index">{index + 1}</div>
                      <div className="asset-import-step-content">
                        <div className="asset-import-step-header">
                          <div>
                            <h4>{step.name}</h4>
                            <p>{step.is_root ? 'Root asset type — no parent needed' : 'Parent asset required'}</p>
                          </div>
                          <button className="btn btn-primary" disabled={step.ready_to_add_rows === 0}>
                            Add {step.ready_to_add_rows} asset{step.ready_to_add_rows === 1 ? '' : 's'}
                          </button>
                        </div>
                        <div className="asset-import-match-stats">
                          <span><strong>{step.rows}</strong> found in file</span>
                          {!step.is_root && <span><strong>{step.parent_matched_rows}</strong> parent matched</span>}
                          {!step.is_root && <span><strong>{step.parent_unmatched_rows}</strong> parent unmatched</span>}
                          <span><strong>{step.ready_to_add_rows}</strong> ready to add</span>
                        </div>
                        {!step.is_root && step.unmatched_parent_values.length > 0 && (
                          <div className="asset-import-unmatched-inline">
                            <strong>Unmatched parents:</strong>
                            {step.unmatched_parent_values.map((item) => (
                              <span key={item.value}>{item.value} ({item.rows})</span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </section>
      )}

      {previewFileId && (
        <div className="asset-sheet-backdrop" onClick={() => setPreviewFileId(undefined)}>
          <aside
            className="asset-sheet-panel"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="asset-file-preview-title"
          >
            <div className="asset-sheet-header">
              <div>
                <h2 id="asset-file-preview-title" className="asset-sheet-title">Data preview</h2>
                <p className="asset-sheet-description">
                  {filePreview?.file_name ?? 'Loading file preview...'}
                </p>
              </div>
              <button className="btn-icon" onClick={() => setPreviewFileId(undefined)} aria-label="Close preview">
                <X size={16} />
              </button>
            </div>
            <div className="asset-sheet-body">
              {previewLoading && <div className="app-table-empty">Loading preview...</div>}
              {!previewLoading && previewSheet && (
                <>
                  <div className="asset-summary-bar" style={{ marginBottom: 12 }}>
                    <span>{previewSheet.sheet_name}</span>
                    <span>{previewSheet.total_rows} rows</span>
                    <span>{previewSheet.total_columns} columns</span>
                  </div>
                  <div className="asset-import-preview-table-wrap">
                    <table className="data-table asset-import-preview-table">
                      <thead>
                        <tr>
                          {previewSheet.column_names.map((column) => <th key={column}>{column}</th>)}
                        </tr>
                      </thead>
                      <tbody>
                        {previewSheet.preview_rows.map((row, rowIndex) => (
                          <tr key={rowIndex}>
                            {previewSheet.column_names.map((column, columnIndex) => (
                              <td key={`${rowIndex}-${column}`}>{String(row[columnIndex] ?? '')}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
              {!previewLoading && !previewSheet && <div className="app-table-empty">No preview available.</div>}
            </div>
          </aside>
        </div>
      )}

      {showUploadModal && (
        <div className="modal-backdrop" onClick={() => setShowUploadModal(false)}>
          <div className="modal-panel" onClick={(event) => event.stopPropagation()} style={{ width: 460 }}>
            <div className="modal-header">
              <h2 className="modal-title">Upload import file</h2>
              <button className="btn-icon" onClick={() => setShowUploadModal(false)} aria-label="Close upload dialog">
                <X size={16} />
              </button>
            </div>
            <form className="modal-body" onSubmit={submitUpload}>
              {!jobId && (
                <div className="asset-form-grid">
                  <div>
                    <label className="form-label">Import name</label>
                    <input className="form-input" value={name} onChange={(event) => setName(event.target.value)} />
                  </div>
                  <div>
                    <label className="form-label">Industry</label>
                    <select className="form-input" value={industry} onChange={(event) => setIndustry(event.target.value)}>
                      {['generic', 'renewable', 'thermal', 'oil_gas'].map((item) => <option key={item} value={item}>{item}</option>)}
                    </select>
                  </div>
                </div>
              )}
              <div className="form-field">
                <label className="form-label">File</label>
                <input
                  className="form-input"
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
                />
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowUploadModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={!uploadFile || createJob.isPending}>
                  <Upload size={14} /> Upload file
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
