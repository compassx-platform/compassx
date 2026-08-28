import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { MessageBubble, CopyMessageButton } from './MessageBubble';
import { ConsolidatedThoughtBlock, TimelineStep } from './ConsolidatedThoughtBlock';
import { parseThoughtContent } from './ThoughtAccordion';
import { markdownComponents } from './markdownComponents';
import { PlanTaskViewer } from '../PlanTaskViewer';
import { TurnEditBadge, TurnEditInfo } from '../TurnEditBadge';
import { transformAssetTagsToMarkdown } from '../AssetChip';
import { ChangeRecord } from '../DiffSummaryCard';

interface ChatMessageListProps {
  messages: any[];
  optimisticUserMsg: { sessionId: number; content: string } | null;
  activeSessionId: number | null;
  isStreaming: boolean;
  streamingSteps: any[];
  streamingText: string;
  activeToolName: string | null;
  activeToolArgs: any;
  agentId?: number | null;
  knownAssetNames?: Set<string>;
  messagesContainerRef: React.RefObject<HTMLDivElement | null>;
  messagesEndRef: React.RefObject<HTMLDivElement | null>;
  latestUserMsgRef: React.RefObject<HTMLDivElement | null>;
  onMessagesScroll: () => void;
  onOpenDiff: (record: ChangeRecord) => void;
  onStatusChange?: (changeId: string, newStatus: 'accepted' | 'rejected') => void;
}

