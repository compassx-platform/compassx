import { useState } from 'react';
import { X, RotateCcw } from 'lucide-react';
import type { ChartConfig } from '@/types/dashboard';

const BG_PRESETS = [
  { label: 'Default Light Slate', color: '#f1f5f9' },
  { label: 'Neutral Gray', color: '#e2e8f0' },
  { label: 'Medium Slate', color: '#94a3b8' },
  { label: 'Dark Slate', color: '#334155' },
  { label: 'Deep Charcoal', color: '#0f172a' },
  { label: 'CompassX Blue', color: '#0052cc' },
  { label: 'Navy Blue', color: '#1e40af' },
  { label: 'Sky Blue Pastel', color: '#dbeafe' },
  { label: 'Teal Pastel', color: '#ccfbf1' },
  { label: 'Deep Teal', color: '#0f766e' },
  { label: 'Emerald Pastel', color: '#d1fae5' },
  { label: 'Forest Green', color: '#166534' },
  { label: 'Indigo Pastel', color: '#e0e7ff' },
  { label: 'Deep Indigo', color: '#4338ca' },
  { label: 'Purple Pastel', color: '#f3e8ff' },
  { label: 'Deep Purple', color: '#7e22ce' },
  { label: 'Amber Pastel', color: '#fef3c7' },
  { label: 'Deep Amber', color: '#b45309' },
  { label: 'Rose Pastel', color: '#ffe4e6' },
  { label: 'Crimson', color: '#be123c' },
];

const FONT_COLOR_PRESETS = [
  { label: 'Charcoal / Slate', color: '#1e293b' },
  { label: 'Muted Slate', color: '#475569' },
  { label: 'Pure White', color: '#ffffff' },
  { label: 'Light Slate', color: '#f1f5f9' },
  { label: 'CompassX Blue', color: '#0052cc' },
  { label: 'Navy Blue', color: '#1e40af' },
  { label: 'Deep Teal', color: '#0f766e' },
  { label: 'Forest Green', color: '#166534' },
  { label: 'Deep Purple', color: '#7e22ce' },
  { label: 'Crimson Red', color: '#be123c' },
];

interface TableHeaderStylePopoverProps {
  config: ChartConfig;
  onPatch: (patch: Partial<ChartConfig>) => void;
  onClose: () => void;
}

