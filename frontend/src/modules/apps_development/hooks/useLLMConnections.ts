/**
 * useLLMConnections — fetches available LLM connections from the platform config.
 */

import { useEffect, useState } from "react";
import api from "@/lib/api";

export interface LLMConnection {
  id: number;
  name: string;
  provider: string;
  model_name: string;
  is_fallback: boolean;
}

export function useLLMConnections() {
  const [connections, setConnections] = useState<LLMConnection[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get("/api/v1/llm-connections")
      .then((r) => setConnections(r.data))
      .catch(() => setConnections([]))
      .finally(() => setLoading(false));
  }, []);

  return { connections, loading };
}
