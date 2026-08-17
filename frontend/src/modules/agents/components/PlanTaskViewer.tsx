import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Check, FileText, X } from 'lucide-react';

export interface PlanStepData {
  id: number;
  description: string;
  status: 'pending' | 'in_progress' | 'done' | 'failed';
  verification: string;
  result?: any;
  corrections: string[];
  attempts: number;
}

export interface PlanData {
  plan_id: string;
  agent_id: string;
  goal: string;
  steps: PlanStepData[];
  approved_at?: string | null;
  execution_approved_at?: string | null;
}

interface PlanTaskViewerProps {
  plan: PlanData;
  onApprovePlan?: () => void;
  onRejectPlan?: () => void;
  onRequestChange?: (feedback: string) => void;
  onApproveExecution?: () => void;
}

export const PlanTaskViewer: React.FC<PlanTaskViewerProps> = ({
  plan,
  onApprovePlan,
  onRejectPlan,
  onRequestChange,
}) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const [feedbackText, setFeedbackText] = useState('');

  const totalCount = plan.steps.length;
  const isApproved = !!plan.approved_at;
  const isAllDone = plan.steps.length > 0 && plan.steps.every((s) => s.status === 'done');

  return (
    <div
      style={{
        width: '100%',
        borderRadius: '12px 12px 0 0',
        border: '1px solid var(--color-border, #e5e7eb)',
        borderBottom: 'none',
        background: 'var(--color-surface, #fcfcfc)',
        boxShadow: 'none',
        fontSize: '0.8rem',
        color: 'var(--color-text, #1f2937)',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      }}
    >
      {/* ── Header Bar ── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 14px',
          cursor: 'pointer',
          userSelect: 'none',
        }}
        onClick={() => setIsExpanded((prev) => !prev)}
      >
        {/* Left: Collapsible Chevron & Step count */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8rem', fontWeight: 500, color: '#374151' }}>
          {isExpanded ? <ChevronDown size={14} color="#6b7280" /> : <ChevronRight size={14} color="#6b7280" />}
          <span>{totalCount} {totalCount === 1 ? 'step' : 'steps'}</span>
        </div>

        {/* Right: Reject all / Accept all Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }} onClick={(e) => e.stopPropagation()}>
          {!isApproved ? (
            <>
              {onRejectPlan && (
                <button
                  type="button"
                  onClick={onRejectPlan}
                  style={{
                    padding: '4px 12px',
                    borderRadius: '6px',
                    border: '1px solid #d1d5db',
                    background: '#ffffff',
                    color: '#374151',
                    fontSize: '0.78rem',
                    fontWeight: 500,
                    cursor: 'pointer',
                  }}
                >
                  Reject
                </button>
              )}
              {onApprovePlan && (
                <button
                  type="button"
                  onClick={onApprovePlan}
                  style={{
                    padding: '4px 14px',
                    borderRadius: '6px',
                    border: 'none',
                    background: '#0284c7',
                    color: '#ffffff',
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Accept
                </button>
              )}
            </>
          ) : isAllDone ? (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: '#16a34a', fontSize: '0.75rem', fontWeight: 600 }}>
              <Check size={14} /> Completed
            </span>
          ) : (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: '#059669', fontSize: '0.75rem', fontWeight: 600 }}>
              <Check size={14} /> Active Plan
            </span>
          )}
        </div>
      </div>

      {/* ── Asset / Step Items List ── */}
      {isExpanded && (
        <div style={{ padding: '0 14px 10px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {plan.steps.map((step) => (
              <div
                key={step.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  fontSize: '0.8rem',
                }}
              >
                {/* Icon + File/Step Name */}
                <FileText size={15} style={{ color: '#4b5563', flexShrink: 0 }} />
                <span
                  style={{
                    fontWeight: 500,
                    color: '#1f2937',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    flex: 1,
                  }}
                >
                  {step.description}
                </span>
                <span
                  style={{
                    fontSize: '0.72rem',
                    fontWeight: 500,
                    color: step.status === 'done' ? '#16a34a' : step.status === 'in_progress' ? '#d97706' : '#6b7280',
                    textTransform: 'capitalize',
                  }}
                >
                  {step.status}
                </span>
              </div>
            ))}
          </div>

          {!isApproved && onRequestChange && (
            <div style={{ marginTop: 8, display: 'flex', gap: 6, alignItems: 'center' }}>
              <input
                type="text"
                value={feedbackText}
                onChange={(e) => setFeedbackText(e.target.value)}
                placeholder="Request changes..."
                style={{
                  flex: 1,
                  padding: '4px 8px',
                  borderRadius: '6px',
                  border: '1px solid #d1d5db',
                  background: '#ffffff',
                  fontSize: '0.75rem',
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && feedbackText.trim() && onRequestChange) {
                    onRequestChange(feedbackText);
                    setFeedbackText('');
                  }
                }}
              />
              <button
                type="button"
                disabled={!feedbackText.trim()}
                onClick={() => {
                  if (feedbackText.trim() && onRequestChange) {
                    onRequestChange(feedbackText);
                    setFeedbackText('');
                  }
                }}
                style={{
                  padding: '4px 10px',
                  borderRadius: '6px',
                  border: 'none',
                  background: feedbackText.trim() ? '#0284c7' : '#9ca3af',
                  color: '#ffffff',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  cursor: feedbackText.trim() ? 'pointer' : 'not-allowed',
                }}
              >
                Send
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
