/**
 * DynamicForm – schema-driven form renderer.
 *
 * Supported field types:
 *   text / string  – single-line text input
 *   textarea       – multi-line text
 *   date           – date picker (default_value: "today" resolves to current date)
 *   time           – time picker
 *   datetime       – date + time picker (default_value: "now" resolves to current local datetime)
 *   number         – numeric input
 *   toggle         – single-select button group (options array)
 *   dropdown       – static select (options array)
 *   conditional_dropdown – select whose options come from options_map[values[depends_on]]
 *   async_select   – select loaded from API (data_source.filter_by_type_name for asset filtering)
 *   asset_type_dropdown – legacy cascading asset type selector
 *   asset_dropdown      – legacy cascading asset selector
 */

import { useEffect, useMemo, useRef, useState, type CSSProperties, type FormEvent } from 'react';
import { Check, ChevronDown, Image as ImageIcon, Trash2, Upload } from 'lucide-react';
import { useAssetTypes, useAssets, useChildAssets, useAssetsByTypeName } from '@/hooks/useAssets';
import type { FormField as FormFieldType, FormSchema, FormValue, FormValues } from '@/types';

interface DynamicFormProps {
  schema: FormSchema;
  initialValues?: FormValues;
  onSubmit: (values: FormValues) => void;
  submitLabel?: string;
  loading?: boolean;
}

type LayoutInfo = {
  x: number;
  y: number;
  w: number;
  h: number;
};

function pad2(value: number): string {
  return String(value).padStart(2, '0');
}

function formatDateInputValue(date: Date): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

function formatTimeInputValue(date: Date): string {
  return `${pad2(date.getHours())}:${pad2(date.getMinutes())}`;
}

function formatDateTimeInputValue(date: Date): string {
  return `${formatDateInputValue(date)}T${formatTimeInputValue(date)}`;
}

function parseNormalizedDate(rawValue: string): Date | null {
  const parsed = new Date(rawValue);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function isMultiSelectField(field: FormFieldType): boolean {
  return Boolean(field.multi_select && ['dropdown', 'conditional_dropdown', 'async_select'].includes(field.type));
}

function asSingleValue(value: FormValue | undefined): string {
  if (Array.isArray(value)) return value[0] ?? '';
  return value ?? '';
}

function asMultiValue(value: FormValue | undefined): string[] {
  if (Array.isArray(value)) return value;
  return value ? [value] : [];
}

/** Resolve a field's default_value to a concrete value. */
function resolveDefault(field: FormFieldType): FormValue {
  const defaultValue = field.default_value;
  if (!defaultValue) return isMultiSelectField(field) ? [] : '';
  if (defaultValue === 'today' && field.type === 'date') return formatDateInputValue(new Date());
  if (defaultValue === 'now' && field.type === 'datetime') return formatDateTimeInputValue(new Date());
  if (isMultiSelectField(field)) {
    try {
      const parsed = JSON.parse(defaultValue);
      if (Array.isArray(parsed)) return parsed.map(String);
    } catch {
      return defaultValue.split(',').map((item) => item.trim()).filter(Boolean);
    }
  }
  return defaultValue;
}

function normalizeFieldValue(field: FormFieldType, rawValue: FormValue): FormValue {
  if (isMultiSelectField(field)) {
    if (Array.isArray(rawValue)) return rawValue.map(String);
    if (!rawValue) return [];
    try {
      const parsed = JSON.parse(rawValue);
      if (Array.isArray(parsed)) return parsed.map(String);
    } catch {
      // Ignore parse failures and fall back to a single selected value.
    }
    return [String(rawValue)];
  }

  const singleValue = asSingleValue(rawValue);
  if (!singleValue) return '';

  const parsedDate = parseNormalizedDate(singleValue);

  switch (field.type) {
    case 'date':
      if (/^\d{4}-\d{2}-\d{2}$/.test(singleValue)) return singleValue;
      return parsedDate ? formatDateInputValue(parsedDate) : singleValue;
    case 'time':
      if (/^\d{2}:\d{2}(:\d{2})?$/.test(singleValue)) return singleValue.slice(0, 5);
      return parsedDate ? formatTimeInputValue(parsedDate) : singleValue;
    case 'datetime':
      if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(singleValue)) return singleValue.slice(0, 16);
      return parsedDate ? formatDateTimeInputValue(parsedDate) : singleValue;
    default:
      return singleValue;
  }
}

