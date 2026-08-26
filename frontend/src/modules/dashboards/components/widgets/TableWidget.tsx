/**
 * TableWidget — interactive data table component with pagination, live search, sorting, column filtering, and custom header titles.
 */

import { useState, useMemo } from 'react';
import { useDashboardStore } from '@/modules/dashboards/stores/dashboardStore';
import { useDatasetQuery } from '@/modules/dashboards/hooks/useDashboard';
import type { Widget } from '@/types/dashboard';
import { Search, ChevronLeft, ChevronRight } from 'lucide-react';

interface Props {
  widget: Widget;
}

function getColumnTitle(col: string, cfg: any): string {
  const found = cfg?.seriesTitles?.find((st: any) => st.field === col);
  if (found?.title) return found.title;
  return col;
}

function getContrastColor(colorStr?: string): string {
  if (!colorStr) return '#334155';
  const str = colorStr.trim().toLowerCase();
  if (str === 'transparent' || str === 'inherit' || str === 'initial') return '#334155';
  if (str === 'white' || str === '#fff' || str === '#ffffff') return '#334155';
  if (str === 'black' || str === '#000' || str === '#000000') return '#ffffff';

  const rgbMatch = str.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
  if (rgbMatch) {
    const r = parseInt(rgbMatch[1], 10);
    const g = parseInt(rgbMatch[2], 10);
    const b = parseInt(rgbMatch[3], 10);
    const yiq = (r * 299 + g * 587 + b * 114) / 1000;
    return yiq >= 135 ? '#334155' : '#ffffff';
  }

  const cleanHex = str.replace('#', '').trim();
  let r = 241, g = 245, b = 249;
  if (cleanHex.length === 3 || cleanHex.length === 4) {
    r = parseInt(cleanHex[0] + cleanHex[0], 16);
    g = parseInt(cleanHex[1] + cleanHex[1], 16);
    b = parseInt(cleanHex[2] + cleanHex[2], 16);
  } else if (cleanHex.length >= 6) {
    r = parseInt(cleanHex.substring(0, 2), 16);
    g = parseInt(cleanHex.substring(2, 4), 16);
    b = parseInt(cleanHex.substring(4, 6), 16);
  } else {
    return '#334155';
  }

  if (isNaN(r) || isNaN(g) || isNaN(b)) return '#334155';
  const yiq = (r * 299 + g * 587 + b * 114) / 1000;
  return yiq >= 135 ? '#334155' : '#ffffff';
}

