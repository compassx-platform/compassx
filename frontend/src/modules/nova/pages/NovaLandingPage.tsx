import { useMemo, useState } from 'react';
import { Code2, Database, FileText, GitBranch, Send, Sparkles, Zap } from 'lucide-react';
import { useNovaStore, type NovaTarget } from '@/modules/nova/stores/novaStore';
import { useAgents } from '@/modules/agents/hooks/useAgents';
import AppNovaSidebar from '@/modules/nova/components/AppNovaSidebar';
import './nova-landing.css';

const PROMPT_CHIPS = [
  { icon: GitBranch, label: 'Explain an asset hierarchy', prompt: 'Help me understand the current asset hierarchy and where I should start.' },
  { icon: Code2, label: 'Build notebook code', prompt: 'Help me create notebook code for a data analysis workflow.' },
  { icon: Database, label: 'Explore data', prompt: 'Help me find the right data source and summarize what I can ask from it.' },
  { icon: Zap, label: 'Plan a workflow', prompt: 'Help me design an automated workflow for an operational task.' },
];

export default function NovaLandingPage() {
  const { data: agents = [] } = useAgents();
  const [draft, setDraft] = useState('');
  const [chatActive, setChatActive] = useState(false);
  const setOpen = useNovaStore((s) => s.setOpen);
  const setRequirement = useNovaStore((s) => s.setRequirement);
  const setSelectedTarget = useNovaStore((s) => s.setSelectedTarget);

  const activeAgents = useMemo(() => agents.filter((agent) => agent.is_active), [agents]);

  function defaultTarget(): NovaTarget | null {
    const firstAgent = activeAgents[0];
    return firstAgent ? { type: 'agent', agentId: firstAgent.id } : null;
  }

  function openNova(prompt: string, target: NovaTarget | null = defaultTarget()) {
    setSelectedTarget(target);
    setRequirement(prompt);
    setOpen(false);
    setChatActive(true);
  }

  function submit() {
    const prompt = draft.trim();
    if (!prompt) return;
    openNova(prompt);
    setDraft('');
  }

  if (chatActive) {
    return (
      <div className="nova-landing nova-landing-chat-page">
        <div className="nova-landing-chat-shell">
          <AppNovaSidebar />
        </div>
      </div>
    );
  }

  return (
    <div className="nova-landing">
      <section className="nova-landing-hero">
        <div className="nova-landing-kicker">
          <Sparkles size={15} />
          <span>Nova is ready</span>
        </div>
        <h1>Welcome to Compass</h1>
        <p className="nova-landing-subtitle">
          Ask Nova to reason across notebooks, assets, jobs, agents, and your platform context.
        </p>

        <div className="nova-landing-ask-card">
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                submit();
              }
            }}
            placeholder="Ask anything about your workspace..."
            rows={2}
          />
          <div className="nova-landing-actions">
            <span className="nova-landing-hint">Press Enter to start a full-page Nova chat.</span>
            <button type="button" className="nova-landing-submit" onClick={submit} disabled={!draft.trim()}>
              Start chat <Send size={15} />
            </button>
          </div>
        </div>

        <div className="nova-landing-info">
          <div className="nova-landing-info-icon">
            <Sparkles size={18} />
          </div>
          <div>
            <strong>Nova connects your platform surface to the right assistant.</strong>
            <span>
              Nova is now a shared shell for user-created agents. Choose an agent to use platform tools and context.
            </span>
          </div>
        </div>
      </section>

      <section className="nova-landing-grid">
        {PROMPT_CHIPS.map((item) => (
          <button key={item.label} type="button" className="nova-landing-chip" onClick={() => openNova(item.prompt)}>
            <item.icon size={17} />
            <span>{item.label}</span>
          </button>
        ))}
      </section>

      {activeAgents.length > 0 && (
        <section className="nova-landing-agents">
          <div>
            <h2>Available agents</h2>
            <p>Jump straight into a specialized assistant from the same Nova surface.</p>
          </div>
          <div className="nova-landing-agent-list">
            {activeAgents.slice(0, 4).map((agent) => (
              <button
                key={agent.id}
                type="button"
                onClick={() => openNova(`Hi ${agent.name}, help me with `, { type: 'agent', agentId: agent.id })}
              >
                <span className="nova-landing-agent-dot" style={{ background: agent.color ?? '#6366f1' }} />
                <span>{agent.name}</span>
              </button>
            ))}
          </div>
        </section>
      )}

      <section className="nova-landing-modules">
        <div><FileText size={16} /> Forms and records</div>
        <div><GitBranch size={16} /> Assets and hierarchies</div>
        <div><Code2 size={16} /> Notebooks and code</div>
        <div><Zap size={16} /> Jobs and automation</div>
      </section>
    </div>
  );
}
