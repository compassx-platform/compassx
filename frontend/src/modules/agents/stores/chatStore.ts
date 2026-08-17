import { create } from "zustand";

export interface ChatMessage {
  id: number;
  session_id: number;
  role: "user" | "assistant" | "tool";
  content: string | null;
  tool_name?: string | null;
  tool_result?: Record<string, unknown> | null;
  tokens_used?: number | null;
  created_at: string;
  // Swarm fields — set when a subagent produced this message
  agent_name?: string | null;
  agent_color?: string | null;
  invocation_depth?: number;
}

export type StreamingTimelineItem =
  | { type: "thought"; text: string }
  | { type: "tool"; name: string; args?: Record<string, unknown>; result?: Record<string, unknown>; error?: string; ok?: boolean };

interface ChatStore {
  streamingText: string;
  isStreaming: boolean;
  activeToolName: string | null;
  activeToolArgs: Record<string, unknown> | null;
  streamingSteps: StreamingTimelineItem[];
  // Active streaming agent (changes as subagents take over)
  streamingAgentName: string | null;
  streamingAgentColor: string | null;
  streamingInvocationDepth: number;
  appendStreamingText: (delta: string) => void;
  setStreaming: (v: boolean) => void;
  setActiveTool: (name: string | null, args?: Record<string, unknown> | null) => void;
  addStreamingTimelineItem: (item: StreamingTimelineItem) => void;
  setStreamingAgent: (name: string | null, color: string | null, depth: number) => void;
  resetStream: () => void;
}

export const useChatStore = create<ChatStore>()((set) => ({
  streamingText: "",
  isStreaming: false,
  activeToolName: null,
  activeToolArgs: null,
  streamingSteps: [],
  streamingAgentName: null,
  streamingAgentColor: null,
  streamingInvocationDepth: 0,
  appendStreamingText: (delta) =>
    set((s) => ({ streamingText: s.streamingText + delta })),
  setStreaming: (v) => set({ isStreaming: v }),
  setActiveTool: (name, args = null) =>
    set({ activeToolName: name, activeToolArgs: name ? (args ?? null) : null }),
  addStreamingTimelineItem: (item) =>
    set((s) => ({ streamingSteps: [...s.streamingSteps, item] })),
  setStreamingAgent: (name, color, depth) =>
    set({ streamingAgentName: name, streamingAgentColor: color, streamingInvocationDepth: depth }),
  resetStream: () =>
    set({
      streamingText: "",
      isStreaming: false,
      activeToolName: null,
      activeToolArgs: null,
      streamingSteps: [],
      streamingAgentName: null,
      streamingAgentColor: null,
      streamingInvocationDepth: 0,
    }),
}));
