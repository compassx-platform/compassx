import { DragEvent, useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { useScopedNavigate } from '@/lib/appNavigation';
import { useToast, extractApiError } from '@/lib/toast';
import GridLayout, { WidthProvider, type Layout, type LayoutItem } from 'react-grid-layout/legacy';
import type { LucideIcon } from 'lucide-react';
import { AlignLeft, ArrowLeft, Calendar, ChevronDown, Clock, Code, Database, Filter, Grip, Hash, Image as ImageIcon, LayoutGrid, Minus, PenTool, Pilcrow, Plus, Save, Settings2, Table as TableIcon, ToggleLeft, Trash2, Type } from 'lucide-react';
import { useCreateForm, useFormSchema, useUpdateForm } from '@/modules/workflows/hooks/useForm';
import { useEntityDefinitions } from '@/modules/workflows/hooks/useEntity';
import type { FormField, FormSchema } from '@/types';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

const GridCanvas = WidthProvider(GridLayout);
const COLS = 12;
const ROW_H = 34;

type Tmpl = {
  key: string; label: string; description: string; category: string; icon: LucideIcon;
  defaultLayout: Required<NonNullable<FormField['layout']>>;
  build: (fields: FormField[]) => FormField | null;
};

const LIB: Tmpl[] = [
  { key: 'text', label: 'Text input', description: 'Single-line response for names, titles, and reference codes.', category: 'Basic', icon: Type, defaultLayout: { x: 0, y: 0, w: 6, h: 4, minW: 3, minH: 3 }, build: (f) => ({ id: uid('text_input', f), type: 'string', label: 'Text Input', required: false }) },
  { key: 'textarea', label: 'Long text', description: 'Expanded response area for notes, descriptions, and handoff details.', category: 'Basic', icon: AlignLeft, defaultLayout: { x: 0, y: 0, w: 12, h: 6, minW: 6, minH: 4 }, build: (f) => ({ id: uid('long_text', f), type: 'textarea', label: 'Long Text', required: false }) },
  { key: 'date', label: 'Date', description: 'Date picker for event dates, deadlines, and timestamps.', category: 'Basic', icon: Calendar, defaultLayout: { x: 0, y: 0, w: 3, h: 4, minW: 2, minH: 3 }, build: (f) => ({ id: uid('date_field', f), type: 'date', label: 'Date', required: false }) },
  { key: 'time', label: 'Time', description: 'Time picker for fault start/end times and resolution times.', category: 'Basic', icon: Clock, defaultLayout: { x: 0, y: 0, w: 3, h: 4, minW: 2, minH: 3 }, build: (f) => ({ id: uid('time_field', f), type: 'time', label: 'Time', required: false }) },
  { key: 'datetime', label: 'Date & time', description: 'Combined date-time picker for exact event timestamps and scheduled moments.', category: 'Basic', icon: Calendar, defaultLayout: { x: 0, y: 0, w: 4, h: 4, minW: 3, minH: 3 }, build: (f) => ({ id: uid('datetime_field', f), type: 'datetime', label: 'Date & Time', required: false }) },
  { key: 'number', label: 'Number', description: 'Numeric input for measurements, quantities, and values.', category: 'Basic', icon: Hash, defaultLayout: { x: 0, y: 0, w: 3, h: 4, minW: 2, minH: 3 }, build: (f) => ({ id: uid('number_field', f), type: 'number', label: 'Number', required: false }) },
  { key: 'toggle', label: 'Toggle group', description: 'Single-select button group for quick categorical choices.', category: 'Choice', icon: ToggleLeft, defaultLayout: { x: 0, y: 0, w: 6, h: 5, minW: 3, minH: 4 }, build: (f) => ({ id: uid('toggle_field', f), type: 'toggle', label: 'Toggle Group', required: false, options: ['Option 1', 'Option 2'] }) },
  { key: 'dropdown', label: 'Select', description: 'Static option list with a simple comma-separated setup.', category: 'Choice', icon: ChevronDown, defaultLayout: { x: 0, y: 0, w: 6, h: 4, minW: 4, minH: 3 }, build: (f) => ({ id: uid('select_field', f), type: 'dropdown', label: 'Select Field', required: false, options: ['Option 1', 'Option 2'] }) },
  { key: 'conditional_dropdown', label: 'Conditional select', description: "Dropdown whose options are filtered by another field's value.", category: 'Choice', icon: Filter, defaultLayout: { x: 0, y: 0, w: 6, h: 4, minW: 4, minH: 3 }, build: (f) => ({ id: uid('conditional_select', f), type: 'conditional_dropdown', label: 'Conditional Select', required: false, depends_on: '', options_map: {} }) },
  { key: 'async_select', label: 'API lookup', description: 'Dropdown loaded from an API endpoint with optional asset type filter.', category: 'System', icon: Database, defaultLayout: { x: 0, y: 0, w: 6, h: 4, minW: 4, minH: 3 }, build: (f) => ({ id: uid('api_lookup', f), type: 'async_select', label: 'API Lookup', required: false, data_source: { type: 'api', endpoint: '/proxy/assets', filter_by_type_name: '' } }) },
  { key: 'asset_type', label: 'Asset type', description: 'System selector that anchors downstream asset lookups.', category: 'System', icon: Database, defaultLayout: { x: 0, y: 0, w: 6, h: 4, minW: 4, minH: 3 }, build: (f) => f.some((x) => x.id === 'asset_type_id') ? null : ({ id: 'asset_type_id', type: 'asset_type_dropdown', label: 'Asset Type', required: true }) },
  { key: 'asset', label: 'Asset lookup', description: 'Primary asset selector driven by the chosen asset type.', category: 'System', icon: Database, defaultLayout: { x: 0, y: 0, w: 6, h: 4, minW: 4, minH: 3 }, build: (f) => f.some((x) => x.id === 'asset_id') ? null : ({ id: 'asset_id', type: 'asset_dropdown', label: 'Asset', required: true }) },
  { key: 'child_asset', label: 'Child asset', description: 'Dependent lookup for nested equipment or sub-assets.', category: 'System', icon: Database, defaultLayout: { x: 0, y: 0, w: 6, h: 4, minW: 4, minH: 3 }, build: (f) => f.some((x) => x.id === 'child_asset_id') ? null : ({ id: 'child_asset_id', type: 'asset_dropdown', label: 'Child Asset', required: false }) },
  { key: 'image', label: 'Image with description', description: 'Upload images and provide descriptions for them.', category: 'Media', icon: ImageIcon, defaultLayout: { x: 0, y: 0, w: 12, h: 6, minW: 4, minH: 4 }, build: (f) => ({ id: uid('image_upload', f), type: 'image', label: 'Image Upload', required: false }) },
  { key: 'divider', label: 'Divider', description: 'Simple horizontal line to separate sections.', category: 'Layout', icon: Minus, defaultLayout: { x: 0, y: 0, w: 12, h: 2, minW: 6, minH: 2 }, build: (f) => ({ id: uid('divider', f), type: 'divider', label: 'Divider', required: false }) },
  { key: 'label', label: 'Label text', description: 'Read-only text shown in the fill form.', category: 'Layout', icon: Pilcrow, defaultLayout: { x: 0, y: 0, w: 12, h: 3, minW: 4, minH: 2 }, build: (f) => ({ id: uid('label_text', f), type: 'label', label: 'Label Text', required: false, default_value: 'Section note' }) },
  { key: 'table', label: 'Data table', description: 'Embed a nested data table allowing users to dynamically add rows of structured columns.', category: 'Layout', icon: TableIcon, defaultLayout: { x: 0, y: 0, w: 12, h: 6, minW: 6, minH: 5 }, build: (f) => ({ id: uid('data_table', f), type: 'table', label: 'Data Table', required: false, columns: [] }) },
];

function uid(base: string, fields: FormField[]) {
  const b = sl(base);
  if (!fields.some((f) => f.id === b)) return b;
  let c = 2; while (fields.some((f) => f.id === `${b}_${c}`)) c++;
  return `${b}_${c}`;
}
function sl(v: string) { return v.toLowerCase().trim().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '') || 'field'; }
function tLabel(f: FormField) {
  const m: Record<string, string> = { dropdown: 'Select', textarea: 'Long text', date: 'Date', time: 'Time', datetime: 'Date & time', number: 'Number', toggle: 'Toggle group', conditional_dropdown: 'Conditional select', async_select: 'API lookup', asset_type_dropdown: 'Asset type', image: 'Image upload', divider: 'Divider', label: 'Label text', table: 'Data table' };
  if (f.type === 'asset_dropdown') return f.id === 'child_asset_id' ? 'Child asset' : 'Asset lookup';
  return m[f.type] || 'Text input';
}
function tSummary(f: FormField) {
  if (f.type === 'dropdown') { const n = f.options?.length || 0; return `${n} option${n === 1 ? '' : 's'} configured${f.multi_select ? ' · multi-select array' : ''}`; }
  if (f.type === 'toggle') { const n = f.options?.length || 0; return `${n} choice${n === 1 ? '' : 's'} · single-select`; }
  if (f.type === 'conditional_dropdown') { const n = Object.keys(f.options_map || {}).length; return f.depends_on ? `Filtered by "${f.depends_on}" · ${n} categor${n === 1 ? 'y' : 'ies'}${f.multi_select ? ' · multi-select array' : ''}` : 'No parent field configured'; }
  if (f.type === 'async_select') return f.data_source?.filter_by_type_name ? `Loads "${f.data_source.filter_by_type_name}" assets${f.multi_select ? ' · multi-select array' : ''}` : `Loads from API${f.multi_select ? ' · multi-select array' : ' — configure filter type'}`;
  if (f.type === 'date') return f.default_value === 'today' ? 'Defaults to today' : 'Date picker';
  if (f.type === 'time') return 'Time picker (HH:MM)';
  if (f.type === 'datetime') return f.default_value === 'now' ? 'Defaults to current date and time' : 'Date and time picker';
  if (f.type === 'number') return 'Numeric input';
  if (f.type === 'asset_type_dropdown') return 'Connected to asset type master data';
  if (f.type === 'asset_dropdown') return f.id === 'child_asset_id' ? 'Depends on the selected parent asset' : 'Depends on the selected asset type';
  if (f.type === 'image') return `Image file with description text${f.multi_select ? ' · allows multiple entries' : ''}`;
  if (f.type === 'divider') return 'Horizontal separator line';
  if (f.type === 'label') return f.default_value?.trim() ? `Read-only text · "${f.default_value}"` : 'Read-only text block';
  if (f.type === 'table') return `Data table · ${f.columns?.length || 0} column${f.columns?.length !== 1 ? 's' : ''}`;
  if (f.visible_if) return `Shown when ${f.visible_if.field} equals ${f.visible_if.value || '…'}`;
  return 'Standard input control';
}
function dups(fields: FormField[]) {
  const c: Record<string, number> = {};
  fields.forEach((f) => { c[f.id] = (c[f.id] || 0) + 1; });
  return Object.entries(c).filter(([, n]) => n > 1).map(([id]) => id);
}
function tmplFor(f: FormField) {
  const m: Record<string, string> = { textarea: 'textarea', dropdown: 'dropdown', date: 'date', time: 'time', datetime: 'datetime', number: 'number', toggle: 'toggle', conditional_dropdown: 'conditional_dropdown', async_select: 'async_select', asset_type_dropdown: 'asset_type', image: 'image', divider: 'divider', label: 'label', table: 'table' };
  if (f.type === 'asset_dropdown') return LIB.find((t) => t.key === (f.id === 'child_asset_id' ? 'child_asset' : 'asset'));
  return LIB.find((t) => t.key === (m[f.type] || 'text'));
}
function defL(f: FormField) { return tmplFor(f)?.defaultLayout || LIB[0].defaultLayout; }
function cl(l: Partial<NonNullable<FormField['layout']>> | undefined, fb: Required<NonNullable<FormField['layout']>>) {
  const mW = Math.max(1, Math.min(COLS, Number(l?.minW ?? fb.minW)));
  const mH = Math.max(2, Number(l?.minH ?? fb.minH));
  const w = Math.max(mW, Math.min(COLS, Number(l?.w ?? fb.w)));
  const h = Math.max(mH, Number(l?.h ?? fb.h));
  return { x: Math.max(0, Math.min(COLS - w, Number(l?.x ?? fb.x))), y: Math.max(0, Number(l?.y ?? fb.y)), w, h, minW: mW, minH: mH };
}
function norm(src: FormField[]) {
  let nx = 0, ny = 0, rh = 0;
  return src.map((f) => {
    const d = defL(f);
    if (f.layout) return { ...f, layout: cl(f.layout, d) };
    const { w, h } = d;
    if (nx + w > COLS) { nx = 0; ny += rh || h; rh = 0; }
    const layout = cl({ x: nx, y: ny, w, h }, d);
    nx += w; rh = Math.max(rh, h);
    if (nx >= COLS) { nx = 0; ny += rh; rh = 0; }
    return { ...f, layout };
  });
}
function toGrid(fields: FormField[]): Layout {
  return fields.map((f) => { const d = defL(f); const l = cl(f.layout, d); return { i: f.id, x: l.x, y: l.y, w: l.w, h: l.h, minW: l.minW, minH: l.minH }; });
}

