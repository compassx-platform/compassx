import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Sparkles,
  Bot,
  Workflow,
  FileCode,
  LayoutDashboard,
  Star,
  Clock,
  Lightbulb,
  X,
  ExternalLink,
  ArrowLeft,
  Send,
} from 'lucide-react';
import api from '@/lib/api';
import { useWorkspaceContext } from '@/lib/workspaceContext';
import { useMe } from '@/lib/userManagerApi';
import { useScopedNavigate } from '@/lib/appNavigation';
import { useAgents } from '@/modules/agents/hooks/useAgents';
import { useDashboards } from '@/modules/dashboards/hooks/useDashboard';
import { useNovaStore, type NovaTarget } from '@/modules/nova/stores/novaStore';
import AppNovaSidebar from '@/modules/nova/components/AppNovaSidebar';
import * as jobsApi from '@/modules/jobs/lib/jobsApi';
import './landing-page.css';

type TabId = 'suggested' | 'recent' | 'favorites' | 'agents' | 'jobs' | 'notebooks' | 'dashboards';

interface WorkspaceFeedItem {
  id: string;
  name: string;
  path: string;
  type: 'Job' | 'Agent' | 'Notebook' | 'Dashboard';
  icon: typeof Workflow;
  timeText: string;
  targetUrl?: string;
  agentId?: string;
}

const TABS: { id: TabId; label: string; icon: typeof Lightbulb }[] = [
  { id: 'suggested', label: 'Suggested', icon: Lightbulb },
  { id: 'recent', label: 'Recent', icon: Clock },
  { id: 'favorites', label: 'Favorites', icon: Star },
  { id: 'agents', label: 'Agents', icon: Bot },
  { id: 'jobs', label: 'Jobs', icon: Workflow },
  { id: 'notebooks', label: 'Notebooks', icon: FileCode },
  { id: 'dashboards', label: 'Dashboards', icon: LayoutDashboard },
];

