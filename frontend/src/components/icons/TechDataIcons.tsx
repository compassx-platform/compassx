import React from 'react';

export interface IconProps extends React.SVGProps<SVGSVGElement> {
  size?: number | string;
  strokeWidth?: number | string;
  className?: string;
}

const defaultProps: IconProps = {
  size: 24,
  strokeWidth: 1.75,
};

function createIcon(svgPath: (props: IconProps) => React.ReactNode, displayName: string) {
  const Component = React.forwardRef<SVGSVGElement, IconProps>((props, ref) => {
    const {
      size = defaultProps.size,
      strokeWidth = defaultProps.strokeWidth,
      className,
      style,
      ...rest
    } = props;

    return (
      <svg
        ref={ref}
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
        style={{ verticalAlign: 'middle', display: 'inline-block', ...style }}
        {...rest}
      >
        {svgPath(props)}
      </svg>
    );
  });

  Component.displayName = displayName;
  return Component;
}

// ════════════════════════════════════════════════════════════════════════════
// 1. Data & Databases
// ════════════════════════════════════════════════════════════════════════════

/** SQL Warehouse / Multi-cluster compute warehouse */
export const IconSqlWarehouse = createIcon(
  () => (
    <>
      <path d="M4 6c0-1.657 3.582-3 8-3s8 1.343 8 3v12c0 1.657-3.582 3-8 3s-8-1.343-8-3V6z" />
      <path d="M4 10c0 1.657 3.582 3 8 3s8-1.343 8-3" />
      <path d="M4 14c0 1.657 3.582 3 8 3s8-1.343 8-3" />
      <path d="M16 19l2 2 4-4" />
    </>
  ),
  'IconSqlWarehouse'
);

/** Lakehouse / Unified Delta Lake Storage */
export const IconLakehouse = createIcon(
  () => (
    <>
      <polygon points="12 2 2 7 12 12 22 7 12 2" />
      <path d="M2 17l10 5 10-5" />
      <path d="M2 12l10 5 10-5" />
      <path d="M12 22v-5" />
      <circle cx="12" cy="12" r="1.5" fill="currentColor" />
    </>
  ),
  'IconLakehouse'
);

/** Data Catalog / Metadata Store */
export const IconDataCatalog = createIcon(
  () => (
    <>
      <rect x="3" y="3" width="18" height="18" rx="3" />
      <path d="M3 9h18" />
      <path d="M9 21V9" />
      <circle cx="6" cy="6" r="1" fill="currentColor" />
      <path d="M13 13h5" />
      <path d="M13 17h3" />
    </>
  ),
  'IconDataCatalog'
);

/** Data Schema / Entity Field Structure */
export const IconDataSchema = createIcon(
  () => (
    <>
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <path d="M10 6.5h4" />
      <path d="M6.5 10v4" />
      <path d="M17.5 10v4" />
      <path d="M10 17.5h4" />
    </>
  ),
  'IconDataSchema'
);

/** Data Table with Primary Column */
export const IconDataTable = createIcon(
  () => (
    <>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M3 10h18" />
      <path d="M3 15h18" />
      <path d="M9 4v16" />
      <path d="M15 4v16" />
    </>
  ),
  'IconDataTable'
);

/** Data Lineage / Graph Flow */
export const IconDataLineage = createIcon(
  () => (
    <>
      <circle cx="5" cy="6" r="3" />
      <circle cx="5" cy="18" r="3" />
      <circle cx="19" cy="12" r="3" />
      <path d="M8 6h3a4 4 0 0 1 4 4v2" />
      <path d="M8 18h3a4 4 0 0 0 4-4v-2" />
      <path d="M15 12h1" />
    </>
  ),
  'IconDataLineage'
);

/** Data Pipeline / Continuous Flow */
export const IconDataPipeline = createIcon(
  () => (
    <>
      <rect x="2" y="7" width="5" height="10" rx="1.5" />
      <rect x="17" y="7" width="5" height="10" rx="1.5" />
      <path d="M7 10h10" />
      <path d="M7 14h10" />
      <path d="M11 7v10" strokeDasharray="2 2" />
      <polygon points="14 12 11 9 11 15" fill="currentColor" />
    </>
  ),
  'IconDataPipeline'
);

