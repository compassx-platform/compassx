import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useScopedNavigate } from "@/lib/appNavigation";
import {
  Bot,
  Plus,
  Search,
  Trash2,
  Copy,
  MessageSquare,
  Settings2,
  Loader2,
  Zap,
  CheckCircle2,
  XCircle,
  Radio,
  Eye,
  Terminal,
  Calendar,
  Filter,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { PageTabs } from "@/components/common/PageTabs";
import { AppTable, type AppTableColumn } from "@/components/common/AppTable";
import { useAgents, useDeleteAgent, useCloneAgent, type AgentListItem } from "@/modules/agents/hooks/useAgents";
import { useActiveStreams, type ActiveStream } from "@/modules/agents/hooks/useActiveStreams";
import { AVAILABLE_TOOLS, type AvailableToolInfo } from "@/modules/agents/toolCatalog";
import { useToast } from "@/lib/toast";
import {
  useSkills,
  useCreateSkill,
  useUpdateSkill,
  useDeleteSkill,
  type Skill,
} from "@/modules/agents/hooks/useSkills";
import {
  useLlmCallLogs,
  useLlmCallLogDetail,
  type LlmCallLogListItem,
  type LlmCallLogDetail,
} from "@/modules/agents/hooks/useLlmCalls";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import { Bold, Italic, List, ListOrdered, Code, Sparkles, Tags, FileText, ChevronRight } from "lucide-react";
import { BudgetsTab } from "../components/BudgetsTab";
import { UsageTab } from "../components/UsageTab";

type AgentsPageTab = "agents" | "tools" | "skills" | "streams" | "llm_calls" | "budgets" | "usage";

const AGENTS_PAGE_TABS = [
  { value: "agents", label: "Agents" },
  { value: "tools", label: "Tools" },
  { value: "skills", label: "Skills Library" },
  { value: "streams", label: "Active Streams" },
  { value: "llm_calls", label: "LLM Call Logs" },
  { value: "budgets", label: "Budgets" },
  { value: "usage", label: "Usage" },
] as const;

function VisibilityBadge({ visibility }: { visibility: string }) {
  const map: Record<string, { label: string; color: string; bg: string }> = {
    shared:  { label: "Shared",  color: "#1B6EF3", bg: "#E8F1FF" },
    private: { label: "Private", color: "#6B6B6B", bg: "#F0F0F0" },
  };
  const cfg = map[visibility] ?? map.private;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: "2px 8px",
        borderRadius: 4,
        fontSize: "0.72rem",
        fontWeight: 600,
        color: cfg.color,
        background: cfg.bg,
      }}
    >
      {cfg.label}
    </span>
  );
}

function AgentsTable({
  agents,
  isLoading,
  error,
  onCreate,
  onChat,
  onEdit,
  onClone,
  onDelete,
  clonePending,
}: {
  agents: AgentListItem[];
  isLoading: boolean;
  error: unknown;
  onCreate: () => void;
  onChat: (agent: AgentListItem) => void;
  onEdit: (agent: AgentListItem) => void;
  onClone: (e: React.MouseEvent, agent: AgentListItem) => void;
  onDelete: (e: React.MouseEvent, agent: AgentListItem) => void;
  clonePending: boolean;
}) {
  const columns: AppTableColumn<AgentListItem>[] = [
    {
      key: 'name',
      header: 'Name',
      width: '30%',
      render: (agent) => (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Bot size={14} color="var(--color-primary)" style={{ flexShrink: 0 }} />
            <span style={{ fontWeight: 500, fontSize: '0.875rem' }}>{agent.name}</span>
          </div>
          {agent.description && (
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: 3, paddingLeft: 22 }}>
              {agent.description}
            </div>
          )}
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      width: '14%',
      render: (agent) => (
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            padding: '2px 8px',
            borderRadius: 4,
            fontSize: '0.72rem',
            fontWeight: 600,
            color: agent.is_active ? '#2E7D32' : '#6B6B6B',
            background: agent.is_active ? '#E8F5E9' : '#F0F0F0',
          }}
        >
          {agent.is_active ? <CheckCircle2 size={11} /> : <XCircle size={11} />}
          {agent.is_active ? 'Active' : 'Inactive'}
        </span>
      ),
    },
    {
      key: 'visibility',
      header: 'Visibility',
      width: '14%',
      render: (agent) => <VisibilityBadge visibility={agent.visibility} />,
    },
    {
      key: 'tools',
      header: 'Tools',
      width: '12%',
      render: (agent) => (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: '0.8rem' }}>
          <Zap size={12} color="var(--color-text-muted)" />
          {agent.tool_count}
        </span>
      ),
    },
    {
      key: 'updated',
      header: 'Updated',
      width: '14%',
      render: (agent) => <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>{new Date(agent.updated_at).toLocaleDateString()}</span>,
    },
    {
      key: 'actions',
      header: '',
      width: '16%',
      align: 'right',
      render: (agent) => (
        <div className="row-actions" onClick={(e) => e.stopPropagation()}>
          <button className="btn-icon" title="Chat" onClick={() => onChat(agent)}>
            <MessageSquare size={14} />
          </button>
          <button className="btn-icon" title="Edit" onClick={() => onEdit(agent)}>
            <Settings2 size={14} />
          </button>
          <button className="btn-icon" title="Clone" onClick={(e) => onClone(e, agent)} disabled={clonePending}>
            <Copy size={14} />
          </button>
          <button className="btn-icon btn-icon-danger" title="Delete" onClick={(e) => onDelete(e, agent)}>
            <Trash2 size={14} />
          </button>
        </div>
      ),
    },
  ];

  if (isLoading) return <div className="table-empty"><Loader2 size={20} className="spin" /> Loading...</div>;
  if (error) return <div className="table-empty error">Failed to load agents.</div>;
  if (agents.length === 0) {
    return <div className="table-empty"><Bot size={32} style={{ opacity: 0.3, marginBottom: 8 }} /><div>No agents yet.</div><button className="btn btn-secondary" style={{ marginTop: 12 }} onClick={onCreate}><Plus size={14} /> Create your first agent</button></div>;
  }

  return <AppTable columns={columns} rows={agents} rowKey={(agent) => agent.id} onRowClick={(agent) => onChat(agent)} />;
}function ToolsTab() {
  const navigate = useScopedNavigate();
  const columns: AppTableColumn<AvailableToolInfo>[] = [
    {
      key: "name",
      header: "Tool Name",
      width: "30%",
      render: (tool) => (
        <div>
          <div style={{ fontWeight: 500, fontSize: "0.875rem" }}>{tool.name}</div>
          <div style={{ fontSize: "0.72rem", color: "var(--color-text-muted)", marginTop: 1 }}>{tool.key}</div>
        </div>
      ),
    },
    {
      key: "description",
      header: "Description",
      render: (tool) => <span style={{ color: "var(--color-text-muted)" }}>{tool.description}</span>,
    },
  ];

  return (
    <AppTable
      columns={columns}
      rows={AVAILABLE_TOOLS}
      rowKey={(tool) => tool.key}
      onRowClick={(tool) => navigate(`/agents/tools/${tool.key}`)}
      emptyText="No tools found."
    />
  );
}