function serializeFieldValue(field: FormFieldType, rawValue: FormValue): FormValue {
  if (isMultiSelectField(field)) return asMultiValue(rawValue);

  const singleValue = asSingleValue(rawValue);
  if (!singleValue) return '';
  if (field.type !== 'datetime') return rawValue;

  const parsed = new Date(singleValue);
  return Number.isNaN(parsed.getTime()) ? singleValue : parsed.toISOString();
}

/** Build an initial values map from schema defaults, then merge with provided initialValues. */
function buildInitialValues(
  schemaFields: FormFieldType[],
  provided: FormValues,
): FormValues {
  const defaults: FormValues = {};
  schemaFields.forEach((f) => {
    if (f.default_value !== undefined) defaults[f.id] = resolveDefault(f);
  });
  return Object.fromEntries(
    Object.entries({ ...defaults, ...provided }).map(([fieldId, value]) => {
      const field = schemaFields.find((item) => item.id === fieldId);
      return [fieldId, field ? normalizeFieldValue(field, value) : value];
    }),
  );
}

export default function DynamicForm({
  schema,
  initialValues = {},
  onSubmit,
  submitLabel = 'Submit',
  loading = false,
}: Readonly<DynamicFormProps>) {
  const [values, setValues] = useState<FormValues>(() =>
    buildInitialValues(schema.fields, initialValues),
  );

  useEffect(() => {
    setValues(buildInitialValues(schema.fields, initialValues));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(initialValues)]);

  const orderedFields = useMemo(
    () =>
      [...schema.fields].sort((left, right) => {
        const leftLayout = getFieldLayout(left);
        const rightLayout = getFieldLayout(right);
        if (leftLayout.y !== rightLayout.y) return leftLayout.y - rightLayout.y;
        if (leftLayout.x !== rightLayout.x) return leftLayout.x - rightLayout.x;
        return left.label.localeCompare(right.label);
      }),
    [schema.fields],
  );

  const set = (id: string, val: FormValue) => {
    setValues((prev) => {
      const next = { ...prev, [id]: val };

      // Generic: clear all fields that declare depends_on pointing to this field
      schema.fields.forEach((f) => {
        if (f.depends_on === id) {
          delete next[f.id];
        }
      });

      // Legacy cascading asset clears
      if (id === 'asset_type_id') {
        delete next.asset_id;
        delete next.child_asset_id;
      }
      if (id === 'asset_id') {
        delete next.child_asset_id;
      }

      return next;
    });
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const serializedValues = Object.fromEntries(
      schema.fields.map((field) => [field.id, serializeFieldValue(field, values[field.id] ?? '')]),
    );
    onSubmit(serializedValues);
  };

  return (
    <form onSubmit={handleSubmit} className="dynamic-form-layout">
      <div className="dynamic-form-grid">
        {orderedFields
          .filter((field) => isFieldVisible(field, values))
          .map((field) => (
            <div key={field.id} className="dynamic-form-grid-item" style={getFieldGridStyle(field)}>
              <FieldRenderer field={field} value={values[field.id] ?? ''} values={values} onChange={set} />
            </div>
          ))}
      </div>
      <div className="dynamic-form-actions">
        <button className="btn-primary" type="submit" disabled={loading}>
          {loading ? 'Saving…' : submitLabel}
        </button>
      </div>
    </form>
  );
}

