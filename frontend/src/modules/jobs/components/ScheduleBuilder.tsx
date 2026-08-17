import { useState } from 'react';
import { cronToHuman, cronToSimple, simpleToCron } from '../lib/cronUtils';
import type { SimpleSchedule } from '../lib/cronUtils';

interface Props {
  value?: string;     // cron string or undefined (manual)
  timezone: string;
  onChange: (cron: string | undefined, timezone: string) => void;
}

const PRESETS = [
  { value: 'hourly',  label: 'Every hour'   },
  { value: 'daily',   label: 'Every day'    },
  { value: 'weekly',  label: 'Every week'   },
  { value: 'monthly', label: 'Every month'  },
  { value: 'custom',  label: 'Custom cron'  },
] as const;

const HOURS = Array.from({ length: 24 }, (_, i) => i);
const MINUTES = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55];
const DAYS_OF_WEEK = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const DOMS = Array.from({ length: 28 }, (_, i) => i + 1);

const COMMON_TZ = [
  'UTC', 'Asia/Kolkata', 'America/New_York', 'America/Chicago',
  'America/Los_Angeles', 'Europe/London', 'Europe/Paris', 'Asia/Tokyo',
  'Australia/Sydney', 'Asia/Singapore', 'America/Sao_Paulo',
];

