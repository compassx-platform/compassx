/**
 * Utility functions for evaluating and applying dashboard filters across dataset rows.
 */

import type { Widget, FilterValue } from '@/types/dashboard';

export function filterRows(
  rows: Record<string, unknown>[] | undefined,
  widgets: Widget[] | undefined,
  filterState: Record<string, FilterValue> | undefined,
  targetDatasetId?: string
): Record<string, unknown>[] {
  if (!rows || rows.length === 0) return [];
  if (!widgets || widgets.length === 0 || !filterState) return rows;

  // Identify all active filter widgets applicable to this dataset
  const activeFilterWidgets = widgets.filter((w) => {
    if (w.widgetType !== 'filter' || !w.filterConfig?.field) return false;
    const cfg = w.filterConfig;

    // If targetDatasetId is provided, check if filter is linked to it (empty datasetIds = applies to all)
    if (targetDatasetId && cfg.datasetIds && cfg.datasetIds.length > 0) {
      if (!cfg.datasetIds.includes(targetDatasetId)) return false;
    }

    const val = filterState[w.id];
    if (val === null || val === undefined || val === '') return false;
    if (Array.isArray(val) && val.length === 0) return false;
    return true;
  });

  if (activeFilterWidgets.length === 0) return rows;

  return rows.filter((row) => {
    return activeFilterWidgets.every((fw) => {
      const cfg = fw.filterConfig!;
      const field = cfg.field!;
      const filterVal = filterState[fw.id];
      const rowVal = row[field];

      if (rowVal === undefined || rowVal === null) return false;

      switch (cfg.filterType) {
        case 'single_value': {
          if (!filterVal) return true;
          return String(rowVal).trim().toLowerCase() === String(filterVal).trim().toLowerCase();
        }

        case 'multi_value': {
          if (!Array.isArray(filterVal) || filterVal.length === 0) return true;
          const rowStr = String(rowVal).trim().toLowerCase();
          return filterVal.some((v) => String(v).trim().toLowerCase() === rowStr);
        }

        case 'date_picker': {
          if (!filterVal || typeof filterVal !== 'string') return true;
          const rowDateStr = String(rowVal).split('T')[0];
          return rowDateStr === filterVal;
        }

        case 'date_range': {
          if (!Array.isArray(filterVal) || filterVal.length < 2) return true;
          const [start, end] = filterVal as [string, string];
          const rowDateStr = String(rowVal).split('T')[0];
          if (start && rowDateStr < start) return false;
          if (end && rowDateStr > end) return false;
          return true;
        }

        case 'text_entry': {
          if (!filterVal || typeof filterVal !== 'string') return true;
          const search = filterVal.trim().toLowerCase();
          const target = String(rowVal).toLowerCase();
          if (cfg.matchMode === 'exact') return target === search;
          if (cfg.matchMode === 'starts_with') return target.startsWith(search);
          return target.includes(search);
        }

        case 'range_slider': {
          if (!Array.isArray(filterVal) || filterVal.length < 2) return true;
          const [min, max] = filterVal as [number, number];
          const num = Number(rowVal);
          if (isNaN(num)) return true;
          return num >= min && num <= max;
        }

        default:
          return true;
      }
    });
  });
}
