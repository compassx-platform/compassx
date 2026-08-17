import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useFormSchema } from '@/modules/workflows/hooks/useForm';
import DynamicForm from '@/components/forms/DynamicForm';
import api from '@/lib/api';
import { useToast, extractApiError } from '@/lib/toast';
import type { FormValues } from '@/types';

export default function FormViewer() {
  const params = useParams<{ formId?: string; form_id?: string }>();
  const formId = params.formId || params.form_id || '';
  const toast = useToast();

  const { data: schema, isLoading, error: loadError } = useFormSchema(formId);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formKey, setFormKey] = useState(0);

  if (!formId) return <div style={{ padding: '2rem' }}>No form ID provided.</div>;
  if (isLoading) return <div style={{ padding: '2rem', color: 'var(--color-text-muted)' }}>Loading form…</div>;
  if (loadError || !schema) return (
    <div style={{ padding: '2rem', color: 'var(--color-danger)' }}>
      Failed to load form. Ensure the form ID is correct.
    </div>
  );

  const handleSubmit = async (values: FormValues) => {
    setIsSubmitting(true);
    try {
      const assetId = Array.isArray(values.asset_id) ? values.asset_id[0] || null : values.asset_id || null;
      await api.post(`/entities/${schema.entity}/records`, {
        asset_id: assetId,
        data: values,
      });
      toast.success('Form submitted successfully.');
      setFormKey((k) => k + 1);
    } catch (err: unknown) {
      toast.error(extractApiError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="animate-fade-in" style={{ maxWidth: 1100, margin: '0 auto', paddingBottom: '3rem' }}>
      <h1 style={{ fontSize: '1.75rem', fontWeight: 600, marginBottom: '1.5rem', textTransform: 'capitalize' }}>
        {schema.entity.replace(/_/g, ' ')} Form
      </h1>

      <div className="glass" style={{ padding: '2rem', borderRadius: 'var(--radius)' }}>
        <DynamicForm
          key={formKey}
          schema={schema}
          initialValues={{}}
          onSubmit={handleSubmit}
          submitLabel="Submit"
          loading={isSubmitting}
        />
      </div>
    </div>
  );
}
