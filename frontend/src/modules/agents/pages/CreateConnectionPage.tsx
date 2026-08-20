import { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  ArrowLeft,
  Search,
  CheckCircle2,
  XCircle,
  Loader2,
  ChevronDown,
  ChevronRight,
  Eye,
  EyeOff,
  Zap,
} from 'lucide-react';
import { useScopedNavigate } from '@/lib/appNavigation';
import {
  useConnectionProviders,
  useCreateCatalogConnection,
  useTestConnection,
  useCatalogs,
} from '@/modules/agents/hooks/useCatalogConnections';
import { ProviderLogo } from '@/modules/agents/components/CreateConnectionWizard';
import { useToast } from '@/lib/toast';

export default function CreateConnectionPage() {
  const navigate = useScopedNavigate();
  const [searchParams] = useSearchParams();
  const toast = useToast();

  const initialProviderParam = searchParams.get('provider');
  const initialCatalogParam = searchParams.get('catalog') || '';
  const initialSchemaParam = searchParams.get('schema') || '';

  const { data: providers = [], isLoading: isLoadingProviders } = useConnectionProviders();
  const { data: catalogs = [] } = useCatalogs();
  const createConn = useCreateCatalogConnection();
  const testConn = useTestConnection();

  const [step, setStep] = useState<1 | 2 | 3>(1);

  // Step 1 state: Name, Type dropdown, optional Catalog & Schema location
  const [connName, setConnName] = useState<string>('');
  const [selectedTypeId, setSelectedTypeId] = useState<string>('');
  const [catalogName, setCatalogName] = useState<string>(initialCatalogParam);
  const [schemaName, setSchemaName] = useState<string>(initialSchemaParam);
  const [description, setDescription] = useState<string>('');

  // Custom Dropdown Open State
  const [isTypeDropdownOpen, setIsTypeDropdownOpen] = useState(false);
  const [dropdownSearch, setDropdownSearch] = useState('');

  // Step 2 state: Dynamic Config & Auth values + password visibility
  const [configValues, setConfigValues] = useState<Record<string, any>>({});
  const [authValues, setAuthValues] = useState<Record<string, any>>({});
  const [showPasswordMap, setShowPasswordMap] = useState<Record<string, boolean>>({});

  // Step 3 state: Live Test outcome
  const [testResult, setTestResult] = useState<{
    tested: boolean;
    success: boolean;
    message: string;
    latency_ms: number;
  } | null>(null);

  // Selected Provider object
  const selectedProvider = useMemo(() => {
    return providers.find((p) => p.type_id === selectedTypeId) || null;
  }, [providers, selectedTypeId]);

  // Selected Catalog object & schemas
  const activeCatalog = useMemo(() => {
    if (!catalogName) return null;
    return catalogs.find((c) => c.name.toLowerCase() === catalogName.toLowerCase()) || null;
  }, [catalogs, catalogName]);

  const availableSchemas = useMemo(() => {
    return activeCatalog?.schemas || [];
  }, [activeCatalog]);

  // Handle URL param initialization or default selection
  useEffect(() => {
    if (providers.length > 0 && !selectedTypeId) {
      const match = initialProviderParam
        ? providers.find((p) => p.type_id === initialProviderParam)
        : providers[0];
      if (match) {
        handleSelectProviderType(match.type_id);
      }
    }
  }, [initialProviderParam, providers]);

  function handleSelectProviderType(typeId: string) {
    setSelectedTypeId(typeId);
    setIsTypeDropdownOpen(false);
    setDropdownSearch('');

    const provider = providers.find((p) => p.type_id === typeId);
    if (provider) {
      const initialCfg: Record<string, any> = {};
      provider.config_fields.forEach((f) => {
        if (f.default !== undefined) initialCfg[f.name] = f.default;
      });
      setConfigValues(initialCfg);

      const initialAuth: Record<string, any> = {};
      provider.auth_fields.forEach((f) => {
        if (f.default !== undefined) initialAuth[f.name] = f.default;
      });
      setAuthValues(initialAuth);
      setTestResult(null);
    }
  }

  function togglePasswordVisibility(fieldName: string) {
    setShowPasswordMap((prev) => ({
      ...prev,
      [fieldName]: !prev[fieldName],
    }));
  }

  function handleRunLiveTest() {
    if (!selectedProvider) return;
    setTestResult(null);
    testConn.mutate(
      {
        connector_type: selectedProvider.type_id,
        config: configValues,
        auth_config: authValues,
      },
      {
        onSuccess: (data) => {
          setTestResult({
            tested: true,
            success: data.success,
            message: data.message,
            latency_ms: data.latency_ms,
          });
          if (data.success) {
            toast.success(`Connection test passed (${data.latency_ms}ms)`);
          } else {
            toast.error(data.message);
          }
        },
        onError: (err: any) => {
          setTestResult({
            tested: true,
            success: false,
            message: err.message || 'Failed to reach server',
            latency_ms: 0,
          });
          toast.error('Test connection failed');
        },
      }
    );
  }

  async function handleFinishCreate() {
    if (!selectedProvider) {
      toast.error('Please select a connection type.');
      return;
    }
    if (!connName.trim()) {
      toast.error('Connection name is required.');
      return;
    }

    try {
      await createConn.mutateAsync({
        catalog: catalogName.trim() || undefined,
        schema: schemaName.trim() || undefined,
        name: connName.trim(),
        connector_type: selectedProvider.type_id,
        category: selectedProvider.category,
        description: description.trim() || undefined,
        config: configValues,
        auth_config: authValues,
        status: 'active',
      });

      toast.success(`Connection "${connName}" created successfully!`);
      navigate('/connections');
    } catch (err: any) {
      toast.error(err.message || 'Failed to save connection');
    }
  }

  const filteredDropdownProviders = providers.filter(
    (p) =>
      !dropdownSearch.trim() ||
      p.name.toLowerCase().includes(dropdownSearch.toLowerCase()) ||
      p.category.toLowerCase().includes(dropdownSearch.toLowerCase()) ||
      p.type_id.toLowerCase().includes(dropdownSearch.toLowerCase())
  );

  const displayScope = catalogName && schemaName ? `${catalogName}.${schemaName}.${connName || 'name'}` : (connName || 'name');

  return (
    <div style={{ maxWidth: 760, margin: '20px auto', padding: '0 16px 60px' }}>
      {/* Back Button */}
      <button
        type="button"
        className="btn btn-secondary"
        onClick={() => navigate('/connections')}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          marginBottom: 16,
          fontSize: '0.82rem',
          padding: '5px 10px',
          color: 'var(--color-text-muted)',
        }}
      >
        <ArrowLeft size={13} /> Back to Connections
      </button>

      {/* Stepper Progress Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 18px',
          background: 'var(--color-surface)',
          borderRadius: 6,
          border: '1px solid var(--color-border)',
          marginBottom: 16,
        }}
      >
        <div
          onClick={() => setStep(1)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            cursor: 'pointer',
            color: step === 1 ? 'var(--color-text)' : 'var(--color-text-muted)',
            fontWeight: step === 1 ? 550 : 450,
            fontSize: '0.82rem',
          }}
        >
          <span
            style={{
              width: 20,
              height: 20,
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '0.72rem',
              fontWeight: 600,
              background: step === 1 ? 'var(--color-surface-hover)' : 'transparent',
              color: 'var(--color-text)',
              border: '1px solid var(--color-border)',
            }}
          >
            {step > 1 ? '✓' : '1'}
          </span>
          <span>1. Details</span>
        </div>

        <ChevronRight size={13} style={{ color: 'var(--color-text-muted)', opacity: 0.4 }} />

        <div
          onClick={() => {
            if (connName.trim() && selectedTypeId) setStep(2);
          }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            cursor: connName.trim() && selectedTypeId ? 'pointer' : 'default',
            color: step === 2 ? 'var(--color-text)' : 'var(--color-text-muted)',
            fontWeight: step === 2 ? 550 : 450,
            fontSize: '0.82rem',
          }}
        >
          <span
            style={{
              width: 20,
              height: 20,
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '0.72rem',
              fontWeight: 600,
              background: step === 2 ? 'var(--color-surface-hover)' : 'transparent',
              color: 'var(--color-text)',
              border: '1px solid var(--color-border)',
            }}
          >
            {step > 2 ? '✓' : '2'}
          </span>
          <span>2. Authentication</span>
        </div>

        <ChevronRight size={13} style={{ color: 'var(--color-text-muted)', opacity: 0.4 }} />

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            color: step === 3 ? 'var(--color-text)' : 'var(--color-text-muted)',
            fontWeight: step === 3 ? 550 : 450,
            fontSize: '0.82rem',
          }}
        >
          <span
            style={{
              width: 20,
              height: 20,
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '0.72rem',
              fontWeight: 600,
              background: step === 3 ? 'var(--color-surface-hover)' : 'transparent',
              color: 'var(--color-text)',
              border: '1px solid var(--color-border)',
            }}
          >
            3
          </span>
          <span>3. Review & Test</span>
        </div>
      </div>

      {/* Main Card */}
      <div
        style={{
          background: 'var(--color-surface)',
          borderRadius: 6,
          border: '1px solid var(--color-border)',
          overflow: 'hidden',
        }}
      >
        {/* Step Header Inside Card */}
        <div
          style={{
            background: 'var(--color-surface)',
            padding: '20px 24px 16px',
            borderBottom: '1px solid var(--color-border)',
          }}
        >
          <div style={{ fontSize: '0.78rem', fontWeight: 500, color: 'var(--color-text-muted)', marginBottom: 4 }}>
            Step {step} of 3
          </div>
          <h2 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 600, color: 'var(--color-text)', letterSpacing: '-0.01em' }}>
            {step === 1 && 'Connection Details'}
            {step === 2 && 'Authentication & Configuration'}
            {step === 3 && 'Review & Test Connection'}
          </h2>
        </div>

        {/* Step Content */}
        <div style={{ padding: '24px' }}>
          {/* ── STEP 1: Details & Type ── */}
          {step === 1 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              {/* Connection Name */}
              <div>
                <label style={{ display: 'block', fontSize: '0.84rem', fontWeight: 500, color: 'var(--color-text)', marginBottom: 2 }}>
                  Connection Name *
                </label>
                <p style={{ margin: '0 0 6px', fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                  Unique identifier used to reference this connection.
                </p>
                <input
                  className="form-input"
                  placeholder="e.g. pg_analytics, stripe_api, prod_loki"
                  value={connName}
                  onChange={(e) => setConnName(e.target.value)}
                  autoFocus
                  required
                />
              </div>

              {/* Connection Type Dropdown */}
              <div style={{ position: 'relative' }}>
                <label style={{ display: 'block', fontSize: '0.84rem', fontWeight: 500, color: 'var(--color-text)', marginBottom: 2 }}>
                  Connection Type *
                </label>
                <p style={{ margin: '0 0 6px', fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                  The source database, API provider, or observability service to connect.
                </p>

                {/* Dropdown Trigger */}
                <div
                  onClick={() => setIsTypeDropdownOpen(!isTypeDropdownOpen)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 12px',
                    borderRadius: 6,
                    border: '1px solid var(--color-border)',
                    background: 'var(--color-surface)',
                    cursor: 'pointer',
                    minHeight: 38,
                  }}
                >
                  {selectedProvider ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <ProviderLogo typeId={selectedProvider.type_id} size={18} />
                      <span style={{ fontWeight: 500, fontSize: '0.86rem', color: 'var(--color-text)' }}>
                        {selectedProvider.name}
                      </span>
                      <span
                        style={{
                          fontSize: '0.68rem',
                          textTransform: 'uppercase',
                          padding: '1px 6px',
                          borderRadius: 4,
                          background: 'var(--color-surface-hover)',
                          color: 'var(--color-text-muted)',
                          fontWeight: 500,
                        }}
                      >
                        {selectedProvider.category}
                      </span>
                    </div>
                  ) : (
                    <span style={{ color: 'var(--color-text-muted)', fontSize: '0.86rem' }}>
                      Select a connection type...
                    </span>
                  )}
                  <ChevronDown size={14} style={{ color: 'var(--color-text-muted)' }} />
                </div>

                {/* Dropdown Menu */}
                {isTypeDropdownOpen && (
                  <div
                    style={{
                      position: 'absolute',
                      top: '100%',
                      left: 0,
                      right: 0,
                      marginTop: 4,
                      background: 'var(--color-surface)',
                      borderRadius: 6,
                      border: '1px solid var(--color-border)',
                      boxShadow: '0 8px 24px rgba(0,0,0,0.08)',
                      zIndex: 100,
                      maxHeight: 300,
                      display: 'flex',
                      flexDirection: 'column',
                      overflow: 'hidden',
                    }}
                  >
                    <div style={{ padding: '6px 8px', borderBottom: '1px solid var(--color-border)' }}>
                      <div className="search-bar-wrapper" style={{ width: '100%' }}>
                        <Search size={13} className="search-icon" />
                        <input
                          className="search-input"
                          placeholder="Search type..."
                          value={dropdownSearch}
                          onChange={(e) => setDropdownSearch(e.target.value)}
                          autoFocus
                          onClick={(e) => e.stopPropagation()}
                        />
                      </div>
                    </div>

                    <div style={{ overflowY: 'auto', padding: '4px 0' }}>
                      {isLoadingProviders ? (
                        <div style={{ padding: 14, textAlign: 'center' }}>
                          <Loader2 className="spin" size={16} />
                        </div>
                      ) : filteredDropdownProviders.length === 0 ? (
                        <div style={{ padding: '10px 14px', fontSize: '0.80rem', color: 'var(--color-text-muted)' }}>
                          No connection types matching "{dropdownSearch}"
                        </div>
                      ) : (
                        filteredDropdownProviders.map((p) => (
                          <div
                            key={p.type_id}
                            onClick={() => handleSelectProviderType(p.type_id)}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              padding: '7px 12px',
                              cursor: 'pointer',
                              background: p.type_id === selectedTypeId ? 'var(--color-surface-hover)' : 'transparent',
                              transition: 'background 0.1s ease',
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <ProviderLogo typeId={p.type_id} size={18} />
                              <span style={{ fontSize: '0.84rem', fontWeight: p.type_id === selectedTypeId ? 550 : 400, color: 'var(--color-text)' }}>
                                {p.name}
                              </span>
                            </div>

                            <span style={{ fontSize: '0.68rem', textTransform: 'uppercase', color: 'var(--color-text-muted)' }}>
                              {p.category}
                            </span>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Destination Catalog */}
              <div>
                <label style={{ display: 'block', fontSize: '0.84rem', fontWeight: 500, color: 'var(--color-text)', marginBottom: 2 }}>
                  Catalog Location
                </label>
                <p style={{ margin: '0 0 6px', fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                  Catalog location in data catalog. Leave unselected for account-level connection.
                </p>
                <select
                  className="form-input"
                  value={catalogName}
                  onChange={(e) => {
                    const val = e.target.value;
                    setCatalogName(val);
                    if (!val) {
                      setSchemaName('');
                    } else {
                      const matched = catalogs.find((c) => c.name === val);
                      if (matched && matched.schemas.length > 0) {
                        setSchemaName(matched.schemas[0].name);
                      } else {
                        setSchemaName('');
                      }
                    }
                  }}
                >
                  <option value="">-- None (Account-Level Connection) --</option>
                  {catalogs.map((cat) => (
                    <option key={cat.name} value={cat.name}>
                      {cat.name} ({cat.catalog_type || 'catalog'})
                    </option>
                  ))}
                </select>
              </div>

              {/* Destination Schema */}
              <div>
                <label style={{ display: 'block', fontSize: '0.84rem', fontWeight: 500, color: 'var(--color-text)', marginBottom: 2 }}>
                  Schema
                </label>
                <p style={{ margin: '0 0 6px', fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                  Schema namespace inside the selected catalog.
                </p>
                <select
                  className="form-input"
                  value={schemaName}
                  onChange={(e) => setSchemaName(e.target.value)}
                  disabled={!catalogName}
                >
                  <option value="">-- None --</option>
                  {availableSchemas.map((sch) => (
                    <option key={sch.name} value={sch.name}>
                      {sch.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Description */}
              <div>
                <label style={{ display: 'block', fontSize: '0.84rem', fontWeight: 500, color: 'var(--color-text)', marginBottom: 2 }}>
                  Description
                </label>
                <p style={{ margin: '0 0 6px', fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                  Optional comment or purpose of this connection.
                </p>
                <textarea
                  className="form-input"
                  rows={2}
                  placeholder="e.g. Production analytics database replica"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>
            </div>
          )}

          {/* ── STEP 2: Authentication & Connection Settings ── */}
          {step === 2 && selectedProvider && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              {/* Dynamic Config Fields */}
              {selectedProvider.config_fields.map((f) => (
                <div key={f.name}>
                  <label style={{ display: 'block', fontSize: '0.84rem', fontWeight: 500, color: 'var(--color-text)', marginBottom: 2 }}>
                    {f.label} {f.required && '*'}
                  </label>
                  <p style={{ margin: '0 0 6px', fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                    {f.help_text || `Configuration value for ${f.label.toLowerCase()}.`}
                  </p>
                  {f.type === 'textarea' ? (
                    <textarea
                      className="form-input"
                      rows={3}
                      placeholder={f.placeholder}
                      value={configValues[f.name] || ''}
                      onChange={(e) => setConfigValues({ ...configValues, [f.name]: e.target.value })}
                    />
                  ) : f.type === 'select' ? (
                    <select
                      className="form-input"
                      value={configValues[f.name] || ''}
                      onChange={(e) => setConfigValues({ ...configValues, [f.name]: e.target.value })}
                    >
                      {(f.options || []).map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  ) : f.type === 'boolean' ? (
                    <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: '0.84rem', color: 'var(--color-text)', marginTop: 4 }}>
                      <input
                        type="checkbox"
                        checked={Boolean(configValues[f.name])}
                        onChange={(e) => setConfigValues({ ...configValues, [f.name]: e.target.checked })}
                      />
                      {f.label}
                    </label>
                  ) : (
                    <input
                      type={f.type === 'number' ? 'number' : 'text'}
                      className="form-input"
                      placeholder={f.placeholder}
                      value={configValues[f.name] ?? ''}
                      onChange={(e) => setConfigValues({ ...configValues, [f.name]: f.type === 'number' ? Number(e.target.value) : e.target.value })}
                      required={f.required}
                    />
                  )}
                </div>
              ))}

              {/* Dynamic Auth Fields */}
              {selectedProvider.auth_fields.map((f) => (
                <div key={f.name}>
                  <label style={{ display: 'block', fontSize: '0.84rem', fontWeight: 500, color: 'var(--color-text)', marginBottom: 2 }}>
                    {f.label} {f.required && '*'}
                  </label>
                  <p style={{ margin: '0 0 6px', fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                    {f.help_text || `Credentials for ${f.label.toLowerCase()}.`}
                  </p>
                  {f.type === 'password' ? (
                    <div style={{ position: 'relative' }}>
                      <input
                        type={showPasswordMap[f.name] ? 'text' : 'password'}
                        className="form-input"
                        placeholder={f.placeholder || '••••••••'}
                        value={authValues[f.name] || ''}
                        onChange={(e) => setAuthValues({ ...authValues, [f.name]: e.target.value })}
                        required={f.required}
                        style={{ paddingRight: 36 }}
                      />
                      <button
                        type="button"
                        onClick={() => togglePasswordVisibility(f.name)}
                        style={{
                          position: 'absolute',
                          right: 8,
                          top: '50%',
                          transform: 'translateY(-50%)',
                          background: 'none',
                          border: 'none',
                          cursor: 'pointer',
                          color: 'var(--color-text-muted)',
                          padding: 4,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                        title={showPasswordMap[f.name] ? 'Hide password' : 'Show password'}
                      >
                        {showPasswordMap[f.name] ? <EyeOff size={14} /> : <Eye size={14} />}
                      </button>
                    </div>
                  ) : f.type === 'textarea' ? (
                    <textarea
                      className="form-input"
                      rows={3}
                      placeholder={f.placeholder}
                      value={authValues[f.name] || ''}
                      onChange={(e) => setAuthValues({ ...authValues, [f.name]: e.target.value })}
                    />
                  ) : f.type === 'select' ? (
                    <select
                      className="form-input"
                      value={authValues[f.name] || ''}
                      onChange={(e) => setAuthValues({ ...authValues, [f.name]: e.target.value })}
                    >
                      {(f.options || []).map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="text"
                      className="form-input"
                      placeholder={f.placeholder || (f.name === 'username' ? 'username' : '')}
                      value={authValues[f.name] || ''}
                      onChange={(e) => setAuthValues({ ...authValues, [f.name]: e.target.value })}
                      required={f.required}
                    />
                  )}
                </div>
              ))}
            </div>
          )}

          {/* ── STEP 3: Review & Test ── */}
          {step === 3 && selectedProvider && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* Summary Box */}
              <div
                style={{
                  padding: '14px 18px',
                  borderRadius: 6,
                  background: 'var(--color-surface-hover)',
                  border: '1px solid var(--color-border)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                  <ProviderLogo typeId={selectedProvider.type_id} size={24} />
                  <div>
                    <div style={{ fontWeight: 550, fontSize: '0.90rem', color: 'var(--color-text)' }}>
                      {displayScope}
                    </div>
                    <div style={{ fontSize: '0.76rem', color: 'var(--color-text-muted)' }}>
                      {selectedProvider.name} • {catalogName && schemaName ? `Catalog: ${catalogName}.${schemaName}` : 'Account Level'}
                    </div>
                  </div>
                </div>
                {description && (
                  <div style={{ fontSize: '0.80rem', color: 'var(--color-text-muted)', marginTop: 4 }}>
                    {description}
                  </div>
                )}
              </div>

              {/* Live Test Box */}
              <div
                style={{
                  padding: '16px 18px',
                  borderRadius: 6,
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-surface)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10, flexWrap: 'wrap', gap: 8 }}>
                  <div>
                    <div style={{ fontWeight: 550, fontSize: '0.86rem', color: 'var(--color-text)' }}>
                      Test Connectivity
                    </div>
                    <div style={{ fontSize: '0.76rem', color: 'var(--color-text-muted)' }}>
                      Validate network access and credentials before saving.
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={handleRunLiveTest}
                    disabled={testConn.isPending}
                    style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 12px', fontSize: '0.80rem' }}
                  >
                    {testConn.isPending ? <Loader2 size={13} className="spin" /> : <Zap size={13} />}
                    {testConn.isPending ? 'Testing...' : 'Test Connection'}
                  </button>
                </div>

                {testResult && (
                  <div
                    style={{
                      padding: '8px 12px',
                      borderRadius: 6,
                      fontSize: '0.80rem',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      background: 'var(--color-surface-hover)',
                      border: '1px solid var(--color-border)',
                      color: testResult.success ? 'var(--color-success)' : 'var(--color-danger)',
                    }}
                  >
                    {testResult.success ? <CheckCircle2 size={15} /> : <XCircle size={15} />}
                    <span style={{ flex: 1 }}>{testResult.message}</span>
                    {testResult.latency_ms > 0 && <span>({testResult.latency_ms}ms)</span>}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Card Footer Actions */}
        <div
          style={{
            padding: '14px 24px',
            background: 'var(--color-surface)',
            borderTop: '1px solid var(--color-border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div>
            {step > 1 && (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setStep((s) => (s - 1) as any)}
                style={{ fontSize: '0.82rem', padding: '6px 12px' }}
              >
                Back
              </button>
            )}
          </div>

          <div style={{ display: 'flex', gap: 8 }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => navigate('/connections')}
              style={{ fontSize: '0.82rem', padding: '6px 12px' }}
            >
              Cancel
            </button>

            {step < 3 ? (
              <button
                type="button"
                className="btn btn-primary"
                disabled={step === 1 && (!connName.trim() || !selectedTypeId)}
                onClick={() => {
                  if (step === 1) {
                    if (!connName.trim()) {
                      toast.error('Please enter a connection name.');
                      return;
                    }
                    if (!selectedTypeId) {
                      toast.error('Please select a connection type.');
                      return;
                    }
                  }
                  setStep((s) => (s + 1) as any);
                }}
                style={{ fontSize: '0.82rem', padding: '6px 14px' }}
              >
                Next
              </button>
            ) : (
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleFinishCreate}
                disabled={createConn.isPending}
                style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.82rem', padding: '6px 14px' }}
              >
                {createConn.isPending && <Loader2 size={13} className="spin" />}
                {createConn.isPending ? 'Creating...' : 'Create'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