function getFieldLayout(field: FormFieldType): LayoutInfo {
  const isTextarea = field.type === 'textarea';
  const isToggle = field.type === 'toggle';
  const fallback = isTextarea
    ? { x: 0, y: 0, w: 12, h: 6 }
    : isToggle
      ? { x: 0, y: 0, w: 6, h: 5 }
      : { x: 0, y: 0, w: 6, h: 4 };

  const width = Math.max(1, Math.min(12, Number(field.layout?.w ?? fallback.w)));
  const height = Math.max(3, Number(field.layout?.h ?? fallback.h));

  return {
    x: Math.max(0, Math.min(12 - width, Number(field.layout?.x ?? fallback.x))),
    y: Math.max(0, Number(field.layout?.y ?? fallback.y)),
    w: width,
    h: height,
  };
}

function getFieldGridStyle(field: FormFieldType): CSSProperties {
  const layout = getFieldLayout(field);
  return {
    gridColumn: `${layout.x + 1} / span ${layout.w}`,
    gridRow: `${layout.y + 1} / span ${layout.h}`,
    minHeight: `${layout.h * 1.2}rem`,
  };
}

function isFieldVisible(field: FormFieldType, values: FormValues) {
  if (!field.visible_if) return true;
  const currentValue = values[field.visible_if.field];
  return Array.isArray(currentValue)
    ? currentValue.includes(field.visible_if.value)
    : currentValue === field.visible_if.value;
}

/* ── Field Renderer ── */