/** Data Stream / Real-time Ingestion */
export const IconDataStream = createIcon(
  () => (
    <>
      <path d="M2 8c4-4 8 4 12 0s8 4 8 4" />
      <path d="M2 14c4-4 8 4 12 0s8 4 8 4" />
      <circle cx="6" cy="7" r="1.5" fill="currentColor" />
      <circle cx="14" cy="13" r="1.5" fill="currentColor" />
      <circle cx="18" cy="15" r="1.5" fill="currentColor" />
    </>
  ),
  'IconDataStream'
);

/** Data Query / SQL Code Runner */
export const IconDataQuery = createIcon(
  () => (
    <>
      <rect x="3" y="3" width="18" height="18" rx="3" />
      <path d="M7 8l4 4-4 4" />
      <path d="M13 16h4" />
      <circle cx="17" cy="7" r="1.5" fill="currentColor" />
    </>
  ),
  'IconDataQuery'
);

// ════════════════════════════════════════════════════════════════════════════
// 2. AI & Autonomous Agents
// ════════════════════════════════════════════════════════════════════════════

/** Autonomous AI Agent / Specialist */
export const IconAiAgent = createIcon(
  () => (
    <>
      <rect x="4" y="8" width="16" height="12" rx="3" />
      <circle cx="9" cy="13" r="1.5" fill="currentColor" />
      <circle cx="15" cy="13" r="1.5" fill="currentColor" />
      <path d="M12 4v4" />
      <path d="M10 4h4" />
      <path d="M2 13h2" />
      <path d="M20 13h2" />
      <path d="M9 17h6" />
    </>
  ),
  'IconAiAgent'
);

/** Neural Engine / LLM Reasoning Brain */
export const IconNeuralEngine = createIcon(
  () => (
    <>
      <circle cx="12" cy="12" r="3" />
      <circle cx="4" cy="6" r="2" />
      <circle cx="20" cy="6" r="2" />
      <circle cx="4" cy="18" r="2" />
      <circle cx="20" cy="18" r="2" />
      <path d="M6 7l4 3" />
      <path d="M18 7l-4 3" />
      <path d="M6 17l4-3" />
      <path d="M18 17l-4-3" />
      <path d="M12 4v5" />
      <path d="M12 15v5" />
    </>
  ),
  'IconNeuralEngine'
);

/** Agent Memory / Episodic Vector Store */
export const IconAgentMemory = createIcon(
  () => (
    <>
      <path d="M12 3C7 3 3 7 3 12s4 9 9 9 9-4 9-9-4-9-9-9z" />
      <path d="M12 7v5l3 3" />
      <circle cx="12" cy="12" r="2" fill="currentColor" />
      <path d="M7 4.5l1.5 2" />
      <path d="M17 4.5l-1.5 2" />
    </>
  ),
  'IconAgentMemory'
);

/** Multi-Agent Swarm / Collaborative Agents */
export const IconMultiAgentSwarm = createIcon(
  () => (
    <>
      <circle cx="12" cy="6" r="3" />
      <circle cx="6" cy="17" r="3" />
      <circle cx="18" cy="17" r="3" />
      <path d="M10 8.5l-2.5 6" />
      <path d="M14 8.5l2.5 6" />
      <path d="M9 17h6" strokeDasharray="2 2" />
    </>
  ),
  'IconMultiAgentSwarm'
);

/** Tool Registry / Function Attachment */
export const IconToolRegistry = createIcon(
  () => (
    <>
      <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
      <circle cx="18" cy="18" r="2" />
    </>
  ),
  'IconToolRegistry'
);

/** Vector Embeddings / Semantic Space */
export const IconVectorEmbedding = createIcon(
  () => (
    <>
      <circle cx="6" cy="6" r="2" fill="currentColor" />
      <circle cx="18" cy="8" r="2" fill="currentColor" />
      <circle cx="10" cy="18" r="2" fill="currentColor" />
      <circle cx="19" cy="19" r="2" fill="currentColor" />
      <path d="M8 7l8 1" strokeDasharray="2 2" />
      <path d="M7 8l2 8" strokeDasharray="2 2" />
      <path d="M12 18l5 1" strokeDasharray="2 2" />
      <path d="M17 10l2 7" strokeDasharray="2 2" />
    </>
  ),
  'IconVectorEmbedding'
);