function formatDuration(startedAt: string) {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ${seconds % 60}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

function ActiveStreamsTab({ agents }: { agents: AgentListItem[] }) {
  const { data: streams = [], isLoading, error, refetch, isFetching } = useActiveStreams();
  const agentNameById = new Map(agents.map((agent) => [agent.id, agent.name]));

  const columns: AppTableColumn<ActiveStream>[] = [
    {
      key: "kind",
      header: "Type",
      width: "12%",
      render: (stream) => (
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontWeight: 600 }}>
          <Radio size={13} color="#2563eb" />
          Agent
        </span>
      ),
    },
    {
      key: "agent",
      header: "Agent / Session",
      width: "24%",
      render: (stream) => (
        <div>
          <div style={{ fontWeight: 500 }}>
            {stream.agent_id ? agentNameById.get(stream.agent_id) ?? `Agent ${stream.agent_id}` : "Agent"}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
            {stream.session_id ? `Session ${stream.session_id}` : "No session"}
          </div>
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      width: "14%",
      render: (stream) => (
        <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "#166534", background: "#dcfce7", padding: "2px 8px", borderRadius: 4 }}>
          {stream.status}
        </span>
      ),
    },
    {
      key: "detail",
      header: "Last Event",
      render: (stream) => <span style={{ color: "var(--color-text-muted)" }}>{stream.detail ?? "-"}</span>,
    },
    {
      key: "duration",
      header: "Duration",
      width: "12%",
      render: (stream) => formatDuration(stream.started_at),
    },
    {
      key: "updated",
      header: "Updated",
      width: "16%",
      render: (stream) => new Date(stream.updated_at).toLocaleTimeString(),
    },
  ];

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <div style={{ fontSize: "0.82rem", color: "var(--color-text-muted)" }}>
          Shows backend streams still running in this backend process. Refreshes every 5 seconds.
        </div>
        <button className="btn btn-secondary" onClick={() => refetch()} disabled={isFetching}>
          {isFetching ? <Loader2 size={14} className="spin" /> : <Radio size={14} />}
          Refresh
        </button>
      </div>
      {isLoading ? (
        <div className="table-empty"><Loader2 size={20} className="spin" /> Loading active streams...</div>
      ) : error ? (
        <div className="table-empty error">Failed to load active streams.</div>
      ) : (
        <AppTable
          columns={columns}
          rows={streams}
          rowKey={(stream) => stream.id}
          emptyText="No active streams."
        />
      )}
    </div>
  );
}

