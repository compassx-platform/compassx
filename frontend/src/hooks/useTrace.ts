/** React Query hooks and types for Run Tracing */

import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface RunTrace {
  run_id: string;
  job_id: string;
  correlation_id?: string;
  status: string;
  started_at: string;
  ended_at?: string;
  duration_ms?: number;
  metric_count?: number;
  stage_count?: number;
  error_message?: string;
}

export interface RunTraceStep {
  step_id: string;
  run_id: string;
  step_name: string;
  step_type: string;
  step_order: number;
  parent_step_id?: string;
  status: string;
  started_at: string;
  ended_at?: string;
  duration_ms?: number;
  step_metadata?: Record<string, unknown>;
  error_message?: string;
}

export interface RunTraceDetail extends RunTrace {
  scope_summary?: Record<string, unknown>;
  graph_summary?: unknown;
  steps: RunTraceStep[];
}

export interface RunTraceStepDataSample {
  sample_id: string;
  step_id: string;
  dataset_name: string;
  row_count: number;
  column_count: number;
  columns?: Array<{ name: string; dtype: string }>;
  sample_data?: Record<string, unknown>[];
  stats?: Record<string, { mean?: number; min?: number; max?: number; std?: number }>;
}

export interface StepTreeNode extends RunTraceStep {
  children: StepTreeNode[];
}

// ── Utility: build step tree from flat list ───────────────────────────────────

export function buildStepTree(steps: RunTraceStep[]): StepTreeNode[] {
  const map: Record<string, StepTreeNode> = {};
  for (const s of steps) {
    map[s.step_id] = { ...s, children: [] };
  }
  const roots: StepTreeNode[] = [];
  for (const s of steps) {
    if (s.parent_step_id && map[s.parent_step_id]) {
      map[s.parent_step_id].children.push(map[s.step_id]);
    } else {
      roots.push(map[s.step_id]);
    }
  }
  return roots;
}

// ── Step type display labels & colors ─────────────────────────────────────────

export const STEP_TYPE_LABELS: Record<string, string> = {
  DSL:         "DSL Build",
  SCOPE:       "Scope Resolution",
  DATA_PLAN:   "Data Planning",
  DATA_FETCH:  "Data Fetch",
  METRIC_EXEC: "Metric Execution",
  BLOCK:       "Block Evaluation",
  OPERAND:     "Operand Resolution",
  EXPRESSION:  "Expression Eval",
  PERSIST:     "Persistence",
  ROLLUP:      "Rollup",
};

export const STEP_TYPE_COLORS: Record<string, string> = {
  DSL:         "#6366F1",
  SCOPE:       "#8B5CF6",
  DATA_PLAN:   "#EC4899",
  DATA_FETCH:  "#F59E0B",
  METRIC_EXEC: "#3B82F6",
  BLOCK:       "#10B981",
  OPERAND:     "#14B8A6",
  EXPRESSION:  "#F97316",
  PERSIST:     "#6B7280",
  ROLLUP:      "#A855F7",
};

// ── Hooks ─────────────────────────────────────────────────────────────────────

export function useTraces(jobId: number | undefined) {
  return useQuery({
    queryKey: ["traces", { jobId }],
    queryFn: async () => {
      const { data } = await api.get<RunTrace[]>("/traces", {
        params: { job_id: String(jobId) },
      });
      return data;
    },
    enabled: jobId != null,
    staleTime: 30_000,
  });
}

export function useTrace(runId: string | undefined) {
  return useQuery({
    queryKey: ["traces", runId],
    queryFn: async () => {
      const { data } = await api.get<RunTraceDetail>(`/traces/${runId}`);
      return data;
    },
    enabled: runId != null && runId !== "",
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "RUNNING" ? 3_000 : false;
    },
    staleTime: 5_000,
  });
}

/** Fetch ALL traces across every job — used by GlobalRunsPage */
export function useAllTraces(params?: { status?: string; limit?: number }) {
  return useQuery({
    queryKey: ["traces", "all", params],
    queryFn: async () => {
      const { data } = await api.get<RunTrace[]>("/traces", {
        params: params ?? {},
      });
      return data;
    },
    staleTime: 30_000,
    refetchInterval: 30_000,
  });
}

export function useStepSamples(stepId: string | undefined) {
  return useQuery({
    queryKey: ["traces", "samples", stepId],
    queryFn: async () => {
      const { data } = await api.get<RunTraceStepDataSample[]>(
        `/traces/steps/${stepId}/samples`,
      );
      return data;
    },
    enabled: stepId != null && stepId !== "",
    staleTime: 60_000,
  });
}
