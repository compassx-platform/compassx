import React, { useState } from 'react';
import {
  Search,
  Plus,
  Play,
  Settings,
  Trash2,
  Copy,
  Clock,
  Database,
  Bot,
  Zap,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Sparkles,
  Layers,
  FileCode,
  LayoutDashboard,
  ExternalLink,
  Code2,
  Workflow,
  X,
  Eye,
  Shield,
  Lightbulb,
  Sun,
  Moon,
} from 'lucide-react';
import { useToast } from '@/lib/toast';
import { useThemeContext } from '@/design-system';
import { CompassXLogo } from '@/components/common/CompassXLogo';
import { PageTabs } from '@/components/common/PageTabs';
import { Table, type TableColumn } from '@/components/common/Table';
import { AppTable, type AppTableColumn } from '@/components/common/AppTable';
import ConfirmDialog from '@/components/common/ConfirmDialog';
import StatusPill from '@/modules/jobs/components/StatusPill';
import { CURATED_TECH_DATA_ICONS } from '@/components/icons/TechDataIcons';
import './design-system-showcase.css';

// ── Dummy Data Models ────────────────────────────────────────────────────────

interface PipelineItem {
  id: string;
  name: string;
  type: 'Ingestion' | 'AI Agent' | 'SQL Batch' | 'CDC Stream';
  status: 'active' | 'running' | 'paused' | 'failed' | 'queued' | 'archived';
  schedule: string;
  duration: string;
  owner: string;
  lastRun: string;
}

interface ComputeResourceItem {
  id: string;
  name: string;
  clusterType: string;
  state: 'running' | 'stopped' | 'error' | 'pending';
  cores: number;
  memoryGb: number;
  uptime: string;
}

const DUMMY_PIPELINES: PipelineItem[] = [
  {
    id: 'pipe-1',
    name: 'Customer 360 Feature Ingestion',
    type: 'Ingestion',
    status: 'running',
    schedule: 'Every 2 hours',
    duration: '4m 12s',
    owner: 'Sarah Chen',
    lastRun: 'Just now',
  },
  {
    id: 'pipe-2',
    name: 'Enterprise Financial Agent Executor',
    type: 'AI Agent',
    status: 'active',
    schedule: 'Continuous Stream',
    duration: '142ms avg',
    owner: 'Alex Rivera',
    lastRun: '2 mins ago',
  },
  {
    id: 'pipe-3',
    name: 'Daily Warehouse Sales Aggregation',
    type: 'SQL Batch',
    status: 'active',
    schedule: 'Daily at 00:00 UTC',
    duration: '12m 45s',
    owner: 'David Kim',
    lastRun: '5 hours ago',
  },
  {
    id: 'pipe-4',
    name: 'Stripe Payments CDC Pipeline',
    type: 'CDC Stream',
    status: 'paused',
    schedule: 'Real-time CDC',
    duration: '18m 02s',
    owner: 'Jessica Taylor',
    lastRun: 'Yesterday',
  },
  {
    id: 'pipe-5',
    name: 'LLM Document Indexing & Embeddings',
    type: 'AI Agent',
    status: 'failed',
    schedule: 'Hourly',
    duration: '1m 20s',
    owner: 'Michael Scott',
    lastRun: '10 mins ago',
  },
];

const DUMMY_COMPUTE: ComputeResourceItem[] = [
  { id: 'cmp-1', name: 'duckdb-analytics-node-01', clusterType: 'DuckDB Engine', state: 'running', cores: 8, memoryGb: 32, uptime: '14d 2h' },
  { id: 'cmp-2', name: 'spark-worker-large-02', clusterType: 'Apache Spark', state: 'running', cores: 16, memoryGb: 64, uptime: '6d 18h' },
  { id: 'cmp-3', name: 'agent-sandbox-runner-03', clusterType: 'Container Runtime', state: 'stopped', cores: 4, memoryGb: 16, uptime: '-' },
  { id: 'cmp-4', name: 'trino-coordinator-main', clusterType: 'Trino Engine', state: 'running', cores: 32, memoryGb: 128, uptime: '45d 6h' },
];

