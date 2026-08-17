/**
 * BreakdownForm — schema-driven breakdown event entry form.
 *
 * Stays on the same page after submit.
 * Shows an inline success/error banner and resets the form so the user
 * can immediately submit another event.
 */

import { useState } from 'react';
import { useScopedNavigate } from '@/lib/appNavigation';
import { useToast, extractApiError } from '@/lib/toast';
import { RefreshCw, ExternalLink, List } from 'lucide-react';
import { useFormSchema } from '@/modules/workflows/hooks/useForm';
import DynamicForm from '@/components/forms/DynamicForm';
import api from '@/lib/api';
import type { FormValues } from '@/types';

const FORM_ID = 'breakdown_event_form';

export default function BreakdownForm() {
  const navigate = useScopedNavigate();
  const toast = useToast();
  const { data: schema, isLoading, error, refetch } = useFormSchema(FORM_ID);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formKey, setFormKey] = useState(0);

  /* ── Submit handler ── */
  const handleSubmit = async (values: FormValues) => {
    if (!schema) return;
    setIsSubmitting(true);
    try {
      const assetValue = values.inverter_name ?? values.asset_id;
      const assetId = Array.isArray(assetValue) ? assetValue[0] || null : assetValue || null;
      await api.post(`/entities/${schema.entity}/records`, {
        asset_id: assetId,
        data: values,
      });
      toast.success('Breakdown event recorded successfully.');
      setFormKey((k) => k + 1);
    } catch (err: any) {
      toast.error(extractApiError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  /* ── Loading ── */
  if (isLoading) {
    return (
      <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--color-text-muted)' }}>
        Loading form schema…
      </div>
    );
  }

  /* ── Error / schema not seeded ── */
  if (error || !schema) {
    return (
      <div className="animate-fade-in" style={{ maxWidth: 640, margin: '3rem auto' }}>
        <div className="glass" style={{ padding: '2rem', borderRadius: 'var(--radius)', textAlign: 'center' }}>
          <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>⚠️</div>
          <h2 style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Form schema not found</h2>
          <p style={{ color: 'var(--color-text-muted)', marginBottom: '1.5rem', fontSize: '0.9rem' }}>
            The{' '}
            <code style={{ fontFamily: 'monospace', background: 'rgba(99,102,241,0.12)', padding: '0.1rem 0.4rem', borderRadius: 4 }}>
              {FORM_ID}
            </code>{' '}
            schema has not been seeded yet.
          </p>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
            Run the seed script from the backend directory:
          </p>
          <pre style={{
            background: 'rgba(15,17,23,0.6)', border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius)', padding: '0.75rem 1rem',
            fontFamily: 'monospace', fontSize: '0.8rem', textAlign: 'left',
            color: 'var(--color-text)', marginBottom: '1.5rem', overflowX: 'auto',
          }}>
            python -m backend.app.seed.seed_breakdown
          </pre>
          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center', flexWrap: 'wrap' }}>
            <button
              className="btn-outline"
              onClick={() => refetch()}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
            >
              <RefreshCw size={14} /> Retry
            </button>
            <button
              className="btn-primary"
              onClick={() => navigate(`/forms/builder/${FORM_ID}`)}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
            >
              <ExternalLink size={14} /> Open in Builder
            </button>
          </div>
        </div>
      </div>
    );
  }

  /* ── Form ── */
  return (
    <div className="animate-fade-in" style={{ paddingBottom: '3rem' }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '1rem',
        marginBottom: '1.5rem', flexWrap: 'wrap',
      }}>
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 600, marginBottom: '0.25rem' }}>
            New Breakdown Event
          </h1>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
            Fill in all required fields (*) and click Save Event.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            className="btn-outline"
            onClick={() => navigate('/breakdown/explorer')}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', padding: '0.4rem 0.8rem' }}
          >
            <List size={14} /> Explorer
          </button>
          <button
            className="btn-outline"
            onClick={() => navigate(`/forms/builder/${FORM_ID}`)}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', padding: '0.4rem 0.8rem' }}
            title="Edit form schema in Visual Builder"
          >
            <ExternalLink size={14} /> Edit Schema
          </button>
        </div>
      </div>

      {/* Form card */}
      <div className="glass" style={{ padding: '2rem', borderRadius: 'var(--radius)' }}>
        <DynamicForm
          key={formKey}
          schema={schema}
          initialValues={{}}
          onSubmit={handleSubmit}
          submitLabel="Save Event"
          loading={isSubmitting}
        />
      </div>
    </div>
  );
}
