/**
 * AgentBuilderPage â€” 4-step wizard: Define â†’ Tools â†’ Data â†’ Context+Test
 */
import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { useScopedNavigate } from "@/lib/appNavigation";
import {
  Zap,
  Database,
  GitBranch,
  BookOpen,
  Loader2,
  Save,
  MessageSquare,
  Plus,
  Trash2,
  Edit2,
  Tag,
} from "lucide-react";
import { PageTabs } from "@/components/common/PageTabs";
import { useAgent, useCreateAgent, useUpdateAgent, type AgentDBConnection } from "@/modules/agents/hooks/useAgents";
import { useLLMConnections } from "@/modules/agents/hooks/useLLMConnections";
import { useDBConnections } from "@/modules/agents/hooks/useDBConnections";
import { useGitConnections, type GitConnection } from "@/modules/agents/hooks/useGitConnections";
import {
  useAgentContext,
  useCreateAgentContext,
  useUpdateAgentContext,
  useDeleteAgentContext,
  type AgentContextEntry,
} from "@/modules/agents/hooks/useAgentContext";
import { useToast } from "@/lib/toast";
import { useSkills, type Skill } from "@/modules/agents/hooks/useSkills";
import api from "@/lib/api";
import { getAuthKey } from "@/lib/auth";
import { AVAILABLE_TOOLS } from "@/modules/agents/toolCatalog";
import { AgentConfigPanel, type AgentManifestData } from "@/modules/agents/components/AgentConfigPanel";

// â”€â”€ Tool catalog â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

type AgentBuilderTab = "define" | "tools" | "data" | "skills" | "context";

const BUILDER_TABS = [
  { value: "define", label: "About" },
  { value: "tools", label: "Tools" },
  { value: "data", label: "Data" },
  { value: "skills", label: "Skills" },
  { value: "context", label: "Context" },
] as const;

const BUILDER_TAB_VALUES = BUILDER_TABS.map((tab) => tab.value) as AgentBuilderTab[];

function StepDefine({
  form,
  setForm,
  llmConnections,
}: {
  form: AgentForm;
  setForm: React.Dispatch<React.SetStateAction<AgentForm>>;
  llmConnections: { id: number; name: string; provider: string; model_name: string }[];
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div className="form-group">
        <label className="form-label">Agent Name *</label>
        <input
          className="form-input"
          value={form.name}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          placeholder="e.g. Data Assistant"
        />
      </div>
      <div className="form-group">
        <label className="form-label">Description</label>
        <input
          className="form-input"
          value={form.description}
          onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
          placeholder="What does this agent do?"
        />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div className="form-group">
          <label className="form-label">Avatar</label>
          <input
            className="form-input"
            value={form.avatar}
            onChange={(e) => setForm((f) => ({ ...f, avatar: e.target.value }))}
            placeholder="ðŸ¤– or image URL"
          />
        </div>
        <div className="form-group">
          <label className="form-label">Colour (hex)</label>
          <input
            className="form-input"
            value={form.color}
            onChange={(e) => setForm((f) => ({ ...f, color: e.target.value }))}
            placeholder="#1b6ef3"
          />
        </div>
      </div>
      <div className="form-group">
        <label className="form-label">System Prompt</label>
        <textarea
          className="form-input"
          rows={6}
          value={form.prompt}
          onChange={(e) => setForm((f) => ({ ...f, prompt: e.target.value }))}
          placeholder="You are a helpful data assistant with access to the company's databasesâ€¦"
        />
        <div style={{ fontSize: "0.72rem", color: "var(--color-text-muted)", marginTop: 4 }}>
          Full system prompt written by admin. Shared context and agent context are prepended automatically.
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
        <div className="form-group">
          <label className="form-label">LLM Connection</label>
          <select
            className="form-input"
            value={form.llm_connection_id ?? ""}
            onChange={(e) =>
              setForm((f) => ({ ...f, llm_connection_id: e.target.value ? parseInt(e.target.value) : undefined }))
            }
          >
            <option value="">â€” Use default connection â€”</option>
            {llmConnections.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.provider} / {c.model_name})
              </option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Model</label>
          <input
            className="form-input"
            value={form.model}
            onChange={(e) => setForm((f) => ({ ...f, model: e.target.value }))}
            placeholder="claude-sonnet-4-6"
          />
        </div>
        <div className="form-group">
          <label className="form-label">Max Tokens</label>
          <input
            className="form-input"
            type="number"
            value={form.max_tokens}
            onChange={(e) => setForm((f) => ({ ...f, max_tokens: parseInt(e.target.value) || 8096 }))}
          />
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div className="form-group">
          <label className="form-label">Visibility</label>
          <select
            className="form-input"
            value={form.visibility}
            onChange={(e) => setForm((f) => ({ ...f, visibility: e.target.value as AgentForm["visibility"] }))}
          >
            <option value="shared">Shared</option>
            <option value="private">Private (only me)</option>
          </select>
        </div>
        <div className="form-group" style={{ display: "flex", alignItems: "center", gap: 10, paddingTop: 24 }}>
          <input
            type="checkbox"
            id="is_orchestrator"
            checked={form.is_orchestrator}
            onChange={(e) => setForm((f) => ({ ...f, is_orchestrator: e.target.checked }))}
          />
          <label htmlFor="is_orchestrator" style={{ fontSize: "0.875rem", cursor: "pointer" }}>
            Orchestrator (can spawn sub-agents)
          </label>
        </div>
      </div>

      {/* Manifest Capability Configuration Panel (Spec v2 E1) */}
      <div style={{ marginTop: 10 }}>
        <AgentConfigPanel
          manifest={
            (form as any).manifest || {
              agent_id: form.name.toLowerCase().replace(/\s+/g, "-") || "custom-agent",
              display_name: form.name || "Custom Agent",
              base_profile: "reactive_agent",
              capabilities: {
                planning: { enabled: false, router_thresholds: "default", max_retry_attempts: 3 },
                checkpoints: { enabled: false, gated_write_categories: [] },
                document_upload: { enabled: true, accepted_types: ["pdf", "docx", "xlsx", "csv", "txt", "md", "json"] },
              },
            }
          }
          onChange={(updatedManifest: AgentManifestData) => {
            setForm((f) => ({ ...f, manifest: updatedManifest } as any));
          }}
        />
      </div>
    </div>
  );
}

