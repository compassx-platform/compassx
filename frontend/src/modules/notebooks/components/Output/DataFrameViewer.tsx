import React, { useState, useMemo } from 'react';
import { 
  ChevronDown, 
  Plus, 
  Search, 
  Filter, 
  Settings, 
  Columns, 
  RefreshCw,
  Hash,
  Type,
  Calendar,
  CheckSquare
} from 'lucide-react';

interface DataFrameViewerProps {
  data: any[];
  columns: string[];
  indexName?: string;
  runtime?: string;
  onRefresh?: () => void;
}

/**
 * DataFrameViewer – A premium interactive table for pandas DataFrames.
 * Matches the design in the provided image.
 */
export default function DataFrameViewer({ 
  data = [], 
  columns = [], 
  indexName = 'ts', 
  runtime = '5.13s',
  onRefresh 
}: DataFrameViewerProps) {
  const [searchTerm, setSearchTerm] = useState('');

  const filteredData = useMemo(() => {
    if (!searchTerm) return data;
    return data.filter(row => 
      Object.values(row).some(val => 
        String(val).toLowerCase().includes(searchTerm.toLowerCase())
      )
    );
  }, [data, searchTerm]);

  // Map column names to icons (mocking type detection)
  const getHeaderIcon = (col: string) => {
    if (col === 'ts' || col.toLowerCase().includes('date') || col.toLowerCase().includes('time')) {
      return <Calendar size={14} className="df-header-icon" />;
    }
    const firstVal = data[0]?.[col];
    if (typeof firstVal === 'number') {
      return <Hash size={14} className="df-header-icon" />;
    }
    if (typeof firstVal === 'boolean') {
      return <CheckSquare size={14} className="df-header-icon" />;
    }
    return <Type size={14} className="df-header-icon" />;
  };

  return (
    <div className="df-viewer glass">
      {/* ── Toolbar ── */}
      <div className="df-toolbar">
        <div className="df-toolbar-left">
          <button className="df-toolbar-btn df-table-selector">
            <span>Table</span>
            <ChevronDown size={14} />
          </button>
          <button className="df-toolbar-btn df-plus-btn">
            <Plus size={16} />
          </button>
        </div>
        <div className="df-toolbar-right">
          <div className="df-search-wrapper">
            <Search size={14} className="df-search-icon" />
            <input 
              type="text" 
              placeholder="Search..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="df-search-input"
            />
          </div>
          <button className="df-toolbar-icon-btn" title="Filter"><Filter size={16} /></button>
          <button className="df-toolbar-icon-btn" title="Columns"><Columns size={16} /></button>
          <button className="df-toolbar-icon-btn" title="Settings"><Settings size={16} /></button>
        </div>
      </div>

      {/* ── Table Grid ── */}
      <div className="df-table-container">
        <table className="df-table">
          <thead>
            <tr>
              <th className="df-index-header"></th>
              {columns.map(col => (
                <th key={col} className="df-col-header">
                  <div className="df-header-content">
                    {getHeaderIcon(col)}
                    <span className="df-header-text">{col}</span>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredData.map((row, idx) => (
              <tr key={idx} className="df-row">
                <td className="df-index-cell">{idx + 1}</td>
                {columns.map(col => (
                  <td key={col} className="df-cell">
                    {String(row[col] ?? '')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Footer ── */}
      <div className="df-footer">
        <div className="df-footer-left">
          <span className="df-status-item">{data.length} rows</span>
          <span className="df-status-divider">|</span>
          <span className="df-status-item">{runtime} runtime</span>
        </div>
        <div className="df-footer-right">
          <span className="df-refresh-status">Refreshed now</span>
          {onRefresh && (
            <button className="df-refresh-btn" onClick={onRefresh}>
              <RefreshCw size={12} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