export default function TableWidget({ widget }: Props) {
  const { filterState, paramState } = useDashboardStore();
  const cfg = widget.chartConfig;
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);

  const { data: queryResult, isLoading } = useDatasetQuery(
    cfg?.datasetId,
    paramState as any,
    filterState as any,
    !!cfg?.datasetId
  );

  const rawCols = queryResult?.columns ?? [];
  const selectedCols = (cfg?.yFields && cfg.yFields.length > 0) ? cfg.yFields : rawCols;
  const visibleCols = useMemo(() => {
    return selectedCols.filter((c) => rawCols.includes(c));
  }, [selectedCols, rawCols]);

  const sortedRows = useMemo(() => {
    if (!queryResult?.rows) return [];
    const rows = [...queryResult.rows];
    const sortField = cfg?.xAxis?.sortByField;
    const sortOrder = cfg?.xAxis?.sortByOrder ?? 'asc';

    if (!sortField) return rows;

    return rows.sort((a, b) => {
      const valA = a[sortField];
      const valB = b[sortField];
      if (valA === valB) return 0;
      if (valA === null || valA === undefined) return 1;
      if (valB === null || valB === undefined) return -1;
      const numA = Number(valA);
      const numB = Number(valB);
      if (!isNaN(numA) && !isNaN(numB)) {
        return sortOrder === 'desc' ? numB - numA : numA - numB;
      }
      const comp = String(valA).localeCompare(String(valB), undefined, { numeric: true, sensitivity: 'base' });
      return sortOrder === 'desc' ? -comp : comp;
    });
  }, [queryResult?.rows, cfg?.xAxis?.sortByField, cfg?.xAxis?.sortByOrder]);

  const filteredRows = useMemo(() => {
    if (!searchTerm.trim()) return sortedRows;
    const term = searchTerm.toLowerCase();
    return sortedRows.filter((r) =>
      visibleCols.some((col) => String(r[col] ?? '').toLowerCase().includes(term))
    );
  }, [sortedRows, visibleCols, searchTerm]);

  const pageSize = cfg?.pageSize ?? 25;
  const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize));
  const activePage = Math.min(currentPage, totalPages);

  const paginatedRows = useMemo(() => {
    const start = (activePage - 1) * pageSize;
    return filteredRows.slice(start, start + pageSize);
  }, [filteredRows, activePage, pageSize]);

  if (isLoading) {
    return <div style={{ padding: 16, fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>Loading table data…</div>;
  }

  if (!queryResult) {
    return <div style={{ padding: 16, fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>No data</div>;
  }

  const showSearch = cfg?.showSearch ?? true;
  const showRowNumbers = cfg?.showRowNumbers ?? false;
  const wrapText = cfg?.wrapText ?? false;

  const titleRowBg = cfg?.titleRowBg ?? cfg?.headerBg ?? cfg?.headerBackgroundColor;
  const headerBg = titleRowBg || '#f1f5f9';
  const autoTextColor = getContrastColor(titleRowBg);
  const headerTextColor = cfg?.titleRowColor ?? cfg?.headerColor ?? autoTextColor;
  const isDarkHeader = autoTextColor === '#ffffff';
  const headerBorderBottom = isDarkHeader ? '2px solid rgba(255, 255, 255, 0.25)' : '2px solid #cbd5e1';
  const rowNumberHeaderColor = isDarkHeader ? 'rgba(255, 255, 255, 0.75)' : '#64748b';

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden', background: '#ffffff' }}>
      {/* Search Bar */}
      {showSearch && (
        <div style={{ padding: '6px 10px', borderBottom: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', gap: 6, background: '#f8fafc', flexShrink: 0 }}>
          <Search size={13} style={{ color: '#64748b' }} />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              setCurrentPage(1);
            }}
            placeholder="Search table rows..."
            style={{
              width: '100%',
              border: 'none',
              background: 'transparent',
              fontSize: '0.74rem',
              color: '#0f172a',
              outline: 'none',
            }}
          />
        </div>
      )}

      {/* Table Surface */}
      <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.76rem', color: '#1e293b' }}>
          <thead style={{ position: 'sticky', top: 0, background: headerBg, zIndex: 2 }}>
            <tr>
              {showRowNumbers && (
                <th style={{
                  padding: '6px 8px',
                  width: 36,
                  textAlign: 'center',
                  fontWeight: 600,
                  borderBottom: headerBorderBottom,
                  color: rowNumberHeaderColor,
                  background: headerBg,
                }}>
                  #
                </th>
              )}
              {visibleCols.map((col) => (
                <th key={col} style={{
                  padding: '6px 10px',
                  textAlign: 'left',
                  fontWeight: 600,
                  borderBottom: headerBorderBottom,
                  color: headerTextColor,
                  background: headerBg,
                  whiteSpace: 'nowrap',
                }}>
                  {getColumnTitle(col, cfg)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paginatedRows.map((row, i) => {
              const rowIndex = (activePage - 1) * pageSize + i + 1;
              return (
                <tr
                  key={i}
                  style={{ borderBottom: '1px solid #f1f5f9' }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = '#f8fafc')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = '')}
                >
                  {showRowNumbers && (
                    <td style={{ padding: '5px 8px', textAlign: 'center', color: '#94a3b8', fontSize: '0.7rem' }}>
                      {rowIndex}
                    </td>
                  )}
                  {visibleCols.map((col) => (
                    <td key={col} style={{
                      padding: '5px 10px',
                      whiteSpace: wrapText ? 'normal' : 'nowrap',
                      maxWidth: wrapText ? undefined : 220,
                      overflow: wrapText ? undefined : 'hidden',
                      textOverflow: wrapText ? undefined : 'ellipsis',
                      wordBreak: wrapText ? 'break-word' : undefined,
                    }}>
                      {String(row[col] ?? '')}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      <div style={{
        padding: '4px 10px',
        borderTop: '1px solid #e2e8f0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: '#f8fafc',
        fontSize: '0.71rem',
        color: '#64748b',
        flexShrink: 0,
      }}>
        <span>
          Showing {filteredRows.length > 0 ? (activePage - 1) * pageSize + 1 : 0} to {Math.min(activePage * pageSize, filteredRows.length)} of {filteredRows.length} rows
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <button
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            disabled={activePage <= 1}
            style={{
              padding: '2px 4px',
              border: '1px solid #cbd5e1',
              borderRadius: 4,
              background: activePage <= 1 ? '#f1f5f9' : '#ffffff',
              color: activePage <= 1 ? '#94a3b8' : '#334155',
              cursor: activePage <= 1 ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <ChevronLeft size={13} />
          </button>
          <span style={{ fontWeight: 600, color: '#0f172a' }}>
            {activePage} / {totalPages}
          </span>
          <button
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            disabled={activePage >= totalPages}
            style={{
              padding: '2px 4px',
              border: '1px solid #cbd5e1',
              borderRadius: 4,
              background: activePage >= totalPages ? '#f1f5f9' : '#ffffff',
              color: activePage >= totalPages ? '#94a3b8' : '#334155',
              cursor: activePage >= totalPages ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <ChevronRight size={13} />
          </button>
        </div>
      </div>
    </div>
  );
}
