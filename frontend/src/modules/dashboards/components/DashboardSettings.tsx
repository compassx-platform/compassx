/**
 * DashboardSettings panel — redesigned matching exact UI specs.
 * Supports Theme (Canvas, Widget, Fonts, Visualization, Textbox, Palette) and General settings.
 */

import { useState } from 'react';
import {
  X, Sun, Moon, AlignLeft, AlignCenter, AlignRight,
  Plus, Trash2, Palette
} from 'lucide-react';
import { useDashboardStore } from '@/modules/dashboards/stores/dashboardStore';
import type { DashboardTheme, FontSettings } from '@/types/dashboard';
import DashboardSidePanel from './DashboardSidePanel';

const AlignTopIcon = ({ size = 13 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <line x1="2" y1="3" x2="14" y2="3" />
    <path d="M8 13V6" />
    <path d="M5 9l3-3 3 3" />
  </svg>
);

const AlignCenterVertIcon = ({ size = 13 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <line x1="2" y1="8" x2="14" y2="8" />
    <path d="M5 5l3-3 3 3" />
    <path d="M5 11l3 3 3-3" />
  </svg>
);

const AlignBottomIcon = ({ size = 13 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <line x1="2" y1="13" x2="14" y2="13" />
    <path d="M8 3v7" />
    <path d="M5 7l3 3 3-3" />
  </svg>
);

interface Props {
  onClose: () => void;
}

const PRESET_THEMES = [
  { value: 'Custom', label: 'Custom' },
  { value: 'Default', label: 'Default' },
  { value: 'Dark', label: 'Dark' },
  { value: 'Light', label: 'Light' },
  { value: 'Ocean', label: 'Ocean' },
  { value: 'Forest', label: 'Forest' },
  { value: 'Sunset', label: 'Sunset' },
];

const LOCALES = [
  { value: 'en-US', label: 'English (US)' },
  { value: 'en-GB', label: 'English (UK)' },
  { value: 'de-DE', label: 'German' },
  { value: 'fr-FR', label: 'French' },
  { value: 'ja-JP', label: 'Japanese' },
];

const COLOR_PALETTES = [
  { name: 'Databricks Blue', colors: ['#1B6EF3', '#2C82F5', '#559BF7', '#80B5F9', '#ABD0FB'] },
  { name: 'Emerald Forest', colors: ['#059669', '#10B981', '#34D399', '#6EE7B7', '#A7F3D0'] },
  { name: 'Warm Sunset', colors: ['#DC2626', '#EA580C', '#F59E0B', '#FBBF24', '#FDE68A'] },
  { name: 'Deep Purple', colors: ['#7C3AED', '#8B5CF6', '#A78BFA', '#C4B5FD', '#DDD6FE'] },
  { name: 'Slate Gray', colors: ['#334155', '#475569', '#64748B', '#94A3B8', '#CBD5E1'] },
];

function ColorRow({
  label,
  value,
  onChange,
}: {
  label: string;
  value?: string;
  onChange: (val: string) => void;
}) {
  const isAuto = !value || value === 'Auto';
  const hexVal = isAuto ? '#ffffff' : value;
  const displayText = isAuto ? 'Auto' : value.toUpperCase();

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
      <span style={{ fontSize: '0.76rem', color: '#101828', fontWeight: 400 }}>{label}</span>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        background: '#f2f4f7',
        borderRadius: 6,
        padding: '3px 8px',
        width: 145,
        justifyContent: 'space-between'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%' }}>
          <label style={{
            width: 18,
            height: 18,
            borderRadius: 4,
            border: '1px solid #d0d5dd',
            background: isAuto ? '#ffffff' : hexVal,
            cursor: 'pointer',
            flexShrink: 0,
            display: 'block',
            position: 'relative',
            boxShadow: 'inset 0 0 0 1px rgba(0,0,0,0.05)'
          }}>
            <input
              type="color"
              value={hexVal}
              onChange={(e) => onChange(e.target.value)}
              style={{ position: 'absolute', opacity: 0, inset: 0, cursor: 'pointer', width: '100%', height: '100%' }}
            />
          </label>
          <input
            type="text"
            value={displayText}
            onChange={(e) => onChange(e.target.value)}
            style={{
              border: 'none',
              background: 'transparent',
              fontSize: '0.74rem',
              color: '#344054',
              width: '100%',
              outline: 'none',
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
              fontWeight: 500,
            }}
          />
        </div>
      </div>
    </div>
  );
}

function SliderRow({
  label,
  value,
  min = 0,
  max = 24,
  onChange,
}: {
  label: string;
  value?: number | string;
  min?: number;
  max?: number;
  onChange: (val: number) => void;
}) {
  const isAuto = value === undefined || value === 'Auto';
  const numericVal = typeof value === 'number' ? value : min;
  const displayVal = isAuto ? 'Auto' : numericVal;

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
      <span style={{ fontSize: '0.76rem', color: '#101828', fontWeight: 400 }}>{label}</span>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        background: '#f2f4f7',
        borderRadius: 6,
        padding: '3px 8px',
        width: 145,
        justifyContent: 'space-between',
        gap: 6
      }}>
        <input
          type="range"
          min={min}
          max={max}
          value={numericVal}
          onChange={(e) => onChange(Number(e.target.value))}
          style={{ width: 85, accentColor: '#2272b4', cursor: 'pointer' }}
        />
        <span style={{ fontSize: '0.74rem', color: '#344054', width: 30, textAlign: 'right', fontWeight: 500 }}>
          {displayVal}
        </span>
      </div>
    </div>
  );
}

