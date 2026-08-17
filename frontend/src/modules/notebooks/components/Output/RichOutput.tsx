import { useState, useMemo } from 'react';
import JsonOutput from './JsonOutput';
import LatexOutput from './LatexOutput';
import DataFrameViewer from './DataFrameViewer';
import { Table } from 'lucide-react';

interface Props {
  data: Record<string, any>;
}

/**
 * Helper to parse a simple HTML table into rows and columns.
 */
/**
 * Robustly parses an HTML table into headers and rows using a 2D grid mapping.
 * Handles colspan, rowspan, and multi-row headers correctly.
 */
function parseHtmlTable(html: string) {
  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    const table = doc.querySelector('table');
    if (!table) return null;

    const rows = Array.from(table.rows);
    if (rows.length === 0) return null;

    // 1. Build a virtual 2D grid to account for merged cells (colspan/rowspan)
    const grid: string[][] = [];
    rows.forEach((tr, r) => {
      const cells = Array.from(tr.cells);
      cells.forEach(cell => {
        const rs = cell.rowSpan || 1;
        const cs = cell.colSpan || 1;
        const content = cell.textContent?.trim() || '';

        // Find the first empty column in this grid row
        if (!grid[r]) grid[r] = [];
        let c = 0;
        while (grid[r][c] !== undefined) c++;

        // Fill all occupied slots in the virtual grid
        for (let dr = 0; dr < rs; dr++) {
          const targetR = r + dr;
          if (!grid[targetR]) grid[targetR] = [];
          for (let dc = 0; dc < cs; dc++) {
            const targetC = c + dc;
            grid[targetR][targetC] = content;
          }
        }
      });
    });

    // 2. Identify header rows vs data rows using thead or <th> heuristic
    const theadRowsCount = table.tHead?.rows.length || 0;
    let headerRowsIdx = 0;

    if (theadRowsCount > 0) {
      headerRowsIdx = theadRowsCount;
    } else {
      for (let i = 0; i < rows.length; i++) {
        const rowCells = Array.from(rows[i].cells);
        if (rowCells.length > 0 && rowCells.every(c => c.tagName === 'TH')) {
          headerRowsIdx = i + 1;
        } else {
          break;
        }
      }
      if (headerRowsIdx === 0) headerRowsIdx = 1;
    }

    // 3. Construct Headers: Combine multi-row headers and sanitize empty ones
    const columnsCount = grid[0]?.length || 0;
    const finalHeaders: string[] = [];

    for (let c = 0; c < columnsCount; c++) {
      const labelParts: string[] = [];
      for (let r = 0; r < headerRowsIdx; r++) {
        const val = grid[r][c];
        if (val && !labelParts.includes(val)) labelParts.push(val);
      }
      let headerName = labelParts.join(' ').trim();
      if (!headerName) {
        // Fallback for empty headers (often indices in pandas)
        headerName = c === 0 ? 'index' : `col_${c}`;
      }
      // Ensure unique headers
      let uniqueName = headerName;
      let counter = 1;
      while (finalHeaders.includes(uniqueName)) {
        uniqueName = `${headerName}_${counter++}`;
      }
      finalHeaders.push(uniqueName);
    }

    // 4. Construct Data Objects
    const data: any[] = [];
    for (let r = headerRowsIdx; r < grid.length; r++) {
      const rowObj: any = {};
      for (let c = 0; c < columnsCount; c++) {
        rowObj[finalHeaders[c]] = grid[r][c] || '';
      }
      data.push(rowObj);
    }

    return { headers: finalHeaders, rows: data };
  } catch (err) {
    console.error('Failed to parse table', err);
    return null;
  }
}

export default function RichOutput({ data }: Props) {
  const [showTableView, setShowTableView] = useState(false);

  // 1. Prioritize structured dataresource+json if available
  const dataResource = data['application/vnd.dataresource+json'];
  if (dataResource) {
    const parsed = typeof dataResource === 'string' ? JSON.parse(dataResource) : dataResource;
    if (parsed.data && parsed.schema?.fields) {
      const cols = parsed.schema.fields.map((f: any) => f.name);
      return <DataFrameViewer data={parsed.data} columns={cols} />;
    }
  }

  // 2. Check for standard application/json that looks like a dataset
  if (data['application/json']) {
    const jsonData = typeof data['application/json'] === 'string' ? JSON.parse(data['application/json']) : data['application/json'];
    if (Array.isArray(jsonData) && jsonData.length > 0 && typeof jsonData[0] === 'object') {
      const cols = Object.keys(jsonData[0]);
      return <DataFrameViewer data={jsonData} columns={cols} />;
    }
  }

  // 3. Handle Images
  if (data['image/png']) {
    return <img src={`data:image/png;base64,${data['image/png']}`} alt="output" className="notebook-output-img" />;
  }
  if (data['image/jpeg']) {
    return <img src={`data:image/jpeg;base64,${data['image/jpeg']}`} alt="output" className="notebook-output-img" />;
  }
  if (data['image/svg+xml']) {
    return <div className="notebook-output-svg" dangerouslySetInnerHTML={{ __html: data['image/svg+xml'] }} />;
  }

  // 4. Handle HTML with potential Table View toggle
  if (data['text/html']) {
    const html = data['text/html'];
    const hasTable = html.includes('<table');
    
    if (hasTable && showTableView) {
      const parsed = parseHtmlTable(html);
      if (parsed && parsed.rows.length > 0) {
        return (
          <div className="notebook-rich-output-wrapper">
            <div className="notebook-view-toggle">
              <button className="notebook-toolbar-btn" onClick={() => setShowTableView(false)}>View HTML</button>
            </div>
            <DataFrameViewer data={parsed.rows} columns={parsed.headers} />
          </div>
        );
      }
    }

    return (
      <div className="notebook-rich-output-wrapper">
        {hasTable && (
          <div className="notebook-view-toggle">
            <button className="notebook-toolbar-btn" onClick={() => setShowTableView(true)}>
              <Table size={14} /> View as Interactive Table
            </button>
          </div>
        )}
        <iframe
          className="notebook-output-html"
          sandbox="allow-scripts"
          srcDoc={html}
          title="rich output"
        />
      </div>
    );
  }

  // 5. Fallbacks
  if (data['text/latex']) {
    return <LatexOutput latex={data['text/latex']} />;
  }
  if (data['text/plain']) {
    return <pre className="notebook-output-text">{data['text/plain']}</pre>;
  }

  // Last resort: JSON view for any other application/json
  if (data['application/json']) {
    return <JsonOutput data={JSON.stringify(data['application/json'], null, 2)} />;
  }

  return null;
}
