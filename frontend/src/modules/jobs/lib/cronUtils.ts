/**
 * Cron utilities — translate between cron expressions and human-readable strings.
 * Supports the most common patterns used in job scheduling UIs.
 */

export function cronToHuman(cron: string | null | undefined): string {
  if (!cron) return 'Manual only';
  const c = cron.trim();

  // Presets
  const presets: Record<string, string> = {
    '0 * * * *':    'Every hour',
    '*/30 * * * *': 'Every 30 minutes',
    '*/15 * * * *': 'Every 15 minutes',
    '0 0 * * *':    'Every day at midnight',
    '0 2 * * *':    'Every day at 02:00',
    '0 6 * * *':    'Every day at 06:00',
    '0 12 * * *':   'Every day at 12:00',
    '0 18 * * *':   'Every day at 18:00',
    '0 0 * * 1':    'Every Monday at midnight',
    '0 0 * * 0':    'Every Sunday at midnight',
    '0 0 1 * *':    'First day of every month',
    '0 0 * * 1-5':  'Every weekday at midnight',
  };
  if (presets[c]) return presets[c];

  // Try to parse simple patterns
  const parts = c.split(/\s+/);
  if (parts.length !== 5) return c;
  const [min, hour, dom, month, dow] = parts;

  const DAYS: Record<string, string> = {
    '0': 'Sunday', '1': 'Monday', '2': 'Tuesday', '3': 'Wednesday',
    '4': 'Thursday', '5': 'Friday', '6': 'Saturday',
    'sun': 'Sunday', 'mon': 'Monday', 'tue': 'Tuesday', 'wed': 'Wednesday',
    'thu': 'Thursday', 'fri': 'Friday', 'sat': 'Saturday',
  };

  if (dom === '*' && month === '*' && dow === '*') {
    if (min === '*' && hour === '*') return 'Every minute';
    if (hour === '*') {
      if (min.startsWith('*/')) return `Every ${min.slice(2)} minutes`;
      return `At minute ${min} of every hour`;
    }
    const h = parseInt(hour, 10);
    const m = parseInt(min, 10);
    if (!isNaN(h) && !isNaN(m)) {
      const time = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
      return `Every day at ${time}`;
    }
  }

  if (dom === '*' && month === '*' && dow !== '*') {
    const dayName = DAYS[dow.toLowerCase()] ?? `day ${dow}`;
    const h = parseInt(hour, 10);
    const m = parseInt(min, 10);
    if (!isNaN(h) && !isNaN(m)) {
      const time = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
      return `Every ${dayName} at ${time}`;
    }
  }

  if (dom !== '*' && month === '*' && dow === '*') {
    const h = parseInt(hour, 10);
    const m = parseInt(min, 10);
    if (!isNaN(h) && !isNaN(m)) {
      const time = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
      return `Day ${dom} of every month at ${time}`;
    }
  }

  return c;
}

export type SimpleSchedulePreset =
  | 'hourly' | 'daily' | 'weekly' | 'monthly' | 'custom';

export interface SimpleSchedule {
  preset: SimpleSchedulePreset;
  hour: number;    // 0-23
  minute: number;  // 0-59
  weekday: number; // 0-6 (Sun-Sat)
  dom: number;     // 1-31 day of month
}

export function simpleToCron(s: SimpleSchedule): string {
  switch (s.preset) {
    case 'hourly':  return `${s.minute} * * * *`;
    case 'daily':   return `${s.minute} ${s.hour} * * *`;
    case 'weekly':  return `${s.minute} ${s.hour} * * ${s.weekday}`;
    case 'monthly': return `${s.minute} ${s.hour} ${s.dom} * *`;
    default:        return '';
  }
}

export function cronToSimple(cron: string | null | undefined): SimpleSchedule {
  const defaults: SimpleSchedule = { preset: 'daily', hour: 0, minute: 0, weekday: 1, dom: 1 };
  if (!cron) return defaults;
  const parts = cron.trim().split(/\s+/);
  if (parts.length !== 5) return { ...defaults, preset: 'custom' };
  const [min, hour, dom, , dow] = parts;
  if (dow !== '*') return {
    preset: 'weekly',
    hour: parseInt(hour, 10) || 0,
    minute: parseInt(min, 10) || 0,
    weekday: parseInt(dow, 10) || 1,
    dom: 1,
  };
  if (dom !== '*') return {
    preset: 'monthly',
    hour: parseInt(hour, 10) || 0,
    minute: parseInt(min, 10) || 0,
    weekday: 1,
    dom: parseInt(dom, 10) || 1,
  };
  if (hour === '*') return {
    preset: 'hourly',
    hour: 0,
    minute: parseInt(min, 10) || 0,
    weekday: 1,
    dom: 1,
  };
  return {
    preset: 'daily',
    hour: parseInt(hour, 10) || 0,
    minute: parseInt(min, 10) || 0,
    weekday: 1,
    dom: 1,
  };
}

export function formatDuration(seconds?: number | null): string {
  if (!seconds && seconds !== 0) return '—';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  const rm = m % 60;
  return `${h}h ${rm}m`;
}

export function relativeTime(iso?: string | null): string {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  const s = Math.round(diff / 1000);
  if (s < 60) return 'just now';
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24);
  return `${d}d ago`;
}
