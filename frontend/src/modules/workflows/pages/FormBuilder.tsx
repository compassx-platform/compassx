import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useToast, extractApiError } from '@/lib/toast';
import { useForms, useCreateForm, useUpdateForm } from '@/modules/workflows/hooks/useForm';
import type { FormSchema, FormField } from '@/types';
import { Plus, Trash2, Save, Code, Database } from 'lucide-react';

function parseOptionList(raw: string): string[] {
  return raw
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function getFormIdError(formId: string): string | null {
  if (!formId.trim()) return null;
  if (/\s/.test(formId)) return 'Form ID cannot contain spaces. Use letters, numbers, underscores, or hyphens.';
  return null;
}

function OptionListInput({
  value,
  onCommit,
  placeholder,
}: Readonly<{
  value: string[];
  onCommit: (next: string[]) => void;
  placeholder?: string;
}>) {
  const [draft, setDraft] = useState(value.join(', '));

  useEffect(() => {
    setDraft(value.join(', '));
  }, [value]);

  return (
    <input
      className="input-field"
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => onCommit(parseOptionList(draft))}
      placeholder={placeholder}
    />
  );
}

export default function FormBuilder() {
  const { data: forms, isLoading } = useForms();
  const createMut = useCreateForm();
  const updateMut = useUpdateForm();

  const [searchParams] = useSearchParams();

  const [selectedFormId, setSelectedFormId] = useState<string>('');
  const [formIdInput, setFormIdInput] = useState('');
  const [entityNameInput, setEntityNameInput] = useState('');
  const [fields, setFields] = useState<FormField[]>([]);
  
  const toast = useToast();
  const [showJson, setShowJson] = useState(false);
  const formIdError = getFormIdError(formIdInput);

  // Initialise from ?form= query param on first load
  useEffect(() => {
    const paramForm = searchParams.get('form');
    if (paramForm) {
      setSelectedFormId(paramForm);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load selected form
  useEffect(() => {
    if (selectedFormId && forms) {
      const f = forms.find(x => x.form_id === selectedFormId);
      if (f) {
        setFormIdInput(f.form_id);
        setEntityNameInput(f.entity_name);
        setFields(f.schema.fields || []);
      }
    } else if (selectedFormId === '') {
      setFormIdInput('');
      setEntityNameInput('');
      setFields([]);
    }
  }, [selectedFormId, forms]);

  const handleAddField = () => {
    setFields([
      ...fields,
      { id: `field_${Date.now()}`, type: 'string', label: 'New Field', required: false }
    ]);
  };

  const updateField = (index: number, updates: Partial<FormField>) => {
    const newFields = [...fields];
    newFields[index] = { ...newFields[index], ...updates };
    setFields(newFields);
  };

  const removeField = (index: number) => {
    const newFields = [...fields];
    newFields.splice(index, 1);
    setFields(newFields);
  };

  const handleSave = async () => {
    if (!formIdInput || !entityNameInput) { toast.error('Form ID and Entity Name are required.'); return; }
    if (formIdError) { toast.error(formIdError); return; }

    const schema: FormSchema = {
      form_id: formIdInput,
      entity: entityNameInput,
      fields,
    };

    try {
      if (selectedFormId) {
        await updateMut.mutateAsync({
          form_id: selectedFormId,
          payload: { entity_name: entityNameInput, schema }
        });
        toast.success('Form updated successfully!');
      } else {
        await createMut.mutateAsync({
          form_id: formIdInput,
          entity_name: entityNameInput,
          schema
        });
        toast.success('Form created successfully!');
        setSelectedFormId(formIdInput);
      }
    } catch (err: unknown) {
      toast.error(extractApiError(err));
    }
  };

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 600 }}>Form Builder Studio</h1>
        <div style={{ display: 'flex', gap: 12 }}>
          <button className="btn-outline" onClick={() => window.open('/breakdown/designer', '_blank')}>
            Visual Builder
          </button>
          <button className="btn-outline" onClick={() => setShowJson(!showJson)}>
            <Code size={16} style={{ marginRight: 6 }} /> {showJson ? 'GUI Mode' : 'JSON Mode'}
          </button>
          {selectedFormId && (
            <button className="btn-outline" onClick={() => window.open(`/forms/${selectedFormId}`, '_blank')}>
              View Form
            </button>
          )}
          {entityNameInput && (
            <button className="btn-outline" onClick={() => window.open(`/entities/${entityNameInput}`, '_blank')}>
              <Database size={16} style={{ marginRight: 6 }} /> View Records
            </button>
          )}
          <button className="btn-primary" onClick={handleSave} disabled={createMut.isPending || updateMut.isPending}>
            <Save size={16} style={{ marginRight: 6 }} /> Save
          </button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start' }}>
        {/* Left pane: File Selector & Form Meta */}
        <div className="glass" style={{ width: 300, padding: '1.5rem', borderRadius: 'var(--radius)' }}>
          <div style={{ marginBottom: 24 }}>
            <label className="label">Select Existing Form</label>
            <select
              className="input-field"
              value={selectedFormId}
              onChange={(e) => setSelectedFormId(e.target.value)}
              disabled={isLoading}
            >
              <option value="">-- Create New Form --</option>
              {forms?.map(f => (
                <option key={f.form_id} value={f.form_id}>{f.form_id} ({f.entity_name})</option>
              ))}
            </select>
          </div>

          <div style={{ paddingBottom: 16, borderBottom: '1px solid var(--color-border)', marginBottom: 16 }}>
            <label className="label">Form ID (unique)</label>
            <input
              className="input-field"
              value={formIdInput}
              onChange={(e) => setFormIdInput(e.target.value)}
              disabled={!!selectedFormId} // can't change ID of existing
            />
            {formIdError && <p style={{ marginTop: 6, fontSize: '0.8rem', color: 'var(--color-danger)' }}>{formIdError}</p>}
          </div>
          <div>
            <label className="label">Target Entity Name</label>
            <input
              className="input-field"
              value={entityNameInput}
              onChange={(e) => setEntityNameInput(e.target.value)}
            />
          </div>
        </div>

        {/* Right pane: Fields Builder */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 16 }}>
          {showJson ? (
            <textarea
              className="input-field glass"
              style={{ height: '600px', fontFamily: 'monospace' }}
              value={JSON.stringify({ form_id: formIdInput, entity: entityNameInput, fields }, null, 2)}
              readOnly
            />
          ) : (
            <div className="glass" style={{ padding: '1.5rem', borderRadius: 'var(--radius)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <h3 style={{ fontWeight: 600 }}>Form Fields</h3>
                <button className="btn-outline" onClick={handleAddField} style={{ padding: '0.3rem 0.6rem' }}>
                  <Plus size={16} /> Add Field
                </button>
              </div>

              {fields.length === 0 ? (
                <p style={{ color: 'var(--color-text-muted)', textAlign: 'center', padding: '2rem' }}>No fields defined yet. Add one to start.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {fields.map((field, i) => (
                    <div key={i} style={{ display: 'flex', gap: 12, padding: '1rem', background: 'var(--color-surface)', borderRadius: 'var(--radius)', border: '1px solid var(--color-border)' }}>
                      <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                        <div>
                          <label className="label">Field ID</label>
                          <input className="input-field" value={field.id} onChange={(e) => updateField(i, { id: e.target.value })} />
                        </div>
                        <div>
                          <label className="label">Label</label>
                          <input className="input-field" value={field.label} onChange={(e) => updateField(i, { label: e.target.value })} />
                        </div>
                        <div>
                          <label className="label">Type</label>
                          <select className="input-field" value={field.type} onChange={(e) => updateField(i, { type: e.target.value })}>
                            <optgroup label="Basic">
                              <option value="string">Text (string)</option>
                              <option value="textarea">Textarea</option>
                              <option value="date">Date</option>
                              <option value="time">Time</option>
                              <option value="number">Number</option>
                            </optgroup>
                            <optgroup label="Choice">
                              <option value="toggle">Toggle group</option>
                              <option value="dropdown">Select (static)</option>
                              <option value="conditional_dropdown">Conditional select</option>
                            </optgroup>
                            <optgroup label="System">
                              <option value="async_select">API lookup</option>
                              <option value="asset_type_dropdown">Asset type</option>
                              <option value="asset_dropdown">Asset lookup</option>
                            </optgroup>
                            <optgroup label="Media">
                              <option value="image">Image with description</option>
                            </optgroup>
                            <optgroup label="Layout">
                              <option value="divider">Divider</option>
                              <option value="label">Label text</option>
                              <option value="table">Table / Grid</option>
                            </optgroup>
                          </select>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', paddingTop: 20 }}>
                          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: '0.875rem' }}>
                            <input type="checkbox" checked={field.required || false} onChange={(e) => updateField(i, { required: e.target.checked })} />
                            Required
                          </label>
                        </div>
                        
                        {/* Options for static dropdown / toggle */}
                        {(field.type === 'dropdown' || field.type === 'toggle') && (
                          <div style={{ gridColumn: '1 / -1' }}>
                            <label className="label">Options (comma-separated)</label>
                            <OptionListInput
                              value={field.options || []}
                              onCommit={(options) => updateField(i, { options })}
                              placeholder="Option A, Option B, Option C"
                            />
                          </div>
                        )}

                        {/* Conditional dropdown: depends_on + options_map */}
                        {field.type === 'conditional_dropdown' && (
                          <>
                            <div style={{ gridColumn: '1 / -1' }}>
                              <label className="label">Depends on field ID</label>
                              <input
                                className="input-field"
                                value={field.depends_on || ''}
                                onChange={(e) => updateField(i, { depends_on: e.target.value })}
                                placeholder="e.g. equipment_category"
                              />
                            </div>
                            <div style={{ gridColumn: '1 / -1' }}>
                              <label className="label">Options map (JSON)</label>
                              <textarea
                                className="input-field"
                                style={{ minHeight: 80, fontFamily: 'monospace', fontSize: '0.78rem' }}
                                value={JSON.stringify(field.options_map || {}, null, 2)}
                                onChange={(e) => {
                                  try { updateField(i, { options_map: JSON.parse(e.target.value) }); } catch { /* ignore parse errors */ }
                                }}
                              />
                            </div>
                          </>
                        )}

                        {/* Async select: filter_by_type_name */}
                        {field.type === 'async_select' && (
                          <div style={{ gridColumn: '1 / -1' }}>
                            <label className="label">Filter by asset type name</label>
                            <input
                              className="input-field"
                              value={field.data_source?.filter_by_type_name || ''}
                              onChange={(e) => updateField(i, { data_source: { ...(field.data_source || { type: 'api', endpoint: '/proxy/assets' }), filter_by_type_name: e.target.value } })}
                              placeholder="e.g. Inverter"
                            />
                          </div>
                        )}

                        {/* Default value */}
                        {(field.type === 'date' || field.type === 'string' || field.type === 'number') && (
                          <div style={{ gridColumn: '1 / -1' }}>
                            <label className="label">Default value {field.type === 'date' && '("today" for current date)'}</label>
                            <input
                              className="input-field"
                              value={field.default_value || ''}
                              onChange={(e) => updateField(i, { default_value: e.target.value })}
                              placeholder={field.type === 'date' ? 'today' : ''}
                            />
                          </div>
                        )}
                      </div>
                      <button className="btn-danger" onClick={() => removeField(i)} style={{ height: 'fit-content', padding: '0.4rem' }}>
                        <Trash2 size={16} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


