import { useState } from "react";
import { Plus, Trash2, Edit2, Loader2, DollarSign, AlertTriangle, ToggleLeft, ToggleRight, Check } from "lucide-react";
import { useBudgets, useCreateBudget, useUpdateBudget, useDeleteBudget, type Budget } from "../hooks/useBudgets";
import { type AgentListItem } from "../hooks/useAgents";
import { useToast } from "@/lib/toast";

interface BudgetsTabProps {
  agents: AgentListItem[];
}

export function BudgetsTab({ agents }: BudgetsTabProps) {
  const toast = useToast();
  const { data: budgets = [], isLoading, error } = useBudgets("agent");
  const createBudgetMutation = useCreateBudget();
  const updateBudgetMutation = useUpdateBudget();
  const deleteBudgetMutation = useDeleteBudget();

  const [showForm, setShowForm] = useState(false);
  const [editingBudget, setEditingBudget] = useState<Budget | null>(null);

  // Form State
  const [agentId, setAgentId] = useState("");
  const [period, setPeriod] = useState<"daily" | "monthly">("daily");
  const [limitAmount, setLimitAmount] = useState("");
  const [warnPct, setWarnPct] = useState("80");
  const [action, setAction] = useState<"alert_only" | "block_new_calls" | "block_and_pause_agent">("alert_only");
  const [isActive, setIsActive] = useState(true);

  // Map agent ID to Name
  const agentMap = new Map(agents.map(a => [a.id.toString(), a.name]));

  const resetForm = () => {
    setAgentId("");
    setPeriod("daily");
    setLimitAmount("");
    setWarnPct("80");
    setAction("alert_only");
    setIsActive(true);
    setEditingBudget(null);
    setShowForm(false);
  };

  const handleEdit = (budget: Budget) => {
    setEditingBudget(budget);
    setAgentId(budget.scope_id);
    setPeriod(budget.period);
    setLimitAmount(budget.limit_amount.toString());
    setWarnPct(budget.warn_threshold_pct.toString());
    setAction(budget.on_exceeded);
    setIsActive(budget.is_active);
    setShowForm(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!agentId || !limitAmount) {
      toast.error("Please fill all required fields");
      return;
    }

    const payload = {
      scope_type: "agent",
      scope_id: agentId,
      period,
      limit_amount: parseFloat(limitAmount),
      warn_threshold_pct: parseInt(warnPct, 10),
      on_exceeded: action,
      is_active: isActive,
    };

    try {
      if (editingBudget) {
        await updateBudgetMutation.mutateAsync({
          budgetId: editingBudget.id,
          payload: {
            limit_amount: payload.limit_amount,
            warn_threshold_pct: payload.warn_threshold_pct,
            on_exceeded: payload.on_exceeded,
            is_active: payload.is_active,
          },
        });
        toast.success("Budget configuration updated");
      } else {
        await createBudgetMutation.mutateAsync(payload);
        toast.success("Budget configuration created");
      }
      resetForm();
    } catch (err: any) {
      const errMsg = err?.response?.data?.detail ?? "Failed to save budget configuration";
      toast.error(errMsg);
    }
  };

  const handleDelete = async (budget: Budget) => {
    const agentName = agentMap.get(budget.scope_id) ?? `Agent #${budget.scope_id}`;
    if (!confirm(`Are you sure you want to delete the ${budget.period} budget for "${agentName}"?`)) return;

    try {
      await deleteBudgetMutation.mutateAsync(budget.id);
      toast.success("Budget deleted successfully");
    } catch {
      toast.error("Failed to delete budget");
    }
  };

  const toggleActive = async (budget: Budget) => {
    try {
      await updateBudgetMutation.mutateAsync({
        budgetId: budget.id,
        payload: { is_active: !budget.is_active },
      });
      toast.success(`Budget ${budget.is_active ? "paused" : "activated"}`);
    } catch (err: any) {
      const errMsg = err?.response?.data?.detail ?? "Failed to update budget status";
      toast.error(errMsg);
    }
  };

  const getActionLabel = (act: string) => {
    switch (act) {
      case "alert_only": return "Alert Only";
      case "block_new_calls": return "Block New Calls";
      case "block_and_pause_agent": return "Block & Pause Agent";
      default: return act;
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontSize: "0.85rem", color: "var(--color-text-muted)" }}>
          Manage budget limits, warning thresholds, and exceeded actions for individual agents.
        </div>
        {!showForm && (
          <button className="btn btn-primary" onClick={() => setShowForm(true)}>
            <Plus size={15} /> Add Budget
          </button>
        )}
      </div>

      {showForm && (
        <div style={{
          padding: "20px 24px",
          background: "var(--color-surface, #ffffff)",
          border: "1px solid var(--color-border)",
          borderRadius: 8,
        }}>
          <h3 style={{ fontSize: "0.95rem", fontWeight: 600, marginBottom: 16 }}>
            {editingBudget ? "Edit Budget Configuration" : "New Agent Budget"}
          </h3>
          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div className="form-group">
                <label className="form-label" htmlFor="budget-agent">Agent *</label>
                <select
                  id="budget-agent"
                  className="form-input"
                  value={agentId}
                  onChange={(e) => setAgentId(e.target.value)}
                  disabled={!!editingBudget}
                  required
                >
                  <option value="">Select an Agent...</option>
                  {agents.map((a) => (
                    <option key={a.id} value={a.id.toString()}>
                      {a.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="budget-period">Period *</label>
                <select
                  id="budget-period"
                  className="form-input"
                  value={period}
                  onChange={(e) => setPeriod(e.target.value as any)}
                  disabled={!!editingBudget}
                  required
                >
                  <option value="daily">Daily</option>
                  <option value="monthly">Monthly</option>
                </select>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
              <div className="form-group">
                <label className="form-label" htmlFor="budget-limit">Limit Amount ($) *</label>
                <div style={{ position: "relative" }}>
                  <span style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--color-text-muted)" }}>$</span>
                  <input
                    id="budget-limit"
                    className="form-input"
                    type="number"
                    step="0.01"
                    min="0.01"
                    style={{ paddingLeft: 24 }}
                    value={limitAmount}
                    onChange={(e) => setLimitAmount(e.target.value)}
                    placeholder="e.g. 5.00"
                    required
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="budget-warn">Warn Threshold (%)</label>
                <input
                  id="budget-warn"
                  className="form-input"
                  type="number"
                  min="1"
                  max="100"
                  value={warnPct}
                  onChange={(e) => setWarnPct(e.target.value)}
                  placeholder="e.g. 80"
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="budget-action">Exceeded Action</label>
                <select
                  id="budget-action"
                  className="form-input"
                  value={action}
                  onChange={(e) => setAction(e.target.value as any)}
                >
                  <option value="alert_only">Alert Only</option>
                  <option value="block_new_calls">Block New Calls</option>
                  <option value="block_and_pause_agent">Block & Pause Agent</option>
                </select>
              </div>
            </div>

            <div className="form-group" style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <input
                id="budget-active"
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                style={{ width: "auto", cursor: "pointer" }}
              />
              <label className="form-label" htmlFor="budget-active" style={{ marginBottom: 0, cursor: "pointer", userSelect: "none" }}>
                Active (Enforce this budget immediately)
              </label>
            </div>

            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 8 }}>
              <button type="button" className="btn btn-secondary" onClick={resetForm}>
                Cancel
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={createBudgetMutation.isPending || updateBudgetMutation.isPending}
              >
                {(createBudgetMutation.isPending || updateBudgetMutation.isPending) && (
                  <Loader2 size={14} className="spin" />
                )}
                {editingBudget ? "Update Budget" : "Create Budget"}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="admin-table-wrap">
        {isLoading ? (
          <div className="table-empty"><Loader2 size={20} className="spin" /> Loading budgets...</div>
        ) : error ? (
          <div className="table-empty error">Failed to load budgets.</div>
        ) : budgets.length === 0 ? (
          <div className="table-empty">
            <DollarSign size={32} style={{ opacity: 0.3, marginBottom: 8 }} />
            <div>No budget configurations yet.</div>
          </div>
        ) : (
          <table className="admin-table">
            <thead>
              <tr>
                <th style={{ width: "25%" }}>Agent</th>
                <th style={{ width: "12%" }}>Period</th>
                <th style={{ width: "15%" }}>Limit</th>
                <th style={{ width: "15%" }}>Warn Threshold</th>
                <th style={{ width: "18%" }}>On Exceeded Action</th>
                <th style={{ width: "8%" }}>Status</th>
                <th style={{ width: "7%" }} />
              </tr>
            </thead>
            <tbody>
              {budgets.map((budget) => {
                const agentName = agentMap.get(budget.scope_id) ?? `Unknown Agent (ID: ${budget.scope_id})`;
                return (
                  <tr key={budget.id}>
                    <td style={{ fontWeight: 500, fontSize: "0.875rem" }}>{agentName}</td>
                    <td style={{ textTransform: "capitalize", fontSize: "0.8rem" }}>{budget.period}</td>
                    <td style={{ fontWeight: 600, fontSize: "0.85rem" }}>${budget.limit_amount.toFixed(2)}</td>
                    <td style={{ fontSize: "0.8rem", color: "var(--color-text-muted)" }}>
                      {budget.warn_threshold_pct}% (${(budget.limit_amount * budget.warn_threshold_pct / 100).toFixed(2)})
                    </td>
                    <td style={{ fontSize: "0.8rem" }}>
                      <span style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 4,
                        color: budget.on_exceeded === "alert_only" ? "var(--color-text-main)" : "var(--color-text-danger, #d32f2f)",
                      }}>
                        {budget.on_exceeded !== "alert_only" && <AlertTriangle size={12} />}
                        {getActionLabel(budget.on_exceeded)}
                      </span>
                    </td>
                    <td>
                      <button
                        onClick={() => toggleActive(budget)}
                        style={{
                          background: "none",
                          border: "none",
                          cursor: "pointer",
                          padding: 0,
                          display: "flex",
                          alignItems: "center",
                          color: budget.is_active ? "#2e7d32" : "#757575",
                        }}
                        title={budget.is_active ? "Click to Pause" : "Click to Activate"}
                      >
                        {budget.is_active ? (
                          <ToggleRight size={26} color="#2e7d32" style={{ transition: "all 0.2s" }} />
                        ) : (
                          <ToggleLeft size={26} color="#757575" style={{ transition: "all 0.2s" }} />
                        )}
                      </button>
                    </td>
                    <td>
                      <div className="row-actions">
                        <button className="btn-icon" title="Edit" onClick={() => handleEdit(budget)}>
                          <Edit2 size={14} />
                        </button>
                        <button className="btn-icon btn-icon-danger" title="Delete" onClick={() => handleDelete(budget)}>
                          <Trash2 size={14} />
                        </button>
                      </div>
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