export default function ScheduleBuilder({ value, timezone, onChange }: Props) {
  const [mode, setMode] = useState<'simple' | 'advanced'>(value && value.split(' ').length === 5 ? 'simple' : 'simple');
  const [rawCron, setRawCron] = useState(value ?? '');
  const simple = cronToSimple(value);
  const [s, setS] = useState<SimpleSchedule>(simple);
  const [noSchedule, setNoSchedule] = useState(!value);

  function applySimple(next: SimpleSchedule) {
    setS(next);
    if (next.preset === 'custom') return;
    const cron = simpleToCron(next);
    onChange(cron, timezone);
  }

  function applyRaw(cron: string) {
    setRawCron(cron);
    onChange(cron.trim() || undefined, timezone);
  }

  function handleNoSchedule(checked: boolean) {
    setNoSchedule(checked);
    if (checked) onChange(undefined, timezone);
    else {
      const cron = mode === 'simple' ? simpleToCron(s) : rawCron;
      onChange(cron || undefined, timezone);
    }
  }

  const previewCron = noSchedule ? undefined : (mode === 'simple' && s.preset !== 'custom' ? simpleToCron(s) : rawCron);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Manual only toggle */}
      <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.875rem', cursor: 'pointer' }}>
        <input
          type="checkbox"
          checked={noSchedule}
          onChange={(e) => handleNoSchedule(e.target.checked)}
          style={{ accentColor: 'var(--color-primary)', width: 15, height: 15 }}
        />
        <span>Manual only (no automatic schedule)</span>
      </label>

      {!noSchedule && (
        <>
          {/* Mode toggle */}
          <div style={{ display: 'flex', gap: 0, borderRadius: 6, overflow: 'hidden', border: '1px solid var(--color-border)', width: 'fit-content' }}>
            {(['simple', 'advanced'] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                style={{
                  padding: '5px 14px', fontSize: '0.78rem', fontWeight: 500,
                  border: 'none', cursor: 'pointer',
                  background: mode === m ? 'var(--color-primary)' : 'var(--color-surface)',
                  color: mode === m ? '#fff' : 'var(--color-text)',
                  fontFamily: 'var(--font-family)',
                }}
              >
                {m === 'simple' ? 'Simple' : 'Advanced'}
              </button>
            ))}
          </div>

          {mode === 'simple' ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {/* Preset */}
              <div className="form-field">
                <label className="form-label">Frequency</label>
                <select
                  className="form-input"
                  value={s.preset}
                  onChange={(e) => applySimple({ ...s, preset: e.target.value as SimpleSchedule['preset'] })}
                >
                  {PRESETS.map((p) => (
                    <option key={p.value} value={p.value}>{p.label}</option>
                  ))}
                </select>
              </div>

              {/* Minute */}
              {s.preset !== 'hourly' && s.preset !== 'custom' && (
                <div style={{ display: 'flex', gap: 10 }}>
                  <div className="form-field" style={{ flex: 1 }}>
                    <label className="form-label">Hour</label>
                    <select className="form-input" value={s.hour}
                      onChange={(e) => applySimple({ ...s, hour: parseInt(e.target.value) })}>
                      {HOURS.map((h) => <option key={h} value={h}>{String(h).padStart(2,'0')}:00</option>)}
                    </select>
                  </div>
                  <div className="form-field" style={{ flex: 1 }}>
                    <label className="form-label">Minute</label>
                    <select className="form-input" value={s.minute}
                      onChange={(e) => applySimple({ ...s, minute: parseInt(e.target.value) })}>
                      {MINUTES.map((m) => <option key={m} value={m}>{String(m).padStart(2,'0')}</option>)}
                    </select>
                  </div>
                </div>
              )}

              {s.preset === 'hourly' && (
                <div className="form-field">
                  <label className="form-label">At minute</label>
                  <select className="form-input" value={s.minute}
                    onChange={(e) => applySimple({ ...s, minute: parseInt(e.target.value) })}>
                    {MINUTES.map((m) => <option key={m} value={m}>{String(m).padStart(2,'0')}</option>)}
                  </select>
                </div>
              )}

              {s.preset === 'weekly' && (
                <div className="form-field">
                  <label className="form-label">On</label>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {DAYS_OF_WEEK.map((d, i) => (
                      <button
                        key={d}
                        type="button"
                        onClick={() => applySimple({ ...s, weekday: i })}
                        style={{
                          padding: '4px 10px', borderRadius: 4, fontSize: '0.78rem',
                          fontWeight: 500, cursor: 'pointer', border: '1px solid var(--color-border)',
                          background: s.weekday === i ? 'var(--color-primary)' : 'var(--color-surface)',
                          color: s.weekday === i ? '#fff' : 'var(--color-text)',
                          fontFamily: 'var(--font-family)',
                        }}
                      >{d}</button>
                    ))}
                  </div>
                </div>
              )}

              {s.preset === 'monthly' && (
                <div className="form-field">
                  <label className="form-label">Day of month</label>
                  <select className="form-input" value={s.dom}
                    onChange={(e) => applySimple({ ...s, dom: parseInt(e.target.value) })}>
                    {DOMS.map((d) => <option key={d} value={d}>{d}</option>)}
                  </select>
                </div>
              )}
            </div>
          ) : (
            <div className="form-field">
              <label className="form-label">Cron expression</label>
              <input
                type="text"
                className="form-input"
                placeholder="0 2 * * *"
                value={rawCron}
                onChange={(e) => applyRaw(e.target.value)}
                style={{ fontFamily: 'monospace' }}
              />
              <span className="form-hint">Standard 5-field cron: minute hour day month weekday</span>
            </div>
          )}

          {/* Timezone */}
          <div className="form-field">
            <label className="form-label">Timezone</label>
            <select
              className="form-input"
              value={timezone}
              onChange={(e) => {
                const cron = mode === 'simple' ? simpleToCron(s) : rawCron;
                onChange(cron || undefined, e.target.value);
              }}
            >
              {COMMON_TZ.map((tz) => <option key={tz} value={tz}>{tz}</option>)}
            </select>
          </div>
        </>
      )}

      {/* Human-readable preview */}
      <div style={{
        padding: '8px 12px', borderRadius: 6,
        background: 'var(--color-bg)', border: '1px solid var(--color-border)',
        fontSize: '0.82rem', color: 'var(--color-text-muted)',
      }}>
        <span style={{ color: 'var(--color-text)', fontWeight: 500 }}>Preview: </span>
        {noSchedule ? 'No automatic schedule — manual trigger only' : (cronToHuman(previewCron) || 'Enter a valid cron expression')}
      </div>
    </div>
  );
}