export default function DesignSystemShowcasePage() {
  const toast = useToast();
  const { isDark, toggleTheme } = useThemeContext();

  // State management for interactive demo
  const [pageTab, setPageTab] = useState<'overview' | 'pipelines' | 'agents' | 'settings'>('overview');
  const [ucActiveTab, setUcActiveTab] = useState('columns');
  const [feedActiveTab, setFeedActiveTab] = useState('suggested');

  const [inputVal, setInputVal] = useState('CompassX Enterprise Lakehouse');
  const [searchVal, setSearchVal] = useState('');
  const [selectVal, setSelectVal] = useState('duckdb');
  const [textareaVal, setTextareaVal] = useState('Configuring intelligent orchestration engine...');
  const [radioVal, setRadioVal] = useState('cloud');

  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [showCustomModal, setShowCustomModal] = useState(false);
  const [isModalLoading, setIsModalLoading] = useState(false);
  const [copiedToken, setCopiedToken] = useState<string | null>(null);

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedToken(label);
    toast.success(`Copied ${label}: ${text}`);
    setTimeout(() => setCopiedToken(null), 2000);
  };

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  // Color Swatches
  const brandColors = [
    { name: '--color-primary', hex: '#1B6EF3', desc: 'Primary Action Blue' },
    { name: '--color-primary-hover', hex: '#1558C7', desc: 'Primary Button Hover' },
    { name: '--color-primary-bg', hex: '#EBF2FF', desc: 'Tinted Background / Active Tab' },
    { name: '--color-brand-primary', hex: '#2272B4', desc: 'Brand Core Blue' },
    { name: '--color-brand-secondary', hex: '#464644', desc: 'Brand Secondary' },
  ];

  const neutralColors = [
    { name: '--color-bg', hex: '#F5F5F5', desc: 'Page Background' },
    { name: '--color-surface', hex: '#FFFFFF', desc: 'Workspace Card / Panels' },
    { name: '--color-surface-hover', hex: '#F0F2F5', desc: 'List Row Hover State' },
    { name: '--color-border', hex: '#E0E0E0', desc: 'Subtle Dividers' },
    { name: '--color-border-strong', hex: '#C8C8C8', desc: 'Emphasized Borders' },
    { name: '--color-text', hex: '#1A1A1A', desc: 'Primary Text Color' },
    { name: '--color-text-muted', hex: '#6B6B6B', desc: 'Muted Supporting Text' },
    { name: '--color-text-subtle', hex: '#9E9E9E', desc: 'Subtle Placeholder / Labels' },
  ];

  const semanticColors = [
    { name: '--color-success', hex: '#2E7D32', bgHex: '#E8F5E9', desc: 'Active / Succeeded' },
    { name: '--color-warning', hex: '#E65100', bgHex: '#FFF3E0', desc: 'Warning / Paused' },
    { name: '--color-danger', hex: '#D32F2F', bgHex: '#FFEBEE', desc: 'Failed / Destructive' },
  ];

  // Business Table Columns
  const pipelineColumns: TableColumn<PipelineItem>[] = [
    {
      key: 'name',
      header: 'Pipeline / Job Name',
      render: (row) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ color: 'var(--color-primary)' }}>
            {row.type === 'AI Agent' ? <Bot size={16} /> : row.type === 'SQL Batch' ? <Database size={16} /> : <Zap size={16} />}
          </span>
          <div>
            <div style={{ fontWeight: 600, color: 'var(--color-text)' }}>{row.name}</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>{row.type} &bull; {row.schedule}</div>
          </div>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      width: '130px',
      render: (row) => <StatusPill state={row.status} size="sm" />,
    },
    {
      key: 'duration',
      header: 'Avg Duration',
      width: '120px',
      render: (row) => <span style={{ fontFamily: 'var(--font-family)', fontSize: '0.8125rem' }}>{row.duration}</span>,
    },
    {
      key: 'owner',
      header: 'Owner',
      width: '140px',
      render: (row) => <span style={{ fontSize: '0.8125rem', color: 'var(--color-text)' }}>{row.owner}</span>,
    },
  ];

  // AppTable Columns (Dense Technical)
  const computeColumns: AppTableColumn<ComputeResourceItem>[] = [
    {
      key: 'name',
      header: 'Resource Name',
      render: (row) => <span style={{ fontWeight: 600, fontFamily: 'monospace' }}>{row.name}</span>,
    },
    {
      key: 'clusterType',
      header: 'Engine Type',
      render: (row) => <span>{row.clusterType}</span>,
    },
    {
      key: 'state',
      header: 'Cluster State',
      render: (row) => <StatusPill state={row.state === 'running' ? 'active' : row.state === 'stopped' ? 'paused' : 'failed'} size="sm" />,
    },
    {
      key: 'cores',
      header: 'Cores',
      align: 'right',
      render: (row) => <span>{row.cores} vCPU</span>,
    },
    {
      key: 'memoryGb',
      header: 'Memory',
      align: 'right',
      render: (row) => <span>{row.memoryGb} GB</span>,
    },
    {
      key: 'uptime',
      header: 'Uptime',
      render: (row) => <span style={{ color: 'var(--color-text-muted)' }}>{row.uptime}</span>,
    },
  ];

  return (
    <div className="ds-showcase-root">
      {/* ── Sticky Subnav Bar ─────────────────────────────────────────────── */}
      <div className="ds-sticky-nav">
        <div className="ds-nav-inner">
          <div className="ds-nav-links">
            <button className="ds-nav-link-btn" onClick={() => scrollToSection('sec-tokens')}>
              <Sparkles size={13} /> Design Tokens
            </button>
            <button className="ds-nav-link-btn" onClick={() => scrollToSection('sec-buttons')}>
              <Zap size={13} /> Buttons & Actions
            </button>
            <button className="ds-nav-link-btn" onClick={() => scrollToSection('sec-forms')}>
              <Settings size={13} /> Forms & Inputs
            </button>
            <button className="ds-nav-link-btn" onClick={() => scrollToSection('sec-status')}>
              <CheckCircle2 size={13} /> Status & Badges
            </button>
            <button className="ds-nav-link-btn" onClick={() => scrollToSection('sec-tabs')}>
              <Layers size={13} /> Navigation & Tabs
            </button>
            <button className="ds-nav-link-btn" onClick={() => scrollToSection('sec-tables')}>
              <Database size={13} /> Business Tables
            </button>
            <button className="ds-nav-link-btn" onClick={() => scrollToSection('sec-apptables')}>
              <Code2 size={13} /> Operator AppTables
            </button>
            <button className="ds-nav-link-btn" onClick={() => scrollToSection('sec-modals')}>
              <Shield size={13} /> Modals & Dialogs
            </button>
            <button className="ds-nav-link-btn" onClick={() => scrollToSection('sec-icons')}>
              <Sparkles size={13} /> Tech Icons
            </button>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={toggleTheme}
            >
              {isDark ? <Sun size={13} style={{ color: '#D97706' }} /> : <Moon size={13} style={{ color: '#6366F1' }} />}
              <span>{isDark ? 'Light Theme' : 'Dark Theme'}</span>
            </button>
          </div>
        </div>
      </div>

      <div className="ds-showcase-container">
        {/* ── Hero Banner ─────────────────────────────────────────────────── */}
        <div className="ds-hero-header">
          <div className="ds-hero-title-row">
            <div>
              <h1 className="ds-hero-title">
                <CompassXLogo size={32} />
                CompassX Design System Showcase
                <span className="badge-count" style={{ marginLeft: 8 }}>Active</span>
              </h1>
              <p className="ds-hero-subtitle">
                Official component catalog and design language specifications for all CompassX applications.
                Showcasing the exact reusable components, CSS classes, tables, tabs, and form controls in active use.
              </p>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => setShowCustomModal(true)}
              >
                <Plus size={14} /> Open Demo Modal
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setShowConfirmModal(true)}
              >
                <Trash2 size={14} /> Open Confirm Dialog
              </button>
            </div>
          </div>
        </div>

        {/* ═══════════════════════════════════════════════════════════════════
            SECTION 1: DESIGN TOKENS
            ═══════════════════════════════════════════════════════════════════ */}
        <section id="sec-tokens" className="ds-section">
          <div className="ds-section-header">
            <div>
              <h2 className="ds-section-title">
                <Sparkles size={20} style={{ color: 'var(--color-primary)' }} />
                1. Core Design Tokens (CSS Variables)
              </h2>
              <p className="ds-section-desc">
                Color tokens, background surfaces, borders, and text scales defined in <code>index.css</code> and <code>variables.css</code>.
              </p>
            </div>
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Click card to copy variable</span>
          </div>

          <div className="ds-sub-title">Brand & Interactive Action Colors</div>
          <div className="ds-swatch-grid">
            {brandColors.map((c) => (
              <div
                key={c.name}
                className="ds-swatch-card"
                onClick={() => copyToClipboard(c.hex, c.name)}
              >
                <div className="ds-swatch-color" style={{ backgroundColor: c.hex }} />
                <div className="ds-swatch-info">
                  <span className="ds-swatch-name">{c.name}</span>
                  <span className="ds-swatch-hex">{copiedToken === c.name ? 'Copied!' : c.hex}</span>
                </div>
              </div>
            ))}
          </div>

          <div className="ds-sub-title">Neutral Workspace Surfaces & Borders</div>
          <div className="ds-swatch-grid">
            {neutralColors.map((c) => (
              <div
                key={c.name}
                className="ds-swatch-card"
                onClick={() => copyToClipboard(c.hex, c.name)}
              >
                <div className="ds-swatch-color" style={{ backgroundColor: c.hex, borderBottom: '1px solid var(--color-border)' }} />
                <div className="ds-swatch-info">
                  <span className="ds-swatch-name">{c.name}</span>
                  <span className="ds-swatch-hex">{c.hex}</span>
                </div>
              </div>
            ))}
          </div>

          <div className="ds-sub-title">Semantic State Tokens</div>
          <div className="ds-swatch-grid">
            {semanticColors.map((c) => (
              <div
                key={c.name}
                className="ds-swatch-card"
                onClick={() => copyToClipboard(c.hex, c.name)}
              >
                <div
                  className="ds-swatch-color"
                  style={{
                    backgroundColor: c.bgHex,
                    borderBottom: `3px solid ${c.hex}`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <div style={{ width: 18, height: 18, borderRadius: '50%', backgroundColor: c.hex }} />
                </div>
                <div className="ds-swatch-info">
                  <span className="ds-swatch-name">{c.name}</span>
                  <span className="ds-swatch-hex">{c.hex}</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ═══════════════════════════════════════════════════════════════════
            SECTION 2: BUTTONS & ACTIONS
            ═══════════════════════════════════════════════════════════════════ */}
        <section id="sec-buttons" className="ds-section">
          <div className="ds-section-header">
            <div>
              <h2 className="ds-section-title">
                <Zap size={20} style={{ color: 'var(--color-primary)' }} />
                2. Buttons & Icon Actions (<code>.btn</code>, <code>.btn-icon</code>)
              </h2>
              <p className="ds-section-desc">
                Standard button hierarchy from <code>_jobs_styles.css</code> and <code>index.css</code>.
              </p>
            </div>
          </div>

          <div className="ds-sub-title">Standard Buttons</div>
          <div className="ds-demo-box">
            <button type="button" className="btn btn-primary" onClick={() => toast.success('Primary button clicked')}>
              <Play size={14} /> Primary Action (.btn.btn-primary)
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => toast.info('Secondary button clicked')}>
              <Settings size={14} /> Secondary Action (.btn.btn-secondary)
            </button>
            <button type="button" className="btn btn-danger" onClick={() => toast.error('Danger button clicked')}>
              <Trash2 size={14} /> Danger Action (.btn.btn-danger)
            </button>
            <button type="button" className="btn btn-primary btn-sm">
              Small (.btn.btn-sm)
            </button>
            <button type="button" className="btn btn-primary" disabled>
              Disabled State
            </button>
          </div>

          <div className="ds-sub-title">Icon Buttons (<code>.btn-icon</code>)</div>
          <div className="ds-demo-box">
            <button type="button" className="btn-icon" title="Settings" aria-label="Settings" onClick={() => toast.info('Settings icon clicked')}>
              <Settings size={15} />
            </button>
            <button type="button" className="btn-icon" title="Copy" aria-label="Copy" onClick={() => toast.success('Copied to clipboard')}>
              <Copy size={15} />
            </button>
            <button type="button" className="btn-icon btn-icon-danger" title="Delete" aria-label="Delete" onClick={() => setShowConfirmModal(true)}>
              <Trash2 size={15} />
            </button>
            <button type="button" className="btn-icon btn-icon-muted" title="Muted Details" aria-label="Details">
              <Clock size={15} />
            </button>
            <button type="button" className="btn-icon" disabled title="Disabled Icon">
              <RotateCcw size={15} />
            </button>
          </div>
        </section>

        {/* ═══════════════════════════════════════════════════════════════════
            SECTION 3: FORMS & INPUT CONTROLS
            ═══════════════════════════════════════════════════════════════════ */}
        <section id="sec-forms" className="ds-section">
          <div className="ds-section-header">
            <div>
              <h2 className="ds-section-title">
                <Settings size={20} style={{ color: 'var(--color-primary)' }} />
                3. Form Controls & Search Bars (<code>.form-field</code>, <code>.search-bar-wrapper</code>)
              </h2>
              <p className="ds-section-desc">
                Standard form inputs, search bars, selects, and textareas used across creation modals and filters.
              </p>
            </div>
          </div>

          <div className="ds-grid-2">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* Search Bar */}
              <div className="form-field">
                <label className="form-label">Search Input (<code>.search-bar-wrapper</code>)</label>
                <div className="search-bar-wrapper" style={{ maxWidth: '100%' }}>
                  <Search size={14} className="search-icon" />
                  <input
                    className="search-input"
                    value={searchVal}
                    onChange={(e) => setSearchVal(e.target.value)}
                    placeholder="Search schemas, models, jobs, agents..."
                  />
                  {searchVal && (
                    <button type="button" className="btn-icon" style={{ width: 20, height: 20 }} onClick={() => setSearchVal('')}>
                      <X size={12} />
                    </button>
                  )}
                </div>
                <span className="form-hint">Standard filter bar found in Jobs, Compute, Ingestion, and Agents.</span>
              </div>

              {/* Text Input */}
              <div className="form-field">
                <label className="form-label">
                  Text Input (<code>.form-input</code>) <span style={{ color: 'var(--color-danger)' }}>*</span>
                </label>
                <input
                  className="form-input"
                  value={inputVal}
                  onChange={(e) => setInputVal(e.target.value)}
                  placeholder="Enter pipeline or connection name"
                />
                <span className="form-hint">Used for naming models, resources, and configuration targets.</span>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* Select */}
              <div className="form-field">
                <label className="form-label">Select Dropdown (<code>select.form-input</code>)</label>
                <select
                  className="form-input"
                  value={selectVal}
                  onChange={(e) => setSelectVal(e.target.value)}
                >
                  <option value="duckdb">DuckDB In-Memory Query Engine (Fast)</option>
                  <option value="spark">Apache Spark Cluster</option>
                  <option value="snowflake">Snowflake Virtual Warehouse</option>
                  <option value="trino">Trino Federated SQL</option>
                </select>
                <span className="form-hint">Engine selection dropdown.</span>
              </div>

              {/* Textarea */}
              <div className="form-field">
                <label className="form-label">Description (<code>textarea.form-input</code>)</label>
                <textarea
                  className="form-input"
                  rows={2}
                  value={textareaVal}
                  onChange={(e) => setTextareaVal(e.target.value)}
                />
              </div>

              {/* Radio Group */}
              <div className="form-field">
                <label className="form-label">Radio Group (<code>.radio-group</code>)</label>
                <div className="radio-group">
                  <label className="radio-option">
                    <input
                      type="radio"
                      name="env"
                      value="cloud"
                      checked={radioVal === 'cloud'}
                      onChange={(e) => setRadioVal(e.target.value)}
                    />
                    <span>Cloud Hosted</span>
                  </label>
                  <label className="radio-option">
                    <input
                      type="radio"
                      name="env"
                      value="hybrid"
                      checked={radioVal === 'hybrid'}
                      onChange={(e) => setRadioVal(e.target.value)}
                    />
                    <span>Hybrid VPC</span>
                  </label>
                  <label className="radio-option">
                    <input
                      type="radio"
                      name="env"
                      value="onprem"
                      checked={radioVal === 'onprem'}
                      onChange={(e) => setRadioVal(e.target.value)}
                    />
                    <span>On-Premises</span>
                  </label>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ═══════════════════════════════════════════════════════════════════
            SECTION 4: STATUS PILLS & BADGES
            ═══════════════════════════════════════════════════════════════════ */}
        <section id="sec-status" className="ds-section">
          <div className="ds-section-header">
            <div>
              <h2 className="ds-section-title">
                <CheckCircle2 size={20} style={{ color: 'var(--color-primary)' }} />
                4. Status Indicators & Badges (<code>StatusPill</code>, <code>.badge-count</code>)
              </h2>
              <p className="ds-section-desc">
                Domain lifecycle status badges from <code>src/modules/jobs/components/StatusPill.tsx</code>.
              </p>
            </div>
          </div>

          <div className="ds-sub-title">StatusPill Component Lifecycle States</div>
          <div className="ds-demo-box">
            <StatusPill state="running" />
            <StatusPill state="success" />
            <StatusPill state="active" />
            <StatusPill state="paused" />
            <StatusPill state="queued" />
            <StatusPill state="failed" />
            <StatusPill state="up_for_retry" />
            <StatusPill state="cancelled" />
            <StatusPill state="archived" />
            <StatusPill state="skipped" />
          </div>

          <div className="ds-sub-title">StatusPill Sizes (sm, md, lg) and iconOnly</div>
          <div className="ds-demo-box">
            <StatusPill state="running" size="sm" />
            <StatusPill state="running" size="md" />
            <StatusPill state="running" size="lg" />
            <div style={{ width: 1, height: 24, background: 'var(--color-border)', margin: '0 8px' }} />
            <StatusPill state="running" iconOnly size="sm" />
            <StatusPill state="running" iconOnly size="md" />
            <StatusPill state="running" iconOnly size="lg" />
            <StatusPill state="success" iconOnly size="md" />
            <StatusPill state="failed" iconOnly size="md" />
          </div>

          <div className="ds-sub-title">Badge Counts & Visibility Badges</div>
          <div className="ds-demo-box">
            <span className="badge-count">12 Items</span>
            <span className="badge-count" style={{ background: 'var(--color-success-bg)', color: 'var(--color-success)' }}>
              99.8% SLA
            </span>
            <span className="badge-count" style={{ background: 'var(--color-danger-bg)', color: 'var(--color-danger)' }}>
              3 Errors
            </span>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                padding: '2px 8px',
                borderRadius: 4,
                fontSize: '0.72rem',
                fontWeight: 600,
                color: '#1B6EF3',
                background: '#E8F1FF',
              }}
            >
              Shared Workspace
            </span>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                padding: '2px 8px',
                borderRadius: 4,
                fontSize: '0.72rem',
                fontWeight: 600,
                color: '#6B6B6B',
                background: '#F0F0F0',
              }}
            >
              Private
            </span>
          </div>
        </section>

        {/* ═══════════════════════════════════════════════════════════════════
            SECTION 5: NAVIGATION & PAGE TABS
            ═══════════════════════════════════════════════════════════════════ */}
        <section id="sec-tabs" className="ds-section">
          <div className="ds-section-header">
            <div>
              <h2 className="ds-section-title">
                <Layers size={20} style={{ color: 'var(--color-primary)' }} />
                5. Page Navigation & Tabs (<code>PageTabs</code>, <code>.uc-tab-bar</code>, <code>.landing-feed-tab-bar</code>)
              </h2>
              <p className="ds-section-desc">
                Standard page tabs from <code>src/components/common/PageTabs.tsx</code>, Data Catalog Right-Side tabs, and Landing Page feed tabs.
              </p>
            </div>
          </div>

          {/* 1. PageTabs */}
          <div className="ds-sub-title">1. Standard Page Navigation Tabs (<code>PageTabs</code>)</div>
          <div style={{ background: 'var(--color-surface)', padding: 16, borderRadius: 'var(--radius-lg)', border: '1px solid var(--color-border)' }}>
            <PageTabs
              tabs={[
                { value: 'overview', label: 'Overview' },
                { value: 'pipelines', label: 'Data Pipelines' },
                { value: 'agents', label: 'AI Agents' },
                { value: 'settings', label: 'Settings & Quotas' },
              ] as const}
              value={pageTab}
              onChange={setPageTab}
            />
            <div style={{ padding: '8px 0', color: 'var(--color-text-muted)', fontSize: '0.8125rem' }}>
              Active Tab Content: <strong>{pageTab.toUpperCase()}</strong>
            </div>
          </div>

          {/* 2. Data Catalog Right-Side Main Tabs */}
          <div className="ds-sub-title">2. Data Catalog Main Tabs (<code>.uc-tab-bar</code> / <code>.uc-tab</code>)</div>
          <div style={{ background: 'var(--color-surface)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--color-border)', overflow: 'hidden' }}>
            <div className="uc-tab-bar">
              {[
                { id: 'overview', label: 'Overview' },
                { id: 'columns', label: 'Columns (18)' },
                { id: 'sample', label: 'Sample Data' },
                { id: 'lineage', label: 'Lineage' },
                { id: 'details', label: 'Details' },
                { id: 'permissions', label: 'Permissions' },
              ].map((t) => (
                <button
                  key={t.id}
                  type="button"
                  className={`uc-tab ${ucActiveTab === t.id ? 'is-active' : ''}`}
                  onClick={() => setUcActiveTab(t.id)}
                >
                  {t.label}
                </button>
              ))}
            </div>
            <div className="uc-tab-content" style={{ padding: 16, fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
              Displaying Data Catalog Right-Side Tab: <strong>{ucActiveTab}</strong>
            </div>
          </div>

          {/* 3. Landing Feed Filter Tabs */}
          <div className="ds-sub-title">3. Landing Page Feed Tabs (<code>.landing-feed-tab-bar</code>)</div>
          <div style={{ background: 'var(--color-surface)', padding: 16, borderRadius: 'var(--radius-lg)', border: '1px solid var(--color-border)' }}>
            <div className="landing-feed-tab-bar">
              {[
                { id: 'suggested', label: 'Suggested', icon: Lightbulb },
                { id: 'recent', label: 'Recent', icon: Clock },
                { id: 'agents', label: 'Agents', icon: Bot },
                { id: 'jobs', label: 'Jobs', icon: Workflow },
                { id: 'notebooks', label: 'Notebooks', icon: FileCode },
                { id: 'dashboards', label: 'Dashboards', icon: LayoutDashboard },
              ].map((tab) => {
                const Icon = tab.icon;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    className={`landing-tab-btn ${feedActiveTab === tab.id ? 'is-active' : ''}`}
                    onClick={() => setFeedActiveTab(tab.id)}
                  >
                    <Icon size={14} />
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </section>

        {/* ═══════════════════════════════════════════════════════════════════
            SECTION 6: BUSINESS-FACING TABLES (Table.tsx)
            ═══════════════════════════════════════════════════════════════════ */}
        <section id="sec-tables" className="ds-section">
          <div className="ds-section-header">
            <div>
              <h2 className="ds-section-title">
                <Database size={20} style={{ color: 'var(--color-primary)' }} />
                6. Business-Facing Table Component (<code>components/common/Table.tsx</code>)
              </h2>
              <p className="ds-section-desc">
                Approachable list table with comfortable row spacing, readable labels, and row-level primary and secondary actions.
              </p>
            </div>
          </div>

          <Table<PipelineItem>
            columns={pipelineColumns}
            rows={DUMMY_PIPELINES}
            keyExtractor={(item) => item.id}
            primaryAction={{
              label: 'Run',
              icon: Play,
              onClick: (row) => toast.info(`Starting pipeline '${row.name}'...`),
            }}
            visibleActions={[
              {
                label: 'Settings',
                icon: Settings,
                onClick: (row) => toast.info(`Configuring '${row.name}'`),
              },
              {
                label: 'Delete',
                icon: Trash2,
                variant: 'danger',
                onClick: () => setShowConfirmModal(true),
              },
            ]}
          />
        </section>

        {/* ═══════════════════════════════════════════════════════════════════
            SECTION 7: OPERATOR / DEVELOPER APP TABLES (AppTable.tsx)
            ═══════════════════════════════════════════════════════════════════ */}
        <section id="sec-apptables" className="ds-section">
          <div className="ds-section-header">
            <div>
              <h2 className="ds-section-title">
                <Code2 size={20} style={{ color: 'var(--color-primary)' }} />
                7. Technical / Operator Table Component (<code>components/common/AppTable.tsx</code>)
              </h2>
              <p className="ds-section-desc">
                Dense, high-density structured table for developer and operator screens with built-in loading skeletons.
              </p>
            </div>
          </div>

          <AppTable<ComputeResourceItem>
            columns={computeColumns}
            rows={DUMMY_COMPUTE}
            rowKey={(item) => item.id}
            onRowClick={(row) => toast.info(`Clicked resource '${row.name}'`)}
          />
        </section>

        {/* ═══════════════════════════════════════════════════════════════════
            SECTION 8: MODALS & DIALOGS
            ═══════════════════════════════════════════════════════════════════ */}
        <section id="sec-modals" className="ds-section">
          <div className="ds-section-header">
            <div>
              <h2 className="ds-section-title">
                <Shield size={20} style={{ color: 'var(--color-primary)' }} />
                8. Modals & Confirmation Dialogs
              </h2>
              <p className="ds-section-desc">
                Standard dialogs using <code>ConfirmDialog.tsx</code> and <code>.modal-backdrop / .modal-panel</code>.
              </p>
            </div>
          </div>

          <div className="ds-demo-box">
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setShowCustomModal(true)}
            >
              <Plus size={14} /> Open Form Modal
            </button>
            <button
              type="button"
              className="btn btn-danger"
              onClick={() => setShowConfirmModal(true)}
            >
              <Trash2 size={14} /> Open Destructive Confirm Dialog
            </button>
          </div>

          {/* Render ConfirmDialog if active */}
          {showConfirmModal && (
            <ConfirmDialog
              title="Delete Database Connection?"
              message="Are you sure you want to delete this connection? Ingestion pipelines dependent on this connection will be paused immediately."
              confirmLabel="Delete Connection"
              isDestructive={true}
              isLoading={isModalLoading}
              onCancel={() => setShowConfirmModal(false)}
              onConfirm={() => {
                setIsModalLoading(true);
                setTimeout(() => {
                  setIsModalLoading(false);
                  setShowConfirmModal(false);
                  toast.success('Connection deleted successfully.');
                }, 700);
              }}
            />
          )}

          {/* Render Custom Modal Panel if active */}
          {showCustomModal && (
            <div className="modal-backdrop" onClick={() => setShowCustomModal(false)}>
              <div
                className="modal-panel"
                style={{ width: '100%', maxWidth: 520 }}
                onClick={(e) => e.stopPropagation()}
                role="dialog"
                aria-modal="true"
              >
                <div className="modal-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <CompassXLogo size={20} />
                    <span className="modal-title">Create Ingestion Job</span>
                  </div>
                  <button
                    type="button"
                    className="btn-icon"
                    onClick={() => setShowCustomModal(false)}
                    aria-label="Close"
                  >
                    <X size={16} />
                  </button>
                </div>
                <div className="modal-body">
                  <div className="form-field">
                    <label className="form-label">Job Name <span style={{ color: 'var(--color-danger)' }}>*</span></label>
                    <input className="form-input" defaultValue="customer_events_cdc_sync" />
                  </div>
                  <div className="form-field">
                    <label className="form-label">Execution Engine</label>
                    <select className="form-input" defaultValue="duckdb">
                      <option value="duckdb">DuckDB High Performance Engine</option>
                      <option value="spark">Apache Spark v3.5 Cluster</option>
                    </select>
                  </div>
                  <div className="form-field">
                    <label className="form-label">Cron Schedule</label>
                    <input className="form-input" defaultValue="0 */2 * * *" />
                    <span className="form-hint">Runs every 2 hours.</span>
                  </div>
                </div>
                <div className="modal-footer" style={{ padding: '12px 20px', background: 'var(--color-bg)', borderTop: '1px solid var(--color-border)' }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setShowCustomModal(false)}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => {
                      setShowCustomModal(false);
                      toast.success('Job created successfully.');
                    }}
                  >
                    Create Job
                  </button>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* ═══════════════════════════════════════════════════════════════════
            SECTION 9: CURATED TECHNOLOGY & DATA ICONS
            ═══════════════════════════════════════════════════════════════════ */}
        <section id="sec-icons" className="ds-section">
          <div className="ds-section-header">
            <div>
              <h2 className="ds-section-title">
                <Sparkles size={20} style={{ color: 'var(--color-primary)' }} />
                9. Curated Technology & Data Icons (<code>TechDataIcons.tsx</code>)
              </h2>
              <p className="ds-section-desc">
                Specialized data engine, AI model, compute, and database icons created for CompassX.
              </p>
            </div>
            <span className="badge-count">{CURATED_TECH_DATA_ICONS.length} Custom Icons</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: 12 }}>
            {CURATED_TECH_DATA_ICONS.slice(0, 14).map((iconItem) => {
              const IconComp = iconItem.component;
              return (
                <div
                  key={iconItem.name}
                  style={{
                    padding: '16px 12px',
                    borderRadius: 'var(--radius)',
                    border: '1px solid var(--color-border)',
                    background: 'var(--color-surface)',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8,
                    textAlign: 'center',
                    cursor: 'pointer',
                  }}
                  onClick={() => copyToClipboard(`<${iconItem.name} />`, iconItem.name)}
                >
                  <IconComp size={26} color="var(--color-primary)" />
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text)' }}>
                    {iconItem.name}
                  </span>
                </div>
              );
            })}
          </div>
        </section>
      </div>
    </div>
  );
}
