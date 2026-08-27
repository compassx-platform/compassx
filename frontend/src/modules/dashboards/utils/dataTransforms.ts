/**
 * Data transformation and aggregation utilities for dashboard charts and metric widgets.
 */

export function aggregateValues(vals: (number | string | null | undefined)[], type?: string): number {
  if (!vals || vals.length === 0) return 0;

  const op = (type || 'NONE').toUpperCase();

  // For COUNT and COUNT DISTINCT, count records directly (works on strings, IDs, dates, numbers)
  if (op === 'COUNT') {
    return vals.filter((v) => v !== null && v !== undefined && v !== '').length;
  }
  if (op === 'COUNT DISTINCT') {
    return new Set(
      vals
        .filter((v) => v !== null && v !== undefined && v !== '')
        .map((v) => String(v).trim())
    ).size;
  }

  // For numeric aggregations, parse numbers cleanly (stripping commas, currency symbols, whitespace)
  const numVals: number[] = [];
  for (const v of vals) {
    if (v === null || v === undefined || v === '') continue;
    if (typeof v === 'number') {
      if (!isNaN(v)) numVals.push(v);
    } else if (typeof v === 'string') {
      const clean = v.replace(/[$€£₹,\s]/g, '').trim();
      const n = Number(clean);
      if (!isNaN(n)) numVals.push(n);
    }
  }

  if (numVals.length === 0) return 0;

  switch (op) {
    case 'SUM':
      return numVals.reduce((acc, v) => acc + v, 0);

    case 'AVG':
      return numVals.reduce((acc, v) => acc + v, 0) / numVals.length;

    case 'MIN':
      return Math.min(...numVals);

    case 'MAX':
      return Math.max(...numVals);

    case 'MEDIAN': {
      const sorted = [...numVals].sort((a, b) => a - b);
      const mid = Math.floor(sorted.length / 2);
      return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
    }

    case 'FIRST':
      return numVals[0];

    case 'LAST':
      return numVals[numVals.length - 1];

    case 'VAR': {
      const mean = numVals.reduce((acc, v) => acc + v, 0) / numVals.length;
      return numVals.reduce((acc, v) => acc + Math.pow(v - mean, 2), 0) / (numVals.length > 1 ? numVals.length - 1 : 1);
    }

    case 'STD': {
      const mean = numVals.reduce((acc, v) => acc + v, 0) / numVals.length;
      const variance = numVals.reduce((acc, v) => acc + Math.pow(v - mean, 2), 0) / (numVals.length > 1 ? numVals.length - 1 : 1);
      return Math.sqrt(variance);
    }

    case 'PERCENTILE': {
      const sorted = [...numVals].sort((a, b) => a - b);
      const p = 0.9;
      const idx = Math.floor(p * (sorted.length - 1));
      return sorted[idx];
    }

    case 'NONE':
    default:
      return numVals[0];
  }
}
