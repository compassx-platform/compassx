/**
 * TimeseriesExplorer – main page for browsing and inline-editing time-series data.
 *
 * Layout:
 *   [Filter Panel (left sidebar)] | [Table + pagination (main area)]
 *
 * Features:
 *   - Asset / tag / time-range filtering
 *   - Inline editable value cells (dirty-row tracking)
 *   - Batch save via POST /timeseries/batch-update
 *   - Link to Upload page
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import { Upload, RefreshCw } from "lucide-react";
import { useScopedPath } from "@/lib/appNavigation";

import FilterPanel from "@/modules/data/components/timeseries/FilterPanel";
import TimeseriesTable from "@/modules/data/components/timeseries/TimeseriesTable";
import {
  useTimeseriesQuery,
  useTagDefinitions,
  useBatchUpdate,
  type BatchUpdateItem,
  type TimeseriesFilters,
} from "@/modules/data/hooks/useTimeseries";

const DEFAULT_FILTERS: TimeseriesFilters = {
  asset_ids: [],
  tag_def_ids: [],
  start_time: undefined,
  end_time: undefined,
  page: 1,
  size: 100,
};

export default function TimeseriesExplorer() {
  const appPath = useScopedPath();
  const [filters, setFilters] = useState<TimeseriesFilters>(DEFAULT_FILTERS);
  const [saveResult, setSaveResult] = useState<string | null>(null);

  const { data, isLoading, isFetching, refetch } = useTimeseriesQuery(filters);
  const { data: tags = [] } = useTagDefinitions();
  const batchUpdate = useBatchUpdate();

  const handleSave = async (rows: BatchUpdateItem[]) => {
    setSaveResult(null);
    try {
      const result = await batchUpdate.mutateAsync({ rows });
      setSaveResult(
        `✓ Saved: ${result.updated} updated, ${result.inserted} inserted`
      );
      setTimeout(() => setSaveResult(null), 4000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Save failed";
      setSaveResult(`✗ ${msg}`);
    }
  };

  const handleReset = () => setFilters(DEFAULT_FILTERS);

  return (
    <div className="animate-fade-in" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 style={{ fontSize: "1.75rem", fontWeight: 600, marginBottom: "0.25rem" }}>
            Time-Series Explorer
          </h1>
          <p style={{ color: "var(--color-text-muted)", fontSize: 14 }}>
            Browse, filter and inline-edit time-series values. Click any value cell to edit.
          </p>
        </div>
        <div style={{ display: "flex", gap: 10, flexShrink: 0 }}>
          <button
            className="btn-secondary"
            onClick={() => refetch()}
            disabled={isFetching}
            style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}
          >
            <RefreshCw size={14} className={isFetching ? "animate-spin" : ""} />
            Refresh
          </button>
          <Link to={appPath("/timeseries/upload")}>
            <button
              className="btn-primary"
              style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}
            >
              <Upload size={14} />
              Upload Data
            </button>
          </Link>
        </div>
      </div>

      {/* Save result toast */}
      {saveResult && (
        <div
          style={{
            padding: "0.6rem 1rem",
            borderRadius: "var(--radius, 8px)",
            background: saveResult.startsWith("✓")
              ? "rgba(34,197,94,0.12)"
              : "rgba(239,68,68,0.12)",
            border: `1px solid ${saveResult.startsWith("✓") ? "rgba(34,197,94,0.35)" : "rgba(239,68,68,0.35)"}`,
            color: saveResult.startsWith("✓") ? "#4ade80" : "#f87171",
            fontSize: 14,
          }}
        >
          {saveResult}
        </div>
      )}

      {/* Main layout */}
      <div style={{ display: "flex", gap: "1.5rem", alignItems: "flex-start" }}>
        {/* Filter sidebar */}
        <div style={{ width: 240, flexShrink: 0 }}>
          <FilterPanel
            filters={filters}
            tags={tags}
            onChange={setFilters}
            onReset={handleReset}
          />
        </div>

        {/* Table area */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <TimeseriesTable
            rows={data?.items ?? []}
            total={data?.total ?? 0}
            page={data?.page ?? 1}
            pages={data?.pages ?? 0}
            size={filters.size ?? 100}
            isLoading={isLoading || isFetching}
            isSaving={batchUpdate.isPending}
            onPageChange={(p) => setFilters((f) => ({ ...f, page: p }))}
            onSave={handleSave}
          />
        </div>
      </div>
    </div>
  );
}
