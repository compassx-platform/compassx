import { useMemo, useState, type ChangeEvent } from 'react';
import { useParams, useLocation } from 'react-router-dom';
import { useScopedNavigate } from '@/lib/appNavigation';
import { useToast, extractApiError } from '@/lib/toast';
import DynamicForm from '@/components/forms/DynamicForm';
import { useForms, useFormSchema } from '@/modules/workflows/hooks/useForm';
import { useEntityRecord, useUpdateEntityRecord } from '@/modules/workflows/hooks/useEntity';
import { useWorkflowTransitions } from '@/modules/workflows/hooks/useWorkflow';
import type { FormValues } from '@/types';

function normalizeInitialValues(data: Record<string, unknown>, assetId: string, status: string | null | undefined) {
  const normalized = Object.entries(data || {}).reduce<FormValues>((acc, [key, value]) => {
    if (value === null || value === undefined) {
      acc[key] = '';
    } else if (Array.isArray(value)) {
      acc[key] = value.map(String);
    } else if (typeof value === 'string') {
      acc[key] = value;
    } else {
      acc[key] = String(value);
    }
    return acc;
  }, {});

  normalized.asset_id = normalized.asset_id || assetId || '';

  if (status) {
    normalized.status = normalized.status || status;
  }

  return normalized;
}

export default function EntityRecordEditor() {
  const navigate = useScopedNavigate();
  const location = useLocation();
  const isPublic = location.pathname.startsWith('/public/');
  const { entity_name, record_id } = useParams<{ entity_name: string; record_id: string }>();

  const { data: forms, isLoading: formsLoading } = useForms();
  const matchingForm = useMemo(
    () => forms?.find((form) => form.entity_name === entity_name) || null,
    [forms, entity_name],
  );

  const formId = matchingForm?.form_id || '';
  const { data: schema, isLoading: schemaLoading, error: schemaError } = useFormSchema(formId);
  const { data: record, isLoading: recordLoading, error: recordError } = useEntityRecord(entity_name || '', record_id ? parseInt(record_id, 10) : 0);
  const updateMut = useUpdateEntityRecord(entity_name || '');
  const transitionsQuery = useWorkflowTransitions(entity_name || '', record?.status || '');
  const [selectedTransition, setSelectedTransition] = useState('');
  const toast = useToast();

  if (!entity_name || !record_id) {
    return <div style={{ padding: '2rem' }}>Missing entity or record identifier.</div>;
  }

  if (formsLoading || recordLoading || (formId && schemaLoading)) {
    return <div style={{ padding: '2rem' }}>Loading editor...</div>;
  }

  if (recordError || !record) {
    return <div style={{ padding: '2rem', color: 'red' }}>Failed to load record.</div>;
  }

  if (!matchingForm) {
    return (
      <div className="animate-fade-in" style={{ maxWidth: 1100, margin: '0 auto', paddingBottom: '3rem' }}>
        <div className="glass" style={{ padding: '2rem', borderRadius: 'var(--radius)' }}>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 600, marginBottom: '0.75rem' }}>No form found for this entity</h1>
          <p style={{ color: 'var(--color-text-muted)' }}>
            Create a form for <strong>{entity_name}</strong> in the builder before editing records through a structured form.
          </p>
        </div>
      </div>
    );
  }

  if (schemaError || !schema) {
    return <div style={{ padding: '2rem', color: 'red' }}>Failed to load form schema.</div>;
  }

  const initialValues = normalizeInitialValues(record.data_json, record.asset_id, record.status);

  const handleSubmit = async (values: FormValues) => {
    try {
      const assetId = Array.isArray(values.asset_id) ? values.asset_id[0] : values.asset_id;
      const status = Array.isArray(values.status) ? values.status[0] : values.status;
      await updateMut.mutateAsync({
        id: record.id,
        asset_id: assetId || record.asset_id,
        data: values,
        status: status || record.status || undefined,
      });
      toast.success('Record updated successfully.');
      // Navigate back to the records list in the correct shell
      navigate(
        isPublic
          ? `/public/entities/${entity_name}/records`
          : `/entities/${entity_name}/records`,
      );
    } catch (err: unknown) {
      toast.error(extractApiError(err));
    }
  };

  const handleApplyTransition = async () => {
    if (!selectedTransition) {
      return;
    }

    try {
      await updateMut.mutateAsync({
        id: record.id,
        asset_id: record.asset_id,
        data: {},
        status: selectedTransition,
      });
      toast.success(`State changed to ${selectedTransition}.`);
      navigate(
        isPublic
          ? `/public/entities/${entity_name}/records`
          : `/entities/${entity_name}/records`,
      );
    } catch (err: unknown) {
      toast.error(extractApiError(err));
    }
  };

  return (
    <div className="animate-fade-in" style={{ maxWidth: 1100, margin: '0 auto', paddingBottom: '3rem' }}>
      <h1 style={{ fontSize: '1.75rem', fontWeight: 600, marginBottom: '0.5rem' }}>
        Edit {entity_name.replace(/_/g, ' ')} Record
      </h1>
      <p style={{ color: 'var(--color-text-muted)', marginBottom: '1.5rem' }}>
        Updating asset {record.asset_id} using form <strong>{formId}</strong>.
      </p>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16, alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <label htmlFor="record-status-transition" style={{ fontWeight: 600, color: 'var(--color-text-muted)' }}>
            Next state:
          </label>
          <select
            id="record-status-transition"
            value={selectedTransition}
            onChange={(event: ChangeEvent<HTMLSelectElement>) => setSelectedTransition(event.target.value)}
            style={{ padding: '0.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--color-border)' }}
          >
            <option value="">Select next state</option>
            {(transitionsQuery.data?.available || []).map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
          <button className="btn-primary" type="button" disabled={!selectedTransition || updateMut.isPending} onClick={handleApplyTransition}>
            Apply
          </button>
        </div>
        {transitionsQuery.isLoading && <div style={{ color: 'var(--color-text-muted)' }}>Loading workflow transitions…</div>}
      </div>

      <div className="glass" style={{ padding: '2rem', borderRadius: 'var(--radius)' }}>
        <DynamicForm
          schema={schema}
          initialValues={initialValues}
          onSubmit={handleSubmit}
          submitLabel="Save Changes"
          loading={updateMut.isPending}
        />
      </div>
    </div>
  );
}

