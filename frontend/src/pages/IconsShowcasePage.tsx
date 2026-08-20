import { useState, useMemo } from 'react';
import {
  Search,
  Copy,
  Check,
  Sparkles,
  Layers,
  Database,
  Bot,
  Code2,
  Workflow,
  ExternalLink,
  Sliders,
} from 'lucide-react';
import { useToast } from '@/lib/toast';
import {
  CURATED_TECH_DATA_ICONS,
  type CuratedIconItem,
  type IconProps,
} from '@/components/icons/TechDataIcons';
import './icons-showcase.css';

type CategoryFilter = 'all' | 'data' | 'ai' | 'compute' | 'ops';

const CATEGORIES: { id: CategoryFilter; label: string; icon: typeof Database }[] = [
  { id: 'all', label: 'All Icons', icon: Layers },
  { id: 'data', label: 'Data & Databases', icon: Database },
  { id: 'ai', label: 'AI & Agents', icon: Bot },
  { id: 'compute', label: 'Compute & Code', icon: Code2 },
  { id: 'ops', label: 'Operations & Twins', icon: Workflow },
];

const SIZES = [16, 20, 24, 32, 40];
const STROKES = [1.25, 1.75, 2.25];
const COLOR_OPTIONS = [
  { label: 'Default', value: 'currentColor' },
  { label: 'Primary Blue', value: '#1B6EF3' },
  { label: 'Emerald', value: '#059669' },
  { label: 'Purple', value: '#8B5CF6' },
  { label: 'Amber', value: '#D97706' },
];

