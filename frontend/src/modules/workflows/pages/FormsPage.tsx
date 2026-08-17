/**
 * FormsPage - lists all form schemas using the business-facing Table.
 * Primary action: "Fill Form" (settled blue link).
 * Secondary actions: Edit, Bulk Upload, Records.
 */
import { useState } from 'react';
import { useScopedNavigate } from '@/lib/appNavigation';
import { Copy, Database, Edit2, FileText, Plus, Search, Table2, Trash2, Upload } from 'lucide-react';
import { useForms, useDeleteForm } from '@/modules/workflows/hooks/useForm';
import { Table } from '@/components/common/Table';
import type { TableColumn, TableAction } from '@/components/common/Table';
import ConfirmDialog from '@/components/common/ConfirmDialog';

interface FormRow {
  form_id: string;
  entity_name: string;
  schema?: { fields?: unknown[] };
}

export default function FormsPage() {
  const navigate = useScopedNavigate();
  const [search, setSearch] = useState('');
  const [formPendingDelete, setFormPendingDelete] = useState<FormRow | null>(null);
  const { data: forms, isLoading, error } = useForms();
  const deleteMutation = useDeleteForm();

  const filtered = (forms ?? []).filter((f: FormRow) => {
    const q = search.trim().toLowerCase();
    return !q || f.form_id.toLowerCase().includes(q) || f.entity_name.toLowerCase().includes(q);
  });

  // Form ID: 22% | Entity: auto (fills remaining) | Fields: 8% | Actions: 13%
  const columns: TableColumn<FormRow>[] = [
    {
      key: 'form_id',
      header: 'Form ID',
      width: '22%',
      render: (row) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, overflow: 'hidden' }}>
          <FileText size={14} color="#1B6EF3" style={{ flexShrink: 0 }} />
          <span style={{ fontWeight: 500, fontFamily: 'monospace', fontSize: '0.875rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {row.form_id}
          </span>
        </div>
      ),
    },
    {
      // No width â€” fills all remaining space
      key: 'entity',
      header: 'Entity',
      render: (row) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, overflow: 'hidden' }}>
          <Database size={13} color="var(--color-text-muted)" style={{ flexShrink: 0 }} />
          <span style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {row.entity_name}
          </span>
        </div>
      ),
    },
    {
      key: 'fields',
      header: 'Fields',
      width: '8%',
      align: 'center',
      render: (row) => {
        const count = row.schema?.fields?.length ?? 0;
        return (
          <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            minWidth: 28,
            padding: '2px 8px',
            borderRadius: 4,
            fontSize: '0.78rem',
            fontWeight: 600,
            background: '#E8F1FF',
            color: '#1B6EF3',
            border: 'none',
          }}>
            {count}
          </span>
        );
      },
    },
  ];

  const visibleActions: TableAction<FormRow>[] = [
    {
      label: 'Edit',
      icon: Edit2,
      onClick: (row) => navigate(`/forms/builder/${row.form_id}`),
    },
    {
      label: 'Clone',
      icon: Copy,
      onClick: (row) => navigate(`/forms/builder?clone=${encodeURIComponent(row.form_id)}`),
    },
    {
      label: 'Bulk Upload',
      icon: Upload,
      onClick: (row) => navigate(`/forms/${row.form_id}/bulk-upload`),
    },
    {
      label: 'Records',
      icon: Table2,
      onClick: (row) => navigate(`/entities/${row.entity_name}/records`),
    },
  ];

  const rowActions: TableAction<FormRow>[] = [
    {
      label: 'Delete',
      icon: Trash2,
      variant: 'danger',
      onClick: (row) => setFormPendingDelete(row),
    },
  ];

  async function handleDeleteForm(row: FormRow) {
    try {
      await deleteMutation.mutateAsync(row.form_id);
      setFormPendingDelete(null);
    } catch {
      setFormPendingDelete(null);
    }
  }

  const toolbar = (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
      <div>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 600, marginBottom: '0.25rem' }}>Forms</h1>
        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
          Form schemas built on top of entity definitions.
        </p>
      </div>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <label
          className="glass"
          style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0.5rem 0.85rem', borderRadius: 'var(--radius)', minWidth: 220 }}
        >
          <Search size={14} color="var(--color-text-muted)" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search formsâ€¦"
            style={{ background: 'transparent', border: 'none', outline: 'none', color: 'var(--color-text)', fontSize: '0.875rem', width: '100%' }}
          />
        </label>
        <button
          type="button"
          className="btn-primary"
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
          onClick={() => navigate('/forms/builder')}
        >
          <Plus size={14} /> New Form
        </button>
      </div>
    </div>
  );

  const emptyState = (
    <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--color-text-muted)' }}>
      <FileText size={28} style={{ marginBottom: '0.75rem', opacity: 0.3 }} />
      <div style={{ fontWeight: 600, marginBottom: '0.4rem', color: 'var(--color-text)' }}>
        {forms?.length ? 'No matching forms' : 'No forms yet'}
      </div>
      <p style={{ fontSize: '0.85rem', maxWidth: 380, margin: '0 auto 1.25rem' }}>
        {forms?.length
          ? 'Try a different search term.'
          : 'Create a form using the visual builder. You must create an entity first.'}
      </p>
      {!forms?.length && (
        <button
          type="button"
          className="btn-primary"
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.85rem' }}
          onClick={() => navigate('/forms/builder')}
        >
          <Plus size={14} /> New Form
        </button>
      )}
    </div>
  );

  if (error) {
    return (
      <div style={{ padding: '2rem', color: 'var(--color-danger)' }}>
        Failed to load forms.
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <Table<FormRow>
        columns={columns}
        rows={filtered}
        keyExtractor={(f) => f.form_id}
        primaryAction={{
          label: 'Fill Form',
          onClick: (row) => navigate(`/forms/${row.form_id}/view`),
        }}
        visibleActions={visibleActions}
        rowActions={rowActions}
        emptyState={emptyState}
        loading={isLoading}
        toolbar={toolbar}
        actionsColumnWidth="22%"
      />
      {formPendingDelete && (
        <ConfirmDialog
          title="Delete form"
          message={`Delete form "${formPendingDelete.form_id}"? This cannot be undone.`}
          confirmLabel="Delete"
          onCancel={() => setFormPendingDelete(null)}
          onConfirm={() => handleDeleteForm(formPendingDelete)}
          isLoading={deleteMutation.isPending}
        />
      )}
    </div>
  );
}