/** LLM Model Provider Key */
export const IconLlmModel = createIcon(
  () => (
    <>
      <rect x="3" y="5" width="18" height="14" rx="3" />
      <path d="M7 12h3" />
      <path d="M14 12h3" />
      <circle cx="12" cy="12" r="1.5" fill="currentColor" />
      <path d="M3 9h18" />
    </>
  ),
  'IconLlmModel'
);

// ════════════════════════════════════════════════════════════════════════════
// 3. Compute & Engineering
// ════════════════════════════════════════════════════════════════════════════

/** Computational Notebook (.ipynb) */
export const IconComputationalNotebook = createIcon(
  () => (
    <>
      <path d="M4 4v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6H6a2 2 0 0 0-2 2z" />
      <polyline points="14 2 14 8 20 8" />
      <path d="M8 13h8" />
      <path d="M8 17h5" />
      <circle cx="8" cy="10" r="1" fill="currentColor" />
    </>
  ),
  'IconComputationalNotebook'
);

/** Python Kernel / Interactive Execution */
export const IconPythonKernel = createIcon(
  () => (
    <>
      <path d="M12 2C8 2 7 3.5 7 5.5V8h5v1H5C3 9 2 10.5 2 13.5S3 18 5 18h2v-2.5C7 13.5 8 12 10 12h5V9h-3V7h5c2 0 3-1.5 3-4.5S19 2 17 2h-5z" />
      <circle cx="9" cy="5" r="1" fill="currentColor" />
      <circle cx="15" cy="19" r="1" fill="currentColor" />
      <path d="M12 22c4 0 5-1.5 5-3.5V16h-5v-1h7c2 0 3-1.5 3-4.5S21 6 19 6h-2v2.5c0 2-1 3.5-3 3.5H9v3h3v2H7c-2 0-3 1.5-3 4.5S5 22 7 22h5z" />
    </>
  ),
  'IconPythonKernel'
);

/** Compute Cluster / Worker Node Grid */
export const IconComputeCluster = createIcon(
  () => (
    <>
      <rect x="3" y="3" width="8" height="6" rx="1.5" />
      <rect x="13" y="3" width="8" height="6" rx="1.5" />
      <rect x="3" y="15" width="8" height="6" rx="1.5" />
      <rect x="13" y="15" width="8" height="6" rx="1.5" />
      <path d="M7 9v6" />
      <path d="M17 9v6" />
      <path d="M7 12h10" />
    </>
  ),
  'IconComputeCluster'
);

/** GPU Accelerator / High-Performance Tensor */
export const IconGpuAccelerator = createIcon(
  () => (
    <>
      <rect x="4" y="4" width="16" height="16" rx="2.5" />
      <rect x="8" y="8" width="8" height="8" rx="1" />
      <path d="M1 9h3" />
      <path d="M1 15h3" />
      <path d="M20 9h3" />
      <path d="M20 15h3" />
      <path d="M9 1v3" />
      <path d="M15 1v3" />
      <path d="M9 20v3" />
      <path d="M15 20v3" />
    </>
  ),
  'IconGpuAccelerator'
);

/** App Engine / Low-code Application */
export const IconAppEngine = createIcon(
  () => (
    <>
      <polygon points="12 2 2 7 12 12 22 7 12 2" />
      <polyline points="2 17 12 22 22 17" />
      <polyline points="2 12 12 17 22 12" />
    </>
  ),
  'IconAppEngine'
);

// ════════════════════════════════════════════════════════════════════════════
// 4. Operations & Digital Assets
// ════════════════════════════════════════════════════════════════════════════

/** Digital Twin / Asset Hierarchy Graph */
export const IconDigitalTwin = createIcon(
  () => (
    <>
      <rect x="9" y="2" width="6" height="6" rx="1.5" />
      <rect x="2" y="16" width="6" height="6" rx="1.5" />
      <rect x="16" y="16" width="6" height="6" rx="1.5" />
      <path d="M12 8v4" />
      <path d="M5 16v-2a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v2" />
      <circle cx="12" cy="12" r="1.5" fill="currentColor" />
    </>
  ),
  'IconDigitalTwin'
);