function FieldRenderer({
  field,
  value,
  values,
  onChange,
}: {
  field: FormFieldType;
  value: FormValue;
  values: FormValues;
  onChange: (id: string, val: FormValue) => void;
}) {
  if (!isFieldVisible(field, values)) return null;

  switch (field.type) {
    /* ── Toggle (single-select button group) ── */
    case 'toggle':
      return (
        <div className="dynamic-form-field">
          <label className="label">
            {field.label}
            {field.required && ' *'}
          </label>
          <div className="toggle-group">
            {(field.options || []).map((opt) => (
              <button
                key={opt}
                type="button"
                className={`toggle-btn${value === opt ? ' active' : ''}`}
                onClick={() => onChange(field.id, opt)}
              >
                {opt}
              </button>
            ))}
          </div>
          {/* Hidden input to participate in HTML5 form validation */}
          {field.required && (
            <input
              type="text"
              value={value}
              required
              readOnly
              style={{ position: 'absolute', opacity: 0, width: 0, height: 0, pointerEvents: 'none' }}
              tabIndex={-1}
            />
          )}
        </div>
      );

    /* ── Date ── */
    case 'date':
      return (
        <div className="dynamic-form-field">
          <label className="label">
            {field.label}
            {field.required && ' *'}
          </label>
          <input
            className="input-field"
            type="date"
            value={value}
            onChange={(e) => onChange(field.id, e.target.value)}
            required={field.required}
          />
        </div>
      );

    /* ── Time ── */
    case 'time':
      return (
        <div className="dynamic-form-field">
          <label className="label">
            {field.label}
            {field.required && ' *'}
          </label>
          <input
            className="input-field"
            type="time"
            value={value}
            onChange={(e) => onChange(field.id, e.target.value)}
            required={field.required}
          />
        </div>
      );

    /* ── Datetime ── */
    case 'datetime':
      return (
        <div className="dynamic-form-field">
          <label className="label">
            {field.label}
            {field.required && ' *'}
          </label>
          <input
            className="input-field"
            type="datetime-local"
            value={value}
            onChange={(e) => onChange(field.id, e.target.value)}
            required={field.required}
          />
        </div>
      );

    /* ── Number ── */
    case 'number':
      return (
        <div className="dynamic-form-field">
          <label className="label">
            {field.label}
            {field.required && ' *'}
          </label>
          <input
            className="input-field"
            type="number"
            value={value}
            onChange={(e) => onChange(field.id, e.target.value)}
            required={field.required}
            step="any"
          />
        </div>
      );

    /* ── Static Dropdown ── */
    case 'dropdown':
      if (isMultiSelectField(field)) {
        return (
          <MultiSelectField
            field={field}
            value={value}
            onChange={onChange}
            options={field.options || []}
            placeholder="Select…"
          />
        );
      }
      return (
        <div className="dynamic-form-field">
          <label className="label">
            {field.label}
            {field.required && ' *'}
          </label>
          <select
            className="input-field"
            value={asSingleValue(value)}
            onChange={(e) => onChange(field.id, e.target.value)}
            required={field.required}
          >
            <option value="">Select…</option>
            {(field.options || []).map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </div>
      );

    /* ── Conditional Dropdown (options filtered by depends_on field value) ── */
    case 'conditional_dropdown': {
      const parentValue = asSingleValue(values[field.depends_on || '']);
      const filteredOptions = (field.options_map || {})[parentValue] || [];
      const placeholder = !parentValue
        ? `Select ${(field.depends_on || '').replace(/_/g, ' ')} first…`
        : filteredOptions.length === 0
          ? 'No options for selected category'
          : 'Select…';

      if (isMultiSelectField(field)) {
        return (
          <MultiSelectField
            field={field}
            value={value}
            onChange={onChange}
            options={filteredOptions}
            placeholder={placeholder}
            disabled={!parentValue || filteredOptions.length === 0}
          />
        );
      }

      return (
        <div className="dynamic-form-field">
          <label className="label">
            {field.label}
            {field.required && ' *'}
          </label>
          <select
            className="input-field"
            value={asSingleValue(value)}
            onChange={(e) => onChange(field.id, e.target.value)}
            required={field.required}
            disabled={!parentValue || filteredOptions.length === 0}
          >
            <option value="">{placeholder}</option>
            {filteredOptions.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </div>
      );
    }

    /* ── Async Select (loaded from API) ── */
    case 'async_select':
      return <AsyncSelectField field={field} value={value} onChange={onChange} />;

    /* ── Legacy: Asset Type Dropdown ── */
    case 'asset_type_dropdown':
      return <AssetTypeDropdown field={field} value={asSingleValue(value)} onChange={onChange} />;

    /* ── Legacy: Asset / Child Asset Dropdown ── */
    case 'asset_dropdown':
      if (field.id === 'asset_id') {
        return <AssetDropdown field={field} value={asSingleValue(value)} assetTypeId={asSingleValue(values.asset_type_id)} onChange={onChange} />;
      }
      if (field.id === 'child_asset_id') {
        return <ChildAssetDropdown field={field} value={asSingleValue(value)} parentAssetId={asSingleValue(values.asset_id)} onChange={onChange} />;
      }
      return null;

    /* ── Table ── */
    case 'table':
      return <TableInputField field={field} value={value} onChange={onChange} />;

    /* ── Divider ── */
    case 'divider':
      return (
        <div className="dynamic-form-field" aria-hidden="true">
          <div style={{ width: '100%', borderTop: '1px solid var(--color-border)', marginTop: '0.85rem' }} />
        </div>
      );

    /* ── Label ── */
    case 'label':
      return (
        <div className="dynamic-form-field">
          <div style={{ color: 'var(--color-text)', fontSize: '0.95rem', lineHeight: 1.6 }}>
            {field.default_value || field.label}
          </div>
        </div>
      );

    /* ── Image ── */
    case 'image':
      return <ImageUploadField field={field} value={value} onChange={onChange} />;

    /* ── Textarea ── */
    case 'textarea':
      return (
        <div className="dynamic-form-field">
          <label className="label">
            {field.label}
            {field.required && ' *'}
          </label>
          <textarea
            className="input-field dynamic-form-textarea"
            value={asSingleValue(value)}
            onChange={(e) => onChange(field.id, e.target.value)}
            required={field.required}
          />
        </div>
      );

    /* ── Default: Text Input ── */
    default:
      return (
        <div className="dynamic-form-field">
          <label className="label">
            {field.label}
            {field.required && ' *'}
          </label>
          <input
            className="input-field"
            type="text"
            value={asSingleValue(value)}
            onChange={(e) => onChange(field.id, e.target.value)}
            required={field.required}
          />
        </div>
      );
  }
}

/* ── Async Select ── */

function AsyncSelectField({
  field,
  value,
  onChange,
}: {
  field: FormFieldType;
  value: FormValue;
  onChange: (id: string, val: FormValue) => void;
}) {
  const typeName = field.data_source?.filter_by_type_name;
  const { data: assets, isLoading } = useAssetsByTypeName(typeName);

  // Build options as {value: id, label: name} so the stored payload contains
  // the asset ID (integer) while the UI displays the human-readable name.
  const assetOptions: SelectOption[] = (assets || []).map((a) => ({
    value: String(a.id),
    label: a.name,
  }));

  if (isMultiSelectField(field)) {
    return (
      <MultiSelectField
        field={field}
        value={value}
        onChange={onChange}
        options={assetOptions}
        placeholder={isLoading ? 'Loading…' : 'Select…'}
        disabled={isLoading}
      />
    );
  }

  return (
    <div className="dynamic-form-field">
      <label className="label">
        {field.label}
        {field.required && ' *'}
      </label>
      <select
        className="input-field"
        value={asSingleValue(value)}
        onChange={(e) => onChange(field.id, e.target.value)}
        required={field.required}
        disabled={isLoading}
      >
        <option value="">{isLoading ? 'Loading…' : 'Select…'}</option>
        {assetOptions.map((opt) => (
          <option key={optionValue(opt)} value={optionValue(opt)}>
            {optionLabel(opt)}
          </option>
        ))}
      </select>
    </div>
  );
}

/** An option entry for MultiSelectField — either a plain string (value === label)
 *  or an explicit {value, label} pair (used when the stored value differs from the
 *  display label, e.g. asset IDs vs asset names). */
type SelectOption = string | { value: string; label: string };

function optionValue(opt: SelectOption): string {
  return typeof opt === 'string' ? opt : opt.value;
}

function optionLabel(opt: SelectOption): string {
  return typeof opt === 'string' ? opt : opt.label;
}

function getMultiSelectSummaryFromOptions(
  selectedValues: string[],
  allOptions: SelectOption[],
  placeholder: string,
): string {
  if (selectedValues.length === 0) return placeholder;

  return selectedValues
    .map((selectedValue) => {
      const match = allOptions.find((o) => optionValue(o) === selectedValue);
      return match ? optionLabel(match) : selectedValue;
    })
    .join(', ');
}

function MultiSelectField({
  field,
  value,
  onChange,
  options,
  placeholder,
  disabled = false,
}: Readonly<{
  field: FormFieldType;
  value: FormValue;
  onChange: (id: string, val: FormValue) => void;
  options: SelectOption[];
  placeholder: string;
  disabled?: boolean;
}>) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const selectedValues = asMultiValue(value);
  const summary = getMultiSelectSummaryFromOptions(selectedValues, options, placeholder);

  useEffect(() => {
    if (disabled && open) setOpen(false);
  }, [disabled, open]);

  useEffect(() => {
    if (!open) return undefined;

    const handlePointerDown = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleEscape);

    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [open]);

  const toggleOption = (option: string) => {
    const nextValues = selectedValues.includes(option)
      ? selectedValues.filter((item) => item !== option)
      : [...selectedValues, option];

    onChange(field.id, nextValues);
  };

  return (
    <div className="dynamic-form-field">
      <label className="label">
        {field.label}
        {field.required && ' *'}
      </label>
      <div className={`multi-select${open ? ' is-open' : ''}${disabled ? ' is-disabled' : ''}`} ref={containerRef}>
        <button
          type="button"
          className="multi-select-trigger"
          onClick={() => !disabled && setOpen((current) => !current)}
          aria-haspopup="listbox"
          aria-expanded={open}
          disabled={disabled}
        >
          <span className={`multi-select-trigger-text${selectedValues.length === 0 ? ' is-placeholder' : ''}`}>{summary}</span>
          <ChevronDown size={16} className="multi-select-trigger-icon" />
        </button>
        {open && (
          <div className="multi-select-menu" role="listbox" aria-multiselectable="true">
            {options.length === 0 ? (
              <div className="multi-select-empty">No options available</div>
            ) : (
              options.map((option) => {
                const val = optionValue(option);
                const lbl = optionLabel(option);
                const checked = selectedValues.includes(val);
                return (
                  <button
                    key={val}
                    type="button"
                    className={`multi-select-option${checked ? ' is-selected' : ''}`}
                    onClick={() => toggleOption(val)}
                    role="option"
                    aria-selected={checked}
                  >
                    <span className={`multi-select-check${checked ? ' is-selected' : ''}`}>
                      {checked && <Check size={13} strokeWidth={3} />}
                    </span>
                    <span className="multi-select-option-label">{lbl}</span>
                  </button>
                );
              })
            )}
          </div>
        )}
        {field.required && (
          <input
            type="text"
            value={selectedValues.join(',')}
            required
            readOnly
            tabIndex={-1}
            style={{ position: 'absolute', opacity: 0, width: 0, height: 0, pointerEvents: 'none' }}
          />
        )}
      </div>
    </div>
  );
}

/* ── Legacy Asset Sub-components ── */

function AssetTypeDropdown({
  field,
  value,
  onChange,
}: {
  field: FormFieldType;
  value: string;
  onChange: (id: string, val: string) => void;
}) {
  const { data: types, isLoading } = useAssetTypes();
  return (
    <div className="dynamic-form-field">
      <label className="label">
        {field.label}
        {field.required && ' *'}
      </label>
      <select
        className="input-field"
        value={asSingleValue(value)}
        onChange={(e) => onChange(field.id, e.target.value)}
        required={field.required}
        disabled={isLoading}
      >
        <option value="">{isLoading ? 'Loading…' : 'Select asset type…'}</option>
        {(types || []).map((t) => (
          <option key={t.id} value={String(t.id)}>
            {t.name}
          </option>
        ))}
      </select>
    </div>
  );
}

function AssetDropdown({
  field,
  value,
  assetTypeId,
  onChange,
}: {
  field: FormFieldType;
  value: string;
  assetTypeId?: string;
  onChange: (id: string, val: string) => void;
}) {
  const { data: assets, isLoading } = useAssets(assetTypeId ? Number(assetTypeId) : undefined);
  return (
    <div className="dynamic-form-field">
      <label className="label">
        {field.label}
        {field.required && ' *'}
      </label>
      <select
        className="input-field"
        value={asSingleValue(value)}
        onChange={(e) => onChange(field.id, e.target.value)}
        required={field.required}
        disabled={!assetTypeId || isLoading}
      >
        <option value="">
          {!assetTypeId ? 'Select asset type first…' : isLoading ? 'Loading…' : 'Select asset…'}
        </option>
        {(assets || []).map((a) => (
          <option key={a.id} value={String(a.id)}>
            {a.name}
          </option>
        ))}
      </select>
    </div>
  );
}

function ChildAssetDropdown({
  field,
  value,
  parentAssetId,
  onChange,
}: {
  field: FormFieldType;
  value: string;
  parentAssetId?: string;
  onChange: (id: string, val: string) => void;
}) {
  const { data: children, isLoading } = useChildAssets(parentAssetId ? Number(parentAssetId) : undefined);
  return (
    <div className="dynamic-form-field">
      <label className="label">{field.label}</label>
      <select
        className="input-field"
        value={asSingleValue(value)}
        onChange={(e) => onChange(field.id, e.target.value)}
        disabled={!parentAssetId || isLoading}
      >
        <option value="">
          {!parentAssetId ? 'Select parent asset first…' : isLoading ? 'Loading…' : 'None (optional)…'}
        </option>
        {(children || []).map((c) => (
          <option key={c.asset_id} value={String(c.asset_id)}>
            {c.asset_name}
          </option>
        ))}
      </select>
    </div>
  );
}

/* ── Image Upload Component ── */

function ImageUploadField({
  field,
  value,
  onChange,
}: {
  field: FormFieldType;
  value: FormValue;
  onChange: (id: string, val: FormValue) => void;
}) {
  const allowMultiple = !!field.multi_select;
  
  // Parse value to internal state: array of { image: string, description: string }
  const getEntries = () => {
    try {
      const parsed = JSON.parse(asSingleValue(value));
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  };

  const entries = getEntries();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    Array.from(files).forEach((file) => {
      const reader = new FileReader();
      reader.onload = (ev) => {
        const base64 = ev.target?.result as string;
        if (base64) {
          // React state might not be fast enough for synchronous reads of multiples without functional update
          // However FileReader is async, we should use a previous state based update, but we are emitting to parent onChange.
          // Since parent manages value, we need to carefully aggregate. We can just use the latest `value` 
          // Wait, multiple file reads completing close together might overwrite each other because `getEntries()` 
          // uses the current render cycle's value. 
          // To fix this cleanly for multiple images, we should process all files at once.
        }
      };
    });

    // Safe multiple processing approach
    Promise.all(Array.from(files).map(file => {
      return new Promise<string>((resolve) => {
        const reader = new FileReader();
        reader.onload = (ev) => resolve(ev.target?.result as string);
        reader.readAsDataURL(file);
      });
    })).then(base64s => {
      const newAdditions = base64s.map(b64 => ({ image: b64, description: '' }));
      let newEntries = [];
      if (allowMultiple) {
        newEntries = [...getEntries(), ...newAdditions];
      } else {
        newEntries = [newAdditions[0]];
      }
      onChange(field.id, JSON.stringify(newEntries));
    });
  };

  const handleDescriptionChange = (index: number, newDesc: string) => {
    const newEntries = [...entries];
    newEntries[index].description = newDesc;
    onChange(field.id, JSON.stringify(newEntries));
  };

  const handleRemove = (index: number) => {
    const newEntries = entries.filter((_, i) => i !== index);
    onChange(field.id, JSON.stringify(newEntries));
  };

  return (
    <div className="dynamic-form-field">
      <label className="label">
        {field.label}
        {field.required && ' *'}
      </label>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
        {entries.map((entry: any, idx: number) => (
          <div key={idx} style={{ display: 'flex', gap: '1rem', alignItems: 'flex-start', background: 'var(--color-surface)', padding: '0.8rem', borderRadius: 'var(--radius)', border: '1px solid var(--color-border)' }}>
            <img src={entry.image} alt="Uploaded preview" style={{ width: 80, height: 80, objectFit: 'cover', borderRadius: 'calc(var(--radius) - 2px)', background: 'var(--color-bg)' }} />
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <input 
                className="input-field" 
                placeholder="Image description..." 
                value={entry.description || ''} 
                onChange={(e) => handleDescriptionChange(idx, e.target.value)}
              />
            </div>
            <button type="button" className="btn-danger" onClick={() => handleRemove(idx)} style={{ padding: '0.4rem' }}>
              <Trash2 size={16} />
            </button>
          </div>
        ))}
        {(!entries.length || allowMultiple) && (
          <label style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '1.5rem', border: '2px dashed var(--color-border)', borderRadius: 'var(--radius)', cursor: 'pointer', background: 'var(--color-bg-subtle)' }}>
            <Upload size={24} style={{ color: 'var(--color-text-muted)', marginBottom: '0.5rem' }} />
            <span style={{ fontSize: '0.875rem', fontWeight: 500, color: 'var(--color-text)' }}>Click or drag to upload image(s)</span>
            <input type="file" accept="image/*" multiple={allowMultiple} onChange={handleFileChange} style={{ display: 'none' }} />
          </label>
        )}
      </div>
      {field.required && entries.length === 0 && (
        <input type="text" readOnly required value="" style={{ position: 'absolute', opacity: 0, width: 0, height: 0, pointerEvents: 'none' }} tabIndex={-1} />
      )}
    </div>
  );
}