// â”€â”€ Step 2: Tools â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function StepTools({
  selectedTools,
  setSelectedTools,
}: {
  selectedTools: string[];
  setSelectedTools: React.Dispatch<React.SetStateAction<string[]>>;
}) {
  function toggle(key: string) {
    setSelectedTools((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  }

  const enabledKeys = new Set(selectedTools);
  const hasClaudeAgent = enabledKeys.has("claude_agent");
  const hasInvokeAgent = enabledKeys.has("invoke_agent");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <p style={{ fontSize: "0.85rem", color: "var(--color-text-muted)", margin: 0 }}>
        Choose which tools this agent can use. Tools are invoked by the LLM via tool-use.
      </p>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: 12,
        }}
      >
        {AVAILABLE_TOOLS.map((tool) => {
          const enabled = enabledKeys.has(tool.key);
          return (
            <div
              key={tool.key}
              onClick={() => toggle(tool.key)}
              style={{
                border: `1.5px solid ${enabled ? "var(--color-primary)" : "var(--color-border)"}`,
                borderRadius: 8,
                padding: "12px 14px",
                cursor: "pointer",
                background: enabled ? "var(--color-primary-subtle, rgba(27,110,243,0.06))" : "var(--color-surface)",
                transition: "border-color 0.15s, background 0.15s",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <input type="checkbox" readOnly checked={enabled} />
                <span style={{ fontWeight: 500, fontSize: "0.875rem" }}>{tool.name}</span>
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", paddingLeft: 22 }}>
                {tool.description}
              </div>
            </div>
          );
        })}
      </div>

      {hasClaudeAgent && (
        <div
          style={{
            border: "1px solid var(--color-border)",
            borderRadius: 8,
            padding: "14px 16px",
            background: "var(--color-surface)",
            display: "flex",
            alignItems: "center",
            gap: 10,
            fontSize: "0.8rem",
            color: "var(--color-text-muted)",
          }}
        >
          <GitBranch size={14} color="var(--color-primary)" />
          <span>
            Claude Agent requires a Git connection for PR and work item actions. Attach one in{" "}
            <strong style={{ color: "var(--color-text)" }}>Step 3 â†’ Git Connections</strong>.
          </span>
        </div>
      )}

      {hasInvokeAgent && (
        <div
          style={{
            border: "1px solid var(--color-border)",
            borderRadius: 8,
            padding: "14px 16px",
            background: "var(--color-surface)",
            display: "flex",
            alignItems: "center",
            gap: 10,
            fontSize: "0.8rem",
            color: "var(--color-text-muted)",
          }}
        >
          <Zap size={14} color="var(--color-primary)" />
          <span>
            Invoke Agent lets this agent hand off tasks to other agents.
            Add a prompt instruction like:{" "}
            <em style={{ color: "var(--color-text)" }}>
              "If the task requires specialised analysis, invoke the 'Agent Name' agent using invoke_agent."
            </em>
          </span>
        </div>
      )}
    </div>
  );
}


// â”€â”€ Step 3: Data â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function StepData({
  dbConnections,
  selectedDBs,
  setSelectedDBs,
  gitConnections,
  selectedGits,
  setSelectedGits,
}: {
  dbConnections: { id: number; name: string; db_type: string }[];
  selectedDBs: AgentDBConnection[];
  setSelectedDBs: React.Dispatch<React.SetStateAction<AgentDBConnection[]>>;
  gitConnections: GitConnection[];
  selectedGits: { git_connection_id: number }[];
  setSelectedGits: React.Dispatch<React.SetStateAction<{ git_connection_id: number }[]>>;
}) {
  function toggleDB(id: number) {
    setSelectedDBs((prev) =>
      prev.find((d) => d.db_connection_id === id)
        ? prev.filter((d) => d.db_connection_id !== id)
        : [...prev, { db_connection_id: id }]
    );
  }

  function toggleGit(id: number) {
    setSelectedGits((prev) =>
      prev.find((g) => g.git_connection_id === id)
        ? prev.filter((g) => g.git_connection_id !== id)
        : [...prev, { git_connection_id: id }]
    );
  }

  const enabledDBIds = new Set(selectedDBs.map((d) => d.db_connection_id));
  const enabledGitIds = new Set(selectedGits.map((g) => g.git_connection_id));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
      {/* DB Connections */}
      <div>
        <div style={{ fontWeight: 600, fontSize: "0.875rem", marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
          <Database size={14} color="var(--color-primary)" /> Database Connections
        </div>
        <p style={{ fontSize: "0.8rem", color: "var(--color-text-muted)", marginBottom: 12, marginTop: 0 }}>
          Select databases this agent can query (requires SQL Query skill).
        </p>
        {dbConnections.length === 0 ? (
          <div style={{ fontSize: "0.8rem", color: "var(--color-text-muted)" }}>
            No database connections yet. Add them from Agents â†’ Connections.
          </div>
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
                    gap: 12,
                    padding: "10px 14px",
                    border: `1.5px solid ${enabled ? "var(--color-primary)" : "var(--color-border)"}`,
                    borderRadius: 8,
                    cursor: "pointer",
                    background: enabled ? "var(--color-primary-subtle, rgba(27,110,243,0.06))" : "var(--color-surface)",
                  }}
                >
                  <input type="checkbox" checked={enabled} onChange={() => toggleDB(db.id)} />
                  <Database size={14} color="var(--color-text-muted)" />
                  <div>
                    <div style={{ fontWeight: 500, fontSize: "0.875rem" }}>{db.name}</div>
                    <div style={{ fontSize: "0.72rem", color: "var(--color-text-muted)" }}>{db.db_type}</div>
                  </div>
                </label>
              );
            })}
          </div>
        )}
      </div>

      {/* Git Connections */}
      <div>
        <div style={{ fontWeight: 600, fontSize: "0.875rem", marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
          <GitBranch size={14} color="var(--color-primary)" /> Git Connections
        </div>
        <p style={{ fontSize: "0.8rem", color: "var(--color-text-muted)", marginBottom: 12, marginTop: 0 }}>
          Select Git connections for PR review and code skills.
        </p>
        {gitConnections.length === 0 ? (
          <div style={{ fontSize: "0.8rem", color: "var(--color-text-muted)" }}>
            No Git connections yet. Add them from Agents â†’ Connections.
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {gitConnections.map((gc) => {
              const enabled = enabledGitIds.has(gc.id);
              return (
                <label
                  key={gc.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    padding: "10px 14px",
                    border: `1.5px solid ${enabled ? "var(--color-primary)" : "var(--color-border)"}`,
                    borderRadius: 8,
                    cursor: "pointer",
                    background: enabled ? "var(--color-primary-subtle, rgba(27,110,243,0.06))" : "var(--color-surface)",
                  }}
                >
                  <input type="checkbox" checked={enabled} onChange={() => toggleGit(gc.id)} />
                  <GitBranch size={14} color="var(--color-text-muted)" />
                  <div>
                    <div style={{ fontWeight: 500, fontSize: "0.875rem" }}>{gc.name}</div>
                    <div style={{ fontSize: "0.72rem", color: "var(--color-text-muted)" }}>
                      {gc.provider === "azure_devops" ? "Azure DevOps" : "GitHub"}
                      {gc.organization ? ` Â· ${gc.organization}` : ""}
                      {gc.default_project ? ` / ${gc.default_project}` : ""}
                      {gc.pat_configured && <span style={{ color: "var(--color-success, #38a169)", marginLeft: 4 }}>âœ“ PAT</span>}
                    </div>
                  </div>
                </label>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// â”€â”€ Agent Context entry form â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function AgentContextForm({
  initial,
  onSave,
  onCancel,
  isSaving,
}: {
  initial?: Partial<AgentContextEntry>;
  onSave: (data: { text: string; tags: string[] }) => void;
  onCancel: () => void;
  isSaving: boolean;
}) {
  const [text, setText] = useState(initial?.text ?? "");
  const [tagInput, setTagInput] = useState("");
  const [tags, setTags] = useState<string[]>(initial?.tags ?? []);

  function addTag() {
    const t = tagInput.trim().toLowerCase();
    if (t && !tags.includes(t)) setTags((prev) => [...prev, t]);
    setTagInput("");
  }

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); onSave({ text, tags }); }}
      style={{ display: "flex", flexDirection: "column", gap: 12 }}
    >
      <div className="form-group">
        <label className="form-label">Content *</label>
        <textarea
          className="form-input"
          rows={4}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Specific facts or instructions for this agent onlyâ€¦"
          required
        />
      </div>
      <div className="form-group">
        <label className="form-label">Tags</label>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 6 }}>
          {tags.map((t) => (
            <span
              key={t}
              style={{
                display: "inline-flex", alignItems: "center", gap: 4,
                padding: "2px 8px", borderRadius: 12, fontSize: "0.75rem",
                background: "var(--color-primary-subtle, rgba(27,110,243,0.1))",
                color: "var(--color-primary)",
              }}
            >
              <Tag size={10} />{t}
              <button type="button" onClick={() => setTags((p) => p.filter((x) => x !== t))}
                style={{ background: "none", border: "none", cursor: "pointer", padding: 0, lineHeight: 1 }}>Ã—</button>
            </span>
          ))}
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <input className="form-input" style={{ flex: 1 }} value={tagInput}
            onChange={(e) => setTagInput(e.target.value)} placeholder="Add tagâ€¦"
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addTag(); } }} />
          <button type="button" className="btn btn-secondary" onClick={addTag}>Add</button>
        </div>
      </div>
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
        <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={isSaving || !text.trim()}>
          {isSaving ? <Loader2 size={14} className="spin" /> : null}
          {initial?.id ? "Update" : "Add"}
        </button>
      </div>
    </form>
  );
}

