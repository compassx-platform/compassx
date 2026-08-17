/**
 * UploadWizard – 4-step upload flow component.
 *
 * Steps:
 *   1. File Upload   – drag & drop CSV/Excel
 *   2. Validate      – trigger validation, show counts
 *   3. Diff Preview  – tabbed preview of new/updated/invalid rows
 *   4. Apply         – confirm and apply to raw_data
 */

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import {
  Upload,
  CheckCircle2,
  AlertCircle,
  Loader2,
  FileSpreadsheet,
  ChevronRight,
  RotateCcw,
} from "lucide-react";

import DiffPreview from "./DiffPreview";
import {
  useUploadFile,
  useValidateBatch,
  useDiff,
  useApplyBatch,
  type ValidateResponse,
} from "@/modules/data/hooks/useTimeseries";

// ---------------------------------------------------------------------------
// Step indicator
// ---------------------------------------------------------------------------

const STEPS = ["Upload File", "Validate", "Preview Diff", "Apply"];

function StepIndicator({ current }: { current: number }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 0, marginBottom: "2rem" }}>
      {STEPS.map((label, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", flex: i < STEPS.length - 1 ? 1 : undefined }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 13,
                  fontWeight: 600,
                  background: done
                    ? "var(--color-success, #4ade80)"
                    : active
                    ? "var(--color-primary, #6366f1)"
                    : "rgba(255,255,255,0.08)",
                  color: done || active ? "#fff" : "var(--color-text-muted)",
                  border: active ? "2px solid var(--color-primary, #6366f1)" : "2px solid transparent",
                  transition: "all 0.2s",
                }}
              >
                {done ? <CheckCircle2 size={16} /> : i + 1}
              </div>
              <span
                style={{
                  fontSize: 11,
                  color: active ? "var(--color-primary, #6366f1)" : done ? "var(--color-success, #4ade80)" : "var(--color-text-muted)",
                  fontWeight: active ? 600 : 400,
                  whiteSpace: "nowrap",
                }}
              >
                {label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div
                style={{
                  flex: 1,
                  height: 2,
                  background: done ? "var(--color-success, #4ade80)" : "rgba(255,255,255,0.08)",
                  margin: "0 8px",
                  marginBottom: 20,
                  transition: "background 0.2s",
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main wizard
// ---------------------------------------------------------------------------

interface UploadWizardProps {
  onComplete?: () => void;
}

export default function UploadWizard({ onComplete }: UploadWizardProps) {
  const [step, setStep] = useState(0);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [validateResult, setValidateResult] = useState<ValidateResponse | null>(null);
  const [applyResult, setApplyResult] = useState<{ applied: number; skipped: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const uploadFile = useUploadFile();
  const validateBatch = useValidateBatch();
  const { data: diff, isLoading: diffLoading } = useDiff(batchId && step >= 2 ? batchId : null);
  const applyBatch = useApplyBatch();

  // ---------------------------------------------------------------------------
  // Dropzone
  // ---------------------------------------------------------------------------

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted.length > 0) {
      setSelectedFile(accepted[0]);
      setError(null);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "text/csv": [".csv"],
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
      "application/vnd.ms-excel": [".xls"],
    },
    maxFiles: 1,
  });

  // ---------------------------------------------------------------------------
  // Step handlers
  // ---------------------------------------------------------------------------

  const handleUpload = async () => {
    if (!selectedFile) return;
    setError(null);
    try {
      const result = await uploadFile.mutateAsync(selectedFile);
      setBatchId(result.batch_id);
      setStep(1);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed");
    }
  };

  const handleValidate = async () => {
    if (!batchId) return;
    setError(null);
    try {
      const result = await validateBatch.mutateAsync({ batchId });
      setValidateResult(result);
      setStep(2);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Validation failed");
    }
  };

  const handleApply = async () => {
    if (!batchId) return;
    setError(null);
    try {
      const result = await applyBatch.mutateAsync({ batchId });
      setApplyResult(result);
      setStep(3);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Apply failed");
    }
  };

  const handleReset = () => {
    setStep(0);
    setSelectedFile(null);
    setBatchId(null);
    setValidateResult(null);
    setApplyResult(null);
    setError(null);
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <StepIndicator current={step} />

      {/* Error banner */}
      {error && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "0.75rem 1rem",
            background: "rgba(239,68,68,0.12)",
            border: "1px solid rgba(239,68,68,0.35)",
            borderRadius: "var(--radius, 8px)",
            color: "#f87171",
            fontSize: 14,
          }}
        >
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Step 0: File Upload                                                  */}
      {/* ------------------------------------------------------------------ */}
      {step === 0 && (
        <div className="glass" style={{ padding: "2rem", borderRadius: "var(--radius, 8px)" }}>
          <h3 style={{ fontWeight: 600, marginBottom: "0.5rem" }}>Upload File</h3>
          <p style={{ color: "var(--color-text-muted)", fontSize: 14, marginBottom: "1.5rem" }}>
            Upload a CSV or Excel file. Required columns:{" "}
            <code style={{ fontSize: 12 }}>ts</code>,{" "}
            <code style={{ fontSize: 12 }}>asset</code>,{" "}
            <code style={{ fontSize: 12 }}>tag</code>,{" "}
            <code style={{ fontSize: 12 }}>value</code>.
          </p>

          {/* Dropzone */}
          <div
            {...getRootProps()}
            style={{
              border: `2px dashed ${isDragActive ? "var(--color-primary, #6366f1)" : "var(--color-border)"}`,
              borderRadius: "var(--radius, 8px)",
              padding: "3rem 2rem",
              textAlign: "center",
              cursor: "pointer",
              background: isDragActive ? "rgba(99,102,241,0.08)" : "rgba(255,255,255,0.02)",
              transition: "all 0.2s",
            }}
          >
            <input {...getInputProps()} />
            <Upload
              size={40}
              style={{ margin: "0 auto 1rem", color: "var(--color-text-muted)", display: "block" }}
            />
            {isDragActive ? (
              <p style={{ color: "var(--color-primary, #6366f1)", fontWeight: 600 }}>
                Drop file here…
              </p>
            ) : (
              <>
                <p style={{ fontWeight: 500, marginBottom: 4 }}>
                  Drag & drop a CSV or Excel file here
                </p>
                <p style={{ color: "var(--color-text-muted)", fontSize: 13 }}>
                  or click to browse
                </p>
              </>
            )}
          </div>

          {/* Selected file */}
          {selectedFile && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                marginTop: "1rem",
                padding: "0.75rem 1rem",
                background: "rgba(99,102,241,0.1)",
                borderRadius: "var(--radius, 8px)",
                border: "1px solid rgba(99,102,241,0.3)",
              }}
            >
              <FileSpreadsheet size={18} style={{ color: "var(--color-primary, #6366f1)" }} />
              <span style={{ flex: 1, fontSize: 14 }}>{selectedFile.name}</span>
              <span style={{ fontSize: 12, color: "var(--color-text-muted)" }}>
                {(selectedFile.size / 1024).toFixed(1)} KB
              </span>
            </div>
          )}

          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "1.5rem" }}>
            <button
              className="btn-primary"
              onClick={handleUpload}
              disabled={!selectedFile || uploadFile.isPending}
              style={{ display: "flex", alignItems: "center", gap: 6 }}
            >
              {uploadFile.isPending ? (
                <Loader2 size={15} className="animate-spin" />
              ) : (
                <ChevronRight size={15} />
              )}
              {uploadFile.isPending ? "Uploading…" : "Upload & Continue"}
            </button>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Step 1: Validate                                                     */}
      {/* ------------------------------------------------------------------ */}
      {step === 1 && (
        <div className="glass" style={{ padding: "2rem", borderRadius: "var(--radius, 8px)" }}>
          <h3 style={{ fontWeight: 600, marginBottom: "0.5rem" }}>Validate Batch</h3>
          <p style={{ color: "var(--color-text-muted)", fontSize: 14, marginBottom: "1.5rem" }}>
            File uploaded successfully. Click Validate to resolve asset/tag references and check
            for errors.
          </p>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "0.75rem 1rem",
              background: "rgba(99,102,241,0.1)",
              borderRadius: "var(--radius, 8px)",
              border: "1px solid rgba(99,102,241,0.3)",
              marginBottom: "1.5rem",
            }}
          >
            <FileSpreadsheet size={18} style={{ color: "var(--color-primary, #6366f1)" }} />
            <span style={{ fontSize: 14 }}>{selectedFile?.name}</span>
            <span style={{ fontSize: 12, color: "var(--color-text-muted)", marginLeft: "auto" }}>
              Batch: {batchId?.slice(0, 8)}…
            </span>
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button
              className="btn-primary"
              onClick={handleValidate}
              disabled={validateBatch.isPending}
              style={{ display: "flex", alignItems: "center", gap: 6 }}
            >
              {validateBatch.isPending ? (
                <Loader2 size={15} className="animate-spin" />
              ) : (
                <CheckCircle2 size={15} />
              )}
              {validateBatch.isPending ? "Validating…" : "Validate"}
            </button>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Step 2: Diff Preview                                                 */}
      {/* ------------------------------------------------------------------ */}
      {step === 2 && (
        <div className="glass" style={{ borderRadius: "var(--radius, 8px)", overflow: "hidden" }}>
          {/* Validation summary */}
          {validateResult && (
            <div
              style={{
                display: "flex",
                gap: 24,
                padding: "1rem 1.5rem",
                borderBottom: "1px solid var(--color-border)",
                flexWrap: "wrap",
              }}
            >
              {[
                { label: "New", value: validateResult.new_count, color: "#4ade80" },
                { label: "Updated", value: validateResult.updated_count, color: "#60a5fa" },
                { label: "Duplicate", value: validateResult.duplicate_count, color: "#94a3b8" },
                { label: "Invalid", value: validateResult.invalid_count, color: "#f87171" },
              ].map(({ label, value, color }) => (
                <div key={label} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <span style={{ fontSize: 11, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    {label}
                  </span>
                  <span style={{ fontSize: 22, fontWeight: 700, color }}>{value}</span>
                </div>
              ))}
            </div>
          )}

          {/* Diff table */}
          {diffLoading ? (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "3rem",
                gap: 8,
                color: "var(--color-text-muted)",
              }}
            >
              <Loader2 size={18} className="animate-spin" /> Loading diff…
            </div>
          ) : diff ? (
            <DiffPreview diff={diff} />
          ) : null}

          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              gap: 10,
              padding: "1rem 1.5rem",
              borderTop: "1px solid var(--color-border)",
            }}
          >
            <button
              className="btn-secondary"
              onClick={handleReset}
              style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}
            >
              <RotateCcw size={14} /> Start Over
            </button>
            <button
              className="btn-primary"
              onClick={handleApply}
              disabled={
                applyBatch.isPending ||
                (validateResult?.new_count === 0 && validateResult?.updated_count === 0)
              }
              style={{ display: "flex", alignItems: "center", gap: 6 }}
            >
              {applyBatch.isPending ? (
                <Loader2 size={15} className="animate-spin" />
              ) : (
                <CheckCircle2 size={15} />
              )}
              {applyBatch.isPending
                ? "Applying…"
                : `Apply ${(validateResult?.new_count ?? 0) + (validateResult?.updated_count ?? 0)} rows`}
            </button>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Step 3: Done                                                         */}
      {/* ------------------------------------------------------------------ */}
      {step === 3 && applyResult && (
        <div
          className="glass"
          style={{
            padding: "3rem 2rem",
            borderRadius: "var(--radius, 8px)",
            textAlign: "center",
          }}
        >
          <CheckCircle2
            size={56}
            style={{ color: "#4ade80", margin: "0 auto 1rem", display: "block" }}
          />
          <h3 style={{ fontWeight: 600, fontSize: "1.25rem", marginBottom: "0.5rem" }}>
            Upload Complete
          </h3>
          <p style={{ color: "var(--color-text-muted)", fontSize: 14, marginBottom: "2rem" }}>
            {applyResult.applied} row{applyResult.applied !== 1 ? "s" : ""} applied to raw_data.
            {applyResult.skipped > 0 && ` ${applyResult.skipped} skipped.`}
          </p>
          <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
            <button
              className="btn-secondary"
              onClick={handleReset}
              style={{ display: "flex", alignItems: "center", gap: 6 }}
            >
              <Upload size={14} /> Upload Another File
            </button>
            {onComplete && (
              <button
                className="btn-primary"
                onClick={onComplete}
                style={{ display: "flex", alignItems: "center", gap: 6 }}
              >
                View in Explorer
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
