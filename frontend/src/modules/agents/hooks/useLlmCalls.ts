import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";

export interface LlmCallLogListItem {
  id: number;
  agent_id: number;
  agent_name?: string;
  session_id?: number;
  call_sequence_number: number;
  created_at: string;
  model: string;
  input_tokens?: number;
  output_tokens?: number;
  finish_reason?: string;
  summary?: string;
  response_tool_calls?: any[];
}

export interface LlmCallLogDetail {
  id: number;
  agent_id: number;
  agent_name?: string;
  session_id?: number;
  call_sequence_number: number;
  created_at: string;
  model: string;
  model_params: Record<string, any>;
  system_prompt_base?: string;
  skills_available: any[];
  skills_injected: any[];
  message_history: any[];
  tools_available: any[];
  response_text?: string;
  response_tool_calls: any[];
  finish_reason?: string;
  input_tokens?: number;
  output_tokens?: number;
}

export interface ListLlmCallLogsFilters {
  agent_id?: number;
  session_id?: number;
  model?: string;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
}

export function useLlmCallLogs(filters: ListLlmCallLogsFilters = {}) {
  return useQuery({
    queryKey: ["llm-call-logs", filters],
    queryFn: async () => {
      const params: Record<string, any> = {};
      if (filters.agent_id) params.agent_id = filters.agent_id;
      if (filters.session_id) params.session_id = filters.session_id;
      if (filters.model) params.model = filters.model;
      if (filters.start_date) params.start_date = filters.start_date;
      if (filters.end_date) params.end_date = filters.end_date;
      if (filters.limit) params.limit = filters.limit;
      if (filters.offset) params.offset = filters.offset;

      const { data } = await api.get<LlmCallLogListItem[]>("/llm-calls", { params });
      return data;
    },
    staleTime: 5000,
    refetchInterval: 10000,
  });
}

export function useLlmCallLogDetail(callId: number | null) {
  return useQuery({
    queryKey: ["llm-call-logs", callId],
    queryFn: async () => {
      const { data } = await api.get<LlmCallLogDetail>(`/llm-calls/${callId}`);
      return data;
    },
    enabled: callId !== null,
    staleTime: 30000,
  });
}