// â”€â”€ Step 3.5: Skills â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function StepSkills({
  allSkills,
  selectedSkills,
  setSelectedSkills,
}: {
  allSkills: Skill[];
  selectedSkills: { skill_id: number; position: number }[];
  setSelectedSkills: React.Dispatch<React.SetStateAction<{ skill_id: number; position: number }[]>>;
}) {
  const [attachId, setAttachId] = useState<string>("");

  // Map skill_id to full Skill object for easy access
  const skillsMap = new Map(allSkills.map((s) => [s.id, s]));

  // Get currently attached skills in correct order
  const attachedList = [...selectedSkills]
    .sort((a, b) => a.position - b.position)
    .map((item) => skillsMap.get(item.skill_id))
    .filter((s): s is Skill => !!s);

  // Available skills that are not yet attached
  const attachedSet = new Set(selectedSkills.map((s) => s.skill_id));
  const availableList = allSkills.filter((s) => !attachedSet.has(s.id));

  const handleAttach = () => {
    if (!attachId) return;
    const id = parseInt(attachId, 10);
    setSelectedSkills((prev) => [
      ...prev,
      { skill_id: id, position: prev.length },
    ]);
    setAttachId("");
  };

  const handleDetach = (skillId: number) => {
    setSelectedSkills((prev) =>
      prev
        .filter((s) => s.skill_id !== skillId)
        .map((s, idx) => ({ ...s, position: idx }))
    );
  };

  const handleMove = (index: number, direction: "up" | "down") => {
    const list = [...attachedList];
    const targetIndex = direction === "up" ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= list.length) return;

    // Swap elements
    const temp = list[index];
    list[index] = list[targetIndex];
    list[targetIndex] = temp;

    setSelectedSkills(
      list.map((s, idx) => ({ skill_id: s.id, position: idx }))
    );
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Search / Attach section */}
      <div style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", borderRadius: 8, padding: 16 }}>
        <div style={{ fontWeight: 600, fontSize: "0.875rem", marginBottom: 12 }}>Attach Skill from Library</div>
        <div style={{ display: "flex", gap: 12 }}>
          <select
            className="form-input"
            style={{ flex: 1 }}
            value={attachId}
            onChange={(e) => setAttachId(e.target.value)}
          >
            <option value="">â€” Select a skill to attach â€”</option>
            {availableList.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.description})
              </option>
            ))}
          </select>
          <button className="btn btn-primary" onClick={handleAttach} disabled={!attachId} type="button">
            <Plus size={14} /> Attach
          </button>
        </div>
      </div>

      {/* Attached skills list */}
      <div>
        <div style={{ fontWeight: 600, fontSize: "0.875rem", marginBottom: 12 }}>Attached Skills ({attachedList.length})</div>
        {attachedList.length === 0 ? (
          <div style={{ padding: 24, textAlign: "center", border: "1px dashed var(--color-border)", borderRadius: 8, color: "var(--color-text-muted)", fontSize: "0.85rem" }}>
            No skills attached to this agent. The agent will only use its system prompt and direct tools.
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {attachedList.map((skill, index) => (
              <div
                key={skill.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "10px 14px",
                  background: "var(--color-background)",
                  border: "1px solid var(--color-border)",
                  borderRadius: 8,
                }}
              >
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <div style={{ fontWeight: 500, fontSize: "0.875rem", display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ fontSize: "0.72rem", background: "var(--color-border)", color: "var(--color-text-muted)", padding: "1px 6px", borderRadius: 4, fontWeight: 600 }}>
                      {index + 1}
                    </span>
                    {skill.name}
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
                    {skill.description}
                  </div>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  {/* Reordering buttons */}
                  <button
                    className="btn btn-secondary btn-xs"
                    title="Move up"
                    disabled={index === 0}
                    onClick={() => handleMove(index, "up")}
                    type="button"
                    style={{ padding: "2px 6px", minHeight: 0 }}
                  >
                    â†‘
                  </button>
                  <button
                    className="btn btn-secondary btn-xs"
                    title="Move down"
                    disabled={index === attachedList.length - 1}
                    onClick={() => handleMove(index, "down")}
                    type="button"
                    style={{ padding: "2px 6px", minHeight: 0 }}
                  >
                    â†“
                  </button>
                  <button
                    className="btn-icon btn-icon-danger btn-icon-sm"
                    title="Detach skill"
                    onClick={() => handleDetach(skill.id)}
                    type="button"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// â”€â”€ Step 4: Context + Test â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function StepContext({
  agentId,
  form,
}: {
  agentId: number | null;
  form: AgentForm;
}) {
  const toast = useToast();
  const { data: contextEntries = [], isLoading: ctxLoading } = useAgentContext(agentId);
  const createCtx = useCreateAgentContext();
  const updateCtx = useUpdateAgentContext();
  const deleteCtx = useDeleteAgentContext();

  const [showCtxForm, setShowCtxForm] = useState(false);
  const [editingCtx, setEditingCtx] = useState<AgentContextEntry | null>(null);

  const [testMessage, setTestMessage] = useState("");
  const [testResponse, setTestResponse] = useState("");
  const [testing, setTesting] = useState(false);

  async function handleCtxSave(data: { text: string; tags: string[] }) {
    if (!agentId) return;
    try {
      if (editingCtx) {
        await updateCtx.mutateAsync({ agentId, entryId: editingCtx.id, payload: data });
        toast.success("Context entry updated");
        setEditingCtx(null);
      } else {
        await createCtx.mutateAsync({ agentId, payload: data });
        toast.success("Context entry added");
        setShowCtxForm(false);
      }
    } catch {
      toast.error("Failed to save context entry");
    }
  }

  async function handleCtxDelete(entry: AgentContextEntry) {
    if (!agentId || !confirm(`Delete this context entry?`)) return;
    try {
      await deleteCtx.mutateAsync({ agentId, entryId: entry.id });
      toast.success("Entry deleted");
    } catch {
      toast.error("Failed to delete");
    }
  }

  async function runTest() {
    if (!agentId || !testMessage.trim()) return;
    setTesting(true);
    setTestResponse("");
    try {
      const sessionRes = await api.post(
        `/agents/${agentId}/sessions`,
        {}
      );
      const sessionId = sessionRes.data.id;

      const baseUrl = (import.meta.env.VITE_API_BASE_URL || "/api/v1").replace(/\/$/, "");
      const match = window.location.pathname.match(/^\/w\/([^/]+)/);
      const workspaceSlug = match ? match[1] : null;
      const url = `${baseUrl}/agents/${agentId}/sessions/${sessionId}/stream${workspaceSlug ? `?workspace=${workspaceSlug}` : ""}`;
      const authkey = getAuthKey();
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (authkey) {
        headers["authkey"] = authkey;
        headers["Authorization"] = `Bearer ${authkey}`;
      }
      if (workspaceSlug) headers["X-Workspace-Slug"] = workspaceSlug;

      const response = await fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify({ content: testMessage.trim(), sandbox: true }),
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) return;

      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        for (const line of chunk.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          try {
            const ev = JSON.parse(line.slice(6));
            if (ev.type === "text" && ev.delta) buf += ev.delta;
            if (ev.type === "tool_start") buf += `\n[Calling ${ev.tool_name}â€¦]\n`;
            if (ev.type === "error") buf += `\n[Error: ${ev.error}]\n`;
          } catch { /* skip malformed */ }
        }
        setTestResponse(buf);
      }
    } catch (err) {
      setTestResponse(`Error: ${err}`);
    } finally {
      setTesting(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Context flow banner */}
      <div
        style={{
          padding: "12px 16px",
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: 8,
          fontSize: "0.8rem",
          color: "var(--color-text-muted)",
        }}
      >
        System prompt order: <strong style={{ color: "var(--color-text)" }}>Shared context</strong>
        {" â†’ "}<strong style={{ color: "var(--color-text)" }}>Agent context (below)</strong>
        {" â†’ "}<strong style={{ color: "var(--color-text)" }}>System prompt</strong> (Step 1)
      </div>

      {/* Agent context entries */}
      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <div style={{ fontWeight: 600, fontSize: "0.875rem", display: "flex", alignItems: "center", gap: 6 }}>
            <BookOpen size={14} color="var(--color-primary)" />
            Agent Context
            {!agentId && (
              <span style={{ fontWeight: 400, fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
                (save agent first)
              </span>
            )}
          </div>
          {agentId && !showCtxForm && !editingCtx && (
            <button className="btn btn-secondary" style={{ fontSize: "0.78rem" }} onClick={() => setShowCtxForm(true)}>
              <Plus size={13} /> Add Entry
            </button>
          )}
        </div>

        {(showCtxForm || editingCtx) && (
          <div
            style={{
              padding: "16px", background: "var(--color-surface)",
              border: "1px solid var(--color-border)", borderRadius: 8, marginBottom: 12,
            }}
          >
            <div style={{ fontWeight: 500, fontSize: "0.8rem", marginBottom: 12 }}>
              {editingCtx ? "Edit Entry" : "New Context Entry"}
            </div>
            <AgentContextForm
              initial={editingCtx ?? undefined}
              onSave={handleCtxSave}
              onCancel={() => { setShowCtxForm(false); setEditingCtx(null); }}
              isSaving={createCtx.isPending || updateCtx.isPending}
            />
          </div>
        )}

        {ctxLoading ? (
          <div style={{ fontSize: "0.8rem", color: "var(--color-text-muted)", display: "flex", gap: 6 }}>
            <Loader2 size={13} className="spin" /> Loadingâ€¦
          </div>
        ) : !agentId ? (
          <div style={{ fontSize: "0.8rem", color: "var(--color-text-muted)", padding: "12px 0" }}>
            Save the agent to manage context entries.
          </div>
        ) : contextEntries.length === 0 && !showCtxForm ? (
          <div style={{ fontSize: "0.8rem", color: "var(--color-text-muted)", padding: "12px 0" }}>
            No agent context entries yet. Add entries to inject agent-specific knowledge.
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {contextEntries.map((entry) => (
              <div
                key={entry.id}
                style={{
                  padding: "12px 14px", background: "var(--color-surface)",
                  border: "1px solid var(--color-border)", borderRadius: 8,
                }}
              >
                <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                  <div style={{ flex: 1 }}>
                    <div
                      style={{
                        fontSize: "0.8rem", color: "var(--color-text)",
                        whiteSpace: "pre-wrap", maxHeight: 64, overflow: "hidden",
                      }}
                    >
                      {entry.text}
                    </div>
                    <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 6, alignItems: "center" }}>
                      <span style={{ fontSize: "0.7rem", color: "var(--color-text-muted)" }}>v{entry.version}</span>
                      {entry.tags.map((t) => (
                        <span
                          key={t}
                          style={{
                            display: "inline-flex", alignItems: "center", gap: 3,
                            padding: "1px 7px", borderRadius: 12, fontSize: "0.7rem",
                            background: "var(--color-primary-subtle, rgba(27,110,243,0.1))",
                            color: "var(--color-primary)",
                          }}
                        >
                          <Tag size={9} />{t}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="row-actions">
                    <button className="btn-icon" title="Edit"
                      onClick={() => { setEditingCtx(entry); setShowCtxForm(false); }}>
                      <Edit2 size={13} />
                    </button>
                    <button className="btn-icon btn-icon-danger" title="Delete"
                      onClick={() => handleCtxDelete(entry)}>
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Test chat */}
      <div>
        <div style={{ fontWeight: 600, fontSize: "0.875rem", marginBottom: 12 }}>
          Test Chat
          {!agentId && (
            <span style={{ marginLeft: 8, fontWeight: 400, fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
              (save agent first)
            </span>
          )}
        </div>
        <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
          <input
            className="form-input"
            style={{ flex: 1 }}
            placeholder={agentId ? "Type a test messageâ€¦" : "Save agent first"}
            value={testMessage}
            onChange={(e) => setTestMessage(e.target.value)}
            disabled={!agentId || testing}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); runTest(); } }}
          />
          <button
            className="btn btn-primary"
            onClick={runTest}
            disabled={!agentId || !testMessage.trim() || testing}
          >
            {testing ? <Loader2 size={14} className="spin" /> : <MessageSquare size={14} />}
            Send
          </button>
        </div>
        {testResponse && (
          <div
            style={{
              padding: "12px 14px",
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: 8,
              fontSize: "0.8rem",
              whiteSpace: "pre-wrap",
              maxHeight: 320,
              overflowY: "auto",
              fontFamily: "monospace",
            }}
          >
            {testResponse}
          </div>
        )}
      </div>
    </div>
  );
}

// â”€â”€ Main component â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

interface AgentForm {
  name: string;
  description: string;
  avatar: string;
  color: string;
  prompt: string;
  model: string;
  max_tokens: number;
  is_orchestrator: boolean;
  visibility: "shared" | "private";
  llm_connection_id?: number;
}

export default function AgentBuilderPage() {
  const { agentId: agentIdStr } = useParams<{ agentId?: string }>();
  const editingId = agentIdStr ? parseInt(agentIdStr, 10) : null;
  const isEditing = editingId != null;

  const navigate = useScopedNavigate();
  const toast = useToast();
  const [step, setStep] = useState(0);

  const { data: existingAgent } = useAgent(editingId);
  const { data: llmConnections = [] } = useLLMConnections();
  const { data: dbConnections = [] } = useDBConnections();
  const { data: gitConnections = [] } = useGitConnections();
  const { data: allSkills = [] } = useSkills();

  const createMutation = useCreateAgent();
  const updateMutation = useUpdateAgent();

  const [form, setForm] = useState<AgentForm>({
    name: "",
    description: "",
    avatar: "",
    color: "",
    prompt: "",
    model: "claude-sonnet-4-6",
    max_tokens: 8096,
    is_orchestrator: false,
    visibility: "shared",
  });
  const [selectedTools, setSelectedTools] = useState<string[]>([]);
  const [selectedDBs, setSelectedDBs] = useState<AgentDBConnection[]>([]);
  const [selectedGits, setSelectedGits] = useState<{ git_connection_id: number }[]>([]);
  const [selectedSkills, setSelectedSkills] = useState<{ skill_id: number; position: number }[]>([]);
  const [savedAgentId, setSavedAgentId] = useState<number | null>(editingId);

  // Populate form when editing
  useEffect(() => {
    if (existingAgent) {
      setForm({
        name: existingAgent.name,
        description: existingAgent.description ?? "",
        avatar: existingAgent.avatar ?? "",
        color: existingAgent.color ?? "",
        prompt: existingAgent.prompt ?? "",
        model: existingAgent.model ?? "claude-sonnet-4-6",
        max_tokens: existingAgent.max_tokens ?? 8096,
        is_orchestrator: existingAgent.is_orchestrator ?? false,
        visibility: existingAgent.visibility,
        llm_connection_id: existingAgent.llm_connection_id,
        manifest: (existingAgent as any).manifest ?? undefined,
      });
      setSelectedTools(existingAgent.tools.map((t) => t.tool_name));
      setSelectedDBs(existingAgent.db_connections);
      setSelectedGits((existingAgent as any).git_connections ?? []);
      setSelectedSkills((existingAgent.skills ?? []).map((s) => ({ skill_id: s.skill_id, position: s.position })));
    }
  }, [existingAgent]);

  async function handleSave() {
    const payload = {
      name: form.name.trim(),
      description: form.description.trim() || undefined,
      avatar: form.avatar.trim() || undefined,
      color: form.color.trim() || undefined,
      prompt: form.prompt.trim() || undefined,
      model: form.model || 'claude-sonnet-4-6',
      max_tokens: form.max_tokens,
      is_orchestrator: form.is_orchestrator,
      visibility: form.visibility,
      manifest: (form as any).manifest || undefined,
      llm_connection_id: form.llm_connection_id,
      tools: selectedTools.map((key) => ({ tool_name: key })),
      db_connections: selectedDBs,
      git_connections: selectedGits,
      skills: selectedSkills.map((s, idx) => ({ skill_id: s.skill_id, position: idx })),
    };
    try {
      if (isEditing && savedAgentId) {
        await updateMutation.mutateAsync({ agentId: savedAgentId, payload });
        toast.success("Agent updated");
      } else {
        const agent = await createMutation.mutateAsync({ payload });
        setSavedAgentId(agent.id);
        toast.success(`Agent "${agent.name}" created`);
      }
    } catch {
      toast.error("Failed to save agent");
    }
  }

  const isSaving = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="page-section" style={{ maxWidth: 800, margin: "0 auto" }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">{isEditing ? "Edit Agent" : "New Agent"}</h1>
          <p className="page-subtitle">
            {isEditing ? `Editing: ${existingAgent?.name ?? "â€¦"}` : "Configure your AI agent step by step."}
          </p>
        </div>
      </div>

      <div style={{ marginBottom: 32 }}>
        <PageTabs
          tabs={BUILDER_TABS}
          value={BUILDER_TAB_VALUES[step]}
          onChange={(value) => setStep(BUILDER_TAB_VALUES.indexOf(value))}
        />
      </div>

      <div style={{ minHeight: 400 }}>
        {step === 0 && (
          <StepDefine form={form} setForm={setForm} llmConnections={llmConnections} />
        )}
        {step === 1 && (
          <StepTools selectedTools={selectedTools} setSelectedTools={setSelectedTools} />
        )}
        {step === 2 && (
          <StepData
            dbConnections={dbConnections}
            selectedDBs={selectedDBs}
            setSelectedDBs={setSelectedDBs}
            gitConnections={gitConnections}
            selectedGits={selectedGits}
            setSelectedGits={setSelectedGits}
          />
        )}
        {step === 3 && (
          <StepSkills
            allSkills={allSkills}
            selectedSkills={selectedSkills}
            setSelectedSkills={setSelectedSkills}
          />
        )}
        {step === 4 && (
          <StepContext
            agentId={savedAgentId}
            form={form}
          />
        )}
      </div>

      <div
        style={{
          display: "flex",
          justifyContent: "flex-end",
          marginTop: 32,
          paddingTop: 20,
          borderTop: "1px solid var(--color-border)",
        }}
      >
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-secondary" onClick={handleSave} disabled={isSaving || !form.name.trim()}>
            {isSaving ? <Loader2 size={14} className="spin" /> : <Save size={14} />}
            Save
          </button>
          <button
            className="btn btn-primary"
            onClick={async () => {
              await handleSave();
              if (savedAgentId) {
                navigate(`/agents/${savedAgentId}/chat`);
              } else {
                navigate(`/agents`);
              }
            }}
            disabled={isSaving || !form.name.trim()}
          >
            <MessageSquare size={14} />
            {savedAgentId ? "Go to Chat" : "Save & Finish"}
          </button>
        </div>
      </div>
    </div>
  );
}