/** Airflow DAG / Scheduled Job Pipeline */
export const IconAirflowDag = createIcon(
  () => (
    <>
      <circle cx="5" cy="12" r="3" />
      <circle cx="19" cy="6" r="3" />
      <circle cx="19" cy="18" r="3" />
      <path d="M8 12h3a4 4 0 0 0 4-4V6" />
      <path d="M8 12h3a4 4 0 0 1 4 4v2" />
      <polygon points="15 6 12 4.5 12 7.5" fill="currentColor" />
      <polygon points="15 18 12 16.5 12 19.5" fill="currentColor" />
    </>
  ),
  'IconAirflowDag'
);

/** Scheduled Cron / Automated Trigger */
export const IconScheduledCron = createIcon(
  () => (
    <>
      <circle cx="12" cy="12" r="9" />
      <polyline points="12 6 12 12 16 14" />
      <path d="M12 3V1" />
      <path d="M12 23v-2" />
      <path d="M3 12H1" />
      <path d="M23 12h-2" />
    </>
  ),
  'IconScheduledCron'
);

/** BI Dashboard / Executive Analytics */
export const IconBiDashboard = createIcon(
  () => (
    <>
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M3 9h18" />
      <path d="M9 21V9" />
      <path d="M13 17v-4" />
      <path d="M17 17v-7" />
    </>
  ),
  'IconBiDashboard'
);

/** Telemetry & Metrics / Live Monitor */
export const IconTelemetryMetrics = createIcon(
  () => (
    <>
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
      <circle cx="15" cy="21" r="1" fill="currentColor" />
      <circle cx="9" cy="3" r="1" fill="currentColor" />
    </>
  ),
  'IconTelemetryMetrics'
);

// ════════════════════════════════════════════════════════════════════════════
// Icon Registry & Metadata (for gallery & showcase)
// ════════════════════════════════════════════════════════════════════════════

export interface CuratedIconItem {
  name: string;
  component: React.ComponentType<IconProps>;
  category: 'data' | 'ai' | 'compute' | 'ops';
  description: string;
  tags: string[];
}

