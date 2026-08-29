import React, { useState, useEffect, useRef } from "react";
import {
  SlidersHorizontal,
  MessageSquare,
  Save,
  Loader2,
  BookOpen,
  Check,
  Plus,
  Info,
  Trash2,
  Edit2,
  FileText,
  Search,
  ChevronDown,
  ChevronRight,
  X,
  Wrench,
} from "lucide-react";
import { useAgent, useUpdateAgent } from "@/modules/agents/hooks/useAgents";
import { useLLMConnections } from "@/modules/agents/hooks/useLLMConnections";
import {
  useAgentContext,
  useCreateAgentContext,
  useUpdateAgentContext,
  useDeleteAgentContext,
  type AgentContextEntry,
} from "@/modules/agents/hooks/useAgentContext";
import { useSkills } from "@/modules/agents/hooks/useSkills";
import { AVAILABLE_TOOLS, getAvailableTool } from "@/modules/agents/toolCatalog";
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

  // Tools Tab Search & Dropdown State
  const [toolSearchQuery, setToolSearchQuery] = useState("");
  const [isToolDropdownOpen, setIsToolDropdownOpen] = useState(false);
  const [expandedToolKeys, setExpandedToolKeys] = useState<Record<string, boolean>>({});
  const toolSearchRef = useRef<HTMLDivElement>(null);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (toolSearchRef.current && !toolSearchRef.current.contains(event.target as Node)) {
        setIsToolDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleAddTool = (toolKey: string) => {
    if (!selectedTools.includes(toolKey)) {
      setSelectedTools((prev) => [...prev, toolKey]);
      setExpandedToolKeys((prev) => ({ ...prev, [toolKey]: true }));
    }
  };

  const handleRemoveTool = (toolKey: string) => {
    setSelectedTools((prev) => prev.filter((k) => k !== toolKey));
  };

  const toggleToolExpand = (toolKey: string) => {
    setExpandedToolKeys((prev) => ({
      ...prev,
      [toolKey]: !prev[toolKey],
    }));
  };

  const filteredAvailableTools = AVAILABLE_TOOLS.filter((tool) => {
    const q = toolSearchQuery.trim().toLowerCase();
    if (!q) return true;
    if (tool.name.toLowerCase().includes(q)) return true;
    if (tool.key.toLowerCase().includes(q)) return true;
    if (tool.description.toLowerCase().includes(q)) return true;
    if (
      tool.atomicTools?.some(
        (at) =>
          at.name.toLowerCase().includes(q) ||
          at.key.toLowerCase().includes(q) ||
          at.description.toLowerCase().includes(q)
      )
    ) {
      return true;
    }
    return false;
  });

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
            <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
              {/* Header & Tool Search Bar */}
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <label className="form-label" style={{ fontWeight: 600, fontSize: "0.82rem", margin: 0, color: "#1e293b" }}>
                    Agent Tools
                  </label>
                  <span style={{ fontSize: "0.72rem", color: "#64748b" }}>
                    {selectedTools.length} {selectedTools.length === 1 ? "tool" : "tools"} enabled
                  </span>
                </div>

                {/* Search Bar with Dropdown */}
                <div ref={toolSearchRef} style={{ position: "relative", width: "100%" }}>
                  <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
                    <Search
                      size={15}
                      style={{
                        position: "absolute",
                        left: 12,
                        color: "#94a3b8",
                        pointerEvents: "none",
                      }}
                    />
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Search and add tools (e.g. Notebook Manager, SQL Warehouse, Catalog)..."
                      value={toolSearchQuery}
                      onChange={(e) => {
                        setToolSearchQuery(e.target.value);
                        setIsToolDropdownOpen(true);
                      }}
                      onFocus={() => setIsToolDropdownOpen(true)}
                      style={{
                        paddingLeft: 34,
                        paddingRight: toolSearchQuery ? 30 : 12,
                        height: 36,
                        fontSize: "0.8rem",
                        background: "#ffffff",
                        border: "1px solid #e2e8f0",
                        borderRadius: 8,
                      }}
                    />
                    {toolSearchQuery && (
                      <button
                        type="button"
                        className="btn-icon"
                        onClick={() => {
                          setToolSearchQuery("");
                        }}
                        style={{
                          position: "absolute",
                          right: 8,
                          color: "#94a3b8",
                          padding: 3,
                        }}
                      >
                        <X size={13} />
                      </button>
                    )}
                  </div>

                  {/* Dropdown Menu */}
                  {isToolDropdownOpen && (
                    <div
                      style={{
                        position: "absolute",
                        top: "calc(100% + 4px)",
                        left: 0,
                        right: 0,
                        background: "#ffffff",
                        borderRadius: 8,
                        border: "1px solid #e2e8f0",
                        boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.08), 0 8px 10px -6px rgba(0, 0, 0, 0.04)",
                        zIndex: 50,
                        maxHeight: 320,
                        overflowY: "auto",
                      }}
                    >
                      {filteredAvailableTools.length === 0 ? (
                        <div style={{ padding: "14px 16px", textAlign: "center", color: "#64748b", fontSize: "0.78rem" }}>
                          No tools matching "{toolSearchQuery}".
                        </div>
                      ) : (
                        <div style={{ display: "flex", flexDirection: "column", padding: "4px" }}>
                          {filteredAvailableTools.map((tool) => {
                            const isSelected = selectedTools.includes(tool.key);
                            return (
                              <div
                                key={tool.key}
                                onClick={() => {
                                  if (isSelected) {
                                    handleRemoveTool(tool.key);
                                  } else {
                                    handleAddTool(tool.key);
                                  }
                                }}
                                style={{
                                  padding: "9px 12px",
                                  borderRadius: 6,
                                  cursor: "pointer",
                                  display: "flex",
                                  alignItems: "flex-start",
                                  justifyContent: "space-between",
                                  gap: 12,
                                  background: isSelected ? "#f1f5f9" : "transparent",
                                  transition: "background 0.12s ease",
                                }}
                                onMouseEnter={(e) => {
                                  if (!isSelected) e.currentTarget.style.background = "#f8fafc";
                                }}
                                onMouseLeave={(e) => {
                                  if (!isSelected) e.currentTarget.style.background = "transparent";
                                }}
                              >
                                <div style={{ flex: 1, minWidth: 0 }}>
                                  <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                                    <span style={{ fontWeight: 600, fontSize: "0.8rem", color: isSelected ? "#1e293b" : "#0f172a" }}>
                                      {tool.name}
                                    </span>
                                    {tool.atomicTools && tool.atomicTools.length > 0 && (
                                      <span style={{ fontSize: "0.66rem", color: "#475569", background: "#f1f5f9", padding: "1px 6px", borderRadius: 10, fontWeight: 500 }}>
                                        {tool.atomicTools.length} ops
                                      </span>
                                    )}
                                  </div>
                                  <div style={{ fontSize: "0.72rem", color: "#64748b", marginTop: 2, lineHeight: 1.35 }}>
                                    {tool.description}
                                  </div>
                                </div>

                                <div style={{ flexShrink: 0, marginTop: 2 }}>
                                  {isSelected ? (
                                    <span
                                      style={{
                                        display: "inline-flex",
                                        alignItems: "center",
                                        gap: 3,
                                        fontSize: "0.7rem",
                                        color: "#16a34a",
                                        fontWeight: 600,
                                        background: "#dcfce7",
                                        padding: "2px 7px",
                                        borderRadius: 5,
                                      }}
                                    >
                                      <Check size={11} /> Added
                                    </span>
                                  ) : (
                                    <span
                                      style={{
                                        display: "inline-flex",
                                        alignItems: "center",
                                        gap: 3,
                                        fontSize: "0.7rem",
                                        color: "#2563eb",
                                        fontWeight: 600,
                                        background: "#eff6ff",
                                        padding: "2px 7px",
                                        borderRadius: 5,
                                      }}
                                    >
                                      <Plus size={11} /> Add
                                    </span>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Selected Tools List on the Page */}
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {selectedTools.length === 0 ? (
                  <div
                    style={{
                      padding: "28px 16px",
                      borderRadius: 8,
                      border: "1px dashed #cbd5e1",
                      background: "#fafafa",
                      textAlign: "center",
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: 8,
                    }}
                  >
                    <Wrench size={20} style={{ color: "#94a3b8" }} />
                    <div style={{ fontSize: "0.8rem", fontWeight: 500, color: "#475569" }}>
                      No tools attached yet
                    </div>
                    <div style={{ fontSize: "0.73rem", color: "#94a3b8", maxWidth: 360 }}>
                      Click the search bar above to browse and attach tools like Notebook Manager, SQL Warehouse, or Catalog Manager.
                    </div>
                  </div>
                ) : (
                  selectedTools.map((toolKey) => {
                    const tool = getAvailableTool(toolKey) || {
                      key: toolKey,
                      name: toolKey,
                      description: "Custom registered tool.",
                      atomicTools: [],
                    };
                    const isExpanded = !!expandedToolKeys[toolKey];
                    const hasAtomicTools = tool.atomicTools && tool.atomicTools.length > 0;

                    return (
                      <div
                        key={toolKey}
                        style={{
                          borderRadius: 8,
                          border: "1px solid #e2e8f0",
                          background: "#ffffff",
                          boxShadow: "0 1px 2px rgba(0,0,0,0.02)",
                          overflow: "hidden",
                          transition: "border-color 0.15s ease",
                        }}
                      >
                        {/* Tool Item Header with Description directly below name */}
                        <div
                          style={{
                            padding: "12px 14px",
                            display: "flex",
                            alignItems: "flex-start",
                            justifyContent: "space-between",
                            gap: 12,
                            background: "#ffffff",
                            borderBottom: isExpanded ? "1px solid #f1f5f9" : "none",
                            cursor: hasAtomicTools ? "pointer" : "default",
                            userSelect: "none",
                          }}
                          onClick={() => {
                            if (hasAtomicTools) toggleToolExpand(toolKey);
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "flex-start", gap: 10, flex: 1, minWidth: 0 }}>
                            {hasAtomicTools ? (
                              <span
                                style={{
                                  color: "#64748b",
                                  marginTop: 2,
                                  display: "inline-flex",
                                  alignItems: "center",
                                  flexShrink: 0,
                                }}
                              >
                                {isExpanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                              </span>
                            ) : (
                              <div style={{ width: 15, flexShrink: 0 }} />
                            )}

                            <div style={{ display: "flex", flexDirection: "column", gap: 3, flex: 1, minWidth: 0 }}>
                              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                <span style={{ fontWeight: 600, fontSize: "0.84rem", color: "#0f172a" }}>
                                  {tool.name}
                                </span>
                                {hasAtomicTools && (
                                  <span
                                    style={{
                                      fontSize: "0.66rem",
                                      padding: "1px 6px",
                                      borderRadius: 10,
                                      background: "#f1f5f9",
                                      color: "#475569",
                                      fontWeight: 500,
                                    }}
                                  >
                                    {tool.atomicTools!.length} operations
                                  </span>
                                )}
                              </div>
                              <div style={{ fontSize: "0.75rem", color: "#64748b", lineHeight: 1.35 }}>
                                {tool.description}
                              </div>
                            </div>
                          </div>

                          <div style={{ display: "flex", alignItems: "center", flexShrink: 0, marginTop: 1 }}>
                            <button
                              type="button"
                              className="btn-icon"
                              style={{ color: "#94a3b8", padding: 3 }}
                              title="Remove tool"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleRemoveTool(toolKey);
                              }}
                              onMouseEnter={(e) => (e.currentTarget.style.color = "#ef4444")}
                              onMouseLeave={(e) => (e.currentTarget.style.color = "#94a3b8")}
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </div>

                        {/* Expanded Atomic Operations - Simple Readable UI with horizontal dividers */}
                        {isExpanded && hasAtomicTools && (
                          <div style={{ background: "#ffffff", padding: "8px 16px 12px 39px" }}>
                            <div style={{ display: "flex", flexDirection: "column" }}>
                              {tool.atomicTools!.map((at, idx) => (
                                <div
                                  key={at.key}
                                  style={{
                                    display: "flex",
                                    flexDirection: "column",
                                    gap: 2,
                                    paddingTop: idx === 0 ? 4 : 8,
                                    paddingBottom: idx === tool.atomicTools!.length - 1 ? 4 : 8,
                                    borderTop: idx === 0 ? "none" : "1px solid #f1f5f9",
                                  }}
                                >
                                  <div style={{ fontSize: "0.78rem", fontWeight: 600, color: "#1e293b" }}>
                                    {at.name}
                                  </div>
                                  <div style={{ fontSize: "0.72rem", color: "#64748b", lineHeight: 1.35 }}>
                                    {at.description}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}

          {/* 4. Skills */}
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
