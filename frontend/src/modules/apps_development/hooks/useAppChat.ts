/**
 * useAppChat — manages app IDE chat sessions and SSE streaming.
 * Each chat session is scoped to an (appId, branchId) pair.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import api from "@/lib/api";

const BASE = "/api/v1/apps";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface AppChatSession {
  id: number;
  app_id: string;
  branch_id: string;
  title: string | null;
  llm_connection_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface AppChatMessage {
  id: number;
  session_id: number;
  role: "user" | "assistant" | "tool";
  content: string | null;
  tool_name: string | null;
  tool_args: Record<string, unknown> | null;
  tool_result: Record<string, unknown> | null;
  created_at: string;
}

export interface StreamEvent {
  type: "text" | "tool_start" | "tool_end" | "error" | "done";
  delta?: string;
  tool_name?: string;
  args?: Record<string, unknown>;
  result?: Record<string, unknown>;
  ok?: boolean;
  error?: string | null;
  message?: string;
  usage?: Record<string, unknown>;
  session_id?: number;
  message_id?: number | null;
}

// In-progress message assembled from streaming text deltas
export interface LiveMessage {
  role: "user" | "assistant";
  content: string;
  isStreaming: boolean;
  toolCalls: LiveToolCall[];
}

export interface LiveToolCall {
  id: string;
  tool_name: string;
  args: Record<string, unknown>;
  result?: Record<string, unknown>;
  ok?: boolean;
  error?: string | null;
  done: boolean;
}

// ─── API helpers ──────────────────────────────────────────────────────────────

async function fetchSessions(appId: string, branchId: string): Promise<AppChatSession[]> {
  const r = await api.get(`${BASE}/${appId}/branches/${branchId}/chat/sessions`);
  return r.data;
}

async function createSession(
  appId: string,
  branchId: string,
  llmConnectionId?: number | null,
): Promise<AppChatSession> {
  const r = await api.post(`${BASE}/${appId}/branches/${branchId}/chat/sessions`, {
    title: null,
    llm_connection_id: llmConnectionId ?? null,
  });
  return r.data;
}

async function fetchMessages(
  appId: string,
  branchId: string,
  sessionId: number,
): Promise<AppChatMessage[]> {
  const r = await api.get(
    `${BASE}/${appId}/branches/${branchId}/chat/sessions/${sessionId}/messages`,
  );
  return r.data;
}

async function deleteSession(
  appId: string,
  branchId: string,
  sessionId: number,
): Promise<void> {
  await api.delete(`${BASE}/${appId}/branches/${branchId}/chat/sessions/${sessionId}`);
}

// ─── Main hook ────────────────────────────────────────────────────────────────

export function useAppChat(
  appId: string,
  branchId: string,
  llmConnectionId: number | null,
) {
  const [sessions, setSessions] = useState<AppChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [messages, setMessages] = useState<AppChatMessage[]>([]);
  const [liveMessages, setLiveMessages] = useState<LiveMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  // Load sessions on mount / when appId/branchId changes
  useEffect(() => {
    if (!appId || !branchId) return;
    fetchSessions(appId, branchId)
      .then((list) => {
        setSessions(list);
        if (list.length > 0) {
          setActiveSessionId(list[0].id);
        }
      })
      .catch(() => {});
  }, [appId, branchId]);

  // Load messages when activeSessionId changes
  useEffect(() => {
    if (!activeSessionId || !appId || !branchId) {
      setMessages([]);
      return;
    }
    setLoadingMessages(true);
    fetchMessages(appId, branchId, activeSessionId)
      .then(setMessages)
      .catch(() => setMessages([]))
      .finally(() => setLoadingMessages(false));
  }, [activeSessionId, appId, branchId]);

  const ensureSession = useCallback(async (): Promise<number> => {
    if (activeSessionId) return activeSessionId;
    const s = await createSession(appId, branchId, llmConnectionId);
    setSessions((prev) => [s, ...prev]);
    setActiveSessionId(s.id);
    return s.id;
  }, [activeSessionId, appId, branchId, llmConnectionId]);

  const newSession = useCallback(async () => {
    const s = await createSession(appId, branchId, llmConnectionId);
    setSessions((prev) => [s, ...prev]);
    setActiveSessionId(s.id);
    setMessages([]);
    setLiveMessages([]);
  }, [appId, branchId, llmConnectionId]);

  const switchSession = useCallback(
    (sessionId: number) => {
      setActiveSessionId(sessionId);
      setLiveMessages([]);
    },
    [],
  );

  const removeSession = useCallback(
    async (sessionId: number) => {
      await deleteSession(appId, branchId, sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
        setMessages([]);
        setLiveMessages([]);
      }
    },
    [appId, branchId, activeSessionId],
  );

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isStreaming) return;

      const sessionId = await ensureSession();
      setIsStreaming(true);

      // Optimistically add user message to live messages
      const userMsg: LiveMessage = {
        role: "user",
        content,
        isStreaming: false,
        toolCalls: [],
      };
      const assistantMsg: LiveMessage = {
        role: "assistant",
        content: "",
        isStreaming: true,
        toolCalls: [],
      };
      setLiveMessages((prev) => [...prev, userMsg, assistantMsg]);

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const response = await fetch(
          `/api/v1/apps/${appId}/branches/${branchId}/chat/sessions/${sessionId}/stream`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ content, llm_connection_id: llmConnectionId }),
            signal: controller.signal,
          },
        );

        if (!response.ok || !response.body) {
          throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const raw = line.slice(6).trim();
            if (!raw) continue;
            let event: StreamEvent;
            try {
              event = JSON.parse(raw);
            } catch {
              continue;
            }

            switch (event.type) {
              case "text":
                setLiveMessages((prev) => {
                  const copy = [...prev];
                  const last = copy[copy.length - 1];
                  if (last && last.role === "assistant") {
                    copy[copy.length - 1] = {
                      ...last,
                      content: last.content + (event.delta ?? ""),
                    };
                  }
                  return copy;
                });
                break;

              case "tool_start":
                setLiveMessages((prev) => {
                  const copy = [...prev];
                  const last = copy[copy.length - 1];
                  if (last && last.role === "assistant") {
                    const newCall: LiveToolCall = {
                      id: `${event.tool_name}-${Date.now()}`,
                      tool_name: event.tool_name ?? "",
                      args: event.args ?? {},
                      done: false,
                    };
                    copy[copy.length - 1] = {
                      ...last,
                      toolCalls: [...last.toolCalls, newCall],
                    };
                  }
                  return copy;
                });
                break;

              case "tool_end":
                setLiveMessages((prev) => {
                  const copy = [...prev];
                  const last = copy[copy.length - 1];
                  if (last && last.role === "assistant") {
                    const updated = last.toolCalls.map((tc) =>
                      tc.tool_name === event.tool_name && !tc.done
                        ? {
                            ...tc,
                            result: event.result,
                            ok: event.ok,
                            error: event.error,
                            done: true,
                          }
                        : tc,
                    );
                    copy[copy.length - 1] = { ...last, toolCalls: updated };
                  }
                  return copy;
                });
                break;

              case "done":
                setLiveMessages((prev) => {
                  const copy = [...prev];
                  const last = copy[copy.length - 1];
                  if (last && last.role === "assistant") {
                    copy[copy.length - 1] = { ...last, isStreaming: false };
                  }
                  return copy;
                });
                // Re-fetch messages from server after stream completes
                fetchMessages(appId, branchId, sessionId)
                  .then(setMessages)
                  .catch(() => {});
                // Update session title in list
                fetchSessions(appId, branchId)
                  .then(setSessions)
                  .catch(() => {});
                break;

              case "error":
                setLiveMessages((prev) => {
                  const copy = [...prev];
                  const last = copy[copy.length - 1];
                  if (last && last.role === "assistant") {
                    copy[copy.length - 1] = {
                      ...last,
                      content: last.content + `\n\n⚠️ **Error:** ${event.message}`,
                      isStreaming: false,
                    };
                  }
                  return copy;
                });
                break;
            }
          }
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name !== "AbortError") {
          setLiveMessages((prev) => {
            const copy = [...prev];
            const last = copy[copy.length - 1];
            if (last && last.role === "assistant") {
              copy[copy.length - 1] = {
                ...last,
                content: last.content || "⚠️ Connection error",
                isStreaming: false,
              };
            }
            return copy;
          });
        }
      } finally {
        setIsStreaming(false);
      }
    },
    [appId, branchId, llmConnectionId, isStreaming, ensureSession],
  );

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
    setIsStreaming(false);
    setLiveMessages((prev) => {
      const copy = [...prev];
      const last = copy[copy.length - 1];
      if (last?.isStreaming) {
        copy[copy.length - 1] = { ...last, isStreaming: false };
      }
      return copy;
    });
  }, []);

  return {
    sessions,
    activeSessionId,
    messages,
    liveMessages,
    isStreaming,
    loadingMessages,
    sendMessage,
    stopStreaming,
    newSession,
    switchSession,
    removeSession,
    setLiveMessages,
  };
}