export const CURATED_TECH_DATA_ICONS: CuratedIconItem[] = [
  // Data
  {
    name: 'IconSqlWarehouse',
    component: IconSqlWarehouse,
    category: 'data',
    description: 'SQL Warehouse execution engine & multi-cluster query runner',
    tags: ['sql', 'warehouse', 'database', 'query', 'compute'],
  },
  {
    name: 'IconLakehouse',
    component: IconLakehouse,
    category: 'data',
    description: 'Lakehouse unified Delta lake storage & parquet layer',
    tags: ['lakehouse', 'delta', 'storage', 'data', 'parquet'],
  },
  {
    name: 'IconDataCatalog',
    component: IconDataCatalog,
    category: 'data',
    description: 'Enterprise data catalog, schemas & column metadata',
    tags: ['catalog', 'metadata', 'schema', 'governance'],
  },
  {
    name: 'IconDataSchema',
    component: IconDataSchema,
    category: 'data',
    description: 'Entity schemas, relational fields & foreign keys',
    tags: ['schema', 'fields', 'structure', 'entities'],
  },
  {
    name: 'IconDataTable',
    component: IconDataTable,
    category: 'data',
    description: 'Tabular dataset, columns & primary keys',
    tags: ['table', 'grid', 'columns', 'records'],
  },
  {
    name: 'IconDataLineage',
    component: IconDataLineage,
    category: 'data',
    description: 'End-to-end data lineage graph & transformation paths',
    tags: ['lineage', 'graph', 'provenance', 'flow'],
  },
  {
    name: 'IconDataPipeline',
    component: IconDataPipeline,
    category: 'data',
    description: 'Continuous ETL data pipeline & data ingestion stream',
    tags: ['pipeline', 'etl', 'ingestion', 'stream'],
  },
  {
    name: 'IconDataStream',
    component: IconDataStream,
    category: 'data',
    description: 'Real-time telemetry stream & event stream processing',
    tags: ['stream', 'realtime', 'kafka', 'events'],
  },
  {
    name: 'IconDataQuery',
    component: IconDataQuery,
    category: 'data',
    description: 'Interactive SQL query editor & analytical script',
    tags: ['query', 'sql', 'script', 'editor'],
  },

  // AI & Autonomous Agents
  {
    name: 'IconAiAgent',
    component: IconAiAgent,
    category: 'ai',
    description: 'Autonomous AI specialist agent with custom reasoning',
    tags: ['agent', 'ai', 'bot', 'assistant', 'autonomous'],
  },
  {
    name: 'IconNeuralEngine',
    component: IconNeuralEngine,
    category: 'ai',
    description: 'Neural network LLM engine & multi-model reasoning core',
    tags: ['neural', 'llm', 'brain', 'model', 'reasoning'],
  },
  {
    name: 'IconAgentMemory',
    component: IconAgentMemory,
    category: 'ai',
    description: 'Long-term episodic agent memory & context retention',
    tags: ['memory', 'recall', 'context', 'history'],
  },
  {
    name: 'IconMultiAgentSwarm',
    component: IconMultiAgentSwarm,
    category: 'ai',
    description: 'Collaborative multi-agent swarm & consensus coordination',
    tags: ['swarm', 'multi-agent', 'collaboration', 'teams'],
  },
  {
    name: 'IconToolRegistry',
    component: IconToolRegistry,
    category: 'ai',
    description: 'Agent tool execution registry & API functions',
    tags: ['tool', 'function', 'api', 'execution'],
  },
  {
    name: 'IconVectorEmbedding',
    component: IconVectorEmbedding,
    category: 'ai',
    description: 'High-dimensional vector embeddings & semantic search space',
    tags: ['vector', 'embedding', 'rag', 'semantic'],
  },
  {
    name: 'IconLlmModel',
    component: IconLlmModel,
    category: 'ai',
    description: 'LLM connection providers (OpenAI, Claude, Gemini, Ollama)',
    tags: ['llm', 'model', 'openai', 'claude', 'gemini'],
  },

  // Compute & Engineering
  {
    name: 'IconComputationalNotebook',
    component: IconComputationalNotebook,
    category: 'compute',
    description: 'Interactive computational notebook (.ipynb) with cell execution',
    tags: ['notebook', 'jupyter', 'python', 'code'],
  },
  {
    name: 'IconPythonKernel',
    component: IconPythonKernel,
    category: 'compute',
    description: 'Python execution kernel & runtime environment',
    tags: ['python', 'kernel', 'runtime', 'exec'],
  },
  {
    name: 'IconComputeCluster',
    component: IconComputeCluster,
    category: 'compute',
    description: 'Scalable compute cluster & worker instance pool',
    tags: ['compute', 'cluster', 'nodes', 'servers'],
  },
  {
    name: 'IconGpuAccelerator',
    component: IconGpuAccelerator,
    category: 'compute',
    description: 'GPU hardware accelerator for deep learning & tensor compute',
    tags: ['gpu', 'hardware', 'cuda', 'tensor', 'acceleration'],
  },
  {
    name: 'IconAppEngine',
    component: IconAppEngine,
    category: 'compute',
    description: 'Low-code operational application builder & app deployer',
    tags: ['app', 'engine', 'deploy', 'builder'],
  },

  // Operations & Digital Assets
  {
    name: 'IconDigitalTwin',
    component: IconDigitalTwin,
    category: 'ops',
    description: 'Digital Twin asset hierarchy & connected telemetry components',
    tags: ['digital-twin', 'asset', 'hierarchy', 'physical'],
  },
  {
    name: 'IconAirflowDag',
    component: IconAirflowDag,
    category: 'ops',
    description: 'Airflow DAG workflow orchestration & pipeline schedule',
    tags: ['airflow', 'dag', 'job', 'schedule', 'pipeline'],
  },
  {
    name: 'IconScheduledCron',
    component: IconScheduledCron,
    category: 'ops',
    description: 'Automated cron trigger & recurring time scheduler',
    tags: ['cron', 'schedule', 'time', 'automation'],
  },
  {
    name: 'IconBiDashboard',
    component: IconBiDashboard,
    category: 'ops',
    description: 'Business intelligence dashboard & metric charts',
    tags: ['dashboard', 'bi', 'analytics', 'charts'],
  },
  {
    name: 'IconTelemetryMetrics',
    component: IconTelemetryMetrics,
    category: 'ops',
    description: 'Real-time telemetry pulse & cluster health monitoring',
    tags: ['telemetry', 'metrics', 'monitoring', 'health'],
  },
];