export default function IconsShowcasePage() {
  const toast = useToast();
  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState<CategoryFilter>('all');
  const [size, setSize] = useState<number>(24);
  const [strokeWidth, setStrokeWidth] = useState<number>(1.75);
  const [selectedColor, setSelectedColor] = useState<string>('currentColor');
  const [copiedName, setCopiedName] = useState<string | null>(null);

  const filteredIcons = useMemo(() => {
    return CURATED_TECH_DATA_ICONS.filter((item) => {
      const matchCat = activeCategory === 'all' || item.category === activeCategory;
      const q = search.toLowerCase().trim();
      const matchSearch =
        !q ||
        item.name.toLowerCase().includes(q) ||
        item.description.toLowerCase().includes(q) ||
        item.tags.some((t) => t.toLowerCase().includes(q));
      return matchCat && matchSearch;
    });
  }, [activeCategory, search]);

  function handleCopy(text: string, label: string) {
    navigator.clipboard.writeText(text);
    setCopiedName(text);
    toast.success(`Copied ${label} to clipboard`);
    setTimeout(() => setCopiedName(null), 2000);
  }

  return (
    <div className="icons-showcase-root">
      {/* ── Header ────────────────────────────────────────────────────────── */}
      <header className="icons-showcase-header">
        <div className="icons-showcase-title-row">
          <h1 className="icons-showcase-title">
            <Sparkles size={24} style={{ color: 'var(--color-primary, #1b6ef3)' }} />
            Curated Technology & Data Icons
            <span className="icons-count-badge">{CURATED_TECH_DATA_ICONS.length} Custom Icons</span>
          </h1>
        </div>
        <p className="icons-showcase-subtitle">
          A bespoke collection of modern, clean-stroke, high-legibility SVG icons designed specifically
          for enterprise data platforms, multi-agent AI systems, computational notebooks, and digital twins.
        </p>
      </header>

      {/* ── Control Panel & Live Customization ─────────────────────────────── */}
      <section className="icons-controls-panel">
        <div className="icons-controls-row">
          {/* Search */}
          <div className="icons-search-input-wrapper">
            <Search size={16} style={{ color: 'var(--color-text-muted)' }} />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search icons by name, keyword, or domain (e.g. warehouse, agent, notebook)..."
            />
          </div>

          {/* Sizing & Stroke Controls */}
          <div className="icons-toggles-group">
            {/* Size */}
            <div className="icons-control-group">
              <span>Size:</span>
              <div className="icons-segmented-btn-group">
                {SIZES.map((s) => (
                  <button
                    key={s}
                    type="button"
                    className={`icons-segment-btn ${size === s ? 'active' : ''}`}
                    onClick={() => setSize(s)}
                  >
                    {s}px
                  </button>
                ))}
              </div>
            </div>

            {/* Stroke Width */}
            <div className="icons-control-group">
              <span>Stroke:</span>
              <div className="icons-segmented-btn-group">
                {STROKES.map((st) => (
                  <button
                    key={st}
                    type="button"
                    className={`icons-segment-btn ${strokeWidth === st ? 'active' : ''}`}
                    onClick={() => setStrokeWidth(st)}
                  >
                    {st}px
                  </button>
                ))}
              </div>
            </div>

            {/* Color preview */}
            <div className="icons-control-group">
              <span>Color:</span>
              <div className="icons-segmented-btn-group">
                {COLOR_OPTIONS.map((c) => (
                  <button
                    key={c.label}
                    type="button"
                    className={`icons-segment-btn ${selectedColor === c.value ? 'active' : ''}`}
                    onClick={() => setSelectedColor(c.value)}
                  >
                    {c.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Category Pills */}
        <div className="icons-category-tabs">
          {CATEGORIES.map((cat) => {
            const Icon = cat.icon;
            const isActive = activeCategory === cat.id;
            return (
              <button
                key={cat.id}
                type="button"
                className={`icons-cat-tab ${isActive ? 'active' : ''}`}
                onClick={() => setActiveCategory(cat.id)}
              >
                <Icon size={14} />
                <span>{cat.label}</span>
              </button>
            );
          })}
        </div>
      </section>

      {/* ── Icons Grid Showcase ───────────────────────────────────────────── */}
      <section className="icons-grid">
        {filteredIcons.map((item) => {
          const IconComponent = item.component;
          const isCopied = copiedName === item.name || copiedName === `<${item.name} size={${size}} />`;

          return (
            <div key={item.name} className="icon-preview-card">
              <div className="icon-display-frame">
                <IconComponent
                  size={size}
                  strokeWidth={strokeWidth}
                  style={{ color: selectedColor }}
                />
              </div>

              <div className="icon-info-group">
                <span className="icon-component-name">{item.name}</span>
                <span className="icon-description">{item.description}</span>
              </div>

              <div className="icon-card-actions">
                <button
                  type="button"
                  className="icon-action-btn"
                  onClick={() => handleCopy(item.name, item.name)}
                  title="Copy Component Name"
                >
                  {isCopied ? <Check size={12} style={{ color: '#10b981' }} /> : <Copy size={12} />}
                  <span>Name</span>
                </button>

                <button
                  type="button"
                  className="icon-action-btn"
                  onClick={() => handleCopy(`<${item.name} size={${size}} />`, `JSX tag <${item.name} />`)}
                  title="Copy JSX Tag"
                >
                  <Code2 size={12} />
                  <span>JSX</span>
                </button>
              </div>
            </div>
          );
        })}
      </section>

      {/* ── Implementation & Evaluation Notes ─────────────────────────────── */}
      <section className="icons-evaluation-box">
        <h3 className="icons-eval-title">How to Use These Icons in CompassX Codebase</h3>
        <p className="icons-eval-desc">
          All icons are 100% SVG React components designed on a 24×24 grid with vector stroke paths that cleanly
          inherit typography color (<code>currentColor</code>) and support dynamic <code>size</code> and <code>strokeWidth</code> props.
        </p>
        <div className="icons-eval-code-snippet">
          {`import { IconSqlWarehouse, IconAiAgent, IconComputationalNotebook } from '@/components/icons/TechDataIcons';

// Example Usage:
<IconSqlWarehouse size={20} strokeWidth={1.75} />
<IconAiAgent size={24} style={{ color: 'var(--color-primary)' }} />
<IconComputationalNotebook size={18} />`}
        </div>
      </section>
    </div>
  );
}
