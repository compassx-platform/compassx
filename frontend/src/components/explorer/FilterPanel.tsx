/** FilterPanel – search, severity, status, and breakdown type filters */

interface FilterPanelProps {
  filters: Record<string, string>;
  onChange: (filters: Record<string, string>) => void;
}

export default function FilterPanel({ filters, onChange }: FilterPanelProps) {
  const set = (key: string, val: string) => {
    const next = { ...filters, [key]: val };
    if (!val) delete next[key];
    onChange(next);
  };

  return (
    <div
      className="glass animate-fade-in"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 12,
        padding: '1rem 1.25rem',
        borderRadius: 'var(--radius)',
        marginBottom: '1.5rem',
      }}
    >
      <input
        className="input-field"
        placeholder="Search description…"
        value={filters.search || ''}
        onChange={(e) => set('search', e.target.value)}
        style={{ flex: '1 1 200px', maxWidth: 300 }}
      />
      <select
        className="input-field"
        value={filters.severity || ''}
        onChange={(e) => set('severity', e.target.value)}
        style={{ flex: '0 0 150px' }}
      >
        <option value="">All Severities</option>
        <option value="low">Low</option>
        <option value="medium">Medium</option>
        <option value="high">High</option>
        <option value="critical">Critical</option>
      </select>
      <select
        className="input-field"
        value={filters.status || ''}
        onChange={(e) => set('status', e.target.value)}
        style={{ flex: '0 0 140px' }}
      >
        <option value="">All Statuses</option>
        <option value="OPEN">Open</option>
        <option value="IN_PROGRESS">In Progress</option>
        <option value="RESOLVED">Resolved</option>
        <option value="CLOSED">Closed</option>
      </select>
      <select
        className="input-field"
        value={filters.breakdown_type || ''}
        onChange={(e) => set('breakdown_type', e.target.value)}
        style={{ flex: '0 0 160px' }}
      >
        <option value="">All Types</option>
        <option value="inverter">Inverter</option>
        <option value="grid">Grid</option>
        <option value="transformer">Transformer</option>
        <option value="turbine">Turbine</option>
        <option value="other">Other</option>
      </select>
    </div>
  );
}
