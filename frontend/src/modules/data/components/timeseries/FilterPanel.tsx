/**
 * FilterPanel – asset hierarchy + time range + tag selector for time-series explorer.
 *
 * Uses the existing proxy endpoints for asset data (same pattern as BreakdownExplorer).
 */

import { useEffect, useState } from "react";
import { Filter, X } from "lucide-react";
import api from "@/lib/api";
import type { TagDefinition, TimeseriesFilters } from "@/modules/data/hooks/useTimeseries";

interface Asset {
  id: number;
  name: string;
}

interface FilterPanelProps {
  filters: TimeseriesFilters;
  tags: TagDefinition[];
  onChange: (filters: TimeseriesFilters) => void;
  onReset: () => void;
}

export default function FilterPanel({ filters, tags, onChange, onReset }: FilterPanelProps) {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loadingAssets, setLoadingAssets] = useState(false);

  // Load top-level assets via proxy
  useEffect(() => {
    setLoadingAssets(true);
    api
      .get<{ items?: Asset[]; data?: Asset[] } | Asset[]>("/proxy/assets")
      .then((res) => {
        const body = res.data;
        const list: Asset[] = Array.isArray(body)
          ? body
          : (body as { items?: Asset[] }).items ?? (body as { data?: Asset[] }).data ?? [];
        setAssets(list);
      })
      .catch(() => setAssets([]))
      .finally(() => setLoadingAssets(false));
  }, []);

  const toggleAsset = (id: number) => {
    const current = filters.asset_ids ?? [];
    const next = current.includes(id) ? current.filter((x) => x !== id) : [...current, id];
    onChange({ ...filters, asset_ids: next, page: 1 });
  };

  const toggleTag = (id: number) => {
    const current = filters.tag_def_ids ?? [];
    const next = current.includes(id) ? current.filter((x) => x !== id) : [...current, id];
    onChange({ ...filters, tag_def_ids: next, page: 1 });
  };

  const setStartTime = (v: string) =>
    onChange({ ...filters, start_time: v || undefined, page: 1 });

  const setEndTime = (v: string) =>
    onChange({ ...filters, end_time: v || undefined, page: 1 });

  const hasFilters =
    (filters.asset_ids?.length ?? 0) > 0 ||
    (filters.tag_def_ids?.length ?? 0) > 0 ||
    !!filters.start_time ||
    !!filters.end_time;

  return (
    <div
      className="glass"
      style={{
        padding: "1.25rem",
        borderRadius: "var(--radius, 8px)",
        display: "flex",
        flexDirection: "column",
        gap: "1.25rem",
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 600, fontSize: 14 }}>
          <Filter size={15} />
          Filters
        </div>
        {hasFilters && (
          <button
            onClick={onReset}
            style={{
              background: "transparent",
              border: "none",
              color: "var(--color-text-muted)",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 4,
              fontSize: 12,
            }}
          >
            <X size={13} /> Clear all
          </button>
        )}
      </div>

      {/* Time range */}
      <div>
        <div style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-muted)", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>
          Time Range
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div>
            <label style={{ fontSize: 11, color: "var(--color-text-muted)" }}>From</label>
            <input
              type="datetime-local"
              className="input-field"
              value={filters.start_time ? filters.start_time.slice(0, 16) : ""}
              onChange={(e) => setStartTime(e.target.value ? new Date(e.target.value).toISOString() : "")}
              style={{ width: "100%", marginTop: 2, fontSize: 12 }}
            />
          </div>
          <div>
            <label style={{ fontSize: 11, color: "var(--color-text-muted)" }}>To</label>
            <input
              type="datetime-local"
              className="input-field"
              value={filters.end_time ? filters.end_time.slice(0, 16) : ""}
              onChange={(e) => setEndTime(e.target.value ? new Date(e.target.value).toISOString() : "")}
              style={{ width: "100%", marginTop: 2, fontSize: 12 }}
            />
          </div>
        </div>
      </div>

      {/* Assets */}
      <div>
        <div style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-muted)", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>
          Assets {loadingAssets && <span style={{ opacity: 0.5 }}>(loading…)</span>}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4, maxHeight: 200, overflowY: "auto" }}>
          {assets.length === 0 && !loadingAssets && (
            <span style={{ fontSize: 12, color: "var(--color-text-muted)" }}>No assets available</span>
          )}
          {assets.map((asset) => {
            const selected = (filters.asset_ids ?? []).includes(asset.id);
            return (
              <label
                key={asset.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  cursor: "pointer",
                  fontSize: 13,
                  padding: "3px 0",
                  color: selected ? "var(--color-primary)" : "inherit",
                }}
              >
                <input
                  type="checkbox"
                  checked={selected}
                  onChange={() => toggleAsset(asset.id)}
                  style={{ accentColor: "var(--color-primary)" }}
                />
                {asset.name}
              </label>
            );
          })}
        </div>
      </div>

      {/* Tags */}
      <div>
        <div style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-muted)", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>
          Metrics / Tags
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4, maxHeight: 200, overflowY: "auto" }}>
          {tags.length === 0 && (
            <span style={{ fontSize: 12, color: "var(--color-text-muted)" }}>No tags available</span>
          )}
          {tags.map((tag) => {
            const selected = (filters.tag_def_ids ?? []).includes(tag.id);
            return (
              <label
                key={tag.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  cursor: "pointer",
                  fontSize: 13,
                  padding: "3px 0",
                  color: selected ? "var(--color-primary)" : "inherit",
                }}
              >
                <input
                  type="checkbox"
                  checked={selected}
                  onChange={() => toggleTag(tag.id)}
                  style={{ accentColor: "var(--color-primary)" }}
                />
                {tag.name}
              </label>
            );
          })}
        </div>
      </div>

      {/* Page size */}
      <div>
        <div style={{ fontSize: 12, fontWeight: 600, color: "var(--color-text-muted)", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>
          Rows per page
        </div>
        <select
          className="input-field"
          value={filters.size ?? 100}
          onChange={(e) => onChange({ ...filters, size: Number(e.target.value), page: 1 })}
          style={{ width: "100%", fontSize: 13 }}
        >
          {[50, 100, 200, 500].map((n) => (
            <option key={n} value={n}>{n}</option>
          ))}
        </select>
      </div>
    </div>
  );
}
