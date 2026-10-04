export const ROW_META_SLOT_CLASS = 'w-14';
export const ROW_ACTION_SIZE_CLASS = 'size-[18px]';
export const ROW_STATUS_SLOT_CLASS = 'w-[22px]';

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null || !Number.isFinite(bytes) || bytes < 0) return '—';
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let value = bytes / 1024;
  for (let i = 0; i < units.length; i += 1) {
    if (value < 1024 || i === units.length - 1) {
      return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[i]}`;
    }
    value /= 1024;
  }
  return `${bytes} B`;
}
