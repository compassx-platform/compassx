import { createContext, useContext, type ReactNode } from 'react';
import { lightCanvasTheme, type CanvasTheme } from './theme';

const ThemeContext = createContext<CanvasTheme>(lightCanvasTheme);

export function CanvasThemeProvider({ theme, children }: { theme: CanvasTheme; children: ReactNode }) {
  return <ThemeContext.Provider value={theme}>{children}</ThemeContext.Provider>;
}

export function useHostTheme(): CanvasTheme {
  return useContext(ThemeContext);
}

export { useEffect, useMemo, useState } from 'react';

export interface ChartPoint {
  label: string;
  value: number;
}

function useText() {
  const theme = useHostTheme();
  return theme;
}

export function Stack({ gap = 12, children }: { gap?: number; children?: ReactNode }) {
  const theme = useText();
  return <div style={{ display: 'flex', flexDirection: 'column', gap, color: theme.text }}>{children}</div>;
}

export function Row({ gap = 12, children }: { gap?: number; children?: ReactNode }) {
  return <div style={{ display: 'flex', flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap }}>{children}</div>;
}

export function Grid({ columns = 2, gap = 12, children }: { columns?: number; gap?: number; children?: ReactNode }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.max(1, columns)}, minmax(0, 1fr))`, gap }}>
      {children}
    </div>
  );
}

export function H1({ children }: { children?: ReactNode }) {
  const theme = useHostTheme();
  return <h1 style={{ margin: 0, fontSize: 22, lineHeight: 1.3, fontWeight: 650, color: theme.text }}>{children}</h1>;
}

export function H2({ children }: { children?: ReactNode }) {
  const theme = useHostTheme();
  return <h2 style={{ margin: 0, fontSize: 16, lineHeight: 1.35, fontWeight: 650, color: theme.text }}>{children}</h2>;
}

export function H3({ children }: { children?: ReactNode }) {
  const theme = useHostTheme();
  return <h3 style={{ margin: 0, fontSize: 14, lineHeight: 1.4, fontWeight: 650, color: theme.text }}>{children}</h3>;
}

export function Text({ children }: { children?: ReactNode }) {
  const theme = useHostTheme();
  return <p style={{ margin: 0, fontSize: 14, lineHeight: 1.5, color: theme.text }}>{children}</p>;
}

export function Divider() {
  const theme = useHostTheme();
  return <hr style={{ width: '100%', border: 'none', borderTop: `1px solid ${theme.border}`, margin: 0 }} />;
}

export function Card({ children }: { children?: ReactNode }) {
  const theme = useHostTheme();
  return (
    <section style={{ background: theme.card, border: `1px solid ${theme.border}`, borderRadius: 10, padding: 14 }}>
      {children}
    </section>
  );
}

export function CardHeader({ children }: { children?: ReactNode }) {
  return <div style={{ marginBottom: 8 }}>{children}</div>;
}

export function CardBody({ children }: { children?: ReactNode }) {
  return <div>{children}</div>;
}

export function Stat({ label, value }: { label: string; value: string | number }) {
  const theme = useHostTheme();
  return (
    <div style={{ minWidth: 120 }}>
      <div style={{ fontSize: 12, color: theme.muted }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 650, color: theme.text, marginTop: 2 }}>{value}</div>
    </div>
  );
}

export function Callout({ tone = 'info', children }: { tone?: 'info' | 'warning' | 'success'; children?: ReactNode }) {
  const theme = useHostTheme();
  const color = tone === 'warning' ? theme.warning : tone === 'success' ? theme.positive : theme.accent;
  return (
    <div style={{ border: `1px solid ${theme.border}`, borderLeft: `3px solid ${color}`, borderRadius: 8, padding: '10px 12px', color: theme.text, fontSize: 14, lineHeight: 1.5 }}>
      {children}
    </div>
  );
}

export function Pill({ children }: { children?: ReactNode }) {
  const theme = useHostTheme();
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', border: `1px solid ${theme.border}`, borderRadius: 999, padding: '2px 8px', fontSize: 12, color: theme.text }}>
      {children}
    </span>
  );
}

export function Table({ title, columns, rows }: { title: string; columns: string[]; rows: (string | number)[][] }) {
  const theme = useHostTheme();
  if (!columns?.length) return null;
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, color: theme.text }}>
      <caption style={{ captionSide: 'top', textAlign: 'left', fontWeight: 650, fontSize: 14, padding: '0 0 8px' }}>{title}</caption>
      <thead>
        <tr>
          {columns.map((column) => (
            <th key={column} scope="col" style={{ textAlign: 'left', fontWeight: 650, padding: '6px 8px', borderBottom: `1px solid ${theme.border}`, color: theme.muted }}>
              {column}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, index) => (
          <tr key={`${title}-${index}`}>
            {columns.map((column, cell) => (
              <td key={`${column}-${cell}`} style={{ padding: '6px 8px', borderBottom: `1px solid ${theme.border}` }}>
                {row[cell] ?? ''}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function chartPoints(points: ChartPoint[]) {
  return (points || [])
    .map((point) => ({ label: String(point.label ?? ''), value: Number(point.value) || 0 }))
    .filter((point) => point.label);
}

export function BarChart({ title, points }: { title: string; points: ChartPoint[] }) {
  const theme = useHostTheme();
  const data = chartPoints(points);
  if (!data.length) return <H3>{title}</H3>;
  const max = Math.max(...data.map((point) => point.value), 1);
  const width = 420;
  const height = 180;
  const slot = width / data.length;
  return (
    <figure style={{ margin: 0 }}>
      <figcaption style={{ fontSize: 14, fontWeight: 650, color: theme.text, marginBottom: 8 }}>{title}</figcaption>
      <svg viewBox={`0 0 ${width} ${height + 28}`} role="img" aria-label={title} style={{ width: '100%', height: 'auto' }}>
        <text x="0" y="12" fill={theme.muted} fontSize="11">Value</text>
        {data.map((point, index) => {
          const barHeight = Math.max(2, (point.value / max) * (height - 24));
          const x = index * slot + slot * 0.2;
          const y = height - barHeight;
          return (
            <g key={point.label}>
              <rect x={x} y={y} width={slot * 0.6} height={barHeight} fill={theme.accent} />
              <text x={x + slot * 0.3} y={height + 16} textAnchor="middle" fill={theme.muted} fontSize="11">{point.label}</text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}

export function LineChart({ title, points }: { title: string; points: ChartPoint[] }) {
  const theme = useHostTheme();
  const data = chartPoints(points);
  if (!data.length) return <H3>{title}</H3>;
  const max = Math.max(...data.map((point) => point.value), 1);
  const width = 420;
  const height = 180;
  const step = data.length === 1 ? 0 : width / (data.length - 1);
  const coords = data.map((point, index) => {
    const x = index * step;
    const y = height - (point.value / max) * (height - 16) - 8;
    return `${x},${y}`;
  });
  return (
    <figure style={{ margin: 0 }}>
      <figcaption style={{ fontSize: 14, fontWeight: 650, color: theme.text, marginBottom: 8 }}>{title}</figcaption>
      <svg viewBox={`0 0 ${width} ${height + 28}`} role="img" aria-label={title} style={{ width: '100%', height: 'auto' }}>
        <text x="0" y="12" fill={theme.muted} fontSize="11">Value</text>
        <polyline fill="none" stroke={theme.accent} strokeWidth="2" points={coords.join(' ')} />
        {data.map((point, index) => (
          <text key={point.label} x={index * step} y={height + 16} textAnchor={index === 0 ? 'start' : 'middle'} fill={theme.muted} fontSize="11">
            {point.label}
          </text>
        ))}
      </svg>
    </figure>
  );
}

export function PieChart({ title, points }: { title: string; points: ChartPoint[] }) {
  const theme = useHostTheme();
  const data = chartPoints(points).filter((point) => point.value > 0);
  if (!data.length) return <H3>{title}</H3>;
  const total = data.reduce((sum, point) => sum + point.value, 0);
  const palette = [theme.accent, theme.positive, theme.warning, theme.muted];
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  return (
    <figure style={{ margin: 0 }}>
      <figcaption style={{ fontSize: 14, fontWeight: 650, color: theme.text, marginBottom: 8 }}>{title}</figcaption>
      <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
        <svg viewBox="0 0 140 140" width="140" height="140" role="img" aria-label={title}>
          {data.map((point, index) => {
            const length = (point.value / total) * circumference;
            const dash = `${length} ${circumference - length}`;
            const circle = (
              <circle
                key={point.label}
                cx="70"
                cy="70"
                r={radius}
                fill="none"
                stroke={palette[index % palette.length]}
                strokeWidth="18"
                strokeDasharray={dash}
                strokeDashoffset={-offset}
                transform="rotate(-90 70 70)"
              />
            );
            offset += length;
            return circle;
          })}
        </svg>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {data.map((point, index) => (
            <div key={point.label} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: theme.text }}>
              <span style={{ width: 8, height: 8, background: palette[index % palette.length] }} />
              <span>{point.label}</span>
              <span style={{ color: theme.muted }}>{point.value}</span>
            </div>
          ))}
        </div>
      </div>
    </figure>
  );
}