/* ── Table Component ── */

function TableInputField({ field, value, onChange }: { field: FormFieldType; value: FormValue; onChange: (id: string, val: FormValue) => void; }) {
  const parseRows = () => {
    try {
      if (!value) return [];
      const parsed = JSON.parse(asSingleValue(value));
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  };
  
  const rows = parseRows();
  const cols = field.columns || [];

  const addRow = () => {
    const newRows = [...rows, {}];
    onChange(field.id, JSON.stringify(newRows));
  };
  
  const removeRow = (idx: number) => {
    const newRows = [...rows];
    newRows.splice(idx, 1);
    onChange(field.id, JSON.stringify(newRows));
  };
  
  const updateCell = (rIdx: number, cId: string, val: any) => {
    const newRows = [...rows];
    newRows[rIdx] = { ...newRows[rIdx], [cId]: val };
    onChange(field.id, JSON.stringify(newRows));
  };

  return (
    <div className="dynamic-form-field">
      <label className="label">{field.label}{field.required && ' *'}</label>
      <div style={{ border: '1px solid var(--color-border)', borderRadius: 'var(--radius)', overflowX: 'auto', background: 'var(--color-surface)' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
          <thead style={{ background: 'var(--color-bg-subtle)' }}>
            <tr>
              {field.show_serial_number && <th style={{ padding: '0.5rem', textAlign: 'left', fontWeight: 600, borderBottom: '1px solid var(--color-border)', whiteSpace: 'nowrap', width: 60 }}>S/N</th>}
              {cols.map((c) => <th key={c.id} style={{ padding: '0.5rem', textAlign: 'left', fontWeight: 600, borderBottom: '1px solid var(--color-border)', whiteSpace: 'nowrap' }}>{c.label || c.id}</th>)}
              <th style={{ padding: '0.5rem', width: 40, borderBottom: '1px solid var(--color-border)' }}></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r: any, rIdx: number) => (
              <tr key={rIdx}>
                {field.show_serial_number && (
                  <td style={{ padding: '0.5rem', borderBottom: '1px solid var(--color-border)', verticalAlign: 'top', color: 'var(--color-text-muted)', textAlign: 'center' }}>
                    {rIdx + 1}
                  </td>
                )}
                {cols.map((c) => (
                  <td key={c.id} style={{ padding: '0.5rem', borderBottom: '1px solid var(--color-border)', verticalAlign: 'top' }}>
                    {c.type === 'dropdown' ? (
                      <select className="input-field" style={{ minWidth: 120, padding: '0.4rem' }} value={r[c.id] || ''} onChange={(e) => updateCell(rIdx, c.id, e.target.value)}>
                        <option value="">Select…</option>
                        {(c.options || []).map(opt => <option key={opt} value={opt}>{opt}</option>)}
                      </select>
                    ) : (
                      <input 
                        className="input-field" 
                        style={{ minWidth: 120, padding: '0.4rem' }} 
                        type={c.type === 'number' ? 'number' : c.type === 'date' ? 'date' : 'text'} 
                        value={r[c.id] || ''} 
                        onChange={(e) => updateCell(rIdx, c.id, e.target.value)}
                        placeholder="…"
                      />
                    )}
                  </td>
                ))}
                <td style={{ padding: '0.5rem', textAlign: 'center', borderBottom: '1px solid var(--color-border)', verticalAlign: 'top' }}>
                  <button type="button" className="btn-danger" style={{ padding: '0.3rem', width: 'auto' }} onClick={() => removeRow(rIdx)}>
                    <Trash2 size={15} />
                  </button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={cols.length + 1 + (field.show_serial_number ? 1 : 0)} style={{ padding: '1rem', textAlign: 'center', color: 'var(--color-text-muted)' }}>No rows added yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <button type="button" className="btn-outline" onClick={addRow} style={{ marginTop: '0.5rem', display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.4rem 0.8rem' }}>
        <Upload size={14} style={{ display: 'none' }} />+ Add Row
      </button>
      
      {field.required && rows.length === 0 && (
        <input type="text" readOnly required value="" style={{ position: 'absolute', opacity: 0, width: 0, height: 0, pointerEvents: 'none' }} tabIndex={-1} />
      )}
    </div>
  );
}