function SelectRow({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value?: string;
  options: Array<{ value: string; label: string }>;
  onChange: (val: string) => void;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
      <span style={{ fontSize: '0.76rem', color: '#101828', fontWeight: 400 }}>{label}</span>
      <select
        value={value ?? 'Auto'}
        onChange={(e) => onChange(e.target.value)}
        style={{
          width: 145,
          padding: '4px 8px',
          fontSize: '0.74rem',
          borderRadius: 6,
          border: 'none',
          background: '#f2f4f7',
          color: '#344054',
          outline: 'none',
          cursor: 'pointer',
          fontWeight: 500
        }}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  );
}

function SegmentedRow({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value?: string;
  options: Array<{ value: string; icon: React.ReactNode }>;
  onChange: (val: string) => void;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
      <span style={{ fontSize: '0.76rem', color: '#101828', fontWeight: 400 }}>{label}</span>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        background: '#f2f4f7',
        borderRadius: 6,
        padding: 2,
        width: 145,
        justifyContent: 'space-between',
        gap: 2
      }}>
        {options.map((opt) => {
          const isActive = value === opt.value;
          return (
            <button
              key={opt.value}
              onClick={() => onChange(opt.value)}
              style={{
                flex: 1,
                border: isActive ? '1px solid #d0d5dd' : 'none',
                background: isActive ? '#ffffff' : 'transparent',
                borderRadius: 4,
                padding: '3px 0',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                color: isActive ? '#101828' : '#667085',
                boxShadow: isActive ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
                height: 22
              }}
            >
              {opt.icon}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function SectionTitle({ title }: { title: string }) {
  return (
    <div style={{
      fontSize: '0.68rem',
      fontWeight: 700,
      color: '#667085',
      letterSpacing: '0.06em',
      textTransform: 'uppercase',
      marginTop: 16,
      marginBottom: 8
    }}>
      {title}
    </div>
  );
}

export default function DashboardSettings({ onClose }: Props) {
  const { activeDashboard, updateSettings } = useDashboardStore();
  const settings = activeDashboard?.settings ?? {};
  const theme: DashboardTheme = settings.theme ?? {
    preset: 'Custom',
    previewMode: 'light',
    canvasBg: '#959598',
    widgetBg: '#FFFFFF',
    widgetBorder: 'Auto',
    selectionColor: '#2272B4',
    cornerRadius: 4,
    padding: 8,
    margin: 8,
    shadow: 0,
    titleAlignment: 'left',
    axisColor: 'Auto',
    gridColor: 'Auto',
    verticalAlignment: 'top',
  };

  const [topTab, setTopTab] = useState<'theme' | 'general'>('theme');
  const [themeSubTab, setThemeSubTab] = useState<'interface' | 'palette'>('interface');

  const [tags, setTags] = useState(settings.tags ?? []);
  const [newTagKey, setNewTagKey] = useState('');
  const [newTagVal, setNewTagVal] = useState('');

  function patchTheme(patch: Partial<DashboardTheme>) {
    updateSettings({ theme: { ...theme, ...patch } });
  }

  function addTag() {
    if (!newTagKey.trim()) return;
    const updated = [...tags, { key: newTagKey.trim(), value: newTagVal.trim() }];
    setTags(updated);
    updateSettings({ tags: updated });
    setNewTagKey('');
    setNewTagVal('');
  }

  function removeTag(i: number) {
    const updated = tags.filter((_, idx) => idx !== i);
    setTags(updated);
    updateSettings({ tags: updated });
  }

  return (
    <DashboardSidePanel style={{ background: '#ffffff', fontFamily: 'Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif' }}>
        {/* Header */}
        <div style={{
          padding: '12px 16px 8px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}>
          <span style={{ fontWeight: 600, fontSize: '0.92rem', color: '#101828' }}>Settings</span>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: '#667085',
              padding: 4,
              borderRadius: 4,
              display: 'flex',
              alignItems: 'center'
            }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Top Level Tabs: Theme | General */}
        <div style={{
          display: 'flex',
          borderBottom: '1px solid #eaecf0',
          padding: '0 16px',
          gap: 20,
          flexShrink: 0,
        }}>
          <button
            onClick={() => setTopTab('theme')}
            style={{
              background: 'none',
              border: 'none',
              borderBottom: topTab === 'theme' ? '2px solid #2272b4' : '2px solid transparent',
              padding: '6px 0 8px',
              fontSize: '0.8rem',
              fontWeight: topTab === 'theme' ? 600 : 400,
              color: topTab === 'theme' ? '#101828' : '#667085',
              cursor: 'pointer',
            }}
          >
            Theme
          </button>
          <button
            onClick={() => setTopTab('general')}
            style={{
              background: 'none',
              border: 'none',
              borderBottom: topTab === 'general' ? '2px solid #2272b4' : '2px solid transparent',
              padding: '6px 0 8px',
              fontSize: '0.8rem',
              fontWeight: topTab === 'general' ? 600 : 400,
              color: topTab === 'general' ? '#101828' : '#667085',
              cursor: 'pointer',
            }}
          >
            General
          </button>
        </div>

        {/* Scrollable Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '14px 16px' }}>

          {topTab === 'theme' && (
            <>
              {/* Theme Dropdown */}
              <div style={{ marginBottom: 12 }}>
                <label style={{ fontSize: '0.78rem', fontWeight: 600, color: '#101828', display: 'block', marginBottom: 6 }}>
                  Theme
                </label>
                <select
                  value={theme.preset ?? 'Custom'}
                  onChange={(e) => patchTheme({ preset: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '6px 10px',
                    fontSize: '0.78rem',
                    borderRadius: 6,
                    border: '1px solid #d0d5dd',
                    background: '#ffffff',
                    color: '#101828',
                    outline: 'none',
                    cursor: 'pointer',
                  }}
                >
                  {PRESET_THEMES.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>

              {/* Preview colors in */}
              <div style={{ marginBottom: 14 }}>
                <label style={{ fontSize: '0.78rem', fontWeight: 600, color: '#101828', display: 'block', marginBottom: 6 }}>
                  Preview colors in
                </label>
                <div style={{
                  display: 'flex',
                  background: '#f2f4f7',
                  borderRadius: 6,
                  padding: 3,
                  gap: 4,
                }}>
                  <button
                    onClick={() => patchTheme({ previewMode: 'light' })}
                    style={{
                      flex: 1,
                      border: (theme.previewMode ?? 'light') === 'light' ? '1px solid #d0d5dd' : 'none',
                      background: (theme.previewMode ?? 'light') === 'light' ? '#ffffff' : 'transparent',
                      borderRadius: 4,
                      padding: '5px 0',
                      fontSize: '0.74rem',
                      fontWeight: 500,
                      color: (theme.previewMode ?? 'light') === 'light' ? '#101828' : '#667085',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 6,
                      boxShadow: (theme.previewMode ?? 'light') === 'light' ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
                    }}
                  >
                    <Sun size={13} /> Light mode
                  </button>
                  <button
                    onClick={() => patchTheme({ previewMode: 'dark' })}
                    style={{
                      flex: 1,
                      border: theme.previewMode === 'dark' ? '1px solid #d0d5dd' : 'none',
                      background: theme.previewMode === 'dark' ? '#ffffff' : 'transparent',
                      borderRadius: 4,
                      padding: '5px 0',
                      fontSize: '0.74rem',
                      fontWeight: 500,
                      color: theme.previewMode === 'dark' ? '#101828' : '#667085',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 6,
                      boxShadow: theme.previewMode === 'dark' ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
                    }}
                  >
                    <Moon size={13} /> Dark mode
                  </button>
                </div>
              </div>

              {/* Sub-tabs: Interface | Color palette */}
              <div style={{
                display: 'flex',
                borderBottom: '1px solid #eaecf0',
                marginBottom: 12,
                gap: 16,
              }}>
                <button
                  onClick={() => setThemeSubTab('interface')}
                  style={{
                    background: 'none',
                    border: 'none',
                    borderBottom: themeSubTab === 'interface' ? '2px solid #2272b4' : '2px solid transparent',
                    padding: '4px 0 6px',
                    fontSize: '0.78rem',
                    fontWeight: themeSubTab === 'interface' ? 600 : 400,
                    color: themeSubTab === 'interface' ? '#2272b4' : '#667085',
                    cursor: 'pointer',
                  }}
                >
                  Interface
                </button>
                <button
                  onClick={() => setThemeSubTab('palette')}
                  style={{
                    background: 'none',
                    border: 'none',
                    borderBottom: themeSubTab === 'palette' ? '2px solid #2272b4' : '2px solid transparent',
                    padding: '4px 0 6px',
                    fontSize: '0.78rem',
                    fontWeight: themeSubTab === 'palette' ? 600 : 400,
                    color: themeSubTab === 'palette' ? '#2272b4' : '#667085',
                    cursor: 'pointer',
                  }}
                >
                  Color palette
                </button>
              </div>

              {themeSubTab === 'interface' && (
                <>
                  {/* CANVAS */}
                  <SectionTitle title="CANVAS" />
                  <ColorRow
                    label="Background"
                    value={theme.canvasBg ?? '#959598'}
                    onChange={(val) => patchTheme({ canvasBg: val })}
                  />
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                    <span style={{ fontSize: '0.76rem', color: '#101828', fontWeight: 400 }}>Snap grid lines</span>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={settings.showGridLines ?? true}
                        onChange={(e) => updateSettings({ showGridLines: e.target.checked })}
                        style={{ accentColor: '#2272b4' }}
                      />
                      <span style={{ fontSize: '0.74rem', color: '#344054' }}>Show grid</span>
                    </label>
                  </div>
                  <SliderRow
                    label="Grid columns"
                    value={settings.gridCols ?? 12}
                    min={6}
                    max={24}
                    onChange={(val) => updateSettings({ gridCols: val })}
                  />
                  <SliderRow
                    label="Row height (px)"
                    value={settings.gridRowHeight ?? 40}
                    min={10}
                    max={80}
                    onChange={(val) => updateSettings({ gridRowHeight: val })}
                  />
                  <SliderRow
                    label="Min widget rows"
                    value={settings.minWidgetHeight ?? 1}
                    min={1}
                    max={10}
                    onChange={(val) => updateSettings({ minWidgetHeight: val })}
                  />

                  {/* WIDGET */}
                  <SectionTitle title="WIDGET" />
                  <ColorRow
                    label="Background"
                    value={theme.widgetBg ?? '#FFFFFF'}
                    onChange={(val) => patchTheme({ widgetBg: val })}
                  />
                  <ColorRow
                    label="Border"
                    value={theme.widgetBorder ?? 'Auto'}
                    onChange={(val) => patchTheme({ widgetBorder: val })}
                  />
                  <ColorRow
                    label="Selection"
                    value={theme.selectionColor ?? '#2272B4'}
                    onChange={(val) => patchTheme({ selectionColor: val })}
                  />
                  <SliderRow
                    label="Corner radius"
                    value={theme.cornerRadius ?? 4}
                    min={0}
                    max={24}
                    onChange={(val) => patchTheme({ cornerRadius: val })}
                  />
                  <SliderRow
                    label="Padding"
                    value={theme.padding ?? 8}
                    min={0}
                    max={24}
                    onChange={(val) => patchTheme({ padding: val })}
                  />
                  <SliderRow
                    label="Margin"
                    value={theme.margin ?? 8}
                    min={0}
                    max={24}
                    onChange={(val) => patchTheme({ margin: val })}
                  />
                  <SliderRow
                    label="Shadow"
                    value={theme.shadow ?? 0}
                    min={0}
                    max={12}
                    onChange={(val) => patchTheme({ shadow: val })}
                  />
                  <SegmentedRow
                    label="Title alignment"
                    value={theme.titleAlignment ?? 'left'}
                    options={[
                      { value: 'left', icon: <AlignLeft size={13} /> },
                      { value: 'center', icon: <AlignCenter size={13} /> },
                      { value: 'right', icon: <AlignRight size={13} /> },
                    ]}
                    onChange={(val) => patchTheme({ titleAlignment: val as any })}
                  />

                  {/* VISUALIZATION */}
                  <SectionTitle title="VISUALIZATION" />
                  <ColorRow
                    label="Axis color"
                    value={theme.axisColor ?? 'Auto'}
                    onChange={(val) => patchTheme({ axisColor: val })}
                  />
                  <ColorRow
                    label="Grid color"
                    value={theme.gridColor ?? 'Auto'}
                    onChange={(val) => patchTheme({ gridColor: val })}
                  />

                  {/* TEXTBOX */}
                  <SectionTitle title="TEXTBOX" />
                  <SegmentedRow
                    label="Vertical alignment"
                    value={theme.verticalAlignment ?? 'top'}
                    options={[
                      { value: 'top', icon: <AlignTopIcon size={13} /> },
                      { value: 'center', icon: <AlignCenterVertIcon size={13} /> },
                      { value: 'bottom', icon: <AlignBottomIcon size={13} /> },
                    ]}
                    onChange={(val) => patchTheme({ verticalAlignment: val as any })}
                  />
                </>
              )}

              {themeSubTab === 'palette' && (
                <div style={{ marginTop: 8 }}>
                  <div style={{ fontSize: '0.76rem', fontWeight: 600, color: '#101828', marginBottom: 8 }}>
                    Color Palettes
                  </div>
                  {COLOR_PALETTES.map((p) => (
                    <div
                      key={p.name}
                      onClick={() => patchTheme({ palette: p.colors })}
                      style={{
                        padding: 10,
                        border: '1px solid #eaecf0',
                        borderRadius: 6,
                        marginBottom: 8,
                        cursor: 'pointer',
                        background: '#ffffff',
                      }}
                    >
                      <div style={{ fontSize: '0.74rem', fontWeight: 500, color: '#344054', marginBottom: 6 }}>
                        {p.name}
                      </div>
                      <div style={{ display: 'flex', gap: 4, height: 16, borderRadius: 4, overflow: 'hidden' }}>
                        {p.colors.map((c, i) => (
                          <div key={i} style={{ flex: 1, background: c }} />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {topTab === 'general' && (
            <>
              {/* Locale */}
              <div style={{ marginBottom: 16 }}>
                <label style={{ fontSize: '0.78rem', fontWeight: 600, color: '#101828', display: 'block', marginBottom: 6 }}>
                  Locale
                </label>
                <select
                  value={settings.locale ?? 'en-US'}
                  onChange={(e) => updateSettings({ locale: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '6px 10px',
                    fontSize: '0.78rem',
                    borderRadius: 6,
                    border: '1px solid #d0d5dd',
                    background: '#ffffff',
                    color: '#101828',
                    outline: 'none',
                    cursor: 'pointer',
                  }}
                >
                  {LOCALES.map((l) => (
                    <option key={l.value} value={l.value}>{l.label}</option>
                  ))}
                </select>
              </div>

              {/* Snap Grid Guidelines */}
              <div style={{ marginBottom: 16 }}>
                <label style={{ fontSize: '0.78rem', fontWeight: 600, color: '#101828', display: 'block', marginBottom: 6 }}>
                  Canvas Snap Grid Guidelines
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.76rem', cursor: 'pointer', color: '#344054' }}>
                  <input
                    type="checkbox"
                    checked={settings.showGridLines ?? true}
                    onChange={(e) => updateSettings({ showGridLines: e.target.checked })}
                    style={{ accentColor: '#2272b4' }}
                  />
                  Show 12-column and row grid lines for widget snapping
                </label>
              </div>

              {/* Filter Apply Mode */}
              <div style={{ marginBottom: 16 }}>
                <label style={{ fontSize: '0.78rem', fontWeight: 600, color: '#101828', display: 'block', marginBottom: 6 }}>
                  Filter Apply Behavior
                </label>
                {(['instant', 'button'] as const).map((mode) => (
                  <label key={mode} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, fontSize: '0.76rem', cursor: 'pointer', color: '#344054' }}>
                    <input
                      type="radio"
                      name="filterMode"
                      value={mode}
                      checked={(settings.filterApplyMode ?? 'instant') === mode}
                      onChange={() => updateSettings({ filterApplyMode: mode })}
                      style={{ accentColor: '#2272b4' }}
                    />
                    {mode === 'instant' ? 'Apply instantly on change' : 'Apply with explicit button'}
                  </label>
                ))}
              </div>

              {/* Dashboard Tags */}
              <div style={{ marginBottom: 16 }}>
                <label style={{ fontSize: '0.78rem', fontWeight: 600, color: '#101828', display: 'block', marginBottom: 6 }}>
                  Dashboard Tags
                </label>
                {tags.map((tag, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, background: '#f8fafc', padding: '4px 8px', borderRadius: 4 }}>
                    <span style={{ fontSize: '0.74rem', flex: 1, color: '#344054' }}>
                      {tag.key}: <strong>{tag.value}</strong>
                    </span>
                    <button
                      onClick={() => removeTag(i)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#98a2b3', padding: 2 }}
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                ))}
                <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                  <input
                    placeholder="Key"
                    value={newTagKey}
                    onChange={(e) => setNewTagKey(e.target.value)}
                    style={{ flex: 1, padding: '4px 8px', fontSize: '0.74rem', border: '1px solid #d0d5dd', borderRadius: 4, outline: 'none' }}
                  />
                  <input
                    placeholder="Value"
                    value={newTagVal}
                    onChange={(e) => setNewTagVal(e.target.value)}
                    style={{ flex: 1, padding: '4px 8px', fontSize: '0.74rem', border: '1px solid #d0d5dd', borderRadius: 4, outline: 'none' }}
                  />
                  <button
                    onClick={addTag}
                    style={{
                      background: '#2272b4',
                      color: '#ffffff',
                      border: 'none',
                      borderRadius: 4,
                      padding: '4px 8px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center'
                    }}
                  >
                    <Plus size={13} />
                  </button>
                </div>
              </div>

              {/* Genie AI */}
              <div>
                <label style={{ fontSize: '0.78rem', fontWeight: 600, color: '#101828', display: 'block', marginBottom: 6 }}>
                  Genie AI Integration
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.76rem', cursor: 'pointer', color: '#344054', marginBottom: 8 }}>
                  <input
                    type="checkbox"
                    checked={settings.genieEnabled ?? false}
                    onChange={(e) => updateSettings({ genieEnabled: e.target.checked })}
                    style={{ accentColor: '#2272b4' }}
                  />
                  Enable Genie natural language queries
                </label>
                {settings.genieEnabled && (
                  <div>
                    <input
                      value={settings.genieSpaceUrl ?? ''}
                      onChange={(e) => updateSettings({ genieSpaceUrl: e.target.value })}
                      placeholder="Genie Space URL (https://...)"
                      style={{ width: '100%', padding: '6px 8px', fontSize: '0.74rem', border: '1px solid #d0d5dd', borderRadius: 4, outline: 'none' }}
                    />
                  </div>
                )}
              </div>
            </>
          )}

        </div>
    </DashboardSidePanel>
  );
}