export const ChatMessageList: React.FC<ChatMessageListProps> = React.memo(({
  messages,
  optimisticUserMsg,
  activeSessionId,
  isStreaming,
  streamingSteps,
  streamingText,
  activeToolName,
  activeToolArgs,
  agentId,
  knownAssetNames = new Set(),
  messagesContainerRef,
  messagesEndRef,
  latestUserMsgRef,
  onMessagesScroll,
  onOpenDiff,
  onStatusChange,
}) => {
  // Group messages into user bubbles vs combined assistant turns
  type MessageGroup = {
    type: 'user' | 'assistant_turn';
    id: string;
    userMsg?: (typeof messages)[0];
    items?: typeof messages;
    isStreamingActive?: boolean;
  };

  const groups = useMemo(() => {
    const result: MessageGroup[] = [];
    let currentAssistantTurn: MessageGroup | null = null;

    for (const msg of messages) {
      if (msg.role === 'user') {
        if (currentAssistantTurn) {
          result.push(currentAssistantTurn);
          currentAssistantTurn = null;
        }
        result.push({
          type: 'user',
          id: `user-${msg.id}`,
          userMsg: msg,
        });
      } else {
        if (!currentAssistantTurn) {
          currentAssistantTurn = {
            type: 'assistant_turn',
            id: `turn-${msg.id}`,
            items: [],
          };
        }
        currentAssistantTurn.items!.push(msg);
      }
    }

    if (currentAssistantTurn) {
      result.push(currentAssistantTurn);
    }

    const hasOptimisticForCurrentSession = !!(
      optimisticUserMsg &&
      activeSessionId &&
      optimisticUserMsg.sessionId === activeSessionId
    );

    const lastUserMsgInDb = [...messages].reverse().find((m) => m.role === 'user');
    const lastUserMsgIdxInDb = lastUserMsgInDb ? messages.lastIndexOf(lastUserMsgInDb) : -1;
    const hasAssistantMsgAfterLastUser =
      lastUserMsgIdxInDb !== -1 &&
      messages.slice(lastUserMsgIdxInDb + 1).some((m) => m.role === 'assistant');

    const isOptimisticAlreadyInMessages =
      hasOptimisticForCurrentSession &&
      lastUserMsgInDb != null &&
      lastUserMsgInDb.content === optimisticUserMsg?.content &&
      !hasAssistantMsgAfterLastUser;

    const shouldRenderOptimisticUserMsg =
      hasOptimisticForCurrentSession && !isOptimisticAlreadyInMessages;

    if (isStreaming || shouldRenderOptimisticUserMsg) {
      if (shouldRenderOptimisticUserMsg && optimisticUserMsg) {
        result.push({
          type: 'user',
          id: 'optimistic-user',
          userMsg: { id: -1, role: 'user', content: optimisticUserMsg.content } as any,
        });
      }
      if (isStreaming) {
        const lastGroup = result[result.length - 1];
        if (lastGroup && lastGroup.type === 'assistant_turn') {
          lastGroup.isStreamingActive = true;
        } else {
          result.push({
            type: 'assistant_turn',
            id: 'streaming-turn',
            items: [],
            isStreamingActive: true,
          });
        }
      }
    }

    return result;
  }, [messages, optimisticUserMsg, activeSessionId, isStreaming]);

  const lastUserGroupIndex = useMemo(() => {
    for (let i = groups.length - 1; i >= 0; i--) {
      if (groups[i].type === 'user') return i;
    }
    return -1;
  }, [groups]);

  return (
    <div
      ref={messagesContainerRef}
      onScroll={onMessagesScroll}
      style={{
        flex: 1,
        overflowY: 'auto',
        padding: '24px 24px 0',
        display: 'flex',
        justifyContent: 'center',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 780,
          display: 'flex',
          flexDirection: 'column',
          gap: 20,
          paddingBottom: 'calc(100vh - 140px)',
        }}
      >
        {groups.map((grp, idx) => {
          if (grp.type === 'user' && grp.userMsg) {
            const isLatestUserMsg = idx === lastUserGroupIndex;
            return (
              <div
                key={grp.id}
                ref={isLatestUserMsg ? latestUserMsgRef : undefined}
                data-role="user-message"
                data-latest-user-msg={isLatestUserMsg ? 'true' : undefined}
              >
                <MessageBubble role="user" content={grp.userMsg.content} />
              </div>
            );
          }

          // Combined assistant turn
          const turnItems = grp.items ?? [];
          const timelineSteps: TimelineStep[] = [];
          let finalResponse = '';

          turnItems.forEach((m) => {
            if (m.role === 'tool') {
              timelineSteps.push({
                type: 'tool',
                name: m.tool_name ?? 'tool',
                result: m.tool_result,
              });
            } else {
              const { thought, response } = parseThoughtContent(m.content);
              if (thought) {
                const items = thought
                  .split(/\n+/)
                  .map((item) => item.trim().replace(/^[-*•]\s*/, ''))
                  .filter((item) => item.length > 0);
                items.forEach((txt) => timelineSteps.push({ type: 'thought', text: txt }));
              }
              if (response) {
                finalResponse += (finalResponse ? '\n\n' : '') + response;
              }
            }
          });

          if (grp.isStreamingActive) {
            streamingSteps.forEach((st) => {
              if (st.type === 'tool') {
                timelineSteps.push({
                  type: 'tool',
                  name: st.name ?? 'tool',
                  result: {
                    args: st.args,
                    result: st.result,
                    error: st.error,
                    ok: st.ok,
                  },
                });
              } else {
                timelineSteps.push(st as any);
              }
            });

            const { thought, response } = parseThoughtContent(streamingText);
            if (thought) {
              const items = thought
                .split(/\n+/)
                .map((item) => item.trim().replace(/^[-*•]\s*/, ''))
                .filter((item) => item.length > 0);
              items.forEach((txt) => timelineSteps.push({ type: 'thought', text: txt }));
            }
            if (response) {
              finalResponse += (finalResponse ? '\n\n' : '') + response;
            }
          }

          const cleanFinalResponse = finalResponse.replace(/\r\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();

          // Check if this turn completed an active execution plan
          let inlineCompletedPlanData: any = null;
          const turnHasFinalMarkStep = turnItems.some(
            (m) => m.role === 'tool' && m.tool_name === 'mark_step'
          );

          if (turnHasFinalMarkStep) {
            const firstTurnItem = turnItems[0];
            const msgIdx = messages.indexOf(firstTurnItem);
            const priorMessages = msgIdx >= 0 ? messages.slice(0, msgIdx + turnItems.length) : messages;

            let planIdx = -1;
            for (let i = priorMessages.length - 1; i >= 0; i--) {
              if (priorMessages[i].role === 'tool' && priorMessages[i].tool_name === 'create_plan') {
                planIdx = i;
                break;
              }
            }

            if (planIdx >= 0) {
              const createPlanMsg = priorMessages[planIdx];
              if (createPlanMsg && createPlanMsg.tool_result) {
                const r = createPlanMsg.tool_result.result as any;
                const a = createPlanMsg.tool_result.args as any;
                const steps = a?.steps || r?.steps || [];
                const planIdData = r?.plan_id || 'plan';

                const messagesForPlan = priorMessages.slice(planIdx + 1);
                const stepStatusMap: Record<number, string> = {};

                messagesForPlan.forEach((m) => {
                  if (m.role === 'tool' && m.tool_name === 'mark_step' && m.tool_result) {
                    const mr = m.tool_result.result as any;
                    const stepIdRaw = mr?.updated_step ?? (m.tool_result.args as any)?.step_id;
                    const status = mr?.status ?? (m.tool_result.args as any)?.status;
                    const planId = mr?.plan_id ?? (m.tool_result.args as any)?.plan_id;
                    if ((!planId || planId === planIdData) && stepIdRaw != null && status) {
                      stepStatusMap[Number(stepIdRaw)] = String(status);
                    }
                  }
                });

                const computedSteps = steps.map((s: any, sIdx: number) => {
                  const id = Number(s.id ?? sIdx + 1);
                  return {
                    id,
                    description: s.description ?? s.text ?? '',
                    status: stepStatusMap[id] || s.status || 'pending',
                    verification: s.verification ?? 'Automatic check',
                    corrections: s.corrections ?? [],
                    attempts: s.attempts ?? 1,
                  };
                });

                const isAllDone = computedSteps.length > 0 && computedSteps.every((s: any) => s.status === 'done');

                if (isAllDone) {
                  inlineCompletedPlanData = {
                    plan_id: planIdData,
                    goal: a?.goal || r?.goal || 'Execution Plan',
                    steps: computedSteps,
                    approved_at: r?.approved_at || new Date().toISOString(),
                  };
                }
              }
            }
          }

          return (
            <div key={grp.id} style={{ marginBottom: 16 }}>
              {/* Single consolidated Thinking block for thoughts + tool calls */}
              {(timelineSteps.length > 0 || (grp.isStreamingActive && !cleanFinalResponse) || (grp.isStreamingActive && activeToolName)) && (
                <ConsolidatedThoughtBlock
                  steps={timelineSteps}
                  isStreaming={grp.isStreamingActive}
                  activeTool={grp.isStreamingActive ? activeToolName : null}
                  activeToolArgs={grp.isStreamingActive ? activeToolArgs : null}
                />
              )}

              {/* Final response markdown */}
              {cleanFinalResponse && (
                <div
                  className="assistant-response-content"
                  style={{
                    marginTop: timelineSteps.length > 0 ? 12 : 0,
                    fontSize: '0.9rem',
                    lineHeight: 1.65,
                    color: 'var(--color-text, #1f2937)',
                  }}
                >
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[rehypeHighlight]}
                    components={markdownComponents}
                    urlTransform={(url) => url}
                  >
                    {transformAssetTagsToMarkdown(cleanFinalResponse, knownAssetNames)}
                  </ReactMarkdown>
                </div>
              )}

              {/* Inline Completed Plan Card */}
              {inlineCompletedPlanData && (
                <div style={{ marginTop: 10 }}>
                  <PlanTaskViewer
                    defaultExpanded={false}
                    plan={{
                      plan_id: inlineCompletedPlanData.plan_id,
                      agent_id: 'agent',
                      goal: inlineCompletedPlanData.goal,
                      steps: inlineCompletedPlanData.steps,
                      approved_at: inlineCompletedPlanData.approved_at,
                    }}
                  />
                </div>
              )}

              {/* In-Turn File/Asset Edit Badges */}
              {(() => {
                const turnEdits: TurnEditInfo[] = [];
                const seenNames = new Set<string>();

                turnItems.forEach((m) => {
                  if (m.role === 'tool' && m.tool_result) {
                    const change = (m.tool_result as any).change;
                    if (change && change.full_name && !seenNames.has(change.full_name)) {
                      seenNames.add(change.full_name);
                      turnEdits.push({
                        change_id: change.change_id,
                        full_name: change.full_name,
                        object_type: change.object_type || 'notebook',
                        additions: change.additions,
                        deletions: change.deletions,
                      });
                    } else if (
                      m.tool_result.ok &&
                      (m.tool_name === 'create_notebook' ||
                        m.tool_name === 'catalog_editor' ||
                        (m.tool_name === 'notebook_manager' &&
                          ['edit_cell', 'propose_cell_edit', 'apply_notebook_edit', 'add_multiple_cells', 'add_cells', 'create_cell', 'insert_cell', 'delete_cell', 'append_to_cell', 'create_notebook'].includes(
                            (m.tool_result.args as any)?.operation
                          )))
                    ) {
                      const res = m.tool_result.result as any;
                      const args = m.tool_result.args as any;
                      const fn =
                        res?.full_name ||
                        (args?.catalog_name && args?.schema_name && args?.notebook_name
                          ? `${args.catalog_name}.${args.schema_name}.${args.notebook_name}`
                          : null);
                      if (fn && !seenNames.has(fn)) {
                        seenNames.add(fn);
                        turnEdits.push({
                          full_name: fn,
                          object_type: (res?.object_type || args?.object_type || 'notebook') as any,
                        });
                      }
                    }
                  }
                });

                if (turnEdits.length === 0) return null;
                return (
                  <div style={{ marginTop: 8 }}>
                    <TurnEditBadge
                      edits={turnEdits}
                      agentId={agentId}
                      sessionId={activeSessionId}
                      onOpenDiff={onOpenDiff}
                      onStatusChange={onStatusChange}
                    />
                  </div>
                );
              })()}

              {/* Copy Button */}
              {cleanFinalResponse && (
                <div style={{ marginTop: 8, display: 'flex', alignItems: 'center' }}>
                  <CopyMessageButton text={cleanFinalResponse} />
                </div>
              )}
            </div>
          );
        })}
        <div ref={messagesEndRef} style={{ height: 32, flexShrink: 0 }} />
      </div>
    </div>
  );
});
export default ChatMessageList;
