/**
 * TimeseriesTable – TanStack Table with inline editing and dirty-row tracking.
 *
 * Fixes:
 *  - Row sync moved to useEffect (was calling setState during render → rows never appeared)
 *
 * Features:
 *  - All four columns editable inline (ts, asset_name, tag_name, value)
 *  - Yellow highlight for dirty rows
 *  - "Unsaved changes" banner with Save / Discard buttons
 *  - Pagination controls
 *  - Virtualized rows via @tanstack/react-virtual
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Save, RotateCcw, Loader2 } from "lucide-react";

import type { TimeseriesRow, BatchUpdateItem } from "@/modules/data/hooks/useTimeseries";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TableRow extends TimeseriesRow {
  original_value: number | null;
  original_ts: string;
  original_asset_name: string;
  original_tag_name: string;
  isDirty: boolean;
}

interface TimeseriesTableProps {
  rows: TimeseriesRow[];
  total: number;
  page: number;
  pages: number;
  size: number;
  isLoading: boolean;
  isSaving: boolean;
  onPageChange: (page: number) => void;
  onSave: (rows: BatchUpdateItem[]) => void;
}

// ---------------------------------------------------------------------------
// Inline text cell
// ---------------------------------------------------------------------------

interface InlineTextCellProps {
  value: string;
  isDirty?: boolean;
  onCommit: (v: string) => void;
  type?: "text" | "number" | "datetime-local";
}

function InlineTextCell({ value, isDirty, onCommit, type = "text" }: InlineTextCellProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  // Keep draft in sync when external value changes (e.g. discard)
  useEffect(() => {
    if (!editing) setDraft(value);
  }, [value, editing]);

  const commit = () => {
    setEditing(false);
    if (draft !== value) onCommit(draft);
  };

  if (!editing) {
    return (
      <div
        onClick={() => { setDraft(value); setEditing(true); }}
        style={{
          cursor: "pointer",
          padding: "2px 6px",
          borderRadius: 4,
          border: "1px solid transparent",
          color: isDirty ? "#facc15" : "inherit",
          fontWeight: isDirty ? 600 : "inherit",
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
          minWidth: 60,
        }}
        title="Click to edit"
      >
        {value || <span style={{ color: "var(--color-text-muted)", fontStyle: "italic" }}>—</span>}
      </div>
    );
  }

  return (
    <input
      ref={inputRef}
      type={type}
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") commit();
        if (e.key === "Escape") { setEditing(false); setDraft(value); }
      }}
      style={{
        width: "100%",
        background: "rgba(99,102,241,0.12)",
        border: "1px solid var(--color-primary, #6366f1)",
        borderRadius: 4,
        color: "inherit",
        fontSize: "inherit",
        padding: "2px 6px",
        outline: "none",
      }}
    />
  );
}

// Numeric cell variant
interface InlineNumericCellProps {
  value: number | null;
  isDirty?: boolean;
  onCommit: (v: number) => void;
}

function InlineNumericCell({ value, isDirty, onCommit }: InlineNumericCellProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(String(value ?? ""));
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.select();
  }, [editing]);

  useEffect(() => {
    if (!editing) setDraft(String(value ?? ""));
  }, [value, editing]);

  const commit = () => {
    setEditing(false);
    const n = parseFloat(draft);
    if (!isNaN(n) && n !== value) onCommit(n);
  };

  if (!editing) {
    return (
      <div
        onClick={() => { setDraft(String(value ?? "")); setEditing(true); }}
        style={{
          cursor: "pointer",
          padding: "2px 6px",
          borderRadius: 4,
          border: "1px solid transparent",
          color: isDirty ? "#facc15" : "inherit",
          fontWeight: isDirty ? 600 : "inherit",
          textAlign: "right",
        }}
        title="Click to edit"
      >
        {value != null ? value.toLocaleString() : "—"}
      </div>
    );
  }

  return (
    <input
      ref={inputRef}
      type="number"
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") commit();
        if (e.key === "Escape") { setEditing(false); setDraft(String(value ?? "")); }
      }}
      style={{
        width: "100%",
        background: "rgba(99,102,241,0.12)",
        border: "1px solid var(--color-primary, #6366f1)",
        borderRadius: 4,
        color: "inherit",
        fontSize: "inherit",
        padding: "2px 6px",
        outline: "none",
        textAlign: "right",
      }}
    />
  );
}

// ---------------------------------------------------------------------------
// Column helper
// ---------------------------------------------------------------------------

const col = createColumnHelper<TableRow>();

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function TimeseriesTable({
  rows: rawRows,
  total,
  page,
  pages,
  size,
  isLoading,
  isSaving,
  onPageChange,
  onSave,
}: TimeseriesTableProps) {
  // ── State ─────────────────────────────────────────────────────────────────
  const [tableRows, setTableRows] = useState<TableRow[]>([]);

  // Sync server data → local state via useEffect (NOT during render)
  useEffect(() => {
    setTableRows(
      rawRows.map((r) => ({
        ...r,
        original_value: r.value,
        original_ts: r.ts,
        original_asset_name: r.asset_name,
        original_tag_name: r.tag_name,
        isDirty: false,
      }))
    );
  }, [rawRows]);

  const dirtyRows = useMemo(() => tableRows.filter((r) => r.isDirty), [tableRows]);

  // ── Mutation helpers ──────────────────────────────────────────────────────

  const commitField = useCallback(
    (rowIndex: number, field: keyof TableRow, newVal: unknown) => {
      setTableRows((prev) =>
        prev.map((r, i) => {
          if (i !== rowIndex) return r;
          const updated = { ...r, [field]: newVal };
          const dirty =
            updated.value !== updated.original_value ||
            updated.ts !== updated.original_ts ||
            updated.asset_name !== updated.original_asset_name ||
            updated.tag_name !== updated.original_tag_name;
          return { ...updated, isDirty: dirty };
        })
      );
    },
    []
  );

  const handleDiscard = () => {
    setTableRows((prev) =>
      prev.map((r) => ({
        ...r,
        ts: r.original_ts,
        asset_name: r.original_asset_name,
        tag_name: r.original_tag_name,
        value: r.original_value,
        isDirty: false,
      }))
    );
  };

  const handleSave = () => {
    const payload: BatchUpdateItem[] = dirtyRows.map((r) => ({
      ts: r.ts,
      asset_id: r.asset_id,
      tag_def_id: r.tag_def_id,
      value: r.value as number,
    }));
    onSave(payload);
  };

  // ── Columns ───────────────────────────────────────────────────────────────

  const columns = useMemo(
    () => [
      col.accessor("ts", {
        header: "Timestamp",
        size: 200,
        cell: (info) => {
          const rowIndex = info.row.index;
          const row = tableRows[rowIndex];
          if (!row) return null;
          // Display as local datetime string; edit as text
          const display = (() => {
            try { return new Date(row.ts).toLocaleString(); } catch { return row.ts; }
          })();
          return (
            <InlineTextCell
              value={display}
              isDirty={row.ts !== row.original_ts}
              onCommit={(v) => commitField(rowIndex, "ts", v)}
            />
          );
        },
      }),
      col.accessor("asset_name", {
        header: "Asset",
        size: 160,
        cell: (info) => {
          const rowIndex = info.row.index;
          const row = tableRows[rowIndex];
          if (!row) return null;
          return (
            <InlineTextCell
              value={row.asset_name}
              isDirty={row.asset_name !== row.original_asset_name}
              onCommit={(v) => commitField(rowIndex, "asset_name", v)}
            />
          );
        },
      }),
      col.accessor("tag_name", {
        header: "Tag",
        size: 140,
        cell: (info) => {
          const rowIndex = info.row.index;
          const row = tableRows[rowIndex];
          if (!row) return null;
          return (
            <InlineTextCell
              value={row.tag_name}
              isDirty={row.tag_name !== row.original_tag_name}
              onCommit={(v) => commitField(rowIndex, "tag_name", v)}
            />
          );
        },
      }),
      col.accessor("value", {
        header: "Value",
        size: 130,
        cell: (info) => {
          const rowIndex = info.row.index;
          const row = tableRows[rowIndex];
          if (!row) return null;
          return (
            <InlineNumericCell
              value={row.value}
              isDirty={row.value !== row.original_value}
              onCommit={(v) => commitField(rowIndex, "value", v)}
            />
          );
        },
      }),
      col.display({
        id: "dirty_indicator",
        size: 28,
        cell: (info) => {
          const row = tableRows[info.row.index];
          return row?.isDirty ? (
            <span title="Unsaved" style={{ color: "#facc15", fontSize: 14 }}>●</span>
          ) : null;
        },
      }),
    ],
    [tableRows, commitField]
  );

  // ── Table instance ────────────────────────────────────────────────────────

  const table = useReactTable({
    data: tableRows,
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    pageCount: pages,
  });

  // ── Virtualizer ───────────────────────────────────────────────────────────

  const parentRef = useRef<HTMLDivElement>(null);
  const { rows } = table.getRowModel();

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 40,
    overscan: 10,
  });

  const virtualItems = virtualizer.getVirtualItems();
  const totalVirtualSize = virtualizer.getTotalSize();

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {/* Dirty banner */}
      {dirtyRows.length > 0 && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "0.6rem 1rem",
            background: "rgba(234,179,8,0.12)",
            border: "1px solid rgba(234,179,8,0.35)",
            borderRadius: "var(--radius, 8px)",
            fontSize: 14,
          }}
        >
          <span style={{ color: "#facc15", flex: 1 }}>
            {dirtyRows.length} unsaved change{dirtyRows.length > 1 ? "s" : ""}
          </span>
          <button
            className="btn-secondary"
            onClick={handleDiscard}
            disabled={isSaving}
            style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}
          >
            <RotateCcw size={14} /> Discard
          </button>
          <button
            className="btn-primary"
            onClick={handleSave}
            disabled={isSaving}
            style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}
          >
            {isSaving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            Save Changes
          </button>
        </div>
      )}

      {/* Table */}
      <div
        className="glass"
        style={{ borderRadius: "var(--radius, 8px)", overflow: "hidden" }}
      >
        {/* Fixed header */}
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
            <thead>
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id} style={{ borderBottom: "1px solid var(--color-border)" }}>
                  {hg.headers.map((header) => (
                    <th
                      key={header.id}
                      style={{
                        width: header.getSize(),
                        padding: "10px 12px",
                        textAlign: "left",
                        fontSize: 12,
                        fontWeight: 600,
                        color: "var(--color-text-muted)",
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        background: "rgba(255,255,255,0.03)",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {flexRender(header.column.columnDef.header, header.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
          </table>
        </div>

        {/* Scrollable body */}
        <div
          ref={parentRef}
          style={{ height: 480, overflowY: "auto", overflowX: "auto" }}
        >
          {isLoading ? (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                height: "100%",
                color: "var(--color-text-muted)",
                gap: 8,
              }}
            >
              <Loader2 size={20} className="animate-spin" /> Loading…
            </div>
          ) : tableRows.length === 0 ? (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                height: "100%",
                color: "var(--color-text-muted)",
                fontSize: 14,
              }}
            >
              No data found. Adjust filters or upload data.
            </div>
          ) : (
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                tableLayout: "fixed",
              }}
            >
              <tbody
                style={{
                  height: totalVirtualSize,
                  display: "block",
                  position: "relative",
                }}
              >
                {virtualItems.map((vRow) => {
                  const row = rows[vRow.index];
                  const tRow = tableRows[vRow.index];
                  return (
                    <tr
                      key={row.id}
                      data-index={vRow.index}
                      ref={virtualizer.measureElement}
                      style={{
                        position: "absolute",
                        top: 0,
                        left: 0,
                        width: "100%",
                        transform: `translateY(${vRow.start}px)`,
                        display: "table",
                        tableLayout: "fixed",
                        borderBottom: "1px solid var(--color-border)",
                        background: tRow?.isDirty
                          ? "rgba(234,179,8,0.05)"
                          : "transparent",
                        transition: "background 0.15s",
                      }}
                    >
                      {row.getVisibleCells().map((cell) => (
                        <td
                          key={cell.id}
                          style={{
                            width: cell.column.getSize(),
                            padding: "4px 6px",
                            fontSize: 13,
                            verticalAlign: "middle",
                            overflow: "hidden",
                          }}
                        >
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Pagination */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          fontSize: 13,
          color: "var(--color-text-muted)",
        }}
      >
        <span>
          {total.toLocaleString()} total rows · Page {page} of {pages || 1}
        </span>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            className="btn-secondary"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            style={{ padding: "4px 12px", fontSize: 13 }}
          >
            ← Prev
          </button>
          <button
            className="btn-secondary"
            disabled={page >= pages}
            onClick={() => onPageChange(page + 1)}
            style={{ padding: "4px 12px", fontSize: 13 }}
          >
            Next →
          </button>
        </div>
      </div>
    </div>
  );
}
