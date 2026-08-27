import React, { useState, useEffect } from "react";
import {
  SlidersHorizontal,
  MessageSquare,
  Save,
  Loader2,
  BookOpen,
  Check,
  Plus,
  Info,
  Database,
  GitBranch,
  Trash2,
  Edit2,
  FileText,
} from "lucide-react";
import { useAgent, useUpdateAgent, type AgentDBConnection } from "@/modules/agents/hooks/useAgents";
import { useLLMConnections } from "@/modules/agents/hooks/useLLMConnections";
import { useDBConnections } from "@/modules/agents/hooks/useDBConnections";
import { useGitConnections } from "@/modules/agents/hooks/useGitConnections";
import {
  useAgentContext,
  useCreateAgentContext,
  useUpdateAgentContext,
  useDeleteAgentContext,
  type AgentContextEntry,
} from "@/modules/agents/hooks/useAgentContext";
import { useSkills } from "@/modules/agents/hooks/useSkills";
import { AVAILABLE_TOOLS } from "@/modules/agents/toolCatalog";
import { AgentConfigPanel, type AgentManifestData } from "@/modules/agents/components/AgentConfigPanel";
import { PageTabs } from "@/components/common/PageTabs";
import { useToast } from "@/lib/toast";

interface AgentCustomizationsViewProps {
  agentId: number;
  onClose: () => void;
}

const CUSTOMIZATION_TABS = [
  { value: "about", label: "About" },
  { value: "instruction", label: "Instruction" },
  { value: "tools", label: "Tools" },
  { value: "data", label: "Data Connections" },
  { value: "skills", label: "Skills" },
  { value: "context", label: "Context" },
] as const;

type CustomizationTab = (typeof CUSTOMIZATION_TABS)[number]["value"];