export default function TableHeaderStylePopover({
  config,
  onPatch,
  onClose,
}: TableHeaderStylePopoverProps) {
  const currentBg = config.titleRowBg ?? config.headerBg ?? '#f1f5f9';
  const isDefaultBg = !config.titleRowBg && !config.headerBg;
  const currentFontColor = config.titleRowColor ?? config.headerColor;
  const isAutoFontColor = !currentFontColor;

  const currentFontSize = config.headerFontSize ?? 'medium';
  const currentFontWeight = config.headerFontWeight ?? 'bold';
  const currentTransform = config.headerTextTransform ?? 'none';
  const currentAlignment = config.headerAlignment ?? 'left';

  function handleResetAll() {
    onPatch({
      titleRowBg: undefined,
      headerBg: undefined,
      titleRowColor: undefined,
      headerColor: undefined,
      headerFontSize: undefined,
      headerFontWeight: undefined,
      headerTextTransform: undefined,
      headerAlignment: undefined,
    });
  }

  return (
    <>
      {/* Backdrop */}
      <div
        style={{ position: 'fixed', inset: 0, zIndex: 998 }}
        onClick={onClose}
      />

      {/* Popover Card */}
      <div
        style={{
          position: 'absolute',
          top: 36,
          right: 14,
          zIndex: 999,
          background: '#ffffff',
          border: '1px solid #cbd5e1',
          borderRadius: 8,
          boxShadow: '0 10px 30px rgba(0,0,0,0.16)',
          padding: 14,
          width: 290,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #f1f5f9', paddingBottom: 8 }}>
          <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#1e293b' }}>
            Header Style & Formatting
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <button
              type="button"
              onClick={handleResetAll}
              title="Reset all styles to default"
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: '#64748b',
                display: 'flex',
                alignItems: 'center',
                gap: 3,
                fontSize: '0.68rem',
                padding: '2px 4px',
              }}
            >
              <RotateCcw size={11} /> Reset
            </button>
            <button
              type="button"
              onClick={onClose}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8', padding: 2 }}
            >
              <X size={14} />
            </button>
          </div>
        </div>

        {/* 1. Header Background Color */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 5 }}>
            <span style={{ fontSize: '0.72rem', fontWeight: 600, color: '#475569' }}>Background Color</span>
            {!isDefaultBg && (
              <button
                type="button"
                onClick={() => onPatch({ titleRowBg: undefined, headerBg: undefined })}
                style={{ background: 'none', border: 'none', fontSize: '0.66rem', color: '#0052cc', cursor: 'pointer', padding: 0 }}
              >
                Default
              </button>
            )}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(10, 1fr)', gap: 4, marginBottom: 6 }}>
            {BG_PRESETS.slice(0, 10).map((p) => {
              const isSelected = !isDefaultBg && currentBg.toLowerCase() === p.color.toLowerCase();
              return (
                <div
                  key={p.color}
                  onClick={() => onPatch({ titleRowBg: p.color, headerBg: p.color })}
                  title={`${p.label} (${p.color})`}
                  style={{
                    height: 18,
                    borderRadius: 3,
                    backgroundColor: p.color,
                    cursor: 'pointer',
                    border: isSelected ? '2px solid #0052cc' : '1px solid rgba(0,0,0,0.15)',
                    transform: isSelected ? 'scale(1.15)' : 'none',
                    transition: 'transform 0.1s',
                  }}
                />
              );
            })}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(10, 1fr)', gap: 4, marginBottom: 6 }}>
            {BG_PRESETS.slice(10, 20).map((p) => {
              const isSelected = !isDefaultBg && currentBg.toLowerCase() === p.color.toLowerCase();
              return (
                <div
                  key={p.color}
                  onClick={() => onPatch({ titleRowBg: p.color, headerBg: p.color })}
                  title={`${p.label} (${p.color})`}
                  style={{
                    height: 18,
                    borderRadius: 3,
                    backgroundColor: p.color,
                    cursor: 'pointer',
                    border: isSelected ? '2px solid #0052cc' : '1px solid rgba(0,0,0,0.15)',
                    transform: isSelected ? 'scale(1.15)' : 'none',
                    transition: 'transform 0.1s',
                  }}
                />
              );
            })}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <input
              type="color"
              value={currentBg.startsWith('#') && currentBg.length === 7 ? currentBg : '#f1f5f9'}
              onChange={(e) => onPatch({ titleRowBg: e.target.value, headerBg: e.target.value })}
              style={{ width: 22, height: 22, padding: 0, border: 'none', background: 'none', cursor: 'pointer' }}
            />
            <input
              type="text"
              value={config.titleRowBg ?? ''}
              placeholder="#f1f5f9 (default)"
              onChange={(e) => onPatch({ titleRowBg: e.target.value || undefined, headerBg: e.target.value || undefined })}
              style={{
                flex: 1,
                fontSize: '0.70rem',
                fontFamily: 'monospace',
                padding: '3px 6px',
                border: '1px solid #cbd5e1',
                borderRadius: 4,
                outline: 'none',
              }}
            />
          </div>
        </div>

        {/* 2. Header Font Color */}
        <div style={{ borderTop: '1px solid #f1f5f9', paddingTop: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 5 }}>
            <span style={{ fontSize: '0.72rem', fontWeight: 600, color: '#475569' }}>Font Color</span>
            {!isAutoFontColor && (
              <button
                type="button"
                onClick={() => onPatch({ titleRowColor: undefined, headerColor: undefined })}
                style={{ background: 'none', border: 'none', fontSize: '0.66rem', color: '#0052cc', cursor: 'pointer', padding: 0 }}
              >
                Auto (High Contrast)
              </button>
            )}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(10, 1fr)', gap: 4, marginBottom: 6 }}>
            {FONT_COLOR_PRESETS.map((p) => {
              const isSelected = !isAutoFontColor && currentFontColor.toLowerCase() === p.color.toLowerCase();
              return (
                <div
                  key={p.color}
                  onClick={() => onPatch({ titleRowColor: p.color, headerColor: p.color })}
                  title={`${p.label} (${p.color})`}
                  style={{
                    height: 18,
                    borderRadius: 3,
                    backgroundColor: p.color,
                    cursor: 'pointer',
                    border: isSelected ? '2px solid #0052cc' : '1px solid rgba(0,0,0,0.15)',
                    transform: isSelected ? 'scale(1.15)' : 'none',
                    transition: 'transform 0.1s',
                  }}
                />
              );
            })}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <input
              type="color"
              value={currentFontColor && currentFontColor.startsWith('#') && currentFontColor.length === 7 ? currentFontColor : '#1e293b'}
              onChange={(e) => onPatch({ titleRowColor: e.target.value, headerColor: e.target.value })}
              style={{ width: 22, height: 22, padding: 0, border: 'none', background: 'none', cursor: 'pointer' }}
            />
            <input
              type="text"
              value={currentFontColor ?? ''}
              placeholder="Auto contrast (default)"
              onChange={(e) => onPatch({ titleRowColor: e.target.value || undefined, headerColor: e.target.value || undefined })}
              style={{
                flex: 1,
                fontSize: '0.70rem',
                fontFamily: 'monospace',
                padding: '3px 6px',
                border: '1px solid #cbd5e1',
                borderRadius: 4,
                outline: 'none',
              }}
            />
          </div>
        </div>

        {/* 3. Header Font Size */}
        <div style={{ borderTop: '1px solid #f1f5f9', paddingTop: 8 }}>
          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: '#475569', display: 'block', marginBottom: 4 }}>
            Font Size
          </span>
          <div style={{ display: 'flex', gap: 4 }}>
            {(['small', 'medium', 'large'] as const).map((sz) => {
              const isSelected = currentFontSize === sz;
              return (
                <button
                  key={sz}
                  type="button"
                  onClick={() => onPatch({ headerFontSize: sz })}
                  style={{
                    flex: 1,
                    padding: '3px 6px',
                    fontSize: '0.71rem',
                    fontWeight: isSelected ? 600 : 400,
                    color: isSelected ? '#0052cc' : '#475569',
                    background: isSelected ? '#e7f0ff' : '#f8fafc',
                    border: `1px solid ${isSelected ? '#0052cc' : '#e2e8f0'}`,
                    borderRadius: 4,
                    cursor: 'pointer',
                    textTransform: 'capitalize',
                  }}
                >
                  {sz}
                </button>
              );
            })}
          </div>
        </div>

        {/* 4. Font Weight & Text Transform */}
        <div style={{ display: 'flex', gap: 8, borderTop: '1px solid #f1f5f9', paddingTop: 8 }}>
          <div style={{ flex: 1 }}>
            <span style={{ fontSize: '0.72rem', fontWeight: 600, color: '#475569', display: 'block', marginBottom: 4 }}>
              Weight
            </span>
            <div style={{ display: 'flex', gap: 3 }}>
              {(['normal', 'medium', 'bold'] as const).map((w) => {
                const isSelected = currentFontWeight === w;
                return (
                  <button
                    key={w}
                    type="button"
                    onClick={() => onPatch({ headerFontWeight: w })}
                    style={{
                      flex: 1,
                      padding: '3px 4px',
                      fontSize: '0.70rem',
                      fontWeight: isSelected ? 600 : 400,
                      color: isSelected ? '#0052cc' : '#475569',
                      background: isSelected ? '#e7f0ff' : '#f8fafc',
                      border: `1px solid ${isSelected ? '#0052cc' : '#e2e8f0'}`,
                      borderRadius: 4,
                      cursor: 'pointer',
                      textTransform: 'capitalize',
                    }}
                  >
                    {w === 'normal' ? 'Norm' : w === 'medium' ? 'Med' : 'Bold'}
                  </button>
                );
              })}
            </div>
          </div>

          <div style={{ flex: 1 }}>
            <span style={{ fontSize: '0.72rem', fontWeight: 600, color: '#475569', display: 'block', marginBottom: 4 }}>
              Transform
            </span>
            <div style={{ display: 'flex', gap: 3 }}>
              {(['none', 'uppercase', 'capitalize'] as const).map((t) => {
                const isSelected = currentTransform === t;
                return (
                  <button
                    key={t}
                    type="button"
                    onClick={() => onPatch({ headerTextTransform: t })}
                    style={{
                      flex: 1,
                      padding: '3px 4px',
                      fontSize: '0.70rem',
                      fontWeight: isSelected ? 600 : 400,
                      color: isSelected ? '#0052cc' : '#475569',
                      background: isSelected ? '#e7f0ff' : '#f8fafc',
                      border: `1px solid ${isSelected ? '#0052cc' : '#e2e8f0'}`,
                      borderRadius: 4,
                      cursor: 'pointer',
                    }}
                  >
                    {t === 'none' ? 'None' : t === 'uppercase' ? 'UPPER' : 'Cap'}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* 5. Header Alignment */}
        <div style={{ borderTop: '1px solid #f1f5f9', paddingTop: 8 }}>
          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: '#475569', display: 'block', marginBottom: 4 }}>
            Alignment
          </span>
          <div style={{ display: 'flex', gap: 4 }}>
            {(['left', 'center', 'right'] as const).map((align) => {
              const isSelected = currentAlignment === align;
              return (
                <button
                  key={align}
                  type="button"
                  onClick={() => onPatch({ headerAlignment: align })}
                  style={{
                    flex: 1,
                    padding: '3px 6px',
                    fontSize: '0.71rem',
                    fontWeight: isSelected ? 600 : 400,
                    color: isSelected ? '#0052cc' : '#475569',
                    background: isSelected ? '#e7f0ff' : '#f8fafc',
                    border: `1px solid ${isSelected ? '#0052cc' : '#e2e8f0'}`,
                    borderRadius: 4,
                    cursor: 'pointer',
                    textTransform: 'capitalize',
                  }}
                >
                  {align}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </>
  );
}
