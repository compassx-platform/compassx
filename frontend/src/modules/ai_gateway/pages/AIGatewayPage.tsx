import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Cpu,
  Activity,
  Plus,
  RefreshCw,
  Trash2,
  Edit2,
  Play,
  ArrowLeft,
  Search,
  Eye,
  EyeOff,
  Lock,
  Database,
  Server,
  Layers,
  FileCode,
  Shield,
  CheckCircle2,
  XCircle,
  Clock,
  Terminal,
  HelpCircle,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Filter,
  Sparkles,
  Square,
  MessageSquare,
  Code,
  Settings,
  Copy,
} from 'lucide-react';
import { PageTabs } from '@/components/common/PageTabs';
import { AppTable, type AppTableColumn } from '@/components/common/AppTable';
import { useToast } from '@/lib/toast';
import { useCatalogs } from '@/modules/agents/hooks/useCatalogConnections';
import {
  fetchAIProviders,
  createAIProvider,
  updateAIProvider,
  deleteAIProvider,
  pingAIProvider,
  discoverAIProviderModels,
  fetchMCPServers,
  createMCPServer,
  updateMCPServer,
  deleteMCPServer,
  syncMCPServer,
  pingMCPServer,
  fetchMCPServerTools,
  fetchMCPTools,
  executeMCPTool,
  fetchInferenceLogs,
} from '../api';
import {
  AIProvider,
  MCPServer,
  MCPServerType,
  MCPToolDefinition,
  InferenceLog,
  AIProviderType,
} from '../types';

type AIGatewayTab = 'providers' | 'mcp' | 'logs';
type ViewMode =
  | 'list'
  | 'add_provider'
  | 'edit_provider'
  | 'add_mcp'
  | 'edit_mcp'
  | 'view_mcp_tools';

type McpServerItem =
  | MCPServer
  | {
      id: string | number;
      name: string;
      server_type: string;
      description: string;
      cached_tools: any[];
      is_builtin?: boolean;
      endpoint_url?: string;
      command?: string;
    };

const AI_GATEWAY_TABS = [
  { value: 'providers', label: 'Providers' },
  { value: 'mcp', label: 'MCP' },
  { value: 'logs', label: 'Inference & Audit Logs' },
] as const;

const PROVIDER_METADATA: Record<
  AIProviderType,
  { label: string; description: string; defaultBaseUrl: string; keyPlaceholder: string }
> = {
  openai: {
    label: 'OpenAI',
    description: 'GPT-4o, o1, o3-mini, and text-embedding-3 models.',
    defaultBaseUrl: 'https://api.openai.com/v1',
    keyPlaceholder: 'sk-proj-... or sk-...',
  },
  anthropic: {
    label: 'Anthropic Claude',
    description: 'Claude 3.5 Sonnet, Claude 3.7 Sonnet, and Claude 3.5 Haiku.',
    defaultBaseUrl: 'https://api.anthropic.com/v1',
    keyPlaceholder: 'sk-ant-api03-...',
  },
  gemini: {
    label: 'Google Gemini',
    description: 'Gemini 2.5 Flash, Gemini 2.0 Pro, and text-embedding-004.',
    defaultBaseUrl: 'https://generativelanguage.googleapis.com/v1beta',
    keyPlaceholder: 'AIzaSy...',
  },
  azure: {
    label: 'Azure OpenAI',
    description: 'Enterprise Azure-hosted OpenAI model deployments.',
    defaultBaseUrl: '',
    keyPlaceholder: 'Azure API Key',
  },
  ollama: {
    label: 'Ollama (Local)',
    description: 'Self-hosted open-source models (Llama 3, Mistral, DeepSeek).',
    defaultBaseUrl: 'http://localhost:11434/v1',
    keyPlaceholder: 'Optional (leave blank if unauthenticated)',
  },
  compatible: {
    label: 'OpenAI-Compatible',
    description: 'Custom proxy, LiteLLM, vLLM, or OpenRouter endpoint.',
    defaultBaseUrl: 'https://api.together.xyz/v1',
    keyPlaceholder: 'Bearer API Token',
  },
  bedrock: {
    label: 'AWS Bedrock',
    description: 'Amazon Bedrock models via AWS IAM / API keys.',
    defaultBaseUrl: 'https://bedrock-runtime.us-east-1.amazonaws.com',
    keyPlaceholder: 'AWS Secret Key / IAM Role',
  },
  vertex: {
    label: 'Google Vertex AI',
    description: 'Enterprise Google Cloud Vertex AI Model Garden.',
    defaultBaseUrl: 'https://us-central1-aiplatform.googleapis.com',
    keyPlaceholder: 'GCP Service Account Key JSON',
  },
};

