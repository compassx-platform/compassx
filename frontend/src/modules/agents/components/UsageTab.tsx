import { DollarSign, Loader2, Play, Pause, AlertTriangle, AlertCircle, RefreshCw } from "lucide-react";
import { useBudgets } from "../hooks/useBudgets";
import { useBudgetStatuses } from "../hooks/useBudgets";
import { type AgentListItem, useUpdateAgent } from "../hooks/useAgents";
import { useToast } from "@/lib/toast";

interface UsageTabProps {
  agents: AgentListItem[];
}

export function UsageTab({ agents }: UsageTabProps) {
  const toast = useToast();
  const { data: budgets = [], isLoading: budgetsLoading } = useBudgets("agent");
  const { data: statuses = [], isLoading: statusesLoading, error, refetch, isFetching } = useBudgetStatuses("agent");
  const updateAgentMutation = useUpdateAgent();

  const agentMap = new Map(agents.map(a => [a.id, a]));
  const budgetMap = new Map(budgets.map(b => [`${b.scope_id}-${b.period}`, b]));

  const handleToggleAgentStatus = async (agentId: number, currentStatus: "active" | "paused") => {
    const nextStatus = currentStatus === "active" ? "paused" : "active";
    const agent = agentMap.get(agentId);
    if (!agent) return;

    if (!confirm(`Are you sure you want to ${nextStatus === "paused" ? "pause" : "resume"} agent "${agent.name}"?`)) {
      return;
    }

    try {
      await updateAgentMutation.mutateAsync({
        agentId,
        payload: { status: nextStatus },
      });
      toast.success(`Agent "${agent.name}" status updated to ${nextStatus}`);
    } catch {
      toast.error(`Failed to update agent status`);
    }
  };

  const getStatusColor = (percent: number, warnThreshold: number) => {
    if (percent >= 100) return "var(--color-text-danger, #ef4444)";
    if (percent >= warnThreshold) return "#f59e0b"; // amber
    return "#10b981"; // green
  };

  const getProgressBg = (percent: number, warnThreshold: number) => {
    if (percent >= 100) return "#fecaca"; // light red
    if (percent >= warnThreshold) return "#fef3c7"; // light amber
    return "#d1fae5"; // light green
  };

  const isLoading = budgetsLoading || statusesLoading;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontSize: "0.85rem", color: "var(--color-text-muted)" }}>
          Track real-time spend across agents and take actions to pause or resume agents.
        </div>
        <button className="btn btn-secondary" onClick={() => refetch()} disabled={isFetching || isLoading}>
          {isFetching ? <Loader2 size={14} className="spin" /> : <RefreshCw size={14} />}
          Refresh
        </button>
      </div>

      <div className="admin-table-wrap">
        {isLoading ? (
          <div className="table-empty"><Loader2 size={20} className="spin" /> Loading usage records...</div>
        ) : error ? (
          <div className="table-empty error">Failed to load budget usage statuses.</div>
        ) : statuses.length === 0 ? (
          <div className="table-empty">
            <DollarSign size={32} style={{ opacity: 0.3, marginBottom: 8 }} />
            <div>No usage data available. Configure a budget to start tracking.</div>
          </div>
        ) : (
          <table className="admin-table">
            <thead>
              <tr>
                <th style={{ width: "22%" }}>Agent</th>
                <th style={{ width: "10%" }}>Period</th>
                <th style={{ width: "22%" }}>Spend Tracker</th>
                <th style={{ width: "12%" }}>Warning / Status</th>
                <th style={{ width: "14%" }}>Agent Status</th>
                <th style={{ width: "12%" }}>Last Active</th>
                <th style={{ width: "8%" }} />
              </tr>
            </thead>
            <tbody>
              {statuses.map((status) => {
                const parsedAgentId = parseInt(status.scope_id, 10);
                const agent = agentMap.get(parsedAgentId);
                const agentName = agent?.name ?? `Agent #${status.scope_id}`;
                const agentStatus = agent?.status ?? "active";
                const budgetKey = `${status.scope_id}-${status.period}`;
                const budget = budgetMap.get(budgetKey);

                const limitAmount = budget?.limit_amount ?? 0;
                const warnThreshold = budget?.warn_threshold_pct ?? 80;
                const percentSpent = limitAmount > 0 ? (status.amount_spent / limitAmount) * 100 : 0;
                const progressPercent = Math.min(100, percentSpent);

                const statusColor = getStatusColor(percentSpent, warnThreshold);
                const progressBg = getProgressBg(percentSpent, warnThreshold);

                return (
                  <tr key={status.id}>
                    <td>
                      <div>
                        <div style={{ fontWeight: 500, fontSize: "0.875rem" }}>{agentName}</div>
                        <div style={{ fontSize: "0.72rem", color: "var(--color-text-muted)" }}>
                          ID: {status.scope_id}
                        </div>
                      </div>
                    </td>
                    <td style={{ textTransform: "capitalize", fontSize: "0.8rem" }}>{status.period}</td>
                    <td>
                      <div>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.78rem", marginBottom: 4 }}>
                          <span style={{ fontWeight: 600, color: statusColor }}>
                            ${status.amount_spent.toFixed(4)}
                          </span>
                          <span style={{ color: "var(--color-text-muted)" }}>
                            of ${limitAmount.toFixed(2)} ({percentSpent.toFixed(1)}%)
                          </span>
                        </div>
                        <div style={{ width: "100%", height: 8, background: "var(--color-border-subtle, #e5e7eb)", borderRadius: 4, overflow: "hidden" }}>
                          <div style={{
                            width: `${progressPercent}%`,
                            height: "100%",
                            backgroundColor: statusColor,
                            borderRadius: 4,
                            transition: "width 0.3s ease",
                          }} />
                        </div>
                      </div>
                    </td>
                    <td>
                      {percentSpent >= 100 ? (
                        <span style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 4,
                          fontSize: "0.72rem",
                          fontWeight: 600,
                          color: "var(--color-text-danger, #ef4444)",
                          background: "#fee2e2",
                          padding: "2px 8px",
                          borderRadius: 4,
                        }}>
                          <AlertCircle size={12} />
                          Exceeded
                        </span>
                      ) : percentSpent >= warnThreshold ? (
                        <span style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 4,
                          fontSize: "0.72rem",
                          fontWeight: 600,
                          color: "#d97706",
                          background: "#fef3c7",
                          padding: "2px 8px",
                          borderRadius: 4,
                        }}>
                          <AlertTriangle size={12} />
                          Warn ({warnThreshold}%)
                        </span>
                      ) : (
                        <span style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 4,
                          fontSize: "0.72rem",
                          fontWeight: 600,
                          color: "#059669",
                          background: "#d1fae5",
                          padding: "2px 8px",
                          borderRadius: 4,
                        }}>
                          Normal
                        </span>
                      )}
                    </td>
                    <td>
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 4,
                          padding: "2px 8px",
                          borderRadius: 4,
                          fontSize: "0.72rem",
                          fontWeight: 600,
                          color: agentStatus === "active" ? "#2E7D32" : "#D32F2F",
                          background: agentStatus === "active" ? "#E8F5E9" : "#FFEBEE",
                        }}
                      >
                        {agentStatus === "active" ? "Active" : "Paused"}
                      </span>
                    </td>
                    <td style={{ fontSize: "0.8rem", color: "var(--color-text-muted)" }}>
                      {new Date(status.last_updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </td>
                    <td>
                      {agent && (
                        <button
                          className="btn-icon"
                          title={agentStatus === "active" ? "Pause Agent" : "Resume Agent"}
                          onClick={() => handleToggleAgentStatus(agent.id, agentStatus)}
                          disabled={updateAgentMutation.isPending}
                        >
                          {agentStatus === "active" ? (
                            <Pause size={14} color="#D32F2F" />
                          ) : (
                            <Play size={14} color="#2E7D32" />
                          )}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