function SkillsTab() {
  const { data: skills = [], isLoading, error } = useSkills();
  const createMutation = useCreateSkill();
  const updateMutation = useUpdateSkill();
  const deleteMutation = useDeleteSkill();
  const toast = useToast();

  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  // Form states
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [triggerHints, setTriggerHints] = useState("");

  const editor = useEditor({
    extensions: [
      StarterKit,
      Placeholder.configure({
        placeholder: "Write step-by-step procedural guidelines here...",
      }),
    ],
    content: "",
  });

  const handleSelectSkill = (skill: Skill) => {
    setSelectedSkill(skill);
    setIsEditing(true);
    setIsCreating(false);
    setName(skill.name);
    setDescription(skill.description);
    setTriggerHints(skill.trigger_hints.join(", "));
    editor?.commands.setContent(skill.body);
  };

  const handleNewSkill = () => {
    setSelectedSkill(null);
    setIsEditing(false);
    setIsCreating(true);
    setName("");
    setDescription("");
    setTriggerHints("");
    editor?.commands.clearContent();
  };

  const handleSave = async () => {
    if (!name.trim()) {
      toast.error("Skill name is required");
      return;
    }
    const hintsArray = triggerHints
      .split(",")
      .map((h) => h.trim())
      .filter((h) => h.length > 0);

    const bodyHtml = editor?.getHTML() || "";

    try {
      if (isCreating) {
        await createMutation.mutateAsync({
          name: name.trim(),
          description: description.trim(),
          body: bodyHtml,
          trigger_hints: hintsArray,
        });
        toast.success("Skill created successfully");
        setIsCreating(false);
      } else if (selectedSkill) {
        await updateMutation.mutateAsync({
          skillId: selectedSkill.id,
          payload: {
            name: name.trim(),
            description: description.trim(),
            body: bodyHtml,
            trigger_hints: hintsArray,
          },
        });
        toast.success("Skill updated successfully");
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Failed to save skill");
    }
  };

  const handleDelete = async (skillId: number) => {
    if (!confirm("Are you sure you want to delete this skill? It will be detached from all agents.")) return;
    try {
      await deleteMutation.mutateAsync(skillId);
      toast.success("Skill deleted");
      if (selectedSkill?.id === skillId || isCreating) {
        setSelectedSkill(null);
        setIsEditing(false);
        setIsCreating(false);
      }
    } catch {
      toast.error("Failed to delete skill");
    }
  };

  const columns: AppTableColumn<Skill>[] = [
    {
      key: "name",
      header: "Skill Name",
      width: "30%",
      render: (skill) => (
        <div>
          <div style={{ fontWeight: 500, fontSize: "0.875rem" }}>{skill.name}</div>
          <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
            Version {skill.version}
          </div>
        </div>
      ),
    },
    {
      key: "description",
      header: "Description",
      width: "45%",
      render: (skill) => (
        <div style={{ color: "var(--color-text-muted)", fontSize: "0.82rem" }}>
          {skill.description}
        </div>
      ),
    },
    {
      key: "trigger_hints",
      header: "Trigger Hints",
      render: (skill) => (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {skill.trigger_hints.map((hint, i) => (
            <span
              key={i}
              style={{
                fontSize: "0.7rem",
                background: "#f3f4f6",
                color: "#4b5563",
                padding: "2px 6px",
                borderRadius: 4,
              }}
            >
              {hint}
            </span>
          ))}
        </div>
      ),
    },
    {
      key: "actions",
      header: "",
      width: "10%",
      render: (skill) => (
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }} onClick={(e) => e.stopPropagation()}>
          <button className="btn-icon btn-icon-danger" title="Delete" onClick={() => handleDelete(skill.id)}>
            <Trash2 size={14} />
          </button>
        </div>
      ),
    },
  ];

  return (
    <div style={{ display: "flex", gap: 24, marginTop: 16, height: "calc(100vh - 280px)" }}>
      {/* Left panel: List / table of skills */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", borderRight: "1px solid var(--color-border)", paddingRight: 24, overflowY: "auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <div style={{ fontSize: "0.875rem", fontWeight: 600 }}>Skills Library</div>
          <button className="btn btn-secondary btn-sm" onClick={handleNewSkill}>
            <Plus size={14} /> New Skill
          </button>
        </div>

        {isLoading ? (
          <div className="table-empty"><Loader2 size={20} className="spin" /> Loading skills...</div>
        ) : error ? (
          <div className="table-empty error">Failed to load skills library.</div>
        ) : skills.length === 0 ? (
          <div className="table-empty">
            <Sparkles size={32} style={{ opacity: 0.3, marginBottom: 8 }} />
            <div>No skills found. Create one to get started.</div>
          </div>
        ) : (
          <AppTable
            columns={columns}
            rows={skills}
            rowKey={(skill) => skill.id}
            onRowClick={handleSelectSkill}
            emptyText="No skills found."
          />
        )}
      </div>

      {/* Right panel: Editor */}
      <div style={{ width: 480, display: "flex", flexDirection: "column", overflowY: "auto" }}>
        {(!isEditing && !isCreating) ? (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", border: "1px dashed var(--color-border)", borderRadius: 8, color: "var(--color-text-muted)", padding: 24 }}>
            <FileText size={36} style={{ opacity: 0.2, marginBottom: 8 }} />
            <div style={{ fontSize: "0.85rem" }}>Select a skill from the list or click "New Skill" to write step-by-step instructions.</div>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ fontSize: "1rem", fontWeight: 600, margin: 0 }}>
                {isCreating ? "New Skill" : `Edit Skill: ${selectedSkill?.name}`}
              </h3>
              <div style={{ display: "flex", gap: 8 }}>
                <button className="btn btn-secondary btn-sm" onClick={() => { setIsEditing(false); setIsCreating(false); }}>
                  Cancel
                </button>
                <button className="btn btn-primary btn-sm" onClick={handleSave} disabled={createMutation.isPending || updateMutation.isPending}>
                  {(createMutation.isPending || updateMutation.isPending) ? <Loader2 size={12} className="spin" /> : "Save"}
                </button>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Skill Name</label>
              <input
                className="form-control"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Create Work Order"
              />
            </div>

            <div className="form-group">
              <label className="form-label">Description</label>
              <textarea
                className="form-control"
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Briefly describe when this skill should be executed..."
              />
            </div>

            <div className="form-group">
              <label className="form-label">Trigger Hints</label>
              <div style={{ display: "flex", alignItems: "center", gap: 8, background: "#f9fafb", padding: "4px 8px", borderRadius: 6, border: "1px solid var(--color-border)" }}>
                <Tags size={14} color="#6b7280" />
                <input
                  className="search-input"
                  style={{ border: "none", outline: "none", width: "100%", background: "transparent", fontSize: "0.875rem" }}
                  value={triggerHints}
                  onChange={(e) => setTriggerHints(e.target.value)}
                  placeholder="e.g. work order, repair log (comma separated)"
                />
              </div>
              <span style={{ fontSize: "0.72rem", color: "var(--color-text-muted)", marginTop: 4, display: "block" }}>
                Provide semantic hints to help the agent matching model select this skill.
              </span>
            </div>

            <div className="form-group">
              <label className="form-label">Procedural Guidelines (Markdown)</label>
              <div style={{ border: "1px solid var(--color-border)", borderRadius: 8, overflow: "hidden", background: "var(--color-background)" }}>
                {/* Editor Toolbar */}
                <div style={{ display: "flex", gap: 4, padding: 8, background: "#f9fafb", borderBottom: "1px solid var(--color-border)" }}>
                  <button
                    className={`btn-icon btn-icon-sm ${editor?.isActive("bold") ? "active" : ""}`}
                    onClick={() => editor?.chain().focus().toggleBold().run()}
                    style={{ background: editor?.isActive("bold") ? "#e5e7eb" : "transparent" }}
                  >
                    <Bold size={13} />
                  </button>
                  <button
                    className={`btn-icon btn-icon-sm ${editor?.isActive("italic") ? "active" : ""}`}
                    onClick={() => editor?.chain().focus().toggleItalic().run()}
                    style={{ background: editor?.isActive("italic") ? "#e5e7eb" : "transparent" }}
                  >
                    <Italic size={13} />
                  </button>
                  <button
                    className={`btn-icon btn-icon-sm ${editor?.isActive("bulletList") ? "active" : ""}`}
                    onClick={() => editor?.chain().focus().toggleBulletList().run()}
                    style={{ background: editor?.isActive("bulletList") ? "#e5e7eb" : "transparent" }}
                  >
                    <List size={13} />
                  </button>
                  <button
                    className={`btn-icon btn-icon-sm ${editor?.isActive("orderedList") ? "active" : ""}`}
                    onClick={() => editor?.chain().focus().toggleOrderedList().run()}
                    style={{ background: editor?.isActive("orderedList") ? "#e5e7eb" : "transparent" }}
                  >
                    <ListOrdered size={13} />
                  </button>
                  <button
                    className={`btn-icon btn-icon-sm ${editor?.isActive("codeBlock") ? "active" : ""}`}
                    onClick={() => editor?.chain().focus().toggleCodeBlock().run()}
                    style={{ background: editor?.isActive("codeBlock") ? "#e5e7eb" : "transparent" }}
                  >
                    <Code size={13} />
                  </button>
                </div>
                {/* Editor Area */}
                <div className="tiptap-editor-container" style={{ padding: "12px 16px", minHeight: 200, maxHeight: 300, overflowY: "auto" }}>
                  <div className="tiptap">
                    <EditorContent editor={editor} />
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function LlmCallLogsTab({ agents }: { agents: AgentListItem[] }) {
  const [selectedAgentId, setSelectedAgentId] = useState<number | undefined>();
  const [sessionIdFilter, setSessionIdFilter] = useState<string>("");
  const [modelFilter, setModelFilter] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const [selectedCallId, setSelectedCallId] = useState<number | null>(null);

  const filters = {
    agent_id: selectedAgentId,
    session_id: sessionIdFilter ? Number(sessionIdFilter) : undefined,
    model: modelFilter || undefined,
    start_date: startDate ? new Date(startDate).toISOString() : undefined,
    end_date: endDate ? new Date(endDate).toISOString() : undefined,
    limit,
    offset,
  };

  const { data: logs = [], isLoading, error, refetch, isFetching } = useLlmCallLogs(filters);

  const handleNextPage = () => {
    if (logs.length === limit) {
      setOffset(prev => prev + limit);
    }
  };

  const handlePrevPage = () => {
    setOffset(prev => Math.max(0, prev - limit));
  };

  const handleResetFilters = () => {
    setSelectedAgentId(undefined);
    setSessionIdFilter("");
    setModelFilter("");
    setStartDate("");
    setEndDate("");
    setOffset(0);
  };

  const columns: AppTableColumn<LlmCallLogListItem>[] = [
    {
      key: "seq",
      header: "Seq #",
      width: "8%",
      render: (log) => (
        <span style={{ fontWeight: 600, color: "var(--color-text-muted)" }}>
          #{log.call_sequence_number}
        </span>
      ),
    },
    {
      key: "agent_name",
      header: "Agent",
      width: "16%",
      render: (log) => (
        <span style={{ fontWeight: 500 }}>
          {log.agent_name || `Agent ${log.agent_id}`}
        </span>
      ),
    },
    {
      key: "session",
      header: "Session",
      width: "10%",
      render: (log) => (
        <span style={{ fontSize: "0.78rem", color: "var(--color-text-muted)" }}>
          {log.session_id ? `#${log.session_id}` : "-"}
        </span>
      ),
    },
    {
      key: "model",
      header: "Model",
      width: "16%",
      render: (log) => (
        <code style={{ fontSize: "0.78rem", background: "var(--color-bg-light)", padding: "2px 6px", borderRadius: 4 }}>
          {log.model}
        </code>
      ),
    },
    {
      key: "summary",
      header: "Response Summary",
      width: "28%",
      render: (log) => (
        <span style={{ color: "var(--color-text-muted)", fontSize: "0.8rem", wordBreak: "break-all" }}>
          {log.summary || "-"}
        </span>
      ),
    },
    {
      key: "tokens",
      header: "Tokens (I/O)",
      width: "10%",
      render: (log) => (
        <span style={{ fontSize: "0.78rem" }}>
          {log.input_tokens ?? 0} / {log.output_tokens ?? 0}
        </span>
      ),
    },
    {
      key: "created_at",
      header: "Time",
      width: "8%",
      render: (log) => (
        <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
          {new Date(log.created_at).toLocaleTimeString()}
        </span>
      ),
    },
    {
      key: "actions",
      header: "",
      width: "4%",
      render: (log) => (
        <button
          className="btn-icon"
          title="Inspect Call"
          onClick={() => setSelectedCallId(log.id)}
        >
          <Eye size={14} />
        </button>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <div style={{ fontSize: "0.82rem", color: "var(--color-text-muted)" }}>
          Audit trail of agent LLM connection invocations, prompt assembly, and response token metrics.
        </div>
        <button className="btn btn-secondary btn-sm" onClick={() => refetch()} disabled={isFetching}>
          {isFetching && <Loader2 size={12} className="spin" />}
          Refresh
        </button>
      </div>

      {/* Filters Row */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", background: "#f9fafb", padding: 12, borderRadius: 8, border: "1px solid var(--color-border)", marginBottom: 16 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <label style={{ fontSize: "0.72rem", fontWeight: 600, color: "var(--color-text-muted)" }}>Agent</label>
          <select
            className="form-control"
            style={{ height: 32, padding: "0 8px", fontSize: "0.8rem", minWidth: 150 }}
            value={selectedAgentId || ""}
            onChange={(e) => {
              setSelectedAgentId(e.target.value ? Number(e.target.value) : undefined);
              setOffset(0);
            }}
          >
            <option value="">All Agents</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <label style={{ fontSize: "0.72rem", fontWeight: 600, color: "var(--color-text-muted)" }}>Session ID</label>
          <input
            type="number"
            className="form-control"
            style={{ height: 32, padding: "0 8px", fontSize: "0.8rem", width: 100 }}
            placeholder="Session #"
            value={sessionIdFilter}
            onChange={(e) => {
              setSessionIdFilter(e.target.value);
              setOffset(0);
            }}
          />
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <label style={{ fontSize: "0.72rem", fontWeight: 600, color: "var(--color-text-muted)" }}>Model</label>
          <input
            className="form-control"
            style={{ height: 32, padding: "0 8px", fontSize: "0.8rem", width: 130 }}
            placeholder="Search model..."
            value={modelFilter}
            onChange={(e) => {
              setModelFilter(e.target.value);
              setOffset(0);
            }}
          />
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <label style={{ fontSize: "0.72rem", fontWeight: 600, color: "var(--color-text-muted)" }}>Start Date</label>
          <input
            type="datetime-local"
            className="form-control"
            style={{ height: 32, padding: "0 8px", fontSize: "0.8rem", width: 150 }}
            value={startDate}
            onChange={(e) => {
              setStartDate(e.target.value);
              setOffset(0);
            }}
          />
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <label style={{ fontSize: "0.72rem", fontWeight: 600, color: "var(--color-text-muted)" }}>End Date</label>
          <input
            type="datetime-local"
            className="form-control"
            style={{ height: 32, padding: "0 8px", fontSize: "0.8rem", width: 150 }}
            value={endDate}
            onChange={(e) => {
              setEndDate(e.target.value);
              setOffset(0);
            }}
          />
        </div>

        <div style={{ display: "flex", alignItems: "flex-end", gap: 8 }}>
          <button className="btn btn-secondary btn-sm" style={{ height: 32 }} onClick={handleResetFilters}>
            Reset
          </button>
        </div>
      </div>

      {/* Table & Pagination */}
      {isLoading ? (
        <div className="table-empty"><Loader2 size={20} className="spin" /> Loading call logs...</div>
      ) : error ? (
        <div className="table-empty error">Failed to load LLM call logs.</div>
      ) : logs.length === 0 ? (
        <div className="table-empty">No LLM call logs found.</div>
      ) : (
        <>
          <AppTable
            columns={columns}
            rows={logs}
            rowKey={(log) => log.id}
            onRowClick={(log) => setSelectedCallId(log.id)}
            emptyText="No call logs found."
          />
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 12 }}>
            <span style={{ fontSize: "0.78rem", color: "var(--color-text-muted)" }}>
              Showing logs {offset + 1} - {offset + logs.length}
            </span>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                className="btn btn-secondary btn-sm"
                disabled={offset === 0}
                onClick={handlePrevPage}
              >
                Previous
              </button>
              <button
                className="btn btn-secondary btn-sm"
                disabled={logs.length < limit}
                onClick={handleNextPage}
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}

      {selectedCallId && (
        <LlmCallDetailModal callId={selectedCallId} onClose={() => setSelectedCallId(null)} />
      )}
    </div>
  );
}

function formatJsonOrText(val: any): string {
  if (val === null || val === undefined) return "";
  if (typeof val === "string") return val;
  try {
    return JSON.stringify(val, null, 2);
  } catch {
    return String(val);
  }
}

function LlmCallDetailModal({ callId, onClose }: { callId: number; onClose: () => void }) {
  const { data: detail, isLoading, error } = useLlmCallLogDetail(callId);
  const [rawView, setRawView] = useState(false);
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    systemPrompt: false,
    messageHistory: true,
    skillsInjected: true,
    tools: false,
    response: true,
  });

  const toggleSection = (section: string) => {
    setOpenSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  if (isLoading) {
    return (
      <div style={modalBackdropStyle} onClick={onClose}>
        <div style={modalContentStyle} onClick={(e) => e.stopPropagation()}>
          <div style={modalHeaderStyle}>
            <h3 style={{ margin: 0, fontSize: "1rem", fontWeight: 600 }}>LLM Call Detail</h3>
            <button className="btn-icon" onClick={onClose} style={{ fontSize: "1.5rem", lineHeight: 1 }}>&times;</button>
          </div>
          <div style={{ flex: 1, display: "flex", justifyContent: "center", alignItems: "center" }}>
            <Loader2 size={24} className="spin" style={{ marginRight: 8 }} /> Loading details...
          </div>
        </div>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div style={modalBackdropStyle} onClick={onClose}>
        <div style={modalContentStyle} onClick={(e) => e.stopPropagation()}>
          <div style={modalHeaderStyle}>
            <h3 style={{ margin: 0, fontSize: "1rem", fontWeight: 600 }}>LLM Call Detail</h3>
            <button className="btn-icon" onClick={onClose} style={{ fontSize: "1.5rem", lineHeight: 1 }}>&times;</button>
          </div>
          <div style={{ flex: 1, display: "flex", justifyContent: "center", alignItems: "center", color: "#dc2626" }}>
            Failed to load call log details.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={modalBackdropStyle} onClick={onClose}>
      <div style={modalContentStyle} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div style={modalHeaderStyle}>
          <div>
            <h3 style={{ margin: 0, fontSize: "1.05rem", fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
              <Terminal size={16} color="var(--color-primary)" />
              LLM Call #{detail.call_sequence_number}
            </h3>
            <span style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}>
              {detail.agent_name || `Agent ${detail.agent_id}`} • {new Date(detail.created_at).toLocaleString()}
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button
              className="btn btn-secondary btn-xs"
              onClick={() => setRawView(!rawView)}
              style={{ fontSize: "0.75rem", height: 26 }}
            >
              {rawView ? "Visual View" : "Raw JSON"}
            </button>
            <button className="btn-icon" onClick={onClose} style={{ fontSize: "1.5rem", lineHeight: 1 }}>&times;</button>
          </div>
        </div>

        {/* Scrollable Body */}
        <div style={{ flex: 1, overflowY: "auto", padding: 20 }}>
          {rawView ? (
            <pre style={{ background: "#1e1e1e", color: "#d4d4d4", padding: 16, borderRadius: 8, fontSize: "0.78rem", overflowX: "auto", margin: 0 }}>
              {JSON.stringify(detail, null, 2)}
            </pre>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {/* Metadata Grid */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, background: "#f9fafb", padding: 12, borderRadius: 8, border: "1px solid var(--color-border)" }}>
                <div>
                  <div style={metaLabelStyle}>Model</div>
                  <code style={metaValStyle}>{detail.model}</code>
                </div>
                <div>
                  <div style={metaLabelStyle}>Tokens (I / O)</div>
                  <div style={metaValStyle}>{detail.input_tokens ?? 0} / {detail.output_tokens ?? 0}</div>
                </div>
                <div>
                  <div style={metaLabelStyle}>Finish Reason</div>
                  <div style={metaValStyle}>{detail.finish_reason || "-"}</div>
                </div>
                <div>
                  <div style={metaLabelStyle}>Session ID</div>
                  <div style={metaValStyle}>{detail.session_id ? `#${detail.session_id}` : "None"}</div>
                </div>
              </div>

              {/* 1. System Prompt Section */}
              <div style={sectionStyle}>
                <div style={sectionHeaderStyle} onClick={() => toggleSection("systemPrompt")}>
                  <span>System Prompt</span>
                  {openSections.systemPrompt ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </div>
                {openSections.systemPrompt && (
                  <div style={sectionBodyStyle}>
                    <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.78rem", background: "#f8f9fa", padding: 12, borderRadius: 6, margin: 0, border: "1px solid #e9ecef" }}>
                      {formatJsonOrText(detail.system_prompt_base) || "(Empty system prompt)"}
                    </pre>
                  </div>
                )}
              </div>

              {/* 2. Message History Section */}
              <div style={sectionStyle}>
                <div style={sectionHeaderStyle} onClick={() => toggleSection("messageHistory")}>
                  <span>Message History ({detail.message_history ? detail.message_history.length : 0})</span>
                  {openSections.messageHistory ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </div>
                {openSections.messageHistory && (
                  <div style={{ ...sectionBodyStyle, display: "flex", flexDirection: "column", gap: 8 }}>
                    {detail.message_history.map((msg, i) => {
                      const isUser = msg.role === "user";
                      const isAsst = msg.role === "assistant";
                      const isTool = msg.role === "tool";

                      let bg = "#f3f4f6";
                      let border = "1px solid #e5e7eb";
                      let title = (msg.role || "message").toUpperCase();

                      if (isUser) {
                        bg = "#eff6ff";
                        border = "1px solid #dbeafe";
                        title = "USER";
                      } else if (isAsst) {
                        bg = "#ecfdf5";
                        border = "1px solid #d1fae5";
                        title = "ASSISTANT";
                      } else if (isTool) {
                        bg = "#fff7ed";
                        border = "1px solid #ffedd5";
                        title = `TOOL RESULT: ${msg.tool_name || msg.name || ""}`;
                      }

                      return (
                        <div key={i} style={{ background: bg, border, borderRadius: 6, padding: 10 }}>
                          <div style={{ fontSize: "0.7rem", fontWeight: 700, color: "var(--color-text-muted)", marginBottom: 4 }}>
                            {title}
                          </div>
                          {msg.tool_result ? (
                            <pre style={{ margin: 0, fontSize: "0.75rem", whiteSpace: "pre-wrap", overflowX: "auto" }}>
                              {formatJsonOrText(msg.tool_result)}
                            </pre>
                          ) : msg.tool_calls ? (
                            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                              {msg.tool_calls.map((tc: any, j: number) => {
                                const fnName = tc.name || tc.function?.name || "tool";
                                const argsVal = tc.arguments !== undefined ? tc.arguments : tc.function?.arguments;
                                return (
                                  <div key={j} style={{ background: "rgba(0,0,0,0.03)", padding: 6, borderRadius: 4 }}>
                                    <div style={{ fontSize: "0.72rem", fontWeight: 600 }}>Called: {fnName}</div>
                                    <pre style={{ margin: "4px 0 0 0", fontSize: "0.7rem", overflowX: "auto" }}>
                                      {formatJsonOrText(argsVal)}
                                    </pre>
                                  </div>
                                );
                              })}
                            </div>
                          ) : (
                            <div style={{ fontSize: "0.78rem", whiteSpace: "pre-wrap" }}>
                              {formatJsonOrText(msg.content) || "*(No text content)*"}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* 3. Injected Skills Section */}
              <div style={sectionStyle}>
                <div style={sectionHeaderStyle} onClick={() => toggleSection("skillsInjected")}>
                  <span>Injected Skills ({detail.skills_injected?.length || 0})</span>
                  {openSections.skillsInjected ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </div>
                {openSections.skillsInjected && (
                  <div style={sectionBodyStyle}>
                    {!detail.skills_injected || detail.skills_injected.length === 0 ? (
                      <span style={{ fontSize: "0.78rem", color: "var(--color-text-muted)" }}>No skills were injected in this turn.</span>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                        {detail.skills_injected.map((sk: any, i: number) => (
                          <div key={i} style={{ border: "1px solid var(--color-border)", borderRadius: 6, padding: 10 }}>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                              <span style={{ fontWeight: 600, fontSize: "0.8rem" }}>{sk.name}</span>
                              <span style={{ fontSize: "0.7rem", background: "#f3f4f6", padding: "1px 6px", borderRadius: 4 }}>v{sk.version}</span>
                            </div>
                            <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginBottom: 6 }}>{sk.description}</div>
                            <pre style={{ background: "#f8f9fa", padding: 8, borderRadius: 4, margin: 0, fontSize: "0.72rem", overflowX: "auto", maxHeight: 150, whiteSpace: "pre-wrap" }}>
                              {formatJsonOrText(sk.body)}
                            </pre>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* 4. Tools Available Section */}
              <div style={sectionStyle}>
                <div style={sectionHeaderStyle} onClick={() => toggleSection("tools")}>
                  <span>Tools Available ({detail.tools_available ? detail.tools_available.length : 0})</span>
                  {openSections.tools ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </div>
                {openSections.tools && (
                  <div style={sectionBodyStyle}>
                    {!detail.tools_available || detail.tools_available.length === 0 ? (
                      <span style={{ fontSize: "0.78rem", color: "var(--color-text-muted)" }}>No tools configured for this call.</span>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                        {detail.tools_available.map((t: any, i: number) => (
                          <div key={i} style={{ border: "1px solid var(--color-border)", borderRadius: 6, padding: 8, background: "#f9fafb" }}>
                            <div style={{ fontWeight: 600, fontSize: "0.78rem" }}>{t.name || t.function?.name}</div>
                            {t.description || t.function?.description ? (
                              <div style={{ fontSize: "0.72rem", color: "var(--color-text-muted)", marginTop: 2 }}>{t.description || t.function?.description}</div>
                            ) : null}
                            {(t.function?.parameters || t.parameters) && (
                              <pre style={{ background: "#fff", padding: 6, borderRadius: 4, marginTop: 4, fontSize: "0.7rem", overflowX: "auto" }}>
                                {formatJsonOrText(t.function?.parameters || t.parameters)}
                              </pre>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* 6. Response / Tool Calls Section */}
              <div style={sectionStyle}>
                <div style={sectionHeaderStyle} onClick={() => toggleSection("response")}>
                  <span>LLM Response Output</span>
                  {openSections.response ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </div>
                {openSections.response && (
                  <div style={{ ...sectionBodyStyle, display: "flex", flexDirection: "column", gap: 10 }}>
                    {detail.response_text && (
                      <div>
                        <div style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--color-text-muted)", marginBottom: 4 }}>TEXT RESPONSE</div>
                        <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.78rem", background: "#f0fdf4", border: "1px solid #bbf7d0", padding: 12, borderRadius: 6, margin: 0 }}>
                          {formatJsonOrText(detail.response_text)}
                        </pre>
                      </div>
                    )}
                    {detail.response_tool_calls && detail.response_tool_calls.length > 0 && (
                      <div>
                        <div style={{ fontSize: "0.72rem", fontWeight: 700, color: "var(--color-text-muted)", marginBottom: 4 }}>TOOL CALLS GENERATED</div>
                        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                          {detail.response_tool_calls.map((tc: any, i: number) => {
                            const fnName = tc.name || tc.function?.name || "tool";
                            const argsVal = tc.arguments !== undefined ? tc.arguments : tc.function?.arguments;
                            return (
                              <div key={i} style={{ background: "#fff7ed", border: "1px solid #ffedd5", padding: 10, borderRadius: 6 }}>
                                <div style={{ fontSize: "0.78rem", fontWeight: 600 }}>Function: {fnName}</div>
                                <pre style={{ margin: "4px 0 0 0", fontSize: "0.72rem", overflowX: "auto" }}>
                                  {formatJsonOrText(argsVal)}
                                </pre>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                    {!detail.response_text && (!detail.response_tool_calls || detail.response_tool_calls.length === 0) && (
                      <span style={{ fontSize: "0.78rem", color: "var(--color-text-muted)" }}>*(No response)*</span>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Modal Styles
const modalBackdropStyle: React.CSSProperties = {
  position: "fixed",
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  backgroundColor: "rgba(0, 0, 0, 0.4)",
  backdropFilter: "blur(2px)",
  zIndex: 1000,
  display: "flex",
  justifyContent: "flex-end",
};

const modalContentStyle: React.CSSProperties = {
  width: 600,
  height: "100%",
  backgroundColor: "var(--color-background, #ffffff)",
  boxShadow: "-8px 0 32px rgba(0,0,0,0.12)",
  display: "flex",
  flexDirection: "column",
  outline: "none",
  borderLeft: "1px solid var(--color-border)",
};

const modalHeaderStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  borderBottom: "1px solid var(--color-border)",
  padding: "16px 20px",
};

const metaLabelStyle: React.CSSProperties = {
  fontSize: "0.68rem",
  fontWeight: 600,
  color: "var(--color-text-muted)",
  textTransform: "uppercase",
  marginBottom: 2,
};

const metaValStyle: React.CSSProperties = {
  fontSize: "0.82rem",
  fontWeight: 500,
  color: "var(--color-text-main)",
};

const sectionStyle: React.CSSProperties = {
  border: "1px solid var(--color-border)",
  borderRadius: 8,
  overflow: "hidden",
};

const sectionHeaderStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  background: "#f9fafb",
  padding: "10px 14px",
  fontSize: "0.82rem",
  fontWeight: 600,
  cursor: "pointer",
  userSelect: "none",
  borderBottom: "1px solid var(--color-border)",
};

const sectionBodyStyle: React.CSSProperties = {
  padding: 14,
  background: "#ffffff",
};


export default function AgentsPage() {
  const navigate = useScopedNavigate();
  const { data: agents, isLoading, error } = useAgents();
  const deleteMutation = useDeleteAgent();
  const cloneMutation = useCloneAgent();
  const toast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get("tab");
  const initialTab: AgentsPageTab = tabParam === "tools" ? "tools" : tabParam === "skills" ? "skills" : tabParam === "streams" ? "streams" : tabParam === "llm_calls" ? "llm_calls" : tabParam === "budgets" ? "budgets" : tabParam === "usage" ? "usage" : "agents";
  const [tab, setTab] = useState<AgentsPageTab>(initialTab);
  const [search, setSearch] = useState("");

  const filtered = (agents ?? []).filter((a: AgentListItem) => {
    const q = search.trim().toLowerCase();
    return !q || a.name.toLowerCase().includes(q) || (a.description ?? "").toLowerCase().includes(q);
  });

  async function handleDelete(e: React.MouseEvent, a: AgentListItem) {
    e.stopPropagation();
    if (!confirm(`Delete agent "${a.name}"?`)) return;
    try {
      await deleteMutation.mutateAsync({ agentId: a.id });
      toast.success(`Agent "${a.name}" deleted`);
    } catch {
      toast.error("Failed to delete agent");
    }
  }

  async function handleClone(e: React.MouseEvent, a: AgentListItem) {
    e.stopPropagation();
    try {
      const cloned = await cloneMutation.mutateAsync({ agentId: a.id });
      toast.success(`Cloned as "${cloned.name}"`);
    } catch {
      toast.error("Failed to clone agent");
    }
  }

  return (
    <div className="page-section agents-page">
      <div className="asset-import-breadcrumb" aria-label="Breadcrumb" style={{ marginBottom: 8 }}>
        <span className={tab === "agents" ? "asset-breadcrumb-current" : undefined}>Agents</span>
        {tab !== "agents" && (
          <>
            <span>/</span>
            <span className="asset-breadcrumb-current">
              {tab === "tools" ? "Tools" : tab === "skills" ? "Skills Library" : tab === "streams" ? "Active Streams" : tab === "llm_calls" ? "LLM Call Logs" : tab === "budgets" ? "Budgets" : "Usage"}
            </span>
          </>
        )}
      </div>

      <div className="page-header">
        <div>
          <h1 className="page-title">Agents</h1>
          <p className="page-subtitle">Create agents and review the tools they can use.</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-primary" onClick={() => navigate(`/agents/new`)}>
            <Plus size={15} /> New Agent
          </button>
        </div>
      </div>

      <PageTabs tabs={AGENTS_PAGE_TABS} value={tab} onChange={(value) => { setTab(value); setSearchParams({ tab: value }); }} />

      {tab === "agents" ? (
        <>
          <div className="search-bar-wrapper">
            <Search size={14} className="search-icon" />
            <input
              className="search-input"
              placeholder="Search agents..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <AgentsTable
            agents={filtered}
            isLoading={isLoading}
            error={error}
            onCreate={() => navigate(`/agents/new`)}
            onChat={(agent) => navigate(`/agents/${agent.id}/chat`)}
            onEdit={(agent) => navigate(`/agents/${agent.id}/edit`)}
            onClone={handleClone}
            onDelete={handleDelete}
            clonePending={cloneMutation.isPending}
          />
        </>
      ) : tab === "tools" ? (
        <ToolsTab />
      ) : tab === "skills" ? (
        <SkillsTab />
      ) : tab === "streams" ? (
        <ActiveStreamsTab agents={agents ?? []} />
      ) : tab === "llm_calls" ? (
        <LlmCallLogsTab agents={agents ?? []} />
      ) : tab === "budgets" ? (
        <BudgetsTab agents={agents ?? []} />
      ) : (
        <UsageTab agents={agents ?? []} />
      )}
    </div>
  );
}