// ==========================================
// BRAND ICONS (Databricks Style)
// ==========================================
const OpenAIIcon: React.FC<{ size?: number }> = ({ size = 15 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
    <path
      d="M22.28 10.37c-.12-.87-.49-1.68-1.07-2.33a4.7 4.7 0 0 0-3.34-1.63c-.38-.93-1.03-1.72-1.87-2.28a4.8 4.8 0 0 0-4.8-.44A4.7 4.7 0 0 0 7.8 4.7a4.8 4.8 0 0 0-4.04 2.8 4.7 4.7 0 0 0-.83 3.65c-.39.87-.51 1.83-.35 2.77.16.94.6 1.8 1.27 2.48.3 1 .9 1.85 1.73 2.45a4.8 4.8 0 0 0 4.87.53c.87.82 2 1.3 3.19 1.38.8.05 1.6-.1 2.34-.44a4.8 4.8 0 0 0 2.97-3.03 4.7 4.7 0 0 0 2.9-2.35 4.8 4.8 0 0 0 .43-4.57zM12 14.5a2.5 2.5 0 1 1 0-5 2.5 2.5 0 0 1 0 5z"
      fill="#10A37F"
    />
  </svg>
);

const AzureIcon: React.FC<{ size?: number }> = ({ size = 15 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
    <path d="M5.4 19.5L13 2.5l5.6 17H5.4z" fill="#0078D4" />
    <path d="M12.5 14.5L16 2.5l3.5 17h-7z" fill="#50E6FF" opacity="0.8" />
  </svg>
);

const AnthropicIcon: React.FC<{ size?: number }> = ({ size = 15 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
    <path
      d="M13.8 3h-3.6L4 21h3.7l1.7-4.6h5.2l1.7 4.6h3.7L13.8 3zm-3.3 10.3l1.5-4.2 1.5 4.2h-3z"
      fill="#D97706"
    />
  </svg>
);

const MicrosoftIcon: React.FC<{ size?: number }> = ({ size = 15 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
    <rect x="2" y="2" width="9" height="9" fill="#F25022" />
    <rect x="13" y="2" width="9" height="9" fill="#7FBA00" />
    <rect x="2" y="13" width="9" height="9" fill="#00A4EF" />
    <rect x="13" y="13" width="9" height="9" fill="#FFB900" />
  </svg>
);

const GeminiIcon: React.FC<{ size?: number }> = ({ size = 15 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
    <path
      d="M12 2C12 7.5 7.5 12 2 12C7.5 12 12 16.5 12 22C12 16.5 16.5 12 22 12C16.5 12 12 7.5 12 2Z"
      fill="url(#gemini-pill-grad)"
    />
    <defs>
      <linearGradient id="gemini-pill-grad" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
        <stop stopColor="#1B72E8" />
        <stop offset="0.5" stopColor="#A855F7" />
        <stop offset="1" stopColor="#EF4444" />
      </linearGradient>
    </defs>
  </svg>
);

const BedrockIcon: React.FC<{ size?: number }> = ({ size = 15 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
    <path
      d="M12 2L3 7v10l9 5 9-5V7l-9-5zm0 2.2l6.5 3.6L12 11.4 5.5 7.8 12 4.2zM4.8 9.3l6.2 3.5v7.2l-6.2-3.5V9.3zm8.4 10.7v-7.2l6.2-3.5v7.2l-6.2 3.5z"
      fill="#FF9900"
    />
  </svg>
);

const VertexIcon: React.FC<{ size?: number }> = ({ size = 15 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
    <path d="M12 2L4 7v10l8 5 8-5V7l-8-5z" stroke="#4285F4" strokeWidth="2" fill="none" />
    <path d="M12 8l4 2.5v5L12 18l-4-2.5v-5L12 8z" fill="#4285F4" />
  </svg>
);

interface ProviderPillOption {
  type: AIProviderType;
  label: string;
  icon: React.ReactNode;
}

const PROVIDER_PILLS: ProviderPillOption[] = [
  { type: 'openai', label: 'OpenAI', icon: <OpenAIIcon size={15} /> },
  { type: 'azure', label: 'Azure OpenAI', icon: <AzureIcon size={15} /> },
  { type: 'anthropic', label: 'Anthropic', icon: <AnthropicIcon size={15} /> },
  { type: 'compatible', label: 'Microsoft Foundry', icon: <MicrosoftIcon size={15} /> },
  { type: 'gemini', label: 'Gemini Enterprise', icon: <GeminiIcon size={15} /> },
  { type: 'bedrock', label: 'Amazon Bedrock', icon: <BedrockIcon size={15} /> },
  { type: 'vertex', label: 'Google Vertex AI', icon: <VertexIcon size={15} /> },
  { type: 'ollama', label: 'Ollama (Local)', icon: <Terminal size={14} color="#10B981" /> },
];

interface CatalogModelItem {
  id: string;
  name: string;
  provider: AIProviderType;
}

const HelpTooltip: React.FC<{ content: string }> = ({ content }) => {
  const [visible, setVisible] = useState(false);

  return (
    <div
      style={{
        position: 'relative',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'default',
      }}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
    >
      <HelpCircle
        size={14}
        style={{
          color: 'var(--color-text-muted, #71717A)',
          cursor: 'default',
          flexShrink: 0,
        }}
      />
      {visible && (
        <div
          role="tooltip"
          style={{
            position: 'absolute',
            bottom: 'calc(100% + 7px)',
            left: '50%',
            transform: 'translateX(-50%)',
            backgroundColor: '#0F172A',
            color: '#FFFFFF',
            fontSize: '0.74rem',
            lineHeight: 1.4,
            padding: '6px 10px',
            borderRadius: '6px',
            whiteSpace: 'normal',
            width: 'max-content',
            maxWidth: '280px',
            boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.4), 0 4px 6px -2px rgba(0, 0, 0, 0.3)',
            zIndex: 99999,
            pointerEvents: 'none',
            fontWeight: 400,
            border: '1px solid rgba(255, 255, 255, 0.15)',
            textAlign: 'left',
          }}
        >
          {content}
          <div
            style={{
              position: 'absolute',
              top: '100%',
              left: '50%',
              transform: 'translateX(-50%)',
              borderWidth: '5px',
              borderStyle: 'solid',
              borderColor: '#0F172A transparent transparent transparent',
            }}
          />
        </div>
      )}
    </div>
  );
};

export default function AIGatewayPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = (searchParams.get('tab') as AIGatewayTab) || 'providers';
  const [activeTab, setActiveTab] = useState<AIGatewayTab>(tabParam);
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const toast = useToast();

  // Search filter
  const [searchTerm, setSearchTerm] = useState('');

  // Data State
  const [providers, setProviders] = useState<AIProvider[]>([]);
  const [mcpServers, setMcpServers] = useState<MCPServer[]>([]);
  const [mcpTools, setMcpTools] = useState<MCPToolDefinition[]>([]);
  const [logs, setLogs] = useState<InferenceLog[]>([]);
  const [loading, setLoading] = useState(true);

  // Catalogs
  const { data: catalogs = [] } = useCatalogs();

  // Provider Form State (Full Page)
  const [providerForm, setProviderForm] = useState<{
    id?: number;
    catalog_name: string;
    schema_name: string;
    name: string;
    provider_type: AIProviderType;
    api_key: string;
    base_url: string;
    organization_id: string;
    azure_resource_name: string;
    azure_api_version: string;
    is_active: boolean;
  }>({
    catalog_name: 'default',
    schema_name: 'default',
    name: '',
    provider_type: 'openai',
    api_key: '',
    base_url: 'https://api.openai.com/v1',
    organization_id: '',
    azure_resource_name: '',
    azure_api_version: '2024-06-01',
    is_active: true,
  });

  const [showApiKey, setShowApiKey] = useState(false);
  const [savingProvider, setSavingProvider] = useState(false);
  const [pingingId, setPingingId] = useState<number | null>(null);

  // Databricks Form State
  const [authType, setAuthType] = useState<'plaintext' | 'secret_scope'>('plaintext');
  const [modelSearchTerm, setModelSearchTerm] = useState('');
  const [allowAllModels, setAllowAllModels] = useState(true);
  const [selectedModels, setSelectedModels] = useState<Set<string>>(new Set());
  const [advancedOpen, setAdvancedOpen] = useState(false);

  // MCP Server Form State (Full Page)
  const [mcpForm, setMcpForm] = useState<{
    id?: number;
    catalog_name: string;
    schema_name: string;
    name: string;
    description: string;
    server_type: MCPServerType;
    endpoint_url: string;
    command: string;
    auth_token: string;
    auth_header: string;
  }>({
    catalog_name: 'default',
    schema_name: 'default',
    name: '',
    description: '',
    server_type: 'remote_sse',
    endpoint_url: '',
    command: '',
    auth_token: '',
    auth_header: '',
  });
  const [showMcpToken, setShowMcpToken] = useState(false);
  const [mcpAuthType, setMcpAuthType] = useState<'plaintext' | 'secret_scope'>('plaintext');
  const [savingMcp, setSavingMcp] = useState(false);

  // Modals & Runners
  const [selectedMcpServer, setSelectedMcpServer] = useState<McpServerItem | null>(null);
  const [toolSearchTerm, setToolSearchTerm] = useState('');
  const [testingServerEndpoint, setTestingServerEndpoint] = useState(false);
  const [serverEndpointTestResult, setServerEndpointTestResult] = useState<{
    success: boolean;
    message: string;
    latency_ms: number;
    server_name: string;
    server_type: string;
    endpoint_url?: string;
    tools_count: number;
    tools: any[];
    raw_response?: any;
  } | null>(null);
  const [endpointDetailsExpanded, setEndpointDetailsExpanded] = useState(true);
  const [toolRunnerOpen, setToolRunnerOpen] = useState(false);
  const [selectedTool, setSelectedTool] = useState<MCPToolDefinition | null>(null);
  const [toolArgs, setToolArgs] = useState('{}');
  const [toolResult, setToolResult] = useState<any>(null);
  const [runningTool, setRunningTool] = useState(false);
  const [inspectLog, setInspectLog] = useState<InferenceLog | null>(null);

  // Dynamic discovered/custom models mapping
  const [customModelsMap, setCustomModelsMap] = useState<Record<string, CatalogModelItem[]>>({});
  const [quickModelInput, setQuickModelInput] = useState('');
  const [discoveringModels, setDiscoveringModels] = useState(false);
  const discoveryAbortControllerRef = useRef<AbortController | null>(null);
  const lastAutoDiscoveredKeyRef = useRef<string>('');

  // Only live / user-added models for the selected provider
  const currentModels = useMemo(() => {
    return customModelsMap[providerForm.provider_type] || [];
  }, [providerForm.provider_type, customModelsMap]);

  const handleQuickAddModel = (nameToAdd?: string) => {
    const rawName = typeof nameToAdd === 'string' ? nameToAdd : quickModelInput;
    const modelName = rawName.trim();
    if (!modelName) {
      toast.error('Model name is required');
      return;
    }

    const newItem: CatalogModelItem = {
      id: modelName,
      name: modelName,
      provider: providerForm.provider_type,
    };

    setCustomModelsMap((prev) => {
      const existing = prev[providerForm.provider_type] || [];
      if (existing.some((m) => m.id === modelName)) {
        toast.info(`Model '${modelName}' already in list`);
        return prev;
      }
      return {
        ...prev,
        [providerForm.provider_type]: [newItem, ...existing],
      };
    });

    setSelectedModels((prev) => new Set(prev).add(modelName));
    setQuickModelInput('');
    toast.success(`Model '${modelName}' added`);
  };

  const handleStopDiscovery = () => {
    if (discoveryAbortControllerRef.current) {
      discoveryAbortControllerRef.current.abort();
      discoveryAbortControllerRef.current = null;
    }
    setDiscoveringModels(false);
  };

  const handleDiscoverModels = useCallback(
    async (isAuto: boolean = false) => {
      if (providerForm.provider_type !== 'ollama' && !providerForm.api_key?.trim()) {
        if (!isAuto) toast.error('Please enter an API key before discovering models');
        return;
      }

      if (
        providerForm.provider_type === 'azure' &&
        !providerForm.azure_resource_name?.trim() &&
        (!providerForm.base_url?.trim() || providerForm.base_url.includes('<'))
      ) {
        if (!isAuto) toast.error('Please enter your Azure Resource Name or a valid Endpoint URL');
        return;
      }

      // Cancel any in-flight discovery
      if (discoveryAbortControllerRef.current) {
        discoveryAbortControllerRef.current.abort();
      }

      const controller = new AbortController();
      discoveryAbortControllerRef.current = controller;
      setDiscoveringModels(true);

      try {
        const res = await discoverAIProviderModels(
          {
            provider_type: providerForm.provider_type,
            api_key: providerForm.api_key || undefined,
            base_url: providerForm.base_url || undefined,
            config: {
              is_azure: providerForm.provider_type === 'azure',
              azure_resource_name: providerForm.azure_resource_name,
              azure_api_version: providerForm.azure_api_version,
              api_version: providerForm.azure_api_version,
              organization_id: providerForm.organization_id,
            },
          },
          controller.signal
        );

        if (!res.success) {
          if (!isAuto) toast.error(`Discovery failed: ${res.message}`);
          return;
        }

        if (!res.available_models || res.available_models.length === 0) {
          if (!isAuto) toast.info(`Connected (${res.latency_ms}ms), but no models were returned by the upstream provider.`);
          return;
        }

        const discoveredItems: CatalogModelItem[] = res.available_models.map((mName) => ({
          id: mName,
          name: mName,
          provider: providerForm.provider_type,
        }));

        setCustomModelsMap((prev) => {
          const existing = prev[providerForm.provider_type] || [];
          const map = new Map<string, CatalogModelItem>();
          discoveredItems.forEach((m) => map.set(m.id, m));
          existing.forEach((m) => {
            if (!map.has(m.id)) map.set(m.id, m);
          });
          return {
            ...prev,
            [providerForm.provider_type]: Array.from(map.values()),
          };
        });

        // Auto-select discovered models
        setSelectedModels((prev) => {
          const next = new Set(prev);
          discoveredItems.forEach((m) => next.add(m.id));
          return next;
        });

        toast.success(`Discovered ${discoveredItems.length} models in ${res.latency_ms}ms`);
      } catch (err: any) {
        if (err?.name === 'CanceledError' || err?.name === 'AbortError' || err?.code === 'ERR_CANCELED') {
          toast.info('Model discovery stopped');
        } else {
          if (!isAuto) {
            toast.error(err?.response?.data?.detail || err?.message || 'Failed to discover models');
          }
        }
      } finally {
        if (discoveryAbortControllerRef.current === controller) {
          discoveryAbortControllerRef.current = null;
          setDiscoveringModels(false);
        }
      }
    },
    [providerForm, toast]
  );

  // Auto-discover models when credentials (API key / URL / resource name) are filled in
  useEffect(() => {
    if (viewMode !== 'add_provider' && viewMode !== 'edit_provider') {
      return;
    }

    const pType = providerForm.provider_type;
    const apiKey = providerForm.api_key?.trim() || '';
    const baseUrl = providerForm.base_url?.trim() || '';
    const azureRes = providerForm.azure_resource_name?.trim() || '';

    let canAutoDiscover = false;
    if (pType === 'ollama') {
      canAutoDiscover = baseUrl.length > 5 && !baseUrl.includes('<');
    } else if (pType === 'azure') {
      canAutoDiscover = apiKey.length >= 6 && (azureRes.length >= 2 || (baseUrl.length > 10 && !baseUrl.includes('<')));
    } else if (pType === 'compatible') {
      canAutoDiscover = apiKey.length >= 5 && baseUrl.length > 5 && !baseUrl.includes('<');
    } else {
      canAutoDiscover = apiKey.length >= 6;
    }

    if (!canAutoDiscover) return;

    const fingerprint = `${pType}|${apiKey}|${baseUrl}|${azureRes}|${providerForm.azure_api_version}`;
    if (lastAutoDiscoveredKeyRef.current === fingerprint) {
      return;
    }

    const timer = setTimeout(() => {
      lastAutoDiscoveredKeyRef.current = fingerprint;
      handleDiscoverModels(true);
    }, 650);

    return () => {
      clearTimeout(timer);
    };
  }, [
    viewMode,
    providerForm.provider_type,
    providerForm.api_key,
    providerForm.base_url,
    providerForm.azure_resource_name,
    providerForm.azure_api_version,
    handleDiscoverModels,
  ]);

  const filteredCatalogModels = useMemo(() => {
    if (!modelSearchTerm.trim()) return currentModels;
    const term = modelSearchTerm.toLowerCase();
    return currentModels.filter((m) => m.name.toLowerCase().includes(term));
  }, [currentModels, modelSearchTerm]);

  // Schemas for chosen catalog
  const availableSchemas = useMemo(() => {
    const found = catalogs.find((c) => c.name === providerForm.catalog_name);
    return found?.schemas || [];
  }, [catalogs, providerForm.catalog_name]);

  const handleCatalogChange = (catName: string) => {
    const targetCat = catalogs.find((c) => c.name === catName);
    const firstSchema = targetCat?.schemas?.[0]?.name || 'default';
    setProviderForm((prev) => ({
      ...prev,
      catalog_name: catName,
      schema_name: firstSchema,
    }));
  };

  // Schemas for chosen MCP catalog
  const availableMcpSchemas = useMemo(() => {
    const found = catalogs.find((c) => c.name === mcpForm.catalog_name);
    return found?.schemas || [];
  }, [catalogs, mcpForm.catalog_name]);

  const handleMcpCatalogChange = (catName: string) => {
    const targetCat = catalogs.find((c) => c.name === catName);
    const firstSchema = targetCat?.schemas?.[0]?.name || 'default';
    setMcpForm((prev) => ({
      ...prev,
      catalog_name: catName,
      schema_name: firstSchema,
    }));
  };

  const handleTabChange = (newTab: AIGatewayTab) => {
    setActiveTab(newTab);
    setViewMode('list');
    setSearchParams({ tab: newTab });
  };

  useEffect(() => {
    if (tabParam && tabParam !== activeTab) {
      setActiveTab(tabParam);
    }
  }, [tabParam]);

  // Load data
  const loadData = async () => {
    setLoading(true);
    try {
      if (activeTab === 'providers') {
        const data = await fetchAIProviders();
        setProviders(data);
      } else if (activeTab === 'mcp') {
        const [servers, tools] = await Promise.all([fetchMCPServers(), fetchMCPTools()]);
        setMcpServers(servers);
        setMcpTools(tools);
      } else if (activeTab === 'logs') {
        const logData = await fetchInferenceLogs();
        setLogs(logData);
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to load AI Gateway data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (viewMode === 'list') {
      loadData();
    }
  }, [activeTab, viewMode]);

  // Navigate to Add Provider Form
  const handleOpenAddProvider = () => {
    const defaultCatalog = catalogs?.[0]?.name || 'default';
    const defaultSchema = catalogs?.[0]?.schemas?.[0]?.name || 'default';
    setProviderForm({
      catalog_name: defaultCatalog,
      schema_name: defaultSchema,
      name: '',
      provider_type: 'openai',
      api_key: '',
      base_url: PROVIDER_METADATA.openai.defaultBaseUrl,
      organization_id: '',
      azure_resource_name: '',
      azure_api_version: '2024-06-01',
      is_active: true,
    });
    setShowApiKey(false);
    setViewMode('add_provider');
  };

  const handleOpenEditProvider = (p: AIProvider) => {
    setProviderForm({
      id: p.id,
      catalog_name: p.catalog_name || (catalogs?.[0]?.name || 'default'),
      schema_name: p.schema_name || (catalogs?.[0]?.schemas?.[0]?.name || 'default'),
      name: p.name,
      provider_type: p.provider_type,
      api_key: '',
      base_url: p.base_url || (p.provider_type === 'azure' ? '' : PROVIDER_METADATA[p.provider_type]?.defaultBaseUrl || ''),
      organization_id: p.config?.organization_id || '',
      azure_resource_name: p.config?.azure_resource_name || '',
      azure_api_version: p.config?.api_version || p.config?.azure_api_version || '2024-06-01',
      is_active: p.is_active,
    });
    setShowApiKey(false);
    setViewMode('edit_provider');
  };

  const handleSelectProviderType = (type: AIProviderType) => {
    const meta = PROVIDER_METADATA[type];
    setProviderForm((prev) => ({
      ...prev,
      provider_type: type,
      base_url: type === 'azure' ? '' : meta.defaultBaseUrl,
    }));
  };

  const handleSaveProviderForm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!providerForm.name.trim()) {
      toast.error('Provider name is required');
      return;
    }
    if (!providerForm.catalog_name.trim()) {
      toast.error('Catalog name is required');
      return;
    }
    if (!providerForm.schema_name.trim()) {
      toast.error('Schema name is required');
      return;
    }

    setSavingProvider(true);
    try {
      const config: Record<string, any> = {};
      if (providerForm.organization_id) config.organization_id = providerForm.organization_id;
      if (providerForm.provider_type === 'azure') {
        config.is_azure = true;
        config.azure_resource_name = providerForm.azure_resource_name;
        config.api_version = providerForm.azure_api_version;
      }

      if (viewMode === 'edit_provider' && providerForm.id) {
        await updateAIProvider(providerForm.id, {
          catalog_name: providerForm.catalog_name.trim(),
          schema_name: providerForm.schema_name.trim(),
          name: providerForm.name.trim(),
          provider_type: providerForm.provider_type,
          api_key: providerForm.api_key ? providerForm.api_key : undefined,
          base_url: providerForm.base_url || undefined,
          config,
          is_active: providerForm.is_active,
        });
        toast.success('Provider updated successfully');
      } else {
        await createAIProvider({
          catalog_name: providerForm.catalog_name.trim(),
          schema_name: providerForm.schema_name.trim(),
          name: providerForm.name.trim(),
          provider_type: providerForm.provider_type,
          api_key: providerForm.api_key || undefined,
          base_url: providerForm.base_url || undefined,
          config,
          is_active: providerForm.is_active,
        });
        toast.success('Provider created successfully');
      }

      setViewMode('list');
      loadData();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to save provider');
    } finally {
      setSavingProvider(false);
    }
  };

  // Provider Ping & Delete Actions
  const handlePingProvider = async (id: number) => {
    setPingingId(id);
    try {
      const res = await pingAIProvider(id);
      if (res.success) {
        toast.success(`Connection successful (${res.latency_ms}ms)`);
      } else {
        toast.error(`Connection failed: ${res.message}`);
      }
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Ping failed');
    } finally {
      setPingingId(null);
    }
  };

  const handleDeleteProvider = async (id: number) => {
    if (!confirm('Are you sure you want to delete this provider?')) return;
    try {
      await deleteAIProvider(id);
      toast.success('Provider deleted');
      loadData();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Failed to delete provider');
    }
  };

  // MCP Actions & Forms
  const handleOpenAddMcp = () => {
    const defaultCatalog = catalogs?.[0]?.name || 'default';
    const defaultSchema = catalogs?.[0]?.schemas?.[0]?.name || 'default';
    setMcpForm({
      catalog_name: defaultCatalog,
      schema_name: defaultSchema,
      name: '',
      description: '',
      server_type: 'remote_sse',
      endpoint_url: '',
      command: '',
      auth_token: '',
      auth_header: '',
    });
    setShowMcpToken(false);
    setViewMode('add_mcp');
  };

  const handleOpenEditMcp = (s: MCPServer) => {
    setMcpForm({
      id: s.id,
      catalog_name: s.catalog_name || (catalogs?.[0]?.name || 'default'),
      schema_name: s.schema_name || (catalogs?.[0]?.schemas?.[0]?.name || 'default'),
      name: s.name,
      description: s.description || '',
      server_type: s.server_type,
      endpoint_url: s.endpoint_url || '',
      command: s.command || '',
      auth_token: '',
      auth_header: '',
    });
    setShowMcpToken(false);
    setViewMode('edit_mcp');
  };

  const handleSaveMcpForm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!mcpForm.name.trim()) {
      toast.error('MCP Server name is required');
      return;
    }
    if (!mcpForm.catalog_name.trim()) {
      toast.error('Catalog name is required');
      return;
    }
    if (!mcpForm.schema_name.trim()) {
      toast.error('Schema name is required');
      return;
    }

    setSavingMcp(true);
    try {
      let authHeaders: Record<string, string> | undefined = undefined;
      if (mcpForm.auth_token?.trim()) {
        authHeaders = { Authorization: `Bearer ${mcpForm.auth_token.trim()}` };
      } else if (mcpForm.auth_header?.trim()) {
        authHeaders = { Authorization: mcpForm.auth_header.trim() };
      }

      let savedServer: MCPServer;
      if (viewMode === 'edit_mcp' && mcpForm.id) {
        savedServer = await updateMCPServer(mcpForm.id, {
          catalog_name: mcpForm.catalog_name.trim(),
          schema_name: mcpForm.schema_name.trim(),
          name: mcpForm.name.trim(),
          description: mcpForm.description.trim() || undefined,
          server_type: mcpForm.server_type,
          endpoint_url: mcpForm.server_type === 'remote_sse' ? mcpForm.endpoint_url.trim() : undefined,
          command: mcpForm.server_type === 'subprocess' ? mcpForm.command.trim() : undefined,
          auth_headers: authHeaders,
        });
        toast.success('MCP server updated successfully');
      } else {
        savedServer = await createMCPServer({
          catalog_name: mcpForm.catalog_name.trim(),
          schema_name: mcpForm.schema_name.trim(),
          name: mcpForm.name.trim(),
          description: mcpForm.description.trim() || undefined,
          server_type: mcpForm.server_type,
          endpoint_url: mcpForm.server_type === 'remote_sse' ? mcpForm.endpoint_url.trim() : undefined,
          command: mcpForm.server_type === 'subprocess' ? mcpForm.command.trim() : undefined,
          auth_headers: authHeaders,
        });
        toast.success('MCP server registered and tools loaded');
      }

      await loadData();
      setSelectedMcpServer(savedServer);
      setToolSearchTerm('');
      setViewMode('view_mcp_tools');
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Failed to save MCP server');
    } finally {
      setSavingMcp(false);
    }
  };

  // MCP Actions
  const getServerIdentifier = (server: McpServerItem | MCPServer): string => {
    if ((server as MCPServer).full_name) {
      return (server as MCPServer).full_name!;
    }
    const cat = (server as MCPServer).catalog_name || (server.is_builtin ? 'system' : 'default');
    const sch = (server as MCPServer).schema_name || (server.is_builtin ? 'ai' : 'default');
    return `${cat}.${sch}.${server.name}`;
  };

  const handleTestMcpEndpoint = async (server: McpServerItem) => {
    setTestingServerEndpoint(true);
    setServerEndpointTestResult(null);
    setEndpointDetailsExpanded(true);
    const identifier = getServerIdentifier(server);
    try {
      const res = await fetchMCPServerTools(identifier);
      setServerEndpointTestResult(res);
      if (res.success) {
        toast.success(`Connected (${res.latency_ms}ms, ${res.tools_count} tools returned)`);
        loadData();
      } else {
        toast.error(res.message || 'Endpoint connection failed');
      }
    } catch (err: any) {
      const errMsg = err?.response?.data?.detail || err?.message || 'Failed to connect to endpoint';
      toast.error(errMsg);
      setServerEndpointTestResult({
        success: false,
        message: errMsg,
        latency_ms: 0,
        called_endpoint: `/api/v1/ai-gateway/mcp/servers/${identifier}/tools`,
        http_method: 'GET',
        mcp_method: 'tools/list',
        mcp_protocol: 'JSON-RPC 2.0',
        upstream_target: (server as MCPServer).endpoint_url || (server as MCPServer).command || 'compassx-internal-runtime',
        server_name: server.name,
        server_type: server.server_type,
        tools_count: 0,
        tools: [],
        raw_response: { error: errMsg },
      } as any);
    } finally {
      setTestingServerEndpoint(false);
    }
  };

  const handleSyncMCPServer = async (id: number) => {
    try {
      const res = await syncMCPServer(id);
      toast.success(`Synchronized ${res.tools_count} tools from ${res.server_name}`);
      loadData();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Failed to sync MCP server');
    }
  };

  const handleDeleteMCPServer = async (id: number) => {
    if (!confirm('Are you sure you want to delete this MCP server?')) return;
    try {
      await deleteMCPServer(id);
      toast.success('MCP server deleted');
      loadData();
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || 'Failed to delete MCP server');
    }
  };

  const handleRunTool = async () => {
    if (!selectedTool) return;
    setRunningTool(true);
    setToolResult(null);
    try {
      const parsedArgs = JSON.parse(toolArgs || '{}');
      const res = await executeMCPTool(selectedTool.name, parsedArgs);
      setToolResult(res);
      if (res.is_error) {
        toast.error(`Tool error: ${res.error_message}`);
      } else {
        toast.success(`Tool executed successfully in ${res.latency_ms}ms`);
      }
    } catch (e: any) {
      toast.error(`Execution failed: ${e.message}`);
      setToolResult({ is_error: true, error_message: e.message });
    } finally {
      setRunningTool(false);
    }
  };

  // Combined built-in + registered MCP servers
  const allMcpServers: McpServerItem[] = useMemo(() => {
    const builtins: McpServerItem[] = [
      {
        id: 'native_sql',
        name: 'compassx_sql_warehouse',
        server_type: 'native',
        description: 'Native SQL execution and table introspection in CompassX.',
        cached_tools: [{ name: 'sql_execute_query' }, { name: 'list_tables' }, { name: 'describe_table' }],
        is_builtin: true,
      },
      {
        id: 'native_catalog',
        name: 'compassx_catalog_search',
        server_type: 'native',
        description: 'Unified vector & lexical search over catalog tables, schemas, and assets.',
        cached_tools: [{ name: 'catalog_search' }],
        is_builtin: true,
      },
    ];
    return [...builtins, ...mcpServers];
  }, [mcpServers]);

  const getToolCountForServer = useCallback(
    (server: McpServerItem): number => {
      const matches = mcpTools.filter((t) => {
        if (typeof server.id === 'number' && t.server_id === server.id) return true;
        if (t.server_name && t.server_name.toLowerCase() === server.name.toLowerCase()) return true;
        if (server.name === 'compassx_sql_warehouse' && ['sql_execute_query', 'list_tables', 'describe_table'].includes(t.name)) return true;
        if (server.name === 'compassx_catalog_search' && ['catalog_search'].includes(t.name)) return true;
        return false;
      });
      if (matches.length > 0) return matches.length;
      return server.cached_tools?.length || 0;
    },
    [mcpTools]
  );

  // Tools for the currently selected MCP server
  const serverTools: MCPToolDefinition[] = useMemo(() => {
    if (!selectedMcpServer) return [];
    const matches = mcpTools.filter((t) => {
      if (typeof selectedMcpServer.id === 'number' && t.server_id === selectedMcpServer.id) return true;
      if (t.server_name && t.server_name.toLowerCase() === selectedMcpServer.name.toLowerCase()) return true;
      if (selectedMcpServer.name === 'compassx_sql_warehouse' && ['sql_execute_query', 'list_tables', 'describe_table'].includes(t.name)) return true;
      if (selectedMcpServer.name === 'compassx_catalog_search' && ['catalog_search'].includes(t.name)) return true;
      return false;
    });
    if (matches.length > 0) return matches;

    if (selectedMcpServer.cached_tools && Array.isArray(selectedMcpServer.cached_tools)) {
      return selectedMcpServer.cached_tools.map((ct: any) => ({
        name: ct.name,
        description: ct.description || '',
        server_name: selectedMcpServer.name,
        server_id: typeof selectedMcpServer.id === 'number' ? selectedMcpServer.id : undefined,
        input_schema: ct.inputSchema || ct.input_schema,
      }));
    }
    return [];
  }, [selectedMcpServer, mcpTools]);

  const filteredServerTools = useMemo(() => {
    if (!toolSearchTerm.trim()) return serverTools;
    const q = toolSearchTerm.toLowerCase();
    return serverTools.filter(
      (t) =>
        t.name.toLowerCase().includes(q) ||
        (t.description && t.description.toLowerCase().includes(q))
    );
  }, [serverTools, toolSearchTerm]);

  // Filtered lists
  const filteredProviders = useMemo(() => {
    if (!searchTerm) return providers;
    const q = searchTerm.toLowerCase();
    return providers.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.provider_type.toLowerCase().includes(q) ||
        (p.catalog_name && p.catalog_name.toLowerCase().includes(q)) ||
        (p.schema_name && p.schema_name.toLowerCase().includes(q)) ||
        (p.created_by && p.created_by.toLowerCase().includes(q))
    );
  }, [providers, searchTerm]);

  const filteredMcpServers = useMemo(() => {
    if (!searchTerm) return allMcpServers;
    const q = searchTerm.toLowerCase();
    return allMcpServers.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        (s.description && s.description.toLowerCase().includes(q)) ||
        s.server_type.toLowerCase().includes(q)
    );
  }, [allMcpServers, searchTerm]);

  const filteredLogs = useMemo(() => {
    if (!searchTerm) return logs;
    const q = searchTerm.toLowerCase();
    return logs.filter(
      (l) =>
        l.endpoint_name?.toLowerCase().includes(q) ||
        l.upstream_model_name?.toLowerCase().includes(q) ||
        l.caller_type?.toLowerCase().includes(q)
    );
  }, [logs, searchTerm]);

  // ==========================================
  // TABLE COLUMN DEFINITIONS (Databricks Style)
  // ==========================================

  const providerColumns: AppTableColumn<AIProvider>[] = [
    {
      key: 'name',
      header: 'Name',
      render: (row) => (
        <div>
          <div
            style={{
              fontWeight: 600,
              fontSize: '0.84rem',
              color: 'var(--color-primary, #1B6EF3)',
              cursor: 'pointer',
            }}
            onClick={() => handleOpenEditProvider(row)}
          >
            {row.name}
          </div>
          {row.config?.azure_resource_name && (
            <div style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)' }}>
              {row.config.azure_resource_name}
            </div>
          )}
        </div>
      ),
    },
    {
      key: 'provider',
      header: 'Provider',
      render: (row) => {
        const meta = PROVIDER_METADATA[row.provider_type];
        const pill = PROVIDER_PILLS.find((p) => p.type === row.provider_type);
        return (
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            {pill?.icon}
            <span
              style={{
                fontSize: '0.78rem',
                fontWeight: 500,
                color: 'var(--color-text)',
              }}
            >
              {meta?.label || row.provider_type}
            </span>
          </div>
        );
      },
    },
    {
      key: 'location',
      header: 'Location',
      render: (row) => (
        <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
          {row.catalog_name || 'default'}.{row.schema_name || 'default'}
        </span>
      ),
    },
    {
      key: 'created_by',
      header: 'Created by',
      render: (row) => (
        <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
          {row.created_by || 'system'}
        </span>
      ),
    },
    {
      key: 'last_modified',
      header: 'Last modified',
      render: (row) => {
        const dateVal = row.updated_at || row.created_at;
        return (
          <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
            {dateVal
              ? new Date(dateVal).toLocaleString([], {
                  year: 'numeric',
                  month: 'short',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                })
              : '—'}
          </span>
        );
      },
    },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      className: 'app-table-actions',
      render: (row) => (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 4 }}>
          <button
            className="ghost-icon-btn"
            title="Test Connection"
            onClick={() => handlePingProvider(row.id)}
            disabled={pingingId === row.id}
          >
            <Activity size={13} className={pingingId === row.id ? 'spin' : ''} />
          </button>
          <button
            className="ghost-icon-btn"
            title="Delete Provider"
            onClick={() => handleDeleteProvider(row.id)}
            style={{ color: 'var(--color-danger, #EF4444)' }}
          >
            <Trash2 size={13} />
          </button>
        </div>
      ),
    },
  ];

  const mcpServerColumns: AppTableColumn<McpServerItem>[] = [
    {
      key: 'name',
      header: 'Server Name',
      render: (row) => (
        <div
          style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}
          onClick={() => {
            setSelectedMcpServer(row);
            setToolSearchTerm('');
            setViewMode('view_mcp_tools');
          }}
        >
          <Server size={14} color="var(--color-primary, #1B6EF3)" />
          <span
            style={{
              fontWeight: 600,
              fontSize: '0.84rem',
              color: 'var(--color-primary, #1B6EF3)',
            }}
          >
            {row.name}
          </span>
        </div>
      ),
    },
    {
      key: 'server_type',
      header: 'Transport Type',
      render: (row) => (
        <span
          style={{
            padding: '2px 7px',
            borderRadius: 4,
            fontSize: '0.72rem',
            fontWeight: 600,
            background: row.is_builtin ? 'rgba(34, 197, 94, 0.1)' : 'rgba(27, 110, 243, 0.1)',
            color: row.is_builtin ? '#22C55E' : 'var(--color-primary, #1B6EF3)',
          }}
        >
          {row.server_type.toUpperCase()}
        </span>
      ),
    },
    {
      key: 'location',
      header: 'Location',
      render: (row) => {
        const cat = (row as MCPServer).catalog_name || 'default';
        const sch = (row as MCPServer).schema_name || 'default';
        return (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              fontSize: '0.74rem',
              fontFamily: 'monospace',
              color: 'var(--color-text-muted)',
              background: 'var(--color-bg, #F3F4F6)',
              padding: '2px 7px',
              borderRadius: 4,
              border: '1px solid var(--color-border)',
            }}
          >
            <Database size={11} />
            {cat}.{sch}
          </span>
        );
      },
    },
    {
      key: 'description',
      header: 'Description',
      render: (row) => (
        <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
          {row.description || '—'}
        </span>
      ),
    },
    {
      key: 'cached_tools',
      header: 'Tools',
      render: (row) => {
        const count = getToolCountForServer(row);
        return (
          <button
            type="button"
            onClick={() => {
              setSelectedMcpServer(row);
              setToolSearchTerm('');
              setViewMode('view_mcp_tools');
            }}
            style={{
              background: 'none',
              border: 'none',
              padding: 0,
              cursor: 'pointer',
              color: 'var(--color-primary, #1B6EF3)',
              fontSize: '0.78rem',
              fontWeight: 500,
              textDecoration: 'underline',
              textUnderlineOffset: 2,
            }}
          >
            {count} {count === 1 ? 'tool' : 'tools'}
          </button>
        );
      },
    },
    {
      key: 'endpoint',
      header: 'Endpoint',
      render: (row) => {
        const endpointVal =
          (row as MCPServer).endpoint_url ||
          (row as MCPServer).command ||
          (row.is_builtin ? 'compassx_builtin' : '—');
        return (
          <span
            style={{
              fontSize: '0.78rem',
              fontFamily: 'monospace',
              color: 'var(--color-text)',
              maxWidth: 240,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              display: 'inline-block',
            }}
            title={endpointVal}
          >
            {endpointVal}
          </span>
        );
      },
    },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      className: 'app-table-actions',
      render: (row) => (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 4 }}>
          <button
            className="ghost-icon-btn"
            title="View Tools"
            onClick={() => {
              setSelectedMcpServer(row);
              setToolSearchTerm('');
              setViewMode('view_mcp_tools');
            }}
          >
            <Eye size={13} />
          </button>
          {typeof row.id === 'number' && (
            <>
              <button
                className="ghost-icon-btn"
                title="Sync Tools"
                onClick={() => handleSyncMCPServer(row.id as number)}
              >
                <RefreshCw size={13} />
              </button>
              <button
                className="ghost-icon-btn"
                title="Edit MCP Server"
                onClick={() => handleOpenEditMcp(row as MCPServer)}
              >
                <Edit2 size={13} />
              </button>
              <button
                className="ghost-icon-btn"
                title="Delete Server"
                onClick={() => handleDeleteMCPServer(row.id as number)}
                style={{ color: 'var(--color-danger, #EF4444)' }}
              >
                <Trash2 size={13} />
              </button>
            </>
          )}
        </div>
      ),
    },
  ];

  const serverToolColumns: AppTableColumn<MCPToolDefinition>[] = [
    {
      key: 'name',
      header: 'Tool Function Name',
      render: (row) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Code size={13} color="var(--color-primary, #1B6EF3)" />
          <code style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--color-primary, #1B6EF3)' }}>
            {row.name}
          </code>
        </div>
      ),
    },
    {
      key: 'description',
      header: 'Description',
      render: (row) => (
        <span style={{ fontSize: '0.78rem', color: 'var(--color-text)' }}>
          {row.description || 'No description provided'}
        </span>
      ),
    },
    {
      key: 'input_schema',
      header: 'Parameters',
      render: (row) => {
        const schema = row.input_schema;
        if (!schema || !schema.properties || Object.keys(schema.properties).length === 0) {
          return <span style={{ fontSize: '0.74rem', color: 'var(--color-text-muted)' }}>None</span>;
        }
        const propKeys = Object.keys(schema.properties);
        const requiredList = Array.isArray(schema.required) ? schema.required : [];
        return (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center' }}>
            {propKeys.slice(0, 4).map((prop) => {
              const isReq = requiredList.includes(prop);
              return (
                <span
                  key={prop}
                  style={{
                    fontSize: '0.72rem',
                    fontFamily: 'monospace',
                    padding: '1px 5px',
                    borderRadius: 3,
                    background: isReq ? 'rgba(239, 68, 68, 0.08)' : 'var(--color-surface-hover, #F3F4F6)',
                    color: isReq ? '#DC2626' : 'var(--color-text)',
                    border: `1px solid ${isReq ? 'rgba(239, 68, 68, 0.2)' : 'var(--color-border)'}`,
                  }}
                  title={`${prop}${isReq ? ' (required)' : ''}: ${schema.properties[prop]?.type || 'any'}`}
                >
                  {prop}{isReq && '*'}
                </span>
              );
            })}
            {propKeys.length > 4 && (
              <span style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)' }}>
                +{propKeys.length - 4} more
              </span>
            )}
          </div>
        );
      },
    },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      className: 'app-table-actions',
      render: (row) => (
        <button
          onClick={() => {
            setSelectedTool(row);
            let initialArgs = '{}';
            if (row.input_schema?.properties) {
              const template: Record<string, any> = {};
              for (const [k, v] of Object.entries(row.input_schema.properties as Record<string, any>)) {
                if (v.type === 'string') template[k] = v.default || '';
                else if (v.type === 'number' || v.type === 'integer') template[k] = v.default || 0;
                else if (v.type === 'boolean') template[k] = v.default || false;
                else if (v.type === 'array') template[k] = [];
                else template[k] = null;
              }
              initialArgs = JSON.stringify(template, null, 2);
            }
            setToolArgs(initialArgs);
            setToolResult(null);
            setToolRunnerOpen(true);
          }}
          style={{
            padding: '3px 8px',
            borderRadius: 4,
            background: 'rgba(27, 110, 243, 0.08)',
            color: 'var(--color-primary, #1B6EF3)',
            border: '1px solid rgba(27, 110, 243, 0.2)',
            fontSize: '0.74rem',
            fontWeight: 500,
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
          }}
        >
          <Play size={10} /> Run Tool
        </button>
      ),
    },
  ];

  const logColumns: AppTableColumn<InferenceLog>[] = [
    {
      key: 'created_at',
      header: 'Timestamp',
      render: (row) => (
        <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
          {new Date(row.created_at).toLocaleTimeString()}
        </span>
      ),
    },
    {
      key: 'endpoint_name',
      header: 'Endpoint Alias',
      render: (row) => (
        <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--color-text)' }}>
          {row.endpoint_name}
        </span>
      ),
    },
    {
      key: 'upstream_model_name',
      header: 'Model / Vendor',
      render: (row) => (
        <code style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
          {row.upstream_model_name}
        </code>
      ),
    },
    {
      key: 'caller_type',
      header: 'Caller',
      render: (row) => (
        <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
          {row.caller_type}
        </span>
      ),
    },
    {
      key: 'tokens',
      header: 'Tokens (In / Out)',
      render: (row) => (
        <span style={{ fontSize: '0.78rem', color: 'var(--color-text)' }}>
          {row.input_tokens} / {row.output_tokens}
        </span>
      ),
    },
    {
      key: 'latency_ms',
      header: 'Latency',
      render: (row) => (
        <span style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
          {row.latency_ms}ms
        </span>
      ),
    },
    {
      key: 'total_cost',
      header: 'Cost',
      render: (row) => (
        <span style={{ fontSize: '0.78rem', color: 'var(--color-text)' }}>
          ${Number(row.total_cost || 0).toFixed(4)}
        </span>
      ),
    },
    {
      key: 'status_code',
      header: 'Status',
      render: (row) => (
        <span
          style={{
            padding: '2px 6px',
            borderRadius: 4,
            fontSize: '0.72rem',
            fontWeight: 600,
            background: row.status_code === 200 ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
            color: row.status_code === 200 ? '#22C55E' : '#EF4444',
          }}
        >
          {row.status_code}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Payload',
      align: 'right',
      className: 'app-table-actions',
      render: (row) => (
        <button
          className="ghost-icon-btn"
          title="Inspect inference details"
          onClick={() => setInspectLog(row)}
        >
          <FileCode size={13} />
        </button>
      ),
    },
  ];

  // ==========================================
  // HELPER: MCP TOOL RUNNER MODAL
  // ==========================================
  const renderToolRunnerModal = () => {
    if (!toolRunnerOpen || !selectedTool) return null;
    return (
      <div
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0,0,0,0.55)',
          backdropFilter: 'blur(3px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
        }}
      >
        <div
          style={{
            background: 'var(--color-surface, #FFFFFF)',
            borderRadius: 10,
            padding: 24,
            width: '100%',
            maxWidth: 620,
            border: '1px solid var(--color-border)',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.25), 0 8px 10px -6px rgba(0, 0, 0, 0.2)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--color-text)' }}>
                Test MCP Tool
              </span>
              <code
                style={{
                  fontSize: '0.84rem',
                  fontWeight: 600,
                  color: 'var(--color-primary, #1B6EF3)',
                  background: 'rgba(27, 110, 243, 0.08)',
                  padding: '2px 8px',
                  borderRadius: 4,
                }}
              >
                {selectedTool.name}
              </code>
            </div>
            <span
              style={{
                fontSize: '0.74rem',
                color: 'var(--color-text-muted)',
                border: '1px solid var(--color-border)',
                padding: '2px 8px',
                borderRadius: 12,
              }}
            >
              {selectedTool.server_name || 'native'}
            </span>
          </div>

          <p style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)', margin: '0 0 16px 0', lineHeight: 1.4 }}>
            {selectedTool.description || 'Executes this tool function against the underlying MCP server.'}
          </p>

          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 550, marginBottom: 4, color: 'var(--color-text)' }}>
              Input JSON Arguments
            </label>
            <textarea
              rows={4}
              value={toolArgs}
              onChange={(e) => setToolArgs(e.target.value)}
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: 6,
                border: '1px solid var(--color-border)',
                background: 'var(--color-bg)',
                color: 'var(--color-text)',
                fontFamily: 'monospace',
                fontSize: '0.82rem',
                lineHeight: 1.4,
                resize: 'vertical',
              }}
            />
          </div>

          {toolResult && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                <label style={{ fontSize: '0.78rem', fontWeight: 550, color: 'var(--color-text)' }}>
                  Execution Result
                </label>
                <span
                  style={{
                    fontSize: '0.72rem',
                    fontWeight: 600,
                    padding: '2px 6px',
                    borderRadius: 4,
                    background: toolResult.is_error ? 'rgba(239, 68, 68, 0.1)' : 'rgba(34, 197, 94, 0.1)',
                    color: toolResult.is_error ? '#EF4444' : '#22C55E',
                  }}
                >
                  {toolResult.is_error ? 'Error' : `Success (${toolResult.latency_ms}ms)`}
                </span>
              </div>
              <pre
                style={{
                  maxHeight: 200,
                  overflowY: 'auto',
                  padding: 12,
                  borderRadius: 6,
                  background: '#0F172A',
                  color: '#F8FAFC',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  fontFamily: 'monospace',
                  fontSize: '0.78rem',
                  margin: 0,
                  lineHeight: 1.4,
                }}
              >
                {JSON.stringify(toolResult.result || toolResult, null, 2)}
              </pre>
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
            <button
              type="button"
              onClick={() => setToolRunnerOpen(false)}
              className="btn btn-secondary"
              style={{ fontSize: '0.82rem', padding: '6px 14px' }}
            >
              Close
            </button>
            <button
              type="button"
              onClick={handleRunTool}
              disabled={runningTool}
              className="btn btn-primary"
              style={{ fontSize: '0.82rem', padding: '6px 16px', display: 'inline-flex', alignItems: 'center', gap: 6 }}
            >
              <Play size={12} /> {runningTool ? 'Executing...' : 'Run Tool'}
            </button>
          </div>
        </div>
      </div>
    );
  };

  // ==========================================
  // VIEW: FULL-PAGE ADD / EDIT PROVIDER FORM (Databricks Clean UI)
  // ==========================================
  if (viewMode === 'add_provider' || viewMode === 'edit_provider') {
    return (
      <div className="ai-gateway-root ai-gateway-page" style={{ width: '100%', height: '100%', overflowY: 'auto', padding: '24px 32px 80px', boxSizing: 'border-box' }}>
        {/* Navigation Breadcrumb & Title (Databricks Style) */}
        <div style={{ marginBottom: 24 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: '0.82rem',
              color: 'var(--color-text-muted)',
              marginBottom: 8,
            }}
          >
            <button
              type="button"
              onClick={() => {
                setViewMode('list');
                setActiveTab('providers');
              }}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--color-primary, #1B6EF3)',
                padding: 0,
                cursor: 'pointer',
                fontWeight: 500,
                fontSize: '0.82rem',
              }}
            >
              AI Gateway
            </button>
            <ChevronRight size={13} style={{ color: 'var(--color-text-muted)', opacity: 0.6 }} />
            <button
              type="button"
              onClick={() => {
                setViewMode('list');
                setActiveTab('providers');
              }}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--color-primary, #1B6EF3)',
                padding: 0,
                cursor: 'pointer',
                fontWeight: 500,
                fontSize: '0.82rem',
              }}
            >
              Providers
            </button>
            <ChevronRight size={13} style={{ color: 'var(--color-text-muted)', opacity: 0.6 }} />
          </div>

          <h1 style={{ margin: 0, fontSize: '1.35rem', fontWeight: 600, color: 'var(--color-text)', letterSpacing: '-0.01em' }}>
            {viewMode === 'add_provider' ? 'Create Model Provider Service' : `Edit Model Provider: ${providerForm.name}`}
          </h1>
        </div>

        <form onSubmit={handleSaveProviderForm} style={{ maxWidth: 1100 }}>
          {/* Section 1: Name (3-Tier Catalog & Service Name) */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '180px 1fr',
              gap: 24,
              marginBottom: 26,
              alignItems: 'start',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, paddingTop: 4 }}>
              <span style={{ fontSize: '0.84rem', fontWeight: 600, color: 'var(--color-text)' }}>
                Name
              </span>
              <HelpTooltip content="3-tier Unity Catalog namespace (Catalog.Schema.Name) and service identifier." />
            </div>

            <div>
              <div style={{ display: 'grid', gridTemplateColumns: '180px 180px 1fr', gap: 12 }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 550, marginBottom: 4, color: 'var(--color-text)' }}>
                    Catalog
                  </label>
                  {catalogs.length > 0 ? (
                    <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                      <Database size={13} style={{ position: 'absolute', left: 10, color: 'var(--color-text-muted)', pointerEvents: 'none' }} />
                      <select
                        value={providerForm.catalog_name}
                        onChange={(e) => handleCatalogChange(e.target.value)}
                        style={{
                          width: '100%',
                          padding: '7px 10px 7px 28px',
                          borderRadius: 6,
                          border: '1px solid var(--color-border)',
                          background: 'var(--color-bg)',
                          color: 'var(--color-text)',
                          fontSize: '0.82rem',
                          height: 36,
                        }}
                      >
                        {catalogs.map((cat) => (
                          <option key={cat.name} value={cat.name}>
                            {cat.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  ) : (
                    <input
                      type="text"
                      required
                      placeholder="Select a catalog"
                      value={providerForm.catalog_name}
                      onChange={(e) => setProviderForm({ ...providerForm, catalog_name: e.target.value })}
                      style={{
                        width: '100%',
                        padding: '7px 10px',
                        borderRadius: 6,
                        border: '1px solid var(--color-border)',
                        background: 'var(--color-bg)',
                        color: 'var(--color-text)',
                        fontSize: '0.82rem',
                        height: 36,
                      }}
                    />
                  )}
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 550, marginBottom: 4, color: 'var(--color-text)' }}>
                    Schema
                  </label>
                  {availableSchemas.length > 0 ? (
                    <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                      <Layers size={13} style={{ position: 'absolute', left: 10, color: 'var(--color-text-muted)', pointerEvents: 'none' }} />
                      <select
                        value={providerForm.schema_name}
                        onChange={(e) => setProviderForm({ ...providerForm, schema_name: e.target.value })}
                        style={{
                          width: '100%',
                          padding: '7px 10px 7px 28px',
                          borderRadius: 6,
                          border: '1px solid var(--color-border)',
                          background: 'var(--color-bg)',
                          color: 'var(--color-text)',
                          fontSize: '0.82rem',
                          height: 36,
                        }}
                      >
                        {availableSchemas.map((sch) => (
                          <option key={sch.name} value={sch.name}>
                            {sch.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  ) : (
                    <input
                      type="text"
                      required
                      placeholder="Select a schema"
                      value={providerForm.schema_name}
                      onChange={(e) => setProviderForm({ ...providerForm, schema_name: e.target.value })}
                      style={{
                        width: '100%',
                        padding: '7px 10px',
                        borderRadius: 6,
                        border: '1px solid var(--color-border)',
                        background: 'var(--color-bg)',
                        color: 'var(--color-text)',
                        fontSize: '0.82rem',
                        height: 36,
                      }}
                    />
                  )}
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 550, marginBottom: 4, color: 'var(--color-text)' }}>
                    Name
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="Enter Model Provider Service name"
                    value={providerForm.name}
                    onChange={(e) => setProviderForm({ ...providerForm, name: e.target.value })}
                    style={{
                      width: '100%',
                      padding: '7px 12px',
                      borderRadius: 6,
                      border: '1px solid var(--color-border)',
                      background: 'var(--color-bg)',
                      color: 'var(--color-text)',
                      fontSize: '0.82rem',
                      height: 36,
                    }}
                  />
                </div>
              </div>

              <div style={{ fontSize: '0.74rem', color: 'var(--color-text-muted)', marginTop: 5 }}>
                Name cannot be changed after creation.
              </div>
            </div>
          </div>

          {/* Section 2: Provider (Pill Chips with Logos) */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '180px 1fr',
              gap: 24,
              marginBottom: 26,
              alignItems: 'start',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, paddingTop: 4 }}>
              <span style={{ fontSize: '0.84rem', fontWeight: 600, color: 'var(--color-text)' }}>
                Provider
              </span>
              <HelpTooltip content="Backing AI model vendor or local model provider engine." />
            </div>

            <div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
                {PROVIDER_PILLS.map((p) => {
                  const isSelected = providerForm.provider_type === p.type;
                  return (
                    <button
                      key={p.type}
                      type="button"
                      onClick={() => handleSelectProviderType(p.type)}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 7,
                        padding: '6px 14px',
                        borderRadius: 20,
                        fontSize: '0.82rem',
                        fontWeight: isSelected ? 600 : 500,
                        border: isSelected
                          ? '1.5px solid var(--color-primary, #1B6EF3)'
                          : '1px solid var(--color-border)',
                        background: isSelected
                          ? 'rgba(27, 110, 243, 0.08)'
                          : 'var(--color-surface, #FFFFFF)',
                        color: isSelected ? 'var(--color-primary, #1B6EF3)' : 'var(--color-text)',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      {p.icon}
                      <span>{p.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Section 3: Authentication */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '180px 1fr',
              gap: 24,
              marginBottom: 26,
              alignItems: 'start',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, paddingTop: 4 }}>
              <span style={{ fontSize: '0.84rem', fontWeight: 600, color: 'var(--color-text)' }}>
                Authentication
              </span>
              <HelpTooltip content="Provider credentials, API key, and optional custom endpoint connection settings." />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {/* API Key Segmented Row */}
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 550, marginBottom: 4, color: 'var(--color-text)' }}>
                  API key
                </label>
                <div style={{ display: 'flex', alignItems: 'stretch' }}>
                  <select
                    value={authType}
                    onChange={(e) => setAuthType(e.target.value as 'plaintext' | 'secret_scope')}
                    style={{
                      width: 120,
                      padding: '7px 10px',
                      borderTopLeftRadius: 6,
                      borderBottomLeftRadius: 6,
                      border: '1px solid var(--color-border)',
                      borderRight: 'none',
                      background: 'var(--color-surface-hover, #F9FAFB)',
                      color: 'var(--color-text)',
                      fontSize: '0.82rem',
                      height: 36,
                      fontWeight: 500,
                    }}
                  >
                    <option value="plaintext">Plaintext</option>
                    <option value="secret_scope">Secret Scope</option>
                  </select>

                  <div style={{ flex: 1, position: 'relative', display: 'flex', alignItems: 'center' }}>
                    <input
                      type={showApiKey ? 'text' : 'password'}
                      placeholder={
                        authType === 'secret_scope'
                          ? '{{secrets/scope/key}}'
                          : viewMode === 'edit_provider'
                          ? '•••••••••••••••• (Leave blank to keep existing)'
                          : 'Enter your API key or secret reference'
                      }
                      value={providerForm.api_key}
                      onChange={(e) => setProviderForm({ ...providerForm, api_key: e.target.value })}
                      style={{
                        width: '100%',
                        padding: '7px 40px 7px 12px',
                        borderTopRightRadius: 6,
                        borderBottomRightRadius: 6,
                        border: '1px solid var(--color-border)',
                        background: 'var(--color-bg)',
                        color: 'var(--color-text)',
                        fontSize: '0.82rem',
                        height: 36,
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowApiKey(!showApiKey)}
                      style={{
                        position: 'absolute',
                        right: 8,
                        background: 'none',
                        border: 'none',
                        color: 'var(--color-text-muted)',
                        cursor: 'pointer',
                        padding: 4,
                        display: 'flex',
                        alignItems: 'center',
                      }}
                    >
                      {showApiKey ? <EyeOff size={14} /> : <Eye size={14} />}
                    </button>
                  </div>
                </div>
              </div>

              {/* Base URL */}
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 550, marginBottom: 4, color: 'var(--color-text)' }}>
                  Base URL
                </label>
                <input
                  type="text"
                  placeholder={`${PROVIDER_METADATA[providerForm.provider_type]?.defaultBaseUrl || ''} (optional)`}
                  value={providerForm.base_url}
                  onChange={(e) => setProviderForm({ ...providerForm, base_url: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '7px 12px',
                    borderRadius: 6,
                    border: '1px solid var(--color-border)',
                    background: 'var(--color-bg)',
                    color: 'var(--color-text)',
                    fontSize: '0.82rem',
                    height: 36,
                  }}
                />
              </div>

              {/* Azure Specific */}
              {providerForm.provider_type === 'azure' && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 550, marginBottom: 4, color: 'var(--color-text)' }}>
                      Resource Name
                    </label>
                    <input
                      type="text"
                      placeholder="my-azure-openai-resource"
                      value={providerForm.azure_resource_name}
                      onChange={(e) => setProviderForm({ ...providerForm, azure_resource_name: e.target.value })}
                      style={{
                        width: '100%',
                        padding: '7px 12px',
                        borderRadius: 6,
                        border: '1px solid var(--color-border)',
                        background: 'var(--color-bg)',
                        color: 'var(--color-text)',
                        fontSize: '0.82rem',
                        height: 36,
                      }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 550, marginBottom: 4, color: 'var(--color-text)' }}>
                      API Version
                    </label>
                    <input
                      type="text"
                      placeholder="2024-06-01"
                      value={providerForm.azure_api_version}
                      onChange={(e) => setProviderForm({ ...providerForm, azure_api_version: e.target.value })}
                      style={{
                        width: '100%',
                        padding: '7px 12px',
                        borderRadius: 6,
                        border: '1px solid var(--color-border)',
                        background: 'var(--color-bg)',
                        color: 'var(--color-text)',
                        fontSize: '0.82rem',
                        height: 36,
                      }}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Section 4: Models (Governed Models Selection Table) */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '180px 1fr',
              gap: 24,
              marginBottom: 26,
              alignItems: 'start',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, paddingTop: 4 }}>
              <span style={{ fontSize: '0.84rem', fontWeight: 600, color: 'var(--color-text)' }}>
                Models
              </span>
              <HelpTooltip content="Select which foundation models from this provider are governed and served." />
            </div>

            <div>
              <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--color-text)', marginBottom: 10 }}>
                Select models to serve
              </div>

              {/* Toolbar */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 12,
                  marginBottom: 10,
                  flexWrap: 'wrap',
                }}
              >
                <div style={{ position: 'relative', flex: 1, maxWidth: 320 }}>
                  <Search size={13} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--color-text-muted)' }} />
                  <input
                    type="text"
                    placeholder="Search models in list..."
                    value={modelSearchTerm}
                    onChange={(e) => setModelSearchTerm(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '6px 10px 6px 30px',
                      borderRadius: 6,
                      border: '1px solid var(--color-border)',
                      background: 'var(--color-bg)',
                      color: 'var(--color-text)',
                      fontSize: '0.8rem',
                      height: 32,
                    }}
                  />
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  {currentModels.length > 0 && (
                    <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', cursor: 'pointer', color: 'var(--color-text)', fontWeight: 500 }}>
                      <input
                        type="checkbox"
                        checked={allowAllModels}
                        onChange={(e) => {
                          setAllowAllModels(e.target.checked);
                          if (e.target.checked) {
                            setSelectedModels(new Set(currentModels.map((m) => m.id)));
                          } else {
                            setSelectedModels(new Set());
                          }
                        }}
                      />
                      Allow all and auto-import
                    </label>
                  )}

                  {discoveringModels ? (
                    <button
                      type="button"
                      onClick={handleStopDiscovery}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                        padding: '4px 12px',
                        borderRadius: 6,
                        border: '1px solid var(--color-danger, #EF4444)',
                        background: 'rgba(239, 68, 68, 0.08)',
                        color: 'var(--color-danger, #EF4444)',
                        fontSize: '0.78rem',
                        cursor: 'pointer',
                        height: 32,
                        fontWeight: 600,
                      }}
                      title="Stop the in-flight live model discovery request"
                    >
                      <Square size={10} fill="currentColor" />
                      <span>Stop Discovery</span>
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => handleDiscoverModels(false)}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 5,
                        padding: '4px 12px',
                        borderRadius: 6,
                        border: '1px solid var(--color-border)',
                        background: 'var(--color-bg)',
                        color: 'var(--color-text)',
                        fontSize: '0.78rem',
                        cursor: 'pointer',
                        height: 32,
                        fontWeight: 500,
                      }}
                      title="Connect to provider and fetch real-time available models"
                    >
                      <Sparkles size={12} style={{ color: 'var(--color-primary, #1B6EF3)' }} />
                      <span>Discover Models</span>
                    </button>
                  )}
                </div>
              </div>

              {/* Governed Models Table */}
              <div
                style={{
                  border: '1px solid var(--color-border)',
                  borderRadius: 6,
                  overflow: 'auto',
                  maxHeight: 400,
                  background: 'var(--color-surface, #FFFFFF)',
                }}
              >
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
                  <thead style={{ position: 'sticky', top: 0, zIndex: 2 }}>
                    <tr style={{ background: 'var(--color-surface-hover, #F9FAFB)', borderBottom: '1px solid var(--color-border)', color: 'var(--color-text-muted)', textAlign: 'left' }}>
                      <th style={{ padding: '9px 14px', fontWeight: 600, background: 'var(--color-surface-hover, #F9FAFB)' }}>Model Name / Identifier</th>
                    </tr>
                  </thead>
                  <tbody>
                    {/* First Row: Add Manually */}
                    <tr
                      style={{
                        borderBottom: '1px solid var(--color-border)',
                        background: 'var(--color-surface-hover, #F9FAFB)',
                      }}
                    >
                      <td style={{ padding: '8px 14px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <Plus size={14} style={{ color: 'var(--color-primary, #1B6EF3)', flexShrink: 0 }} />
                          <input
                            type="text"
                            placeholder={providerForm.provider_type === 'azure' ? 'Add deployment name manually (press Enter to add)...' : 'Add model name manually (press Enter to add)...'}
                            value={quickModelInput}
                            onChange={(e) => setQuickModelInput(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                e.preventDefault();
                                handleQuickAddModel();
                              }
                            }}
                            style={{
                              flex: 1,
                              padding: '5px 10px',
                              borderRadius: 4,
                              border: '1px solid var(--color-border)',
                              background: 'var(--color-bg)',
                              color: 'var(--color-text)',
                              fontSize: '0.8rem',
                              fontFamily: 'monospace',
                            }}
                          />
                          <button
                            type="button"
                            onClick={() => handleQuickAddModel()}
                            disabled={!quickModelInput.trim()}
                            className="btn btn-secondary"
                            style={{ height: 28, padding: '0 10px', fontSize: '0.76rem', whiteSpace: 'nowrap' }}
                          >
                            Add
                          </button>
                        </div>
                      </td>
                    </tr>

                    {/* Discovered / Selected Models */}
                    {filteredCatalogModels.map((m) => {
                      const isChecked = allowAllModels || selectedModels.has(m.id);
                      return (
                        <tr
                          key={m.id}
                          style={{
                            borderBottom: '1px solid var(--color-border-subtle, #F1F5F9)',
                            transition: 'background 0.1s ease',
                          }}
                        >
                          <td style={{ padding: '8px 14px' }}>
                            <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', margin: 0 }}>
                              <input
                                type="checkbox"
                                checked={isChecked}
                                onChange={(e) => {
                                  const next = new Set(selectedModels);
                                  if (e.target.checked) next.add(m.id);
                                  else next.delete(m.id);
                                  setSelectedModels(next);
                                  if (next.size < currentModels.length) setAllowAllModels(false);
                                }}
                              />
                              <span style={{ fontWeight: 600, color: 'var(--color-primary, #1B6EF3)', fontFamily: 'monospace', fontSize: '0.84rem' }}>
                                {m.name}
                              </span>
                            </label>
                          </td>
                        </tr>
                      );
                    })}

                    {filteredCatalogModels.length === 0 && (
                      <tr>
                        <td style={{ padding: '24px 14px', textAlign: 'center', color: 'var(--color-text-muted)', fontSize: '0.78rem' }}>
                          {discoveringModels ? (
                            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color: 'var(--color-primary, #1B6EF3)', fontWeight: 500 }}>
                              <Sparkles size={14} className="spin" />
                              <span>Discovering models from upstream provider...</span>
                            </div>
                          ) : modelSearchTerm.trim() ? (
                            `No models matching "${modelSearchTerm}".`
                          ) : (
                            'No models discovered yet. Enter credentials to auto-discover, type a model name above, or click "Discover Models".'
                          )}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* Table Footer */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'flex-end',
                  fontSize: '0.76rem',
                  color: 'var(--color-text-muted)',
                  marginTop: 6,
                }}
              >
                <span>
                  {allowAllModels
                    ? `All ${currentModels.length} models allowed`
                    : `${selectedModels.size} of ${currentModels.length} models allowed`}
                </span>
              </div>
            </div>
          </div>

          {/* Section 5: Advanced (Collapsible Accordion) */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '180px 1fr',
              gap: 24,
              marginBottom: 32,
              alignItems: 'start',
            }}
          >
            <div
              onClick={() => setAdvancedOpen(!advancedOpen)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                paddingTop: 4,
                cursor: 'pointer',
                userSelect: 'none',
              }}
            >
              <span style={{ fontSize: '0.84rem', fontWeight: 600, color: 'var(--color-text)' }}>
                Advanced
              </span>
              <HelpTooltip content="Optional organization IDs and active routing status." />
              {advancedOpen ? <ChevronUp size={13} style={{ color: 'var(--color-text-muted)' }} /> : <ChevronDown size={13} style={{ color: 'var(--color-text-muted)' }} />}
            </div>

            {advancedOpen ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14, background: 'var(--color-surface-hover, #F9FAFB)', padding: 16, borderRadius: 6, border: '1px solid var(--color-border)' }}>
                {/* Organization ID */}
                {providerForm.provider_type === 'openai' && (
                  <div>
                    <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 550, marginBottom: 4, color: 'var(--color-text)' }}>
                      Organization ID (Optional)
                    </label>
                    <input
                      type="text"
                      placeholder="org-..."
                      value={providerForm.organization_id}
                      onChange={(e) => setProviderForm({ ...providerForm, organization_id: e.target.value })}
                      style={{
                        width: '100%',
                        padding: '7px 12px',
                        borderRadius: 6,
                        border: '1px solid var(--color-border)',
                        background: 'var(--color-bg)',
                        color: 'var(--color-text)',
                        fontSize: '0.82rem',
                        height: 36,
                      }}
                    />
                  </div>
                )}

                {/* Routing Active Checkbox */}
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: '0.82rem', fontWeight: 500 }}>
                  <input
                    type="checkbox"
                    checked={providerForm.is_active}
                    onChange={(e) => setProviderForm({ ...providerForm, is_active: e.target.checked })}
                  />
                  Enable this provider for active gateway model routing and fallback failover
                </label>
              </div>
            ) : (
              <div />
            )}
          </div>

          {/* Form Actions */}
          <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr', gap: 24, marginTop: 12 }}>
            <div />
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <button
                type="submit"
                disabled={savingProvider}
                className="btn btn-primary"
                style={{ padding: '8px 20px', fontSize: '0.84rem' }}
              >
                {savingProvider
                  ? 'Saving...'
                  : viewMode === 'edit_provider'
                  ? 'Save Changes'
                  : 'Create Model Provider Service'}
              </button>
              <button
                type="button"
                onClick={() => setViewMode('list')}
                className="btn btn-secondary"
                style={{ padding: '8px 16px', fontSize: '0.84rem' }}
              >
                Cancel
              </button>
            </div>
          </div>
        </form>
      </div>
    );
  }

  // ==========================================
  // VIEW: FULL-PAGE ADD / EDIT MCP FORM (Databricks Clean UI)
  // ==========================================
  if (viewMode === 'add_mcp' || viewMode === 'edit_mcp') {
    return (
      <div className="ai-gateway-root ai-gateway-page" style={{ width: '100%', height: '100%', overflowY: 'auto', padding: '24px 32px 80px', boxSizing: 'border-box' }}>
        {/* Navigation Breadcrumb & Title (Databricks Style) */}
        <div style={{ marginBottom: 24 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: '0.82rem',
              color: 'var(--color-text-muted)',
              marginBottom: 8,
            }}
          >
            <button
              type="button"
              onClick={() => {
                setViewMode('list');
                setActiveTab('mcp');
              }}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--color-primary, #1B6EF3)',
                padding: 0,
                cursor: 'pointer',
                fontWeight: 500,
                fontSize: '0.82rem',
              }}
            >
              AI Gateway
            </button>
            <ChevronRight size={13} style={{ color: 'var(--color-text-muted)', opacity: 0.6 }} />
            <button
              type="button"
              onClick={() => {
                setViewMode('list');
                setActiveTab('mcp');
              }}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--color-primary, #1B6EF3)',
                padding: 0,
                cursor: 'pointer',
                fontWeight: 500,
                fontSize: '0.82rem',
              }}
            >
              MCP
            </button>
            <ChevronRight size={13} style={{ color: 'var(--color-text-muted)', opacity: 0.6 }} />
          </div>

          <h1 style={{ margin: 0, fontSize: '1.35rem', fontWeight: 600, color: 'var(--color-text)', letterSpacing: '-0.01em' }}>
            {viewMode === 'add_mcp' ? 'Register Model Context Protocol (MCP) Server' : `Edit MCP Server: ${mcpForm.name}`}
          </h1>
        </div>

        <form onSubmit={handleSaveMcpForm} style={{ maxWidth: 1100 }}>
          {/* Section 1: Name & Catalog Placement (3-in-1 Row) */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '180px 1fr',
              gap: 24,
              marginBottom: 26,
              alignItems: 'start',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, paddingTop: 4 }}>
              <span style={{ fontSize: '0.84rem', fontWeight: 600, color: 'var(--color-text)' }}>
                Name
              </span>
              <HelpTooltip content="3-tier Unity Catalog location (Catalog.Schema) and unique MCP service name." />
            </div>

            <div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1.5fr', gap: 12 }}>
                {/* Catalog */}
                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 550, marginBottom: 4, color: 'var(--color-text)' }}>
                    Catalog
                  </label>
                  {catalogs.length > 0 ? (
                    <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                      <Database size={13} style={{ position: 'absolute', left: 10, color: 'var(--color-text-muted)', pointerEvents: 'none' }} />
                      <select
                        value={mcpForm.catalog_name}
                        onChange={(e) => handleMcpCatalogChange(e.target.value)}
                        style={{
                          width: '100%',
                          padding: '7px 10px 7px 28px',
                          borderRadius: 6,
                          border: '1px solid var(--color-border)',
                          background: 'var(--color-bg)',
                          color: 'var(--color-text)',
                          fontSize: '0.82rem',
                          height: 36,
                        }}
                      >
                        {catalogs.map((cat) => (
                          <option key={cat.name} value={cat.name}>
                            {cat.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  ) : (
                    <input
                      type="text"
                      required
                      placeholder="Select a catalog"
                      value={mcpForm.catalog_name}
                      onChange={(e) => setMcpForm({ ...mcpForm, catalog_name: e.target.value })}
                      style={{
                        width: '100%',
                        padding: '7px 10px',
                        borderRadius: 6,
                        border: '1px solid var(--color-border)',
                        background: 'var(--color-bg)',
                        color: 'var(--color-text)',
                        fontSize: '0.82rem',
                        height: 36,
                      }}
                    />
                  )}
                </div>

                {/* Schema */}
                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 550, marginBottom: 4, color: 'var(--color-text)' }}>
                    Schema
                  </label>
                  {availableMcpSchemas.length > 0 ? (
                    <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                      <Layers size={13} style={{ position: 'absolute', left: 10, color: 'var(--color-text-muted)', pointerEvents: 'none' }} />
                      <select
                        value={mcpForm.schema_name}
                        onChange={(e) => setMcpForm({ ...mcpForm, schema_name: e.target.value })}
                        style={{
                          width: '100%',
                          padding: '7px 10px 7px 28px',
                          borderRadius: 6,
                          border: '1px solid var(--color-border)',
                          background: 'var(--color-bg)',
                          color: 'var(--color-text)',
                          fontSize: '0.82rem',
                          height: 36,
                        }}
                      >
                        {availableMcpSchemas.map((sch) => (
                          <option key={sch.name} value={sch.name}>
                            {sch.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  ) : (
                    <input
                      type="text"
                      required
                      placeholder="Select a schema"
                      value={mcpForm.schema_name}
                      onChange={(e) => setMcpForm({ ...mcpForm, schema_name: e.target.value })}
                      style={{
                        width: '100%',
                        padding: '7px 10px',
                        borderRadius: 6,
                        border: '1px solid var(--color-border)',
                        background: 'var(--color-bg)',
                        color: 'var(--color-text)',
                        fontSize: '0.82rem',
                        height: 36,
                      }}
                    />
                  )}
                </div>

                {/* MCP Server Name */}
                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 550, marginBottom: 4, color: 'var(--color-text)' }}>
                    Name
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="Enter MCP Server name"
                    value={mcpForm.name}
                    onChange={(e) => setMcpForm({ ...mcpForm, name: e.target.value })}
                    style={{
                      width: '100%',
                      padding: '7px 12px',
                      borderRadius: 6,
                      border: '1px solid var(--color-border)',
                      background: 'var(--color-bg)',
                      color: 'var(--color-text)',
                      fontSize: '0.82rem',
                      height: 36,
                    }}
                  />
                </div>
              </div>

              <div style={{ fontSize: '0.74rem', color: 'var(--color-text-muted)', marginTop: 5 }}>
                Name cannot be changed after creation.
              </div>
            </div>
          </div>

          {/* Section 2: Transport Type */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '180px 1fr',
              gap: 24,
              marginBottom: 26,
              alignItems: 'start',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, paddingTop: 4 }}>
              <span style={{ fontSize: '0.84rem', fontWeight: 600, color: 'var(--color-text)' }}>
                Transport Type
              </span>
              <HelpTooltip content="Communication protocol: Remote HTTP/SSE server or a locally spawned CLI subprocess." />
            </div>

            <div style={{ display: 'flex', gap: 10 }}>
              <button
                type="button"
                onClick={() => setMcpForm({ ...mcpForm, server_type: 'remote_sse' })}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '8px 18px',
                  borderRadius: 20,
                  fontSize: '0.82rem',
                  fontWeight: mcpForm.server_type === 'remote_sse' ? 600 : 500,
                  border:
                    mcpForm.server_type === 'remote_sse'
                      ? '1.5px solid var(--color-primary, #1B6EF3)'
                      : '1px solid var(--color-border)',
                  background:
                    mcpForm.server_type === 'remote_sse'
                      ? 'rgba(27, 110, 243, 0.08)'
                      : 'var(--color-surface, #FFFFFF)',
                  color:
                    mcpForm.server_type === 'remote_sse'
                      ? 'var(--color-primary, #1B6EF3)'
                      : 'var(--color-text)',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <Server size={14} />
                <span>Remote SSE (HTTP/SSE)</span>
              </button>

              <button
                type="button"
                onClick={() => setMcpForm({ ...mcpForm, server_type: 'subprocess' })}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '8px 18px',
                  borderRadius: 20,
                  fontSize: '0.82rem',
                  fontWeight: mcpForm.server_type === 'subprocess' ? 600 : 500,
                  border:
                    mcpForm.server_type === 'subprocess'
                      ? '1.5px solid var(--color-primary, #1B6EF3)'
                      : '1px solid var(--color-border)',
                  background:
                    mcpForm.server_type === 'subprocess'
                      ? 'rgba(27, 110, 243, 0.08)'
                      : 'var(--color-surface, #FFFFFF)',
                  color:
                    mcpForm.server_type === 'subprocess'
                      ? 'var(--color-primary, #1B6EF3)'
                      : 'var(--color-text)',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <Terminal size={14} />
                <span>Local Subprocess (stdio/CLI)</span>
              </button>
            </div>
          </div>

          {/* Section 3: Connection & Authentication */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '180px 1fr',
              gap: 24,
              marginBottom: 26,
              alignItems: 'start',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, paddingTop: 4 }}>
              <span style={{ fontSize: '0.84rem', fontWeight: 600, color: 'var(--color-text)' }}>
                Connection
              </span>
              <HelpTooltip content="Remote endpoint URL or local CLI command line used to launch and connect to the MCP server." />
            </div>

            <div>
              {mcpForm.server_type === 'remote_sse' ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  {/* Connection URL */}
                  <div>
                    <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 550, marginBottom: 4, color: 'var(--color-text)' }}>
                      Connection URL (Endpoint URL)
                    </label>
                    <input
                      type="url"
                      required
                      placeholder="http://localhost:8000/sse or https://mcp.internal.acme.com/sse"
                      value={mcpForm.endpoint_url}
                      onChange={(e) => setMcpForm({ ...mcpForm, endpoint_url: e.target.value })}
                      style={{
                        width: '100%',
                        padding: '7px 12px',
                        borderRadius: 6,
                        border: '1px solid var(--color-border)',
                        background: 'var(--color-bg)',
                        color: 'var(--color-text)',
                        fontSize: '0.82rem',
                        height: 36,
                      }}
                    />
                  </div>

                  {/* Auth Token Segmented Row */}
                  <div>
                    <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 550, marginBottom: 4, color: 'var(--color-text)' }}>
                      Authentication Token (Optional)
                    </label>
                    <div style={{ display: 'flex', alignItems: 'stretch' }}>
                      <select
                        value={mcpAuthType}
                        onChange={(e) => setMcpAuthType(e.target.value as 'plaintext' | 'secret_scope')}
                        style={{
                          width: 125,
                          padding: '7px 10px',
                          borderTopLeftRadius: 6,
                          borderBottomLeftRadius: 6,
                          border: '1px solid var(--color-border)',
                          borderRight: 'none',
                          background: 'var(--color-surface-hover, #F9FAFB)',
                          color: 'var(--color-text)',
                          fontSize: '0.78rem',
                          fontWeight: 500,
                          cursor: 'pointer',
                        }}
                      >
                        <option value="plaintext">Bearer Token</option>
                        <option value="secret_scope">Secret Scope</option>
                      </select>

                      <div style={{ position: 'relative', flex: 1, display: 'flex', alignItems: 'center' }}>
                        <input
                          type={showMcpToken ? 'text' : 'password'}
                          placeholder={
                            mcpAuthType === 'secret_scope'
                              ? '{{secrets/scope/mcp_token}}'
                              : viewMode === 'edit_mcp'
                              ? '•••••••••••••••• (Leave blank to keep existing)'
                              : 'Enter authorization token or secret key'
                          }
                          value={mcpForm.auth_token}
                          onChange={(e) => setMcpForm({ ...mcpForm, auth_token: e.target.value })}
                          style={{
                            width: '100%',
                            padding: '7px 40px 7px 12px',
                            borderTopRightRadius: 6,
                            borderBottomRightRadius: 6,
                            border: '1px solid var(--color-border)',
                            background: 'var(--color-bg)',
                            color: 'var(--color-text)',
                            fontSize: '0.82rem',
                            height: 36,
                          }}
                        />
                        <button
                          type="button"
                          onClick={() => setShowMcpToken(!showMcpToken)}
                          style={{
                            position: 'absolute',
                            right: 8,
                            background: 'none',
                            border: 'none',
                            color: 'var(--color-text-muted)',
                            cursor: 'pointer',
                            padding: 4,
                            display: 'flex',
                            alignItems: 'center',
                          }}
                        >
                          {showMcpToken ? <EyeOff size={14} /> : <Eye size={14} />}
                        </button>
                      </div>
                    </div>
                    <div style={{ fontSize: '0.74rem', color: 'var(--color-text-muted)', marginTop: 4 }}>
                      Encrypted at rest using AES-256 before being stored in the database.
                    </div>
                  </div>
                </div>
              ) : (
                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 550, marginBottom: 4, color: 'var(--color-text)' }}>
                    Command / CLI Executable
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="npx -y @modelcontextprotocol/server-postgres postgresql://localhost:5432/db"
                    value={mcpForm.command}
                    onChange={(e) => setMcpForm({ ...mcpForm, command: e.target.value })}
                    style={{
                      width: '100%',
                      padding: '7px 12px',
                      borderRadius: 6,
                      border: '1px solid var(--color-border)',
                      background: 'var(--color-bg)',
                      color: 'var(--color-text)',
                      fontFamily: 'monospace',
                      fontSize: '0.82rem',
                      height: 36,
                    }}
                  />
                  <div style={{ fontSize: '0.74rem', color: 'var(--color-text-muted)', marginTop: 4 }}>
                    Subprocess command invoked using stdio transport pipes.
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Section 4: Description (Optional) */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '180px 1fr',
              gap: 24,
              marginBottom: 32,
              alignItems: 'start',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, paddingTop: 4 }}>
              <span style={{ fontSize: '0.84rem', fontWeight: 600, color: 'var(--color-text)' }}>
                Description
              </span>
              <HelpTooltip content="Optional summary explaining the capabilities of tools provided by this server." />
            </div>

            <div>
              <input
                type="text"
                placeholder="e.g. Introspects relational databases, queries metadata, and executes tools"
                value={mcpForm.description}
                onChange={(e) => setMcpForm({ ...mcpForm, description: e.target.value })}
                style={{
                  width: '100%',
                  padding: '7px 12px',
                  borderRadius: 6,
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-bg)',
                  color: 'var(--color-text)',
                  fontSize: '0.82rem',
                  height: 36,
                }}
              />
            </div>
          </div>

          {/* Form Actions */}
          <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr', gap: 24, marginTop: 12 }}>
            <div />
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <button
                type="submit"
                disabled={savingMcp}
                className="btn btn-primary"
                style={{ padding: '8px 20px', fontSize: '0.84rem' }}
              >
                {savingMcp
                  ? 'Saving & Loading Tools...'
                  : viewMode === 'edit_mcp'
                  ? 'Save Changes'
                  : 'Create & Load Tools'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setViewMode('list');
                  setActiveTab('mcp');
                }}
                className="btn btn-secondary"
                style={{ padding: '8px 16px', fontSize: '0.84rem' }}
              >
                Cancel
              </button>
            </div>
          </div>
        </form>
      </div>
    );
  }

  // ==========================================
  // VIEW: FULL-PAGE DEDICATED MCP SERVER TOOLS (Databricks Clean UI)
  // ==========================================
  if (viewMode === 'view_mcp_tools' && selectedMcpServer) {
    return (
      <div className="ai-gateway-root ai-gateway-page" style={{ width: '100%', height: '100%', overflowY: 'auto', padding: '24px 32px 80px', boxSizing: 'border-box' }}>
        {/* Navigation Breadcrumb & Back */}
        <div style={{ marginBottom: 20 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: '0.82rem',
              color: 'var(--color-text-muted)',
              marginBottom: 10,
            }}
          >
            <button
              type="button"
              onClick={() => {
                setViewMode('list');
                setActiveTab('mcp');
              }}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--color-primary, #1B6EF3)',
                padding: 0,
                cursor: 'pointer',
                fontWeight: 500,
                fontSize: '0.82rem',
              }}
            >
              AI Gateway
            </button>
            <ChevronRight size={13} style={{ color: 'var(--color-text-muted)', opacity: 0.6 }} />
            <button
              type="button"
              onClick={() => {
                setViewMode('list');
                setActiveTab('mcp');
              }}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--color-primary, #1B6EF3)',
                padding: 0,
                cursor: 'pointer',
                fontWeight: 500,
                fontSize: '0.82rem',
              }}
            >
              MCP
            </button>
            <ChevronRight size={13} style={{ color: 'var(--color-text-muted)', opacity: 0.6 }} />
            <span style={{ fontWeight: 600, color: 'var(--color-text)' }}>
              {selectedMcpServer.name}
            </span>
          </div>

          {/* Header Title Bar */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <h1 style={{ margin: 0, fontSize: '1.35rem', fontWeight: 600, color: 'var(--color-text)', letterSpacing: '-0.01em' }}>
                  {selectedMcpServer.name}
                </h1>
                <span
                  style={{
                    padding: '2px 8px',
                    borderRadius: 4,
                    fontSize: '0.72rem',
                    fontWeight: 600,
                    background: selectedMcpServer.is_builtin ? 'rgba(34, 197, 94, 0.1)' : 'rgba(27, 110, 243, 0.1)',
                    color: selectedMcpServer.is_builtin ? '#22C55E' : 'var(--color-primary, #1B6EF3)',
                  }}
                >
                  {selectedMcpServer.server_type.toUpperCase()}
                </span>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    padding: '2px 8px',
                    borderRadius: 4,
                    fontSize: '0.72rem',
                    fontFamily: 'monospace',
                    fontWeight: 500,
                    background: 'var(--color-bg, #F3F4F6)',
                    color: 'var(--color-text-muted)',
                    border: '1px solid var(--color-border)',
                  }}
                  title="3-tier Unity Catalog location"
                >
                  <Database size={11} />
                  {getServerIdentifier(selectedMcpServer)}
                </span>
                {selectedMcpServer.is_builtin && (
                  <span
                    style={{
                      padding: '2px 8px',
                      borderRadius: 4,
                      fontSize: '0.72rem',
                      fontWeight: 600,
                      background: 'rgba(100, 116, 139, 0.1)',
                      color: 'var(--color-text-muted)',
                    }}
                  >
                    BUILT-IN
                  </span>
                )}
              </div>
              <p style={{ margin: '4px 0 0', color: 'var(--color-text-muted)', fontSize: '0.82rem' }}>
                {selectedMcpServer.description || 'Model Context Protocol tool server.'}
              </p>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <button
                type="button"
                onClick={() => handleTestMcpEndpoint(selectedMcpServer)}
                disabled={testingServerEndpoint}
                className="btn btn-primary"
                style={{ padding: '6px 14px', fontSize: '0.8rem', display: 'inline-flex', alignItems: 'center', gap: 6 }}
              >
                <Play size={12} className={testingServerEndpoint ? 'spin' : ''} />
                {testingServerEndpoint ? 'Testing Endpoint...' : 'Test Endpoint'}
              </button>
              {typeof selectedMcpServer.id === 'number' && (
                <>
                  <button
                    type="button"
                    onClick={() => handleSyncMCPServer(selectedMcpServer.id as number)}
                    className="btn btn-secondary"
                    style={{ padding: '6px 12px', fontSize: '0.8rem', display: 'inline-flex', alignItems: 'center', gap: 6 }}
                  >
                    <RefreshCw size={13} />
                    Sync Tools
                  </button>
                  <button
                    type="button"
                    onClick={() => handleOpenEditMcp(selectedMcpServer as MCPServer)}
                    className="btn btn-secondary"
                    style={{ padding: '6px 12px', fontSize: '0.8rem', display: 'inline-flex', alignItems: 'center', gap: 6 }}
                  >
                    <Edit2 size={13} />
                    Edit Server
                  </button>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Tools Section Header & Search */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 14 }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600, color: 'var(--color-text)' }}>
              Tools Manifest ({filteredServerTools.length})
            </h3>
          </div>

          <div className="search-bar-wrapper" style={{ width: 280 }}>
            <Search size={14} className="search-icon" />
            <input
              className="search-input"
              placeholder={`Search ${selectedMcpServer.name} tools...`}
              value={toolSearchTerm}
              onChange={(e) => setToolSearchTerm(e.target.value)}
            />
          </div>
        </div>

        {/* Server Tools Table */}
        <AppTable
          columns={serverToolColumns}
          rows={filteredServerTools}
          rowKey={(row) => `${row.server_name || selectedMcpServer.name}_${row.name}`}
          emptyText={
            serverTools.length === 0
              ? 'No tools registered for this MCP server. Click "Sync Tools" or "Test Endpoint" to discover tools.'
              : 'No tools match your search criteria.'
          }
          isLoading={loading}
        />

        {/* Tool List Endpoint & Testing Card */}
        <div
          style={{
            marginTop: 22,
            borderRadius: 8,
            background: 'var(--color-surface, #FFFFFF)',
            border: '1px solid var(--color-border)',
            overflow: 'hidden',
          }}
        >
          {/* Main Endpoint Bar */}
          <div
            style={{
              padding: '12px 18px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 12,
              flexWrap: 'wrap',
              background: 'var(--color-surface-hover, #F9FAFB)',
            }}
          >
            {/* Left side: Collapse chevron before GET badge, Method badge, Path, Copy URL icon, and Live status telemetry */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', flex: 1, minWidth: 260 }}>
              {serverEndpointTestResult && (
                <button
                  type="button"
                  onClick={() => setEndpointDetailsExpanded(!endpointDetailsExpanded)}
                  className="ghost-icon-btn"
                  title={endpointDetailsExpanded ? 'Collapse response' : 'Expand response'}
                  style={{ padding: 4, marginRight: 2 }}
                >
                  {endpointDetailsExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                </button>
              )}

              <span
                style={{
                  padding: '2px 6px',
                  borderRadius: 4,
                  fontSize: '0.72rem',
                  fontWeight: 700,
                  fontFamily: 'monospace',
                  background: 'rgba(27, 110, 243, 0.12)',
                  color: 'var(--color-primary, #1B6EF3)',
                }}
              >
                GET
              </span>
              <code
                style={{
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  color: 'var(--color-text)',
                  background: 'var(--color-bg, #F3F4F6)',
                  padding: '3px 8px',
                  borderRadius: 4,
                  wordBreak: 'break-all',
                }}
              >
                /api/v1/ai-gateway/mcp/servers/{getServerIdentifier(selectedMcpServer)}/tools
              </code>
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(`/api/v1/ai-gateway/mcp/servers/${getServerIdentifier(selectedMcpServer)}/tools`);
                  toast.success('Endpoint URL copied');
                }}
                className="ghost-icon-btn"
                title="Copy endpoint path"
                style={{ padding: 4 }}
              >
                <Copy size={13} />
              </button>

              {/* Status telemetry shown inline without duplicating endpoint text */}
              {serverEndpointTestResult && (
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginLeft: 4 }}>
                  <span
                    style={{
                      padding: '2px 7px',
                      borderRadius: 4,
                      fontSize: '0.72rem',
                      fontWeight: 600,
                      background: serverEndpointTestResult.success ? 'rgba(34, 197, 94, 0.12)' : 'rgba(239, 68, 68, 0.12)',
                      color: serverEndpointTestResult.success ? '#16A34A' : '#DC2626',
                    }}
                  >
                    {serverEndpointTestResult.success ? '200 OK' : 'Failed'}
                  </span>
                  <span style={{ fontSize: '0.74rem', color: 'var(--color-text-muted)' }}>
                    {serverEndpointTestResult.latency_ms}ms
                  </span>
                  {serverEndpointTestResult.tools_count !== undefined && (
                    <span style={{ fontSize: '0.74rem', color: 'var(--color-text-muted)' }}>
                      • {serverEndpointTestResult.tools_count} {serverEndpointTestResult.tools_count === 1 ? 'tool' : 'tools'} returned
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* Right side: Test button */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <button
                type="button"
                onClick={() => handleTestMcpEndpoint(selectedMcpServer)}
                disabled={testingServerEndpoint}
                className="btn btn-primary"
                style={{ padding: '5px 12px', fontSize: '0.8rem', display: 'inline-flex', alignItems: 'center', gap: 6 }}
              >
                <Play size={12} className={testingServerEndpoint ? 'spin' : ''} />
                {testingServerEndpoint ? 'Testing...' : 'Test Endpoint'}
              </button>
            </div>
          </div>

          {/* Collapsible JSON Output with Floating Top-Right Copy Button */}
          {serverEndpointTestResult && endpointDetailsExpanded && (
            <div
              style={{
                position: 'relative',
                borderTop: '1px solid var(--color-border)',
                background: '#0F172A',
                padding: '12px 16px',
              }}
            >
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(
                    JSON.stringify(serverEndpointTestResult.raw_response || serverEndpointTestResult, null, 2)
                  );
                  toast.success('Response JSON copied to clipboard');
                }}
                title="Copy response JSON"
                style={{
                  position: 'absolute',
                  top: 10,
                  right: 12,
                  zIndex: 2,
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: 'rgba(255, 255, 255, 0.1)',
                  border: '1px solid rgba(255, 255, 255, 0.18)',
                  borderRadius: 4,
                  padding: '5px 7px',
                  color: '#F8FAFC',
                  cursor: 'pointer',
                  transition: 'background 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'rgba(255, 255, 255, 0.22)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'rgba(255, 255, 255, 0.1)';
                }}
              >
                <Copy size={13} />
              </button>

              <pre
                style={{
                  maxHeight: 280,
                  overflowY: 'auto',
                  fontFamily: 'monospace',
                  fontSize: '0.78rem',
                  color: '#F8FAFC',
                  margin: 0,
                  paddingRight: 36,
                  lineHeight: 1.45,
                }}
              >
                {JSON.stringify(serverEndpointTestResult.raw_response || serverEndpointTestResult, null, 2)}
              </pre>
            </div>
          )}
        </div>

        {/* Modal: MCP Tool Runner */}
        {renderToolRunnerModal()}
      </div>
    );
  }

  // ==========================================
  // VIEW: DEFAULT TABBED LISTS (Databricks Style)
  // ==========================================
  return (
    <div className="ai-gateway-root ai-gateway-page" style={{ width: '100%', height: '100%', overflowY: 'auto', padding: '24px 32px 80px', boxSizing: 'border-box' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 600, color: 'var(--color-text)', letterSpacing: '-0.01em' }}>
            AI Gateway
          </h1>
          <p style={{ margin: '4px 0 0', color: 'var(--color-text-muted)', fontSize: '0.84rem' }}>
            Enterprise AI model governance, multi-vendor routing, rate limiting, and Model Context Protocol (MCP) tool hub.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button
            onClick={loadData}
            className="btn btn-secondary"
            style={{ padding: '6px 12px', fontSize: '0.8rem', display: 'inline-flex', alignItems: 'center', gap: 6 }}
          >
            <RefreshCw size={13} className={loading ? 'spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {/* Main Tabs */}
      <PageTabs
        tabs={AI_GATEWAY_TABS}
        value={activeTab}
        onChange={handleTabChange}
        style={{ marginBottom: 16 }}
      />

      {/* Toolbar: Search & Action Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 14 }}>
        <div className="search-bar-wrapper" style={{ width: 280 }}>
          <Search size={14} className="search-icon" />
          <input
            className="search-input"
            placeholder={`Search ${activeTab}...`}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div>
          {activeTab === 'providers' && (
            <button className="btn btn-primary" onClick={handleOpenAddProvider} style={{ fontSize: '0.82rem' }}>
              <Plus size={14} /> Add Provider
            </button>
          )}

          {activeTab === 'mcp' && (
            <button className="btn btn-primary" onClick={handleOpenAddMcp} style={{ fontSize: '0.82rem' }}>
              <Plus size={14} /> Register MCP Server
            </button>
          )}
        </div>
      </div>

      {/* TAB 1: PROVIDERS */}
      {activeTab === 'providers' && (
        <AppTable
          columns={providerColumns}
          rows={filteredProviders}
          rowKey={(row) => row.id}
          emptyText="No AI model providers registered. Click 'Add Provider' to connect OpenAI, Anthropic, Gemini, Azure, or Ollama."
          isLoading={loading}
        />
      )}

      {/* TAB 2: MCP */}
      {activeTab === 'mcp' && (
        <AppTable
          columns={mcpServerColumns}
          rows={filteredMcpServers}
          rowKey={(row) => row.id}
          emptyText="No MCP servers registered. Click 'Register MCP Server' to connect remote SSE or subprocess tools."
          isLoading={loading}
        />
      )}

      {/* TAB 3: INFERENCE & AUDIT LOGS */}
      {activeTab === 'logs' && (
        <AppTable
          columns={logColumns}
          rows={filteredLogs}
          rowKey={(row) => row.id}
          emptyText="No inference activity logged yet. Query the AI Gateway or run an agent to generate audit logs."
          isLoading={loading}
        />
      )}

      {/* MODAL: MCP Tool Runner */}
      {renderToolRunnerModal()}

      {/* MODAL: Inspect Inference Telemetry */}
      {inspectLog && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.55)',
            backdropFilter: 'blur(3px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
        >
          <div
            style={{
              background: 'var(--color-surface, #FFFFFF)',
              borderRadius: 10,
              padding: 24,
              width: '100%',
              maxWidth: 720,
              maxHeight: '85vh',
              overflowY: 'auto',
              border: '1px solid var(--color-border)',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.25), 0 8px 10px -6px rgba(0, 0, 0, 0.2)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600, color: 'var(--color-text)' }}>
                    Inference Telemetry
                  </h3>
                  <code
                    style={{
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      color: 'var(--color-primary, #1B6EF3)',
                      background: 'rgba(27, 110, 243, 0.08)',
                      padding: '2px 8px',
                      borderRadius: 4,
                    }}
                  >
                    {inspectLog.endpoint_name}
                  </code>
                </div>
                <div style={{ fontSize: '0.74rem', color: 'var(--color-text-muted)', marginTop: 4 }}>
                  {new Date(inspectLog.created_at).toLocaleString()}
                </div>
              </div>

              <span
                style={{
                  padding: '3px 8px',
                  borderRadius: 4,
                  fontSize: '0.74rem',
                  fontWeight: 600,
                  background: inspectLog.status_code === 200 ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                  color: inspectLog.status_code === 200 ? '#22C55E' : '#EF4444',
                }}
              >
                HTTP {inspectLog.status_code}
              </span>
            </div>

            {/* Stat Cards Grid */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: 10,
                marginBottom: 18,
              }}
            >
              <div style={{ background: 'var(--color-surface-hover, #F9FAFB)', padding: '10px 12px', borderRadius: 6, border: '1px solid var(--color-border)' }}>
                <div style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', marginBottom: 2 }}>Model</div>
                <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={inspectLog.upstream_model_name}>
                  {inspectLog.upstream_model_name}
                </div>
              </div>

              <div style={{ background: 'var(--color-surface-hover, #F9FAFB)', padding: '10px 12px', borderRadius: 6, border: '1px solid var(--color-border)' }}>
                <div style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', marginBottom: 2 }}>Latency</div>
                <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text)' }}>
                  {inspectLog.latency_ms}ms
                </div>
              </div>

              <div style={{ background: 'var(--color-surface-hover, #F9FAFB)', padding: '10px 12px', borderRadius: 6, border: '1px solid var(--color-border)' }}>
                <div style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', marginBottom: 2 }}>Tokens (In / Out)</div>
                <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text)' }}>
                  {inspectLog.input_tokens} / {inspectLog.output_tokens}
                </div>
              </div>

              <div style={{ background: 'var(--color-surface-hover, #F9FAFB)', padding: '10px 12px', borderRadius: 6, border: '1px solid var(--color-border)' }}>
                <div style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', marginBottom: 2 }}>Cost</div>
                <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text)' }}>
                  ${Number(inspectLog.total_cost || 0).toFixed(4)}
                </div>
              </div>
            </div>

            {inspectLog.response_text && (
              <div style={{ marginBottom: 14 }}>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 550, marginBottom: 4, color: 'var(--color-text)' }}>
                  Response Output
                </label>
                <pre
                  style={{
                    padding: 12,
                    borderRadius: 6,
                    background: '#0F172A',
                    color: '#F8FAFC',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    fontSize: '0.78rem',
                    maxHeight: 180,
                    overflowY: 'auto',
                    whiteSpace: 'pre-wrap',
                    fontFamily: 'monospace',
                    margin: 0,
                    lineHeight: 1.4,
                  }}
                >
                  {inspectLog.response_text}
                </pre>
              </div>
            )}

            <div style={{ marginBottom: 18 }}>
              <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 550, marginBottom: 4, color: 'var(--color-text)' }}>
                Request Messages Payload
              </label>
              <pre
                style={{
                  padding: 12,
                  borderRadius: 6,
                  background: '#0F172A',
                  color: '#94A3B8',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  fontSize: '0.78rem',
                  maxHeight: 180,
                  overflowY: 'auto',
                  fontFamily: 'monospace',
                  margin: 0,
                  lineHeight: 1.4,
                }}
              >
                {JSON.stringify(inspectLog.request_messages, null, 2)}
              </pre>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={() => setInspectLog(null)}
                className="btn btn-secondary"
                style={{ fontSize: '0.82rem', padding: '6px 16px' }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
