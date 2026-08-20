import React, { useState } from 'react';
import {
  Copy,
  Check,
  Sparkles,
  Sliders,
  Palette,
} from 'lucide-react';
import { CompassXLogo } from '@/components/common/CompassXLogo';
import { useToast } from '@/lib/toast';

type CanvasBackground = 'sidebar' | 'white' | 'dark' | 'navy' | 'checker';

const SOLID_COLORS = [
  { id: 'primary', name: 'Brand Blue', hex: '#1B6EF3' },
  { id: 'obsidian', name: 'Obsidian Dark', hex: '#0F172A' },
  { id: 'slate', name: 'Slate Gray', hex: '#475569' },
  { id: 'white', name: 'Pure White', hex: '#FFFFFF' },
  { id: 'cyan', name: 'Sky Cyan', hex: '#0284C7' },
  { id: 'emerald', name: 'Emerald AI', hex: '#059669' },
  { id: 'violet', name: 'Deep Violet', hex: '#6D28D9' },
  { id: 'amber', name: 'Amber Gold', hex: '#D97706' },
];

const PRESET_SIZES = [16, 20, 24, 26, 28, 36, 48, 64, 96, 128];

export default function LogoShowcasePage() {
  const toast = useToast();
  const [selectedColor, setSelectedColor] = useState<string>('#1B6EF3');
  const [canvasBg, setCanvasBg] = useState<CanvasBackground>('sidebar');
  const [customSize, setCustomSize] = useState<number>(48);
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  function getCanvasStyle(bg: CanvasBackground): React.CSSProperties {
    switch (bg) {
      case 'sidebar':
        return { background: '#FAFAFA', color: '#0F172A', border: '1px solid #E5E7EB' };
      case 'white':
        return { background: '#FFFFFF', color: '#0F172A', border: '1px solid #E5E7EB' };
      case 'dark':
        return { background: '#0D1117', color: '#FFFFFF', border: '1px solid #21262D' };
      case 'navy':
        return { background: '#0F172A', color: '#FFFFFF', border: '1px solid #1E293B' };
      case 'checker':
        return {
          backgroundColor: '#F8FAFC',
          backgroundImage:
            'linear-gradient(45deg, #E2E8F0 25%, transparent 25%), linear-gradient(-45deg, #E2E8F0 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #E2E8F0 75%), linear-gradient(-45deg, transparent 75%, #E2E8F0 75%)',
          backgroundSize: '16px 16px',
          backgroundPosition: '0 0, 0 8px, 8px -8px, -8px 0px',
          color: '#0F172A',
          border: '1px solid #CBD5E1',
        };
    }
  }

  function handleCopy(text: string, label: string) {
    navigator.clipboard.writeText(text);
    setCopiedCode(label);
    toast.success(`Copied ${label} to clipboard!`);
    setTimeout(() => setCopiedCode(null), 2000);
  }

  return (
    <div className="page-section" style={{ padding: '24px 32px 60px', maxWidth: 1280, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <Sparkles size={18} style={{ color: 'var(--color-primary)' }} />
          <h1 style={{ margin: 0, fontSize: '1.35rem', fontWeight: 600, color: 'var(--color-text)', letterSpacing: '-0.01em' }}>
            CompassX Modern Minimalist Logo
          </h1>
        </div>
        <p style={{ margin: 0, color: 'var(--color-text-muted)', fontSize: '0.84rem' }}>
          Clean, bold circular bezel with 4 cardinal cuts at 90° and a 45° North-East tilted diamond needle (Solid Filled top-right & Outline bottom-left).
        </p>
      </div>

      {/* Controls Bar: Solid Color & Canvas Selector */}
      <div
        style={{
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderRadius: 8,
          padding: '14px 18px',
          marginBottom: 24,
          display: 'flex',
          flexDirection: 'column',
          gap: 14,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 14 }}>
          {/* Solid Colors */}
          <div>
            <div style={{ fontSize: '0.76rem', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Palette size={13} /> 1. Solid Color
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
              {SOLID_COLORS.map((col) => {
                const isSelected = selectedColor === col.hex;
                return (
                  <button
                    key={col.id}
                    type="button"
                    onClick={() => setSelectedColor(col.hex)}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                      padding: '4px 9px',
                      borderRadius: 6,
                      border: `1px solid ${isSelected ? 'var(--color-border-strong, #94A3B8)' : 'var(--color-border)'}`,
                      background: isSelected ? 'var(--color-surface-hover)' : 'transparent',
                      color: 'var(--color-text)',
                      fontSize: '0.78rem',
                      fontWeight: isSelected ? 550 : 450,
                      cursor: 'pointer',
                    }}
                  >
                    <span style={{ width: 10, height: 10, borderRadius: '50%', background: col.hex, border: col.hex === '#FFFFFF' ? '1px solid #CBD5E1' : 'none' }} />
                    {col.name}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Canvas Environment */}
          <div>
            <div style={{ fontSize: '0.76rem', fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 6 }}>
              2. Canvas Environment
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              {[
                { id: 'sidebar' as const, label: 'Sidebar (#FAFAFA)' },
                { id: 'white' as const, label: 'White (#FFFFFF)' },
                { id: 'dark' as const, label: 'Obsidian Dark' },
                { id: 'navy' as const, label: 'Navy' },
                { id: 'checker' as const, label: 'Grid' },
              ].map((c) => {
                const isSelected = canvasBg === c.id;
                return (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => setCanvasBg(c.id)}
                    style={{
                      padding: '4px 9px',
                      borderRadius: 6,
                      border: `1px solid ${isSelected ? 'var(--color-border-strong, #94A3B8)' : 'var(--color-border)'}`,
                      background: isSelected ? 'var(--color-surface-hover)' : 'transparent',
                      color: isSelected ? 'var(--color-text)' : 'var(--color-text-muted)',
                      fontSize: '0.78rem',
                      fontWeight: isSelected ? 550 : 450,
                      cursor: 'pointer',
                    }}
                  >
                    {c.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Live Size Slider */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, paddingTop: 10, borderTop: '1px solid var(--color-border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Sliders size={13} style={{ color: 'var(--color-text-muted)' }} />
            <span style={{ fontSize: '0.80rem', fontWeight: 550, color: 'var(--color-text)' }}>
              Interactive Size:
            </span>
            <span style={{ fontSize: '0.80rem', fontFamily: 'monospace', color: 'var(--color-primary)', fontWeight: 600 }}>
              {customSize}px
            </span>
          </div>
          <input
            type="range"
            min={16}
            max={160}
            step={2}
            value={customSize}
            onChange={(e) => setCustomSize(Number(e.target.value))}
            style={{ flex: 1, cursor: 'pointer', accentColor: 'var(--color-primary)' }}
          />
        </div>
      </div>

      {/* Main Interactive Stage */}
      <div
        style={{
          borderRadius: 8,
          padding: '36px 20px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: 32,
          minHeight: 220,
          transition: 'all 0.2s ease',
          ...getCanvasStyle(canvasBg),
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: Math.max(8, Math.round(customSize * 0.28)), marginBottom: 12 }}>
          <CompassXLogo size={customSize} color={selectedColor} />
          {customSize >= 24 && (
            <span
              style={{
                fontSize: `${Math.round(customSize * 0.65)}px`,
                fontWeight: 650,
                letterSpacing: '-0.02em',
                lineHeight: 1,
              }}
            >
              Compass<span style={{ color: selectedColor }}>X</span>
            </span>
          )}
        </div>
        <div style={{ fontSize: '0.76rem', opacity: 0.65, marginTop: 4, fontFamily: 'monospace' }}>
          Rendered at {customSize} × {customSize} px · Solid {selectedColor}
        </div>
      </div>

      {/* Scale Matrix (16px to 128px) */}
      <div style={{ marginBottom: 36 }}>
        <h2 style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--color-text)', marginBottom: 4 }}>
          Full Scale Legibility Matrix
        </h2>
        <p style={{ margin: '0 0 16px', fontSize: '0.80rem', color: 'var(--color-text-muted)' }}>
          Review legibility and optical balance across all standard application dimensions.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
          {PRESET_SIZES.map((sz) => (
            <div
              key={sz}
              style={{
                borderRadius: 8,
                padding: '14px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'space-between',
                minHeight: 140,
                transition: 'all 0.15s ease',
                ...getCanvasStyle(canvasBg),
              }}
            >
              <div style={{ fontSize: '0.70rem', fontWeight: 600, opacity: 0.6, textTransform: 'uppercase', letterSpacing: '0.04em', alignSelf: 'flex-start' }}>
                {sz}px {sz === 26 || sz === 28 ? '· Sidebar Header' : sz === 16 ? '· Favicon' : sz === 24 ? '· Topbar' : sz === 48 ? '· Page Header' : ''}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1, padding: '8px 0' }}>
                <CompassXLogo size={sz} color={selectedColor} />
              </div>

              <div style={{ fontSize: '0.70rem', opacity: 0.6, fontFamily: 'monospace' }}>
                {sz} × {sz} px
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Actual Sidebar Size Preview (26px) */}
      <div style={{ marginBottom: 36 }}>
        <h2 style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--color-text)', marginBottom: 4 }}>
          Sidebar Header Integration (26px)
        </h2>
        <p style={{ margin: '0 0 16px', fontSize: '0.80rem', color: 'var(--color-text-muted)' }}>
          Preview how the logo mark pairs with the "CompassX" typography in the real sidebar header size.
        </p>

        <div style={{ maxWidth: 320 }}>
          <div
            style={{
              borderRadius: 8,
              padding: '14px 20px',
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              ...getCanvasStyle(canvasBg),
            }}
          >
            <CompassXLogo size={26} color={selectedColor} />
            <span style={{ fontSize: '0.95rem', fontWeight: 650, letterSpacing: '-0.02em' }}>
              Compass<span style={{ color: selectedColor }}>X</span>
            </span>
          </div>
        </div>
      </div>

      {/* Code Snippets */}
      <div>
        <h2 style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--color-text)', marginBottom: 4 }}>
          Component Code Snippet
        </h2>
        <div
          style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 8,
            padding: '14px 18px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{ fontSize: '0.80rem', fontWeight: 600, color: 'var(--color-text)' }}>
              Usage with color="{selectedColor}"
            </span>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => handleCopy(`<CompassXLogo size={26} color="${selectedColor}" />`, 'Code')}
              style={{ fontSize: '0.74rem', padding: '4px 8px', display: 'flex', alignItems: 'center', gap: 4 }}
            >
              {copiedCode === 'Code' ? <Check size={12} /> : <Copy size={12} />}
              {copiedCode === 'Code' ? 'Copied' : 'Copy'}
            </button>
          </div>
          <pre
            style={{
              margin: 0,
              padding: '10px 12px',
              borderRadius: 6,
              background: 'var(--color-surface-hover)',
              fontSize: '0.78rem',
              fontFamily: 'monospace',
              color: 'var(--color-text)',
              overflowX: 'auto',
            }}
          >
            {`import { CompassXLogo } from '@/components/common/CompassXLogo';\n\n<CompassXLogo size={26} color="${selectedColor}" />`}
          </pre>
        </div>
      </div>
    </div>
  );
}
