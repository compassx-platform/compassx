/**
 * DataPanel — dataset management surface for the draft-only Data tab.
 */

import { useEffect, useState } from 'react';
import { Database, Plus, MoreVertical, Copy, Trash2, Download, Pencil, ChevronRight, ArrowLeft } from 'lucide-react';
import { useDashboardStore } from '@/modules/dashboards/stores/dashboardStore';
import { useExportDataset, useSaveDashboard } from '@/modules/dashboards/hooks/useDashboard';
import { useToast } from '@/lib/toast';
import { randomUUID } from '@/lib/utils';
import DatasetEditor from './DatasetEditor';
import type { Dataset } from '@/types/dashboard';

interface Props {
  onBackToPages?: () => void;
}

export default function DataPanel({ onBackToPages }: Props) {
  const toast = useToast();
  const { activeDashboard, addDataset, updateDataset, deleteDataset, cloneDataset } = useDashboardStore();
  const exportMutation = useExportDataset();
  const saveDashboardMutation = useSaveDashboard();

  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [editingDataset, setEditingDataset] = useState<Dataset | null>(null);

  const datasets = activeDashboard?.datasets ?? [];

  useEffect(() => {
    setOpenMenuId(null);
    setEditingDataset((current) => {
      if (!current) return null;
      const match = datasets.find((dataset) => dataset.id === current.id);
      return match ?? null;
    });
  }, [activeDashboard?.id, datasets]);

  function handleNew() {
    const newDs: Dataset = {
      id: randomUUID(),
      dashboardId: activeDashboard!.id,
      name: `Dataset ${datasets.length + 1}`,
      sql: 'SELECT * FROM ',
      params: [],
      schema: [],
    };
    addDataset(newDs);
    setEditingDataset(newDs);
  }

  async function handleExport(id: string, format: 'csv' | 'tsv' | 'excel') {
    setOpenMenuId(null);
    try {
      await exportMutation.mutateAsync({ datasetId: id, format });
    } catch {
      toast.error('Export failed');
    }
  }

  function handleDelete(id: string) {
    setOpenMenuId(null);
    const inUse = activeDashboard?.widgets.some((w) => w.chartConfig?.datasetId === id);
    if (inUse) {
      toast.error('Dataset is used by one or more widgets');
      return;
    }
    deleteDataset(id);
  }

  async function persistDataset(datasetId: string, patch: Partial<Dataset>) {
    if (!activeDashboard) return;

    const nextDatasets = activeDashboard.datasets.map((dataset) =>
      dataset.id === datasetId ? { ...dataset, ...patch } : dataset
    );

    updateDataset(datasetId, patch);

    try {
      await saveDashboardMutation.mutateAsync({
        ...activeDashboard,
        datasets: nextDatasets,
      });
      toast.success('Dataset saved');
    } catch {
      toast.error('Failed to save dataset');
    }
  }

  return (
    <div style={{ flex: 1, minWidth: 0, minHeight: 0, height: '100%', background: 'var(--color-bg)', display: 'flex', alignSelf: 'stretch', overflow: 'hidden' }}>
      <div style={{ display: 'flex', flex: 1, minWidth: 0, minHeight: 0, height: '100%', alignItems: 'stretch' }}>
        <div style={{
          width: 290,
          minHeight: 0,
          flexShrink: 0,
          borderRight: '1px solid var(--color-border)',
          background: 'var(--color-surface)',
          display: 'flex',
          flexDirection: 'column',
        }}>
          <div style={{ padding: '14px 14px 10px', display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {onBackToPages && (
                <button className="btn-icon" title="Back to pages" onClick={onBackToPages}>
                  <ArrowLeft size={16} />
                </button>
              )}
              <span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--color-text)' }}>Datasets</span>
            </div>

            <button
              className="btn btn-secondary"
              style={{ justifyContent: 'flex-start', padding: '8px 12px', fontSize: '0.8rem' }}
              onClick={handleNew}
            >
              <Plus size={14} style={{ marginRight: 6 }} /> Add dataset
            </button>
            <button
              className="btn btn-secondary"
              style={{ justifyContent: 'flex-start', padding: '8px 12px', fontSize: '0.8rem' }}
              onClick={handleNew}
            >
              <Plus size={14} style={{ marginRight: 6 }} /> Add SQL dataset
            </button>
          </div>

          <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', borderTop: '1px solid var(--color-border)' }}>
            {datasets.length === 0 ? (
              <div style={{ padding: '24px 16px', textAlign: 'center' }}>
                <Database size={24} style={{ opacity: 0.2, marginBottom: 8 }} />
                <div style={{ fontSize: '0.77rem', color: 'var(--color-text-muted)' }}>No datasets yet</div>
              </div>
            ) : (
              datasets.map((ds) => (
                <div
                  key={ds.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '9px 12px',
                    cursor: 'pointer',
                    borderBottom: '1px solid var(--color-border)',
                    position: 'relative',
                    background: editingDataset?.id === ds.id ? 'var(--color-primary-bg)' : undefined,
                  }}
                  onMouseEnter={(e) => {
                    if (editingDataset?.id !== ds.id) {
                      e.currentTarget.style.background = 'var(--color-surface-hover)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (editingDataset?.id !== ds.id) {
                      e.currentTarget.style.background = '';
                    }
                  }}
                  onClick={() => setEditingDataset(ds)}
                >
                  <Database
                    size={13}
                    color={editingDataset?.id === ds.id ? 'var(--color-primary)' : 'var(--color-primary)'}
                    style={{ flexShrink: 0 }}
                  />
                  <span style={{
                    flex: 1,
                    fontSize: '0.8rem',
                    fontWeight: editingDataset?.id === ds.id ? 600 : 400,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}>
                    {ds.name}
                  </span>

                  <div onClick={(e) => e.stopPropagation()} style={{ position: 'relative', flexShrink: 0 }}>
                    <button
                      className="btn-icon"
                      style={{ opacity: 0.5, padding: '2px' }}
                      onClick={() => setOpenMenuId(openMenuId === ds.id ? null : ds.id)}
                    >
                      <MoreVertical size={12} />
                    </button>
                    {openMenuId === ds.id && (
                      <div className="dropdown-menu" style={{ right: 0, top: 26, minWidth: 160, zIndex: 300 }}>
                        <button className="dropdown-item" onClick={() => { setOpenMenuId(null); setEditingDataset(ds); }}>
                          <Pencil size={12} style={{ marginRight: 6 }} /> Edit query
                        </button>
                        <button className="dropdown-item" onClick={() => { setOpenMenuId(null); cloneDataset(ds.id); }}>
                          <Copy size={12} style={{ marginRight: 6 }} /> Clone
                        </button>
                        <div className="dropdown-divider" />
                        <div style={{ padding: '4px 12px', fontSize: '0.72rem', color: 'var(--color-text-muted)', fontWeight: 600 }}>
                          Download
                        </div>
                        <button className="dropdown-item" onClick={() => handleExport(ds.id, 'csv')}>
                          <Download size={12} style={{ marginRight: 6 }} /> CSV
                        </button>
                        <button className="dropdown-item" onClick={() => handleExport(ds.id, 'tsv')}>
                          <Download size={12} style={{ marginRight: 6 }} /> TSV
                        </button>
                        <button className="dropdown-item" onClick={() => handleExport(ds.id, 'excel')}>
                          <Download size={12} style={{ marginRight: 6 }} /> Excel
                        </button>
                        <div className="dropdown-divider" />
                        <button className="dropdown-item dropdown-item-danger" onClick={() => handleDelete(ds.id)}>
                          <Trash2 size={12} style={{ marginRight: 6 }} /> Delete
                        </button>
                      </div>
                    )}
                  </div>

                  <ChevronRight size={11} style={{ opacity: 0.35, flexShrink: 0 }} />
                </div>
              ))
            )}
          </div>
        </div>

        <div style={{ flex: 1, minWidth: 0, minHeight: 0, height: '100%', padding: 8, display: 'flex', alignItems: 'stretch' }}>
          {editingDataset ? (
            <div style={{ flex: 1, minHeight: 0, height: '100%', border: '1px solid var(--color-border)', borderRadius: 8, overflow: 'hidden', display: 'flex', alignSelf: 'stretch' }}>
              <DatasetEditor
                dataset={editingDataset}
                onClose={() => setEditingDataset(null)}
                onDraftChange={(patch) => {
                  updateDataset(editingDataset.id, patch);
                  setEditingDataset((current) => current ? { ...current, ...patch } : current);
                }}
                onSave={async (patch) => {
                  await persistDataset(editingDataset.id, patch);
                  setEditingDataset((current) => current ? { ...current, ...patch } : current);
                }}
                onSchemaChange={(schema) => {
                  updateDataset(editingDataset.id, { schema });
                  setEditingDataset((current) => current ? { ...current, schema } : current);
                }}
              />
            </div>
          ) : (
            <div style={{
              flex: 1,
              minHeight: 0,
              height: '100%',
              border: '1px solid var(--color-border)',
              borderRadius: 8,
              background: 'var(--color-surface)',
              display: 'flex',
              alignItems: 'flex-start',
              padding: '64px 72px',
            }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 18, maxWidth: 520 }}>
                <ArrowLeft size={44} strokeWidth={1.25} style={{ color: '#c7d3de', flexShrink: 0 }} />
                <div>
                  <div style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--color-text)', marginBottom: 10 }}>
                    Add data to get going
                  </div>
                  <div style={{ fontSize: '0.95rem', lineHeight: 1.6, color: 'var(--color-text-muted)' }}>
                    Create a dataset for your dashboard by writing your own SQL query or selecting an existing table.
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