export const AgentCustomizationsView: React.FC<AgentCustomizationsViewProps> = ({
  agentId,
  onClose,
}) => {
  const toast = useToast();
  const { data: agent, isLoading: isLoadingAgent } = useAgent(agentId);
  const updateMutation = useUpdateAgent();
  const { data: llmConnections = [] } = useLLMConnections();
  const { data: dbConnections = [] } = useDBConnections();
  const { data: gitConnections = [] } = useGitConnections();
  const { data: allSkills = [] } = useSkills();
  const { data: contextEntries = [] } = useAgentContext(agentId);
  const createContextMutation = useCreateAgentContext();
  const updateContextMutation = useUpdateAgentContext();
  const deleteContextMutation = useDeleteAgentContext();

  const [activeTab, setActiveTab] = useState<CustomizationTab>("about");

  // Form State
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [prompt, setPrompt] = useState("");
  const [llmConnectionId, setLlmConnectionId] = useState<number | null>(null);
  const [visibility, setVisibility] = useState<"shared" | "private">("shared");
  const [isOrchestrator, setIsOrchestrator] = useState(false);
  const [manifest, setManifest] = useState<AgentManifestData>({} as AgentManifestData);
  const [selectedTools, setSelectedTools] = useState<string[]>([]);
  const [selectedDBs, setSelectedDBs] = useState<AgentDBConnection[]>([]);
  const [selectedGits, setSelectedGits] = useState<{ git_connection_id: number }[]>([]);
  const [selectedSkills, setSelectedSkills] = useState<{ skill_id: number; position: number }[]>([]);

  // Context entry modal / state
  const [editingContextEntry, setEditingContextEntry] = useState<AgentContextEntry | null>(null);
  const [newContextKey, setNewContextKey] = useState("");
  const [newContextValue, setNewContextValue] = useState("");
  const [isAddingContext, setIsAddingContext] = useState(false);

  // Sync state when agent loads
  useEffect(() => {
    if (agent) {
      setName(agent.name ?? "");
      setDescription(agent.description ?? "");
      setPrompt(agent.prompt ?? "");
      setLlmConnectionId(agent.llm_connection_id ?? null);
      setVisibility(agent.visibility ?? "shared");
      setIsOrchestrator(agent.is_orchestrator ?? false);
      setManifest((agent.manifest as AgentManifestData) ?? ({} as AgentManifestData));
      setSelectedTools((agent.tools ?? []).map((t) => t.tool_name));
      setSelectedDBs(agent.db_connections ?? []);
      setSelectedSkills(
        (agent.skills ?? []).map((s: any, idx: number) => ({
          skill_id: s.skill_id,
          position: s.position ?? idx,
        }))
      );
    }
  }, [agent]);

  const isSaving = updateMutation.isPending;

  const handleSave = async () => {
    if (!name.trim()) {
      toast.error("Agent name is required");
      return;
    }

    try {
      await updateMutation.mutateAsync({
        agentId,
        payload: {
          name: name.trim(),
          description: description.trim(),
          prompt: prompt.trim(),
          llm_connection_id: llmConnectionId,
          visibility,
          is_orchestrator: isOrchestrator,
          manifest: manifest as any,
          tools: selectedTools.map((t) => ({ tool_name: t })),
          db_connections: selectedDBs,
        },
      });
      toast.success("Agent settings updated successfully");
    } catch {
      toast.error("Failed to update agent settings");
    }
  };

  const toggleTool = (toolKey: string) => {
    setSelectedTools((prev) =>
      prev.includes(toolKey) ? prev.filter((k) => k !== toolKey) : [...prev, toolKey]
    );
  };

  const toggleDB = (id: number) => {
    setSelectedDBs((prev) =>
      prev.find((d) => d.db_connection_id === id)
        ? prev.filter((d) => d.db_connection_id !== id)
        : [...prev, { db_connection_id: id }]
    );
  };

  const toggleGit = (id: number) => {
    setSelectedGits((prev) =>
      prev.find((g) => g.git_connection_id === id)
        ? prev.filter((g) => g.git_connection_id !== id)
        : [...prev, { git_connection_id: id }]
    );
  };

  const toggleSkill = (skillId: number) => {
    setSelectedSkills((prev) => {
      const exists = prev.some((s) => s.skill_id === skillId);
      if (exists) {
        return prev.filter((s) => s.skill_id !== skillId);
      } else {
        return [...prev, { skill_id: skillId, position: prev.length }];
      }
    });
  };

  const handleAddContext = async () => {
    if (!newContextKey.trim() || !newContextValue.trim()) return;
    try {
      await createContextMutation.mutateAsync({
        agentId,
        payload: { text: newContextValue.trim(), tags: [newContextKey.trim()] },
      });
      setNewContextKey("");
      setNewContextValue("");
      setIsAddingContext(false);
      toast.success("Context entry added");
    } catch {
      toast.error("Failed to add context");
    }
  };

  const handleUpdateContext = async () => {
    if (!editingContextEntry) return;
    try {
      await updateContextMutation.mutateAsync({
        agentId,
        entryId: editingContextEntry.id,
        payload: { text: editingContextEntry.text, tags: editingContextEntry.tags },
      });
      setEditingContextEntry(null);
      toast.success("Context entry updated");
    } catch {
      toast.error("Failed to update context");
    }
  };

  const handleDeleteContext = async (contextId: number) => {
    try {
      await deleteContextMutation.mutateAsync({ agentId, entryId: contextId });
      toast.success("Context entry deleted");
    } catch {
      toast.error("Failed to delete context");
    }
  };

  if (isLoadingAgent) {
    return (
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 8, color: "#64748b" }}>
        <Loader2 size={18} className="spin" />
        <span style={{ fontSize: "0.85rem" }}>Loading agent settings…</span>
      </div>
    );
  }

  const enabledDBIds = new Set(selectedDBs.map((d) => d.db_connection_id));
  const enabledGitIds = new Set(selectedGits.map((g) => g.git_connection_id));

  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        height: "100%",
        background: "#ffffff",
        overflow: "hidden",
      }}
    >
      {/* Top Tabs & Action Row */}
      <div
        style={{
          padding: "16px 28px 8px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 16,
          background: "#ffffff",
        }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <PageTabs
            tabs={CUSTOMIZATION_TABS}
            value={activeTab}
            onChange={(val) => setActiveTab(val as CustomizationTab)}
          />
        </div>

        <div style={{ flexShrink: 0 }}>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleSave}
            disabled={isSaving || !name.trim()}
            style={{ fontSize: "0.8rem", display: "flex", alignItems: "center", gap: 6, height: 32, padding: "0 14px" }}
          >
            {isSaving ? <Loader2 size={14} className="spin" /> : <Save size={14} />}
            {isSaving ? "Saving…" : "Save Changes"}
          </button>
        </div>
      </div>

      {/* Content Area */}
      <div style={{ flex: 1, overflowY: "auto", padding: "24px 28px 48px" }}>
        <div style={{ maxWidth: 840, margin: "0 auto" }}>
          {/* 1. About Tab (including Agent Execution Profile) */}
          {activeTab === "about" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600, fontSize: "0.82rem" }}>
                    Agent Name *
                  </label>
                  <input
                    className="form-input"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. Data Analytics Agent"
                    style={{ fontSize: "0.85rem" }}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600, fontSize: "0.82rem" }}>
                    Description
                  </label>
                  <input
                    className="form-input"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Brief description of what this agent does"
                    style={{ fontSize: "0.85rem" }}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label" style={{ fontWeight: 600, fontSize: "0.82rem" }}>
                    LLM Model Connection
                  </label>
                  <select
                    className="form-select"
                    value={llmConnectionId ?? ""}
                    onChange={(e) => setLlmConnectionId(e.target.value ? Number(e.target.value) : null)}
                    style={{ fontSize: "0.85rem" }}
                  >
                    <option value="">Default System Model</option>
                    {llmConnections.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} ({c.provider} · {c.model_name})
                      </option>
                    ))}
                  </select>
                </div>

                <div style={{ display: "flex", gap: 20 }}>
                  <div className="form-group" style={{ flex: 1 }}>
                    <label className="form-label" style={{ fontWeight: 600, fontSize: "0.82rem" }}>
                      Visibility
                    </label>
                    <select
                      className="form-select"
                      value={visibility}
                      onChange={(e) => setVisibility(e.target.value as "shared" | "private")}
                      style={{ fontSize: "0.85rem" }}
                    >
                      <option value="shared">Shared with workspace</option>
                      <option value="private">Private to me</option>
                    </select>
                  </div>

                  <div className="form-group" style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center" }}>
                    <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: "0.82rem", fontWeight: 600, marginTop: 18 }}>
                      <input
                        type="checkbox"
                        checked={isOrchestrator}
                        onChange={(e) => setIsOrchestrator(e.target.checked)}
                      />
                      Enable as Orchestrator / Swarm Leader
                    </label>
                  </div>
                </div>
              </div>

              {/* Agent Execution Profile & Capabilities */}
              <div style={{ borderTop: "1px solid var(--color-border, #e5e7eb)", paddingTop: 20 }}>
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontWeight: 600, fontSize: "0.88rem", color: "#0f172a" }}>
                    Execution Profile & Capabilities
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "#64748b", marginTop: 2 }}>
                    Configure execution profile (Reactive vs Build Agent), multi-step planning, checkpoints, and document uploads.
                  </div>
                </div>

                <AgentConfigPanel
                  manifest={manifest}
                  onChange={(nextManifest) => setManifest(nextManifest)}
                />
              </div>
            </div>
          )}

          {/* 2. Instruction Tab */}
          {activeTab === "instruction" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div
                style={{
                  padding: "12px 16px",
                  borderRadius: 8,
                  background: "#f8fafc",
                  border: "1px solid #e2e8f0",
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 10,
                  fontSize: "0.78rem",
                  color: "#475569",
                }}
              >
                <Info size={16} style={{ flexShrink: 0, marginTop: 2, color: "#2563eb" }} />
                <span>
                  Instructions define the agent's persona, operational rules, response style, and specific domain workflows.
                </span>
              </div>

              <div className="form-group">
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                  <label className="form-label" style={{ fontWeight: 600, fontSize: "0.82rem", margin: 0 }}>
                    System Prompt Instructions
                  </label>
                  <span style={{ fontSize: "0.72rem", color: "#94a3b8" }}>
                    Markdown supported
                  </span>
                </div>
                <textarea
                  className="form-input"
                  rows={16}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="You are an expert AI assistant specialized in..."
                  style={{
                    fontFamily: "ui-monospace, monospace",
                    fontSize: "0.82rem",
                    lineHeight: 1.5,
                    resize: "vertical",
                  }}
                />
              </div>
            </div>
          )}

          {/* 3. Tools */}
          {activeTab === "tools" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <p style={{ fontSize: "0.8rem", color: "#64748b", margin: 0 }}>
                Select the tools this agent has access to when assisting with user requests.
              </p>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))",
                  gap: 10,
                }}
              >
                {AVAILABLE_TOOLS.map((tool) => {
                  const isSelected = selectedTools.includes(tool.key);
                  return (
                    <div
                      key={tool.key}
                      onClick={() => toggleTool(tool.key)}
                      style={{
                        padding: "12px 14px",
                        borderRadius: 8,
                        border: isSelected ? "1px solid #2563eb" : "1px solid var(--color-border, #e5e7eb)",
                        background: isSelected ? "rgba(37,99,235,0.03)" : "#ffffff",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "flex-start",
                        gap: 10,
                        transition: "all 0.15s ease",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => {}}
                        style={{ marginTop: 3, cursor: "pointer" }}
                      />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: "0.82rem", fontWeight: 600, color: isSelected ? "#1d4ed8" : "#1e293b" }}>
                          {tool.name}
                        </div>
                        <div style={{ fontSize: "0.72rem", color: "#64748b", marginTop: 2, lineHeight: 1.3 }}>
                          {tool.description}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* 4. Data Connections */}
          {activeTab === "data" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: "0.85rem", marginBottom: 6, display: "flex", alignItems: "center", gap: 6 }}>
                  <Database size={15} color="#2563eb" /> Database Connections
                </div>
                <p style={{ fontSize: "0.78rem", color: "#64748b", marginBottom: 12, marginTop: 0 }}>
                  Select databases this agent can query when answering data questions.
                </p>
                {dbConnections.length === 0 ? (
                  <div style={{ fontSize: "0.78rem", color: "#94a3b8" }}>No database connections configured.</div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {dbConnections.map((db) => {
                      const enabled = enabledDBIds.has(db.id);
                      return (
                        <label
                          key={db.id}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 10,
                            padding: "10px 14px",
                            border: enabled ? "1px solid #2563eb" : "1px solid var(--color-border, #e5e7eb)",
                            borderRadius: 8,
                            background: enabled ? "rgba(37,99,235,0.03)" : "#ffffff",
                            cursor: "pointer",
                          }}
                        >
                          <input type="checkbox" checked={enabled} onChange={() => toggleDB(db.id)} />
                          <div>
                            <div style={{ fontWeight: 600, fontSize: "0.82rem", color: enabled ? "#1d4ed8" : "#1e293b" }}>{db.name}</div>
                            <div style={{ fontSize: "0.72rem", color: "#64748b" }}>Type: {db.db_type}</div>
                          </div>
                        </label>
                      );
                    })}
                  </div>
                )}
              </div>

              <div>
                <div style={{ fontWeight: 600, fontSize: "0.85rem", marginBottom: 6, display: "flex", alignItems: "center", gap: 6 }}>
                  <GitBranch size={15} color="#2563eb" /> Git Connections
                </div>
                <p style={{ fontSize: "0.78rem", color: "#64748b", marginBottom: 12, marginTop: 0 }}>
                  Attach git repositories for code analysis, pipelines, or PR workflows.
                </p>
                {gitConnections.length === 0 ? (
                  <div style={{ fontSize: "0.78rem", color: "#94a3b8" }}>No git connections configured.</div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {gitConnections.map((g) => {
                      const enabled = enabledGitIds.has(g.id);
                      return (
                        <label
                          key={g.id}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 10,
                            padding: "10px 14px",
                            border: enabled ? "1px solid #2563eb" : "1px solid var(--color-border, #e5e7eb)",
                            borderRadius: 8,
                            background: enabled ? "rgba(37,99,235,0.03)" : "#ffffff",
                            cursor: "pointer",
                          }}
                        >
                          <input type="checkbox" checked={enabled} onChange={() => toggleGit(g.id)} />
                          <div>
                            <div style={{ fontWeight: 600, fontSize: "0.82rem", color: enabled ? "#1d4ed8" : "#1e293b" }}>{g.name}</div>
                            <div style={{ fontSize: "0.72rem", color: "#64748b" }}>Provider: {g.provider} · Project: {g.default_project || 'default'}</div>
                          </div>
                        </label>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* 5. Skills */}
          {activeTab === "skills" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <p style={{ fontSize: "0.8rem", color: "#64748b", margin: 0 }}>
                Attach specialized domain skills and workflows to enrich the agent's capabilities.
              </p>

              {allSkills.length === 0 ? (
                <div style={{ padding: "32px 16px", textAlign: "center", color: "#94a3b8", fontSize: "0.8rem" }}>
                  No skills available yet.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {allSkills.map((skill) => {
                    const isAttached = selectedSkills.some((s) => s.skill_id === skill.id);
                    return (
                      <div
                        key={skill.id}
                        onClick={() => toggleSkill(skill.id)}
                        style={{
                          padding: "12px 16px",
                          borderRadius: 8,
                          border: isAttached ? "1px solid #2563eb" : "1px solid var(--color-border, #e5e7eb)",
                          background: isAttached ? "rgba(37,99,235,0.03)" : "#ffffff",
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          gap: 12,
                          transition: "all 0.15s ease",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <BookOpen size={16} color={isAttached ? "#2563eb" : "#64748b"} />
                          <div>
                            <div style={{ fontSize: "0.83rem", fontWeight: 600, color: isAttached ? "#1d4ed8" : "#1e293b" }}>
                              {skill.name}
                            </div>
                            <div style={{ fontSize: "0.73rem", color: "#64748b", marginTop: 2 }}>
                              {skill.description}
                            </div>
                          </div>
                        </div>

                        <button
                          type="button"
                          className={`btn ${isAttached ? "btn-secondary" : "btn-primary"}`}
                          style={{ height: 28, fontSize: "0.72rem", padding: "0 10px" }}
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleSkill(skill.id);
                          }}
                        >
                          {isAttached ? <Check size={12} /> : <Plus size={12} />}
                          {isAttached ? "Attached" : "Attach"}
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* 6. Context */}
          {activeTab === "context" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: "0.85rem", color: "#0f172a" }}>Agent Context Knowledge</div>
                  <p style={{ fontSize: "0.78rem", color: "#64748b", margin: "2px 0 0" }}>
                    Add key-value instructions and domain rules injected into the agent's prompt context.
                  </p>
                </div>
                {!isAddingContext && (
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setIsAddingContext(true)}
                    style={{ fontSize: "0.78rem", height: 30, padding: "0 10px" }}
                  >
                    <Plus size={13} /> Add Context Entry
                  </button>
                )}
              </div>

              {isAddingContext && (
                <div style={{ padding: 14, border: "1px solid #2563eb", borderRadius: 8, background: "#f8fafc", display: "flex", flexDirection: "column", gap: 10 }}>
                  <input
                    className="form-input"
                    placeholder="Context Key (e.g. business_rules)"
                    value={newContextKey}
                    onChange={(e) => setNewContextKey(e.target.value)}
                    style={{ fontSize: "0.8rem" }}
                  />
                  <textarea
                    className="form-input"
                    placeholder="Context Value / Instructions"
                    rows={3}
                    value={newContextValue}
                    onChange={(e) => setNewContextValue(e.target.value)}
                    style={{ fontSize: "0.8rem" }}
                  />
                  <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
                    <button type="button" className="btn btn-secondary" style={{ height: 28, fontSize: "0.75rem" }} onClick={() => setIsAddingContext(false)}>
                      Cancel
                    </button>
                    <button type="button" className="btn btn-primary" style={{ height: 28, fontSize: "0.75rem" }} onClick={handleAddContext}>
                      Add Entry
                    </button>
                  </div>
                </div>
              )}

              {contextEntries.length === 0 && !isAddingContext ? (
                <div style={{ padding: "32px 16px", textAlign: "center", color: "#94a3b8", fontSize: "0.8rem" }}>
                  No context entries configured yet.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {contextEntries.map((c) => (
                    <div
                      key={c.id}
                      style={{
                        padding: "12px 14px",
                        border: "1px solid var(--color-border, #e5e7eb)",
                        borderRadius: 8,
                        background: "#ffffff",
                        display: "flex",
                        alignItems: "flex-start",
                        justifyContent: "space-between",
                        gap: 12,
                      }}
                    >
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 600, fontSize: "0.8rem", color: "#1e293b", fontFamily: "monospace" }}>{c.tags?.[0] || 'context'}</div>
                        <div style={{ fontSize: "0.75rem", color: "#64748b", marginTop: 4, whiteSpace: "pre-wrap" }}>{c.text}</div>
                      </div>
                      <div style={{ display: "flex", gap: 4 }}>
                        <button
                          type="button"
                          className="btn-icon"
                          style={{ color: "#ef4444", padding: 4 }}
                          onClick={() => handleDeleteContext(c.id)}
                          title="Delete entry"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
