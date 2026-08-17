/**
 * TimeseriesUpload – page wrapper for the UploadWizard.
 *
 * Provides page header and navigation back to the explorer.
 */

import { useScopedNavigate } from "@/lib/appNavigation";
import { ArrowLeft } from "lucide-react";
import UploadWizard from "@/modules/data/components/timeseries/UploadWizard";

export default function TimeseriesUpload() {
  const navigate = useScopedNavigate();

  return (
    <div className="animate-fade-in" style={{ maxWidth: 860, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: "2rem" }}>
        <button
          onClick={() => navigate("/timeseries")}
          style={{
            background: "transparent",
            border: "1px solid var(--color-border)",
            color: "var(--color-text-muted)",
            borderRadius: "var(--radius, 8px)",
            padding: "6px 10px",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 4,
            fontSize: 13,
          }}
        >
          <ArrowLeft size={14} /> Back
        </button>
        <div>
          <h1 style={{ fontSize: "1.75rem", fontWeight: 600, marginBottom: "0.15rem" }}>
            Upload Time-Series Data
          </h1>
          <p style={{ color: "var(--color-text-muted)", fontSize: 14 }}>
            Upload a CSV or Excel file to import new or updated time-series values.
          </p>
        </div>
      </div>

      {/* Format guide */}
      <div
        className="glass"
        style={{
          padding: "1rem 1.25rem",
          borderRadius: "var(--radius, 8px)",
          marginBottom: "1.5rem",
          fontSize: 13,
          color: "var(--color-text-muted)",
        }}
      >
        <strong style={{ color: "inherit", marginRight: 8 }}>Expected columns</strong>
        (flexible names, case-insensitive):
        <span style={{ marginLeft: 8 }}>
          <code>ts</code> / <code>timestamp</code> · <code>asset</code> / <code>asset_name</code>{" "}
          · <code>tag</code> / <code>tag_name</code> · <code>value</code>
        </span>
      </div>

      {/* Wizard */}
      <UploadWizard onComplete={() => navigate("/timeseries")} />
    </div>
  );
}