export default function LandingPage() {
  const navigate = useScopedNavigate();
  const workspace = useWorkspaceContext();
  const { data: me } = useMe();

  // Queries
  const { data: agents = [] } = useAgents();
  const { data: dashboards = [] } = useDashboards();
  const { data: jobs = [] } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => jobsApi.listJobs(),
    staleTime: 30_000,
  });
  const { data: notebooksData } = useQuery({
    queryKey: ['notebooks-list'],
    queryFn: async () => {
      try {
        const res = await api.get<{ notebooks: { path: string; name: string }[] }>('/notebook/list');
        return res.data.notebooks || [];
      } catch {
        return [];
      }
    },
    staleTime: 30_000,
  });
  const notebooks = notebooksData || [];

  // State
  const [draft, setDraft] = useState('');
  const [activeTab, setActiveTab] = useState<TabId>('suggested');
  const [showTipBanner, setShowTipBanner] = useState(true);
  const [chatActive, setChatActive] = useState(false);
  const [limit, setLimit] = useState(8);
  const [favorites, setFavorites] = useState<string[]>(() => {
    try {
      const stored = localStorage.getItem('compassx_favorite_items');
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  const setOpen = useNovaStore((s) => s.setOpen);
  const setRequirement = useNovaStore((s) => s.setRequirement);
  const setSelectedTarget = useNovaStore((s) => s.setSelectedTarget);

  const activeAgents = useMemo(() => agents.filter((a) => a.is_active), [agents]);

  function toggleFavorite(itemId: string, e: React.MouseEvent) {
    e.stopPropagation();
    setFavorites((prev) => {
      const next = prev.includes(itemId)
        ? prev.filter((id) => id !== itemId)
        : [...prev, itemId];
      try {
        localStorage.setItem('compassx_favorite_items', JSON.stringify(next));
      } catch {
        // ignore
      }
      return next;
    });
  }

  function openAssistant(prompt: string, target?: NovaTarget | null) {
    let resolvedTarget: NovaTarget | null = null;
    if (target !== undefined) {
      resolvedTarget = target;
    } else if (activeAgents.length > 0) {
      resolvedTarget = { type: 'agent', agentId: activeAgents[0].id };
    }

    setSelectedTarget(resolvedTarget);
    setRequirement(prompt);
    setOpen(false);
    setChatActive(true);
  }

  function handlePromptSubmit() {
    const prompt = draft.trim();
    if (!prompt) return;
    openAssistant(prompt);
    setDraft('');
  }

  // Construct unified feed items
  const allItems: WorkspaceFeedItem[] = useMemo(() => {
    const list: WorkspaceFeedItem[] = [];

    // Dashboards
    dashboards.forEach((d) => {
      list.push({
        id: `dashboard-${d.id}`,
        name: d.name,
        path: `/dashboards/${d.id}`,
        type: 'Dashboard',
        icon: LayoutDashboard,
        timeText: d.isDraft ? 'Draft' : 'Published',
        targetUrl: `/dashboards/${d.id}`,
      });
    });

    // Jobs
    jobs.forEach((job) => {
      list.push({
        id: `job-${job.job_id}`,
        name: job.name,
        path: `/jobs/${job.job_id}${job.cron_schedule ? ` • cron: ${job.cron_schedule}` : ''}`,
        type: 'Job',
        icon: Workflow,
        timeText: `Status: ${job.status}`,
        targetUrl: `/jobs/${job.job_id}`,
      });
    });

    // Agents
    agents.forEach((agent) => {
      list.push({
        id: `agent-${agent.id}`,
        name: agent.name,
        path: `/agents/${agent.id} • ${agent.model_provider || 'Assistant'}`,
        type: 'Agent',
        icon: Bot,
        timeText: agent.is_active ? 'Active' : 'Draft',
        agentId: agent.id,
      });
    });

    // Notebooks
    notebooks.forEach((nb) => {
      list.push({
        id: `notebook-${nb.path}`,
        name: nb.name || nb.path,
        path: `/notebooks/open?path=${encodeURIComponent(nb.path)}`,
        type: 'Notebook',
        icon: FileCode,
        timeText: 'Notebook',
        targetUrl: `/notebooks/open?path=${encodeURIComponent(nb.path)}`,
      });
    });

    // Fallback if empty workspace
    if (list.length === 0) {
      list.push(
        {
          id: 'starter-agent',
          name: 'Create Autonomous Agent',
          path: '/agents/new',
          type: 'Agent',
          icon: Bot,
          timeText: 'Setup',
          targetUrl: '/agents/new',
        },
        {
          id: 'starter-notebook',
          name: 'Launch Python Notebook',
          path: '/notebooks',
          type: 'Notebook',
          icon: FileCode,
          timeText: 'Launch',
          targetUrl: '/notebooks',
        },
        {
          id: 'starter-dashboard',
          name: 'Create BI Dashboard',
          path: '/dashboards',
          type: 'Dashboard',
          icon: LayoutDashboard,
          timeText: 'Analytics',
          targetUrl: '/dashboards',
        },
        {
          id: 'starter-job',
          name: 'Schedule Pipeline Job',
          path: '/jobs',
          type: 'Job',
          icon: Workflow,
          timeText: 'Schedule',
          targetUrl: '/jobs',
        }
      );
    }

    return list;
  }, [dashboards, jobs, agents, notebooks]);

  // Filter items based on active tab
  const filteredItems = useMemo(() => {
    switch (activeTab) {
      case 'favorites':
        return allItems.filter((item) => favorites.includes(item.id));
      case 'agents':
        return allItems.filter((item) => item.type === 'Agent');
      case 'jobs':
        return allItems.filter((item) => item.type === 'Job');
      case 'notebooks':
        return allItems.filter((item) => item.type === 'Notebook');
      case 'dashboards':
        return allItems.filter((item) => item.type === 'Dashboard');
      case 'recent':
      case 'suggested':
      default:
        return allItems;
    }
  }, [allItems, activeTab, favorites]);

  if (chatActive) {
    return (
      <div className="landing-assistant-fullscreen">
        <div className="landing-assistant-bar">
          <button
            type="button"
            className="landing-assistant-back-btn"
            onClick={() => setChatActive(false)}
          >
            <ArrowLeft size={14} /> Back to Landing Page
          </button>
          <span style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)', fontWeight: 500 }}>
            CompassX Assistant
          </span>
        </div>
        <div style={{ flex: 1, minHeight: 0 }}>
          <AppNovaSidebar />
        </div>
      </div>
    );
  }

  return (
    <div className="landing-page-root">
      {/* ── 1. Centered Header ────────────────────────────────────────────── */}
      <header className="landing-hero-header">
        <h1 className="landing-hero-title">
          Welcome to {workspace?.name || 'CompassX'}
        </h1>
      </header>

      {/* ── 2. Clean Omnibar Message Composer ────────────────────────────── */}
      <section className="landing-omnibar-card">
        <textarea
          className="landing-omnibar-textarea"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handlePromptSubmit();
            }
          }}
          placeholder="Ask anything across data, agents, notebooks, and jobs..."
          rows={2}
        />

        <div className="landing-omnibar-bottom">
          <div className="landing-omnibar-hint">
            <Sparkles size={14} className="landing-hint-icon" />
            <span>Press <kbd>Enter</kbd> to ask</span>
          </div>

          <div className="landing-omnibar-right-actions">
            <button
              type="button"
              className="landing-omnibar-submit-btn"
              onClick={handlePromptSubmit}
              disabled={!draft.trim()}
            >
              <span>Ask CompassX</span>
              <ExternalLink size={13} />
            </button>
          </div>
        </div>
      </section>

      {/* ── 3. Assistant Tip Banner ───────────────────────────────────────── */}
      {showTipBanner && (
        <div className="landing-tip-banner">
          <div className="landing-tip-left">
            <Sparkles size={16} className="landing-tip-icon" />
            <div className="landing-tip-text">
              <strong>CompassX AI</strong> lets you ask questions from all data across your workspace without needing to search schemas or write SQL queries manually.
              <span
                className="landing-tip-link"
                onClick={() => openAssistant('Help me explore this workspace and show what queries I can run.')}
              >
                Try CompassX AI
              </span>
            </div>
          </div>
          <button
            type="button"
            className="landing-tip-close"
            onClick={() => setShowTipBanner(false)}
            title="Dismiss"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* ── 4. Filter Tabs Row ────────────────────────────────────────────── */}
      <div className="landing-tabs-row">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              className={`landing-tab-btn ${isActive ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <Icon size={14} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* ── 5. Unified Workspace Items Feed ─────────────────────────────────── */}
      <section className="landing-items-card">
        {filteredItems.length > 0 ? (
          <div className="landing-items-list">
            {filteredItems.slice(0, limit).map((item) => {
              const Icon = item.icon;
              const isStarred = favorites.includes(item.id);

              return (
                <div
                  key={item.id}
                  className="landing-item-row"
                  onClick={() => {
                    if (item.targetUrl) {
                      navigate(item.targetUrl);
                    } else if (item.agentId) {
                      openAssistant(`Hi ${item.name}, `, {
                        type: 'agent',
                        agentId: item.agentId,
                      });
                    }
                  }}
                >
                  <div className="landing-item-row-left">
                    <div className="landing-item-icon-box">
                      <Icon size={16} />
                    </div>
                    <div className="landing-item-meta">
                      <div className="landing-item-name-row">
                        <span className="landing-item-name">{item.name}</span>
                      </div>
                      <span className="landing-item-path">{item.path}</span>
                    </div>
                  </div>

                  <div className="landing-item-row-right">
                    <span className="landing-item-time">{item.timeText}</span>
                    <span className="landing-item-type-badge">{item.type}</span>
                    <button
                      type="button"
                      className={`landing-item-star-btn ${isStarred ? 'starred' : ''}`}
                      onClick={(e) => toggleFavorite(item.id, e)}
                      title={isStarred ? 'Remove from favorites' : 'Add to favorites'}
                    >
                      <Star size={14} fill={isStarred ? 'currentColor' : 'none'} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="landing-empty-state">
            <span>No items found in this tab.</span>
          </div>
        )}
      </section>

      {/* ── 6. Show More Button ───────────────────────────────────────────── */}
      {filteredItems.length > limit && (
        <div className="landing-show-more-row">
          <button
            type="button"
            className="landing-show-more-btn"
            onClick={() => setLimit((prev) => prev + 10)}
          >
            Show more
          </button>
        </div>
      )}
    </div>
  );
}