function FPrev({ f }: { f: FormField }) {
  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '0.55rem 0.8rem',
    background: 'var(--color-bg)', border: '1px solid var(--color-border)',
    borderRadius: 'var(--radius)', color: 'var(--color-text)',
    fontSize: '0.875rem', fontFamily: 'var(--font-family)',
    pointerEvents: 'none', boxSizing: 'border-box',
  };
  const selectStyle: React.CSSProperties = { ...inputStyle, cursor: 'default' };

  if (f.type === 'textarea') return (
    <textarea style={{ ...inputStyle, resize: 'none', minHeight: '5rem' }} readOnly value="" placeholder="Enter text…" />
  );
  if (f.type === 'date') return (
    <input style={inputStyle} type="date" readOnly value={f.default_value === 'today' ? new Date().toISOString().slice(0, 10) : ''} />
  );
  if (f.type === 'time') return (
    <input style={inputStyle} type="time" readOnly value="" />
  );
  if (f.type === 'datetime') return (
    <input style={inputStyle} type="datetime-local" readOnly value={f.default_value === 'now' ? new Date(Date.now() - (new Date().getTimezoneOffset() * 60000)).toISOString().slice(0, 16) : ''} />
  );
  if (f.type === 'number') return (
    <input style={inputStyle} type="number" readOnly value="" placeholder="0.00" />
  );
  if (f.type === 'divider') return (
    <div style={{ width: '100%', borderTop: '1px solid var(--color-border)', marginTop: '0.85rem' }} />
  );
  if (f.type === 'label') return (
    <div style={{ color: 'var(--color-text)', fontSize: '0.9rem', lineHeight: 1.5, padding: '0.35rem 0' }}>
      {f.default_value || f.label}
    </div>
  );
  if (f.type === 'toggle') {
    const opts = f.options || ['Option 1', 'Option 2'];
    return (
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
        {opts.map((o, i) => (
          <span key={o} style={{
            padding: '0.35rem 0.75rem', borderRadius: 'var(--radius)',
            border: '1px solid', fontSize: '0.8125rem', fontWeight: 500,
            borderColor: i === 0 ? 'var(--color-primary)' : 'var(--color-border)',
            background: i === 0 ? 'var(--color-primary)' : 'transparent',
            color: i === 0 ? '#fff' : 'var(--color-text-muted)',
            whiteSpace: 'nowrap',
          }}>{o}</span>
        ))}
      </div>
    );
  }
  if (f.type === 'dropdown' || f.type === 'asset_type_dropdown' || f.type === 'asset_dropdown') {
    const placeholder = f.type === 'asset_type_dropdown' ? 'Select asset type…'
      : f.type === 'asset_dropdown' ? (f.id === 'child_asset_id' ? 'Select child asset…' : 'Select asset…')
      : 'Select…';
    return (
      <select style={selectStyle} disabled multiple={!!f.multi_select}>
        <option>{f.options?.[0] ?? placeholder}</option>
      </select>
    );
  }
  if (f.type === 'conditional_dropdown') return (
    <select style={selectStyle} disabled multiple={!!f.multi_select}>
      <option>{f.depends_on ? 'Select…' : 'Select parent field first…'}</option>
    </select>
  );
  if (f.type === 'async_select') return (
    <select style={selectStyle} disabled multiple={!!f.multi_select}>
      <option>{f.data_source?.filter_by_type_name ? `Select ${f.data_source.filter_by_type_name}…` : 'Select…'}</option>
    </select>
  );
  if (f.type === 'image') return (
    <div style={{...inputStyle, display: 'flex', flexDirection: 'column', gap: '0.4rem', alignItems: 'center', justifyContent: 'center', background: 'var(--color-bg-subtle, rgba(0,0,0,0.02))', minHeight: '6rem', cursor: 'default', borderStyle: 'dashed' }}>
      <ImageIcon size={24} style={{ opacity: 0.4 }} />
      <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>Image Upload Area</span>
    </div>
  );
  if (f.type === 'table') return (
    <div style={{...inputStyle, padding: '0', overflow: 'hidden', cursor: 'default' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8125rem' }}>
        <thead style={{ background: 'var(--color-bg-subtle)' }}>
          <tr>
            {f.show_serial_number && <th style={{ padding: '0.5rem', textAlign: 'left', fontWeight: 600, borderBottom: '1px solid var(--color-border)', width: 60 }}>S/N</th>}
            {(f.columns && f.columns.length > 0) ? f.columns.map(c => <th key={c.id} style={{ padding: '0.5rem', textAlign: 'left', fontWeight: 600, borderBottom: '1px solid var(--color-border)' }}>{c.label || c.id}</th>) : <th style={{ padding: '0.5rem', textAlign: 'left', fontWeight: 600, borderBottom: '1px solid var(--color-border)' }}>Configure columns in the inspector…</th>}
          </tr>
        </thead>
        <tbody>
          <tr>
            {f.show_serial_number && <td style={{ padding: '1rem', borderBottom: '1px solid var(--color-border)', color: 'var(--color-text-muted)', textAlign: 'center' }}>1</td>}
            <td colSpan={Math.max(1, f.columns?.length || 1)} style={{ padding: '1rem', color: 'var(--color-text-muted)', textAlign: 'center' }}>Dynamic rows will appear here</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
  // string / text fallback
  return <input style={inputStyle} type="text" readOnly value="" placeholder="Enter value…" />;
}

/** Entity dropdown — loads entity list from API, enforces entity-first rule */
function EntityDropdown({
  value,
  onChange,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
}) {
  const { data: entities, isLoading } = useEntityDefinitions();

  if (disabled) {
    return (
      <input
        className="input-field"
        value={value}
        readOnly
        disabled
        style={{ opacity: 0.6 }}
      />
    );
  }

  return (
    <select
      className="input-field"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={isLoading}
    >
      <option value="">{isLoading ? 'Loading entities…' : 'Select entity…'}</option>
      {(entities ?? []).map((e) => (
        <option key={e.id} value={e.name}>
          {e.name}
        </option>
      ))}
    </select>
  );
}

/** Generate a slug-safe form ID from a label */
function genFormId(label: string) {
  return label.toLowerCase().trim().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '') || `form_${Date.now()}`;
}

function getFormIdError(formId: string): string | null {
  if (!formId.trim()) return null;
  if (/\s/.test(formId)) return 'Form ID cannot contain spaces. Use letters, numbers, underscores, or hyphens.';
  return null;
}

function parseOptionList(raw: string): string[] {
  return raw
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
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

export default function VisualFormBuilder() {
  const { formId: urlFormId } = useParams<{ formId?: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useScopedNavigate();
  const isEditing = Boolean(urlFormId);
  const cloneFormId = !isEditing ? (searchParams.get('clone') || '').trim() : '';

  const toast = useToast();
  const createMut = useCreateForm();
  const updateMut = useUpdateForm();

  // Load existing schema when editing
  const { data: existingSchema, isLoading: schemaLoading } = useFormSchema(urlFormId || '');
  const { data: cloneSchema, isLoading: cloneLoading } = useFormSchema(cloneFormId);

  const [formId, setFormId] = useState('');
  const [entity, setEntity] = useState('');
  const [fields, setFields] = useState<FormField[]>([]);
  const [selId, setSelId] = useState<string | null>(null);
  const [mode, setMode] = useState<'design' | 'schema'>('design');
  const [showAdv, setShowAdv] = useState(false);
  const [dragKey, setDragKey] = useState<string | null>(null);
  const [mapKey, setMapKey] = useState('');
  const [sideTab, setSideTab] = useState<'library' | 'inspector'>('library');
  // Raw draft for Field ID — allows typing underscores freely; sl() applied only on blur
  const [fieldIdDraft, setFieldIdDraft] = useState<string | null>(null);
  const [cloneHydrated, setCloneHydrated] = useState(false);

  // Populate state when existing schema loads
  useEffect(() => {
    if (!existingSchema) return;
    const nf = norm(existingSchema.fields || []);
    setFormId(existingSchema.form_id || urlFormId || '');
    setEntity(existingSchema.entity || '');
    setFields(nf);
    setSelId(nf[0]?.id || null);
  }, [existingSchema, urlFormId]);

  useEffect(() => {
    if (isEditing || cloneHydrated || !cloneSchema) return;

    const clonedFields = norm(structuredClone(cloneSchema.fields || []));
    const suggestedFormId = genFormId(`${cloneSchema.form_id}_copy`);

    setFormId(suggestedFormId);
    setEntity(cloneSchema.entity || '');
    setFields(clonedFields);
    setSelId(clonedFields[0]?.id || null);
    setCloneHydrated(true);
    toast.success(`Cloned form "${cloneFormId}" into a new draft.`);
  }, [cloneFormId, cloneHydrated, cloneSchema, isEditing, toast]);

  useEffect(() => { if (selId && !fields.some((f) => f.id === selId)) setSelId(fields[0]?.id || null); }, [fields, selId]);
  useEffect(() => { setShowAdv(false); setMapKey(''); setFieldIdDraft(null); }, [selId]);
  // Auto-switch to inspector tab when a field is selected
  useEffect(() => { if (selId) setSideTab('inspector'); }, [selId]);

  const sel = fields.find((f) => f.id === selId) || null;
  const dupList = dups(fields);
  const grid = toGrid(fields);
  const activeTmpl = LIB.find((t) => t.key === dragKey) || null;
  const others = sel ? fields.filter((f) => f.id !== sel.id) : [];
  const byCategory = LIB.reduce<Record<string, Tmpl[]>>((g, t) => { if (!g[t.category]) g[t.category] = []; g[t.category].push(t); return g; }, {});
  const canSave = Boolean(formId.trim() && entity.trim() && fields.length > 0 && dupList.length === 0);
  const formIdError = getFormIdError(formId);

  // Auto-derive entity from form_id when creating new
  const handleFormIdChange = (v: string) => {
    setFormId(v);
    if (!isEditing && !entity) setEntity(v.replace(/_form$/, ''));
  };

  const addFromTmpl = (key: string, lo?: Partial<NonNullable<FormField['layout']>>) => {
    const t = LIB.find((x) => x.key === key); if (!t) return;
    const nf = t.build(fields);
    if (!nf) { const sid = key === 'asset_type' ? 'asset_type_id' : key === 'asset' ? 'asset_id' : key === 'child_asset' ? 'child_asset_id' : null; if (sid) setSelId(sid); return; }
    const layout = cl(lo, t.defaultLayout);
    setFields(norm([...fields, { ...nf, layout }])); setSelId(nf.id);
  };

  const upd = (id: string, u: Partial<FormField>) => setFields((c) => c.map((f) => f.id !== id ? f : { ...f, ...u }));
  const rename = (v: string) => {
    if (!sel) return; const nid = sl(v);
    if (nid !== sel.id && fields.some((f) => f.id === nid)) return;
    setFields((c) => c.map((f) => {
      if (f.id === sel.id) return { ...f, id: nid };
      if (f.visible_if?.field === sel.id) return { ...f, visible_if: { ...f.visible_if, field: nid } };
      if (f.depends_on === sel.id) return { ...f, depends_on: nid };
      return f;
    })); setSelId(nid);
  };
  const updSel = (u: Partial<FormField>) => { if (sel) upd(sel.id, u); };
  const updLayout = (u: Partial<NonNullable<FormField['layout']>>) => { if (sel) updSel({ layout: cl({ ...sel.layout, ...u }, defL(sel)) }); };
  const del = (id: string) => {
    const next = fields.filter((f) => f.id !== id).map((f) => {
      const u: Partial<FormField> = {};
      if (f.visible_if?.field === id) u.visible_if = undefined;
      if (f.depends_on === id) u.depends_on = undefined;
      return Object.keys(u).length ? { ...f, ...u } : f;
    });
    setFields(next); if (selId === id) setSelId(next[0]?.id || null);
  };
  const onLC = (nl: Layout) => setFields((c) => c.map((f) => {
    const li = nl.find((x) => x.i === f.id); if (!li) return f;
    return { ...f, layout: cl({ x: li.x, y: li.y, w: li.w, h: li.h, minW: f.layout?.minW, minH: f.layout?.minH }, defL(f)) };
  }));
  const onDrop = (_l: Layout, item: LayoutItem | undefined, e: DragEvent<HTMLElement> | Event) => {
    const ne = 'dataTransfer' in e ? e : null;
    const key = ne?.dataTransfer?.getData('text/plain') || dragKey;
    if (!key || !item) return;
    addFromTmpl(key, { x: item.x, y: item.y, w: item.w, h: item.h });
    setDragKey(null);
  };
  const save = async () => {
    if (!formId.trim() || !entity.trim()) { toast.error('Form ID and Entity Name are required.'); return; }
    if (formIdError) { toast.error(formIdError); return; }
    if (!fields.length) { toast.error('Add at least one field.'); return; }
    if (dupList.length > 0) { toast.error(`Duplicate field IDs: ${dupList.join(', ')}`); return; }
    const schema: FormSchema = { form_id: formId, entity, fields: norm(fields) };
    try {
      if (isEditing) {
        await updateMut.mutateAsync({ form_id: formId, payload: { entity_name: entity, schema } });
        toast.success('Form updated.');
      } else {
        await createMut.mutateAsync({ form_id: formId, entity_name: entity, schema });
        toast.success('Form created.');
        navigate(`/forms/builder/${formId}`, { replace: true });
      }
    } catch (err: unknown) { toast.error(extractApiError(err)); }
  };

  const om = sel?.options_map || {};
  const addMapEntry = () => { if (!mapKey.trim() || !sel || om[mapKey.trim()] !== undefined) return; updSel({ options_map: { ...om, [mapKey.trim()]: [] } }); setMapKey(''); };
  const delMapEntry = (k: string) => { const n = { ...om }; delete n[k]; updSel({ options_map: n }); };

  if (schemaLoading || cloneLoading) {
    return <div style={{ padding: '2rem', color: 'var(--color-text-muted)' }}>Loading form…</div>;
  }

  return (
    <div className="form-designer-shell animate-fade-in">
      {/* Back + title row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '0.5rem' }}>
        <button
          className="btn-outline"
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}
          onClick={() => navigate('/forms')}
        >
          <ArrowLeft size={15} /> Forms
        </button>
        <h1 style={{ fontSize: '1.4rem', fontWeight: 600 }}>
          {isEditing ? `Editing: ${urlFormId}` : cloneFormId ? `Clone Form: ${cloneFormId}` : 'New Form'}
        </h1>
        <div style={{ flex: 1 }} />
        {isEditing && (
          <>
            <button
              className="btn-outline"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}
              onClick={() => navigate(`/forms/${formId}/view`)}
            >
              Fill Form
            </button>
            <button
              className="btn-outline"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}
              onClick={() => navigate(`/entities/${entity}/records`)}
            >
              <Database size={14} /> Records
            </button>
          </>
        )}
        <button
          className="btn-primary"
          onClick={save}
          disabled={createMut.isPending || updateMut.isPending}
          title={
            !formId.trim() ? 'Enter a Form ID first' :
            formIdError ? formIdError :
            !entity.trim() ? 'Select an entity first' :
            fields.length === 0 ? 'Add at least one field' :
            dupList.length > 0 ? `Duplicate field IDs: ${dupList.join(', ')}` :
            undefined
          }
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
        >
          <Save size={15} />{createMut.isPending || updateMut.isPending ? 'Saving…' : 'Save Form'}
        </button>
      </div>

      <div className="form-designer-layout">
        <section className="form-designer-main">
          <div className="glass form-designer-meta">
            <div className="form-designer-meta-card">
              <label className="label">Form ID</label>
              <input
                className="input-field"
                value={formId}
                onChange={(e) => handleFormIdChange(e.target.value)}
                placeholder="my_form"
                disabled={isEditing}
              />
              {formIdError && <p className="form-designer-help" style={{ color: 'var(--color-danger)' }}>{formIdError}</p>}
              <p className="form-designer-help">Unique identifier — auto-used as the URL path.</p>
            </div>
            <div className="form-designer-meta-card">
              <label className="label">Entity name</label>
              <EntityDropdown
                value={entity}
                onChange={setEntity}
                disabled={isEditing}
              />
              <p className="form-designer-help">
                {isEditing
                  ? 'Entity is locked after creation.'
                  : cloneFormId
                    ? 'Cloned from the base form. You can keep or change the entity before saving.'
                    : 'Select the entity this form writes into. Create the entity first if it does not appear.'}
              </p>
            </div>
          </div>

          {(dupList.length > 0 || !fields.length) && (
            <div className="form-designer-banner glass">
              {dupList.length > 0 ? <span>Resolve duplicate field IDs: {dupList.join(', ')}</span> : <span>Drag a component from the right rail into the canvas, or click Add to place it instantly.</span>}
            </div>
          )}

          <div className="glass form-designer-canvas">
            <div className="form-designer-canvas-header">
              <div>
                <div className="form-designer-section-title">Canvas</div>
                <div className="form-designer-help">Twelve-column grid with drag, snap, and resize behavior.</div>
              </div>
              <div className="form-designer-toolbar">
                <button className={`form-designer-toggle ${mode === 'design' ? 'is-active' : ''}`} onClick={() => setMode('design')} type="button"><LayoutGrid size={14} style={{ marginRight: 6 }} /> Design</button>
                <button className={`form-designer-toggle ${mode === 'schema' ? 'is-active' : ''}`} onClick={() => setMode('schema')} type="button"><Code size={14} style={{ marginRight: 6 }} /> Schema</button>
                <span className="form-designer-count">{fields.length} field{fields.length === 1 ? '' : 's'}</span>
              </div>
            </div>

            {mode === 'schema' ? (
              <textarea className="input-field form-designer-schema" readOnly value={JSON.stringify({ form_id: formId, entity, fields: norm(fields) }, null, 2)} />
            ) : (
              <div className={`form-designer-grid-shell ${dragKey ? 'is-dropping' : ''}`}>
                {!fields.length && (
                  <div className="form-designer-empty">
                    <Plus size={22} />
                    <div className="form-designer-empty-title">Drop components here</div>
                    <p>Each dropped component snaps into the grid and can be resized.</p>
                  </div>
                )}
                <GridCanvas
                  className="form-designer-grid"
                  layout={grid}
                  cols={COLS}
                  rowHeight={ROW_H}
                  margin={[16, 16]}
                  containerPadding={[0, 0]}
                  isDroppable isResizable isDraggable
                  resizeHandles={['se']}
                  compactType="vertical"
                  preventCollision={false}
                  draggableHandle=".form-designer-widget-handle"
                  onLayoutChange={onLC}
                  onDropDragOver={() => activeTmpl ? { w: activeTmpl.defaultLayout.w, h: activeTmpl.defaultLayout.h } : false}
                  onDrop={onDrop}
                >
                  {fields.map((f) => (
                    <div key={f.id} onClick={() => setSelId(f.id)}>
                      <div className={`form-designer-widget ${selId === f.id ? 'is-selected' : ''}`}>
                        {/* Floating overlay — drag handle + delete, visible on hover/select */}
                        <div className="form-designer-widget-overlay">
                          <button className="form-designer-widget-handle" type="button" aria-label="Move"><Grip size={13} /></button>
                          <button className="form-designer-icon-button form-designer-widget-del" type="button" onClick={(e) => { e.stopPropagation(); del(f.id); }}><Trash2 size={13} /></button>
                        </div>
                        {/* WYSIWYG form field */}
                        <div className="form-designer-wysiwyg-field">
                          <label className="form-designer-wysiwyg-label">
                            {f.label || 'Field label'}
                            {f.required && <span style={{ color: 'var(--color-primary)', marginLeft: 3 }}>*</span>}
                          </label>
                          <FPrev f={f} />
                        </div>
                      </div>
                    </div>
                  ))}
                </GridCanvas>
              </div>
            )}
          </div>
        </section>

        <aside className="glass form-designer-sidebar">
          {/* Tab bar */}
          <div className="form-designer-tab-bar">
            <button
              className={`form-designer-tab ${sideTab === 'library' ? 'is-active' : ''}`}
              type="button"
              onClick={() => setSideTab('library')}
            >
              <Settings2 size={13} style={{ marginRight: 5 }} /> Components
            </button>
            <button
              className={`form-designer-tab ${sideTab === 'inspector' ? 'is-active' : ''}`}
              type="button"
              onClick={() => setSideTab('inspector')}
            >
              <PenTool size={13} style={{ marginRight: 5 }} /> Inspector
              {sel && <span className="form-designer-tab-badge" />}
            </button>
          </div>

          {/* ── Library tab ── */}
          {sideTab === 'library' && (
            <div className="form-designer-library">
              {Object.entries(byCategory).map(([cat, items]) => (
                <div key={cat} className="form-designer-library-group">
                  <div className="form-designer-library-group-title">{cat}</div>
                  {items.map((t) => (
                    <div
                      key={t.key}
                      className={`form-designer-library-card ${dragKey === t.key ? 'is-dragging' : ''}`}
                      draggable
                      onDragStart={(e) => { e.dataTransfer.effectAllowed = 'copy'; e.dataTransfer.setData('text/plain', t.key); setDragKey(t.key); }}
                      onDragEnd={() => setDragKey(null)}
                    >
                      <div className="form-designer-library-card-header">
                        <div className="form-designer-library-icon"><t.icon size={15} /></div>
                        <div style={{ flex: 1 }}>
                          <div className="form-designer-library-title">{t.label}</div>
                          <div className="form-designer-library-category">{t.description}</div>
                        </div>
                        <button className="form-designer-secondary-button" type="button" onClick={() => addFromTmpl(t.key)}><Plus size={13} /> Add</button>
                      </div>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}

          {/* ── Inspector tab ── */}
          {sideTab === 'inspector' && (
            sel ? (
              <div className="form-designer-inspector">
                <div className="form-designer-sidebar-header">
                  <div>
                    <div className="form-designer-section-title">Editing field</div>
                    <div className="form-designer-help" style={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>{sel.id}</div>
                  </div>
                  <button className="form-designer-icon-button" type="button" title="Delete field" onClick={() => del(sel.id)}><Trash2 size={14} /></button>
                </div>

                {/* Label */}
                <div className="form-designer-property-row">
                  <label className="form-designer-property-label">Field type</label>
                  <input
                    className="input-field"
                    value={`${tLabel(sel)} (${sel.type})`}
                    readOnly
                  />
                </div>

                <div className="form-designer-property-row">
                  <label className="form-designer-property-label">Label</label>
                  <input
                    className="input-field"
                    value={sel.label}
                    onChange={(e) => updSel({ label: e.target.value })}
                    placeholder="Field label"
                  />
                </div>

                {/* Field ID */}
                <div className="form-designer-property-row">
                  <label className="form-designer-property-label">Field ID</label>
                  <input
                    className="input-field"
                    value={fieldIdDraft ?? sel.id}
                    onChange={(e) => setFieldIdDraft(e.target.value)}
                    onBlur={() => {
                      if (fieldIdDraft !== null) {
                        rename(fieldIdDraft);
                        setFieldIdDraft(null);
                      }
                    }}
                    placeholder="field_id"
                  />
                </div>

                {/* Required */}
                <label className="form-designer-switch">
                  <input type="checkbox" checked={!!sel.required} onChange={(e) => updSel({ required: e.target.checked })} />
                  Required field
                </label>

                {/* Default value */}
                {(sel.type === 'date' || sel.type === 'datetime' || sel.type === 'string' || sel.type === 'text' || sel.type === 'number' || sel.type === 'label') && (
                  <div className="form-designer-property-row">
                    <label className="form-designer-property-label">
                      {sel.type === 'label'
                        ? 'Display text'
                        : `Default value${sel.type === 'date' ? ' — use "today" for current date' : sel.type === 'datetime' ? ' — use "now" for current local datetime' : ''}`}
                    </label>
                    <input
                      className="input-field"
                      value={sel.default_value || ''}
                      onChange={(e) => updSel({ default_value: e.target.value })}
                      placeholder={sel.type === 'label' ? 'Read-only text shown to the user' : sel.type === 'date' ? 'today' : sel.type === 'datetime' ? 'now' : 'optional default'}
                    />
                  </div>
                )}

                {/* Options — toggle / dropdown */}
                {(sel.type === 'toggle' || sel.type === 'dropdown') && (
                  <div className="form-designer-property-row">
                    <label className="form-designer-property-label">Options (comma-separated)</label>
                    <OptionListInput
                      value={sel.options || []}
                      onCommit={(options) => updSel({ options })}
                      placeholder="Option A, Option B, Option C"
                    />
                  </div>
                )}

                {(sel.type === 'dropdown' || sel.type === 'conditional_dropdown' || sel.type === 'async_select' || sel.type === 'image') && (
                  <label className="form-designer-switch">
                    <input
                      type="checkbox"
                      checked={!!sel.multi_select}
                      onChange={(e) => updSel({ multi_select: e.target.checked })}
                    />
                    Allow multiple {sel.type === 'image' ? 'images' : 'selection (stores values as array)'}
                  </label>
                )}

                {/* Conditional dropdown */}
                {sel.type === 'conditional_dropdown' && (
                  <>
                    <div className="form-designer-property-row">
                      <label className="form-designer-property-label">Depends on field</label>
                      <select
                        className="input-field"
                        value={sel.depends_on || ''}
                        onChange={(e) => updSel({ depends_on: e.target.value })}
                      >
                        <option value="">Select parent field…</option>
                        {others.map((f) => <option key={f.id} value={f.id}>{f.label} ({f.id})</option>)}
                      </select>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.8rem', padding: '0.8rem', background: 'var(--color-bg-subtle)', borderRadius: 'var(--radius)', border: '1px solid var(--color-border)' }}>
                      <label className="form-designer-property-label" style={{ fontWeight: 600, width: '100%' }}>Options Mapping Dictionary</label>
                      <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: '0.2rem' }}>Define what options show based on the parent's value.</div>
                      {Object.entries(om).map(([k, opts]) => (
                        <div key={k} style={{ marginBottom: '0.5rem', border: '1px dashed var(--color-border)', padding: '0.5rem', borderRadius: 'var(--radius)', background: 'var(--color-surface)' }}>
                          <div style={{ display: 'flex', gap: '0.4rem', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                            <span style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--color-primary)', fontFamily: 'monospace' }}>Parent value: "{k}"</span>
                            <button className="form-designer-icon-button" style={{ color: 'var(--color-danger)' }} type="button" onClick={() => delMapEntry(k)}><Trash2 size={13} /></button>
                          </div>
                          <div>
                            <OptionListInput
                              value={opts as string[]}
                              onCommit={(next) => updSel({ options_map: { ...om, [k]: next } })}
                              placeholder="Available options: Option A, Option B, ..."
                            />
                          </div>
                        </div>
                      ))}
                      <div style={{ display: 'flex', gap: '0.4rem', marginTop: '0.2rem' }}>
                        <input
                          className="input-field"
                          style={{ flex: 1 }}
                          value={mapKey}
                          onChange={(e) => setMapKey(e.target.value)}
                          placeholder="New parent value…"
                          onKeyDown={(e) => e.key === 'Enter' && addMapEntry()}
                        />
                        <button className="btn-outline" style={{ whiteSpace: 'nowrap' }} type="button" onClick={addMapEntry}><Plus size={13} style={{ marginRight: '0.2rem' }}/> Add mapping</button>
                      </div>
                    </div>
                  </>
                )}

                {/* Async select */}
                {sel.type === 'async_select' && (
                  <div className="form-designer-property-row">
                    <label className="form-designer-property-label">Filter by asset type name</label>
                    <input
                      className="input-field"
                      value={sel.data_source?.filter_by_type_name || ''}
                      onChange={(e) => updSel({ data_source: { ...(sel.data_source || { type: 'api', endpoint: '/proxy/assets' }), filter_by_type_name: e.target.value } })}
                      placeholder="e.g. Inverter"
                    />
                  </div>
                )}

                {/* Table Columns Configurator */}
                {sel.type === 'table' && (
                  <div className="form-designer-property-row" style={{ marginTop: '1rem' }}>
                    <div className="form-designer-section-title" style={{ fontSize: '0.85rem' }}>Table Columns</div>
                    <label className="form-designer-switch" style={{ marginTop: '0.75rem' }}>
                      <input
                        type="checkbox"
                        checked={!!sel.show_serial_number}
                        onChange={(e) => updSel({ show_serial_number: e.target.checked })}
                      />
                      Show serial number column
                    </label>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.5rem' }}>
                      {(sel.columns || []).map((col, idx) => (
                        <div key={idx} style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', padding: '0.6rem', border: '1px solid var(--color-border)', borderRadius: 'var(--radius)', background: 'var(--color-bg-subtle)' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontSize: '0.75rem', fontWeight: 600 }}>Column {idx + 1}</span>
                            <button className="form-designer-icon-button" type="button" onClick={() => {
                              const newCols = [...(sel.columns || [])];
                              newCols.splice(idx, 1);
                              updSel({ columns: newCols });
                            }}><Trash2 size={12} /></button>
                          </div>
                          
                          <input className="input-field" placeholder="Column ID (e.g. part_no)" value={col.id} onChange={(e) => {
                            const newCols = [...(sel.columns || [])];
                            newCols[idx] = { ...newCols[idx], id: sl(e.target.value) };
                            updSel({ columns: newCols });
                          }} />
                          
                          <input className="input-field" placeholder="Column Label (e.g. Part Number)" value={col.label} onChange={(e) => {
                            const newCols = [...(sel.columns || [])];
                            newCols[idx] = { ...newCols[idx], label: e.target.value };
                            updSel({ columns: newCols });
                          }} />
                          
                          <select className="input-field" value={col.type} onChange={(e) => {
                            const newCols = [...(sel.columns || [])];
                            newCols[idx] = { ...newCols[idx], type: e.target.value };
                            updSel({ columns: newCols });
                          }}>
                            <option value="string">Text</option>
                            <option value="number">Number</option>
                            <option value="date">Date</option>
                            <option value="dropdown">Dropdown</option>
                          </select>

                          {col.type === 'dropdown' && (
                            <OptionListInput
                              value={col.options || []}
                              placeholder="Options (comma separated)"
                              onCommit={(options) => {
                                const newCols = [...(sel.columns || [])];
                                newCols[idx] = { ...newCols[idx], options };
                                updSel({ columns: newCols });
                              }}
                            />
                          )}
                        </div>
                      ))}
                      <button className="btn-outline" type="button" onClick={() => {
                        const newCols = [...(sel.columns || [])];
                        newCols.push({ id: `col_${newCols.length + 1}`, type: 'string', label: `Column ${newCols.length + 1}` });
                        updSel({ columns: newCols });
                      }} style={{ justifyContent: 'center', padding: '0.4rem' }}>
                        <Plus size={14} style={{ marginRight: '0.3rem' }} /> Add Column
                      </button>
                    </div>
                  </div>
                )}

                {/* Conditional visibility */}
                <button className="form-designer-advanced-toggle" type="button" onClick={() => setShowAdv((p) => !p)}>
                  {showAdv ? '▲' : '▼'} Conditional visibility
                </button>
                {showAdv && (
                  <div className="form-designer-advanced-panel">
                    <div className="form-designer-property-row">
                      <label className="form-designer-property-label">Show when field</label>
                      <select
                        className="input-field"
                        value={sel.visible_if?.field || ''}
                        onChange={(e) => updSel({ visible_if: e.target.value ? { field: e.target.value, value: sel.visible_if?.value || '' } : undefined })}
                      >
                        <option value="">Always visible</option>
                        {others.map((f) => <option key={f.id} value={f.id}>{f.label} ({f.id})</option>)}
                      </select>
                    </div>
                    {sel.visible_if?.field && (
                      <div className="form-designer-property-row">
                        <label className="form-designer-property-label">Equals value</label>
                        <input
                          className="input-field"
                          value={sel.visible_if?.value || ''}
                          onChange={(e) => updSel({ visible_if: { field: sel.visible_if!.field, value: e.target.value } })}
                        />
                      </div>
                    )}
                  </div>
                )}

                {/* Layout */}
                <div className="form-designer-inline-grid" style={{ gap: '0.5rem' }}>
                  <div className="form-designer-property-row">
                    <label className="form-designer-property-label">Width (cols 1–12)</label>
                    <input
                      className="input-field"
                      type="number"
                      min={1}
                      max={12}
                      value={sel.layout?.w || defL(sel).w}
                      onChange={(e) => updLayout({ w: Number(e.target.value) })}
                    />
                  </div>
                  <div className="form-designer-property-row">
                    <label className="form-designer-property-label">Height (rows)</label>
                    <input
                      className="input-field"
                      type="number"
                      min={2}
                      value={sel.layout?.h || defL(sel).h}
                      onChange={(e) => updLayout({ h: Number(e.target.value) })}
                    />
                  </div>
                </div>
              </div>
            ) : (
              <div className="form-designer-inspector-empty">
                <PenTool size={28} style={{ opacity: 0.25, marginBottom: '0.75rem' }} />
                <p style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem', textAlign: 'center' }}>
                  Click any field on the canvas to select it, then edit its properties here.
                </p>
                <button className="btn-outline" type="button" style={{ marginTop: '0.75rem', fontSize: '0.8rem' }} onClick={() => setSideTab('library')}>
                  ← Back to Components
                </button>
              </div>
            )
          )}
        </aside>
      </div>
    </div>
  );
}

