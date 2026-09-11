import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";

export interface PackageRepositoriesConfig {
  pypi_index_url: string;
  pypi_extra_index_urls: string[];
  npm_registry: string;
  maven_central: string;
  custom_repositories?: Array<{ name: string; url: string; auth_type?: string }>;
}

export interface BaseEnvironmentsConfig {
  python_version: string;
  spark_version: string;
  preinstalled_packages: string[];
  environment_variables: Record<string, string>;
}

export interface ServerlessUsagePoliciesConfig {
  enforce_cost_tags: boolean;
  required_tags: string[];
  max_runtime_hours_per_day: number;
  max_concurrent_queries: number;
  cost_alert_threshold: number;
}

export interface ClassicComputePoliciesConfig {
  allow_unrestricted_cluster_creation: boolean;
  default_node_type: string;
  max_nodes: number;
  auto_termination_minutes: number;
  cluster_tags: Record<string, string>;
}

export interface WorkspaceSettings {
  default_warehouse: string;
  serverless_interactive_timeout: number;
  package_repositories: PackageRepositoriesConfig;
  base_environments: BaseEnvironmentsConfig;
  serverless_usage_policies: ServerlessUsagePoliciesConfig;
  classic_compute_policies: ClassicComputePoliciesConfig;
}

export const DEFAULT_SETTINGS: WorkspaceSettings = {
  default_warehouse: "last_selected",
  serverless_interactive_timeout: 9000,
  package_repositories: {
    pypi_index_url: "https://pypi.org/simple",
    pypi_extra_index_urls: [],
    npm_registry: "https://registry.npmjs.org/",
    maven_central: "https://repo1.maven.org/maven2/",
    custom_repositories: [],
  },
  base_environments: {
    python_version: "3.11",
    spark_version: "3.5.0",
    preinstalled_packages: [
      "pandas>=2.0.0",
      "numpy>=1.24.0",
      "scikit-learn>=1.3.0",
      "plotly>=5.15.0",
      "requests>=2.31.0",
    ],
    environment_variables: {
      PYTHONUNBUFFERED: "1",
    },
  },
  serverless_usage_policies: {
    enforce_cost_tags: true,
    required_tags: ["Environment", "CostCenter", "Project"],
    max_runtime_hours_per_day: 24,
    max_concurrent_queries: 10,
    cost_alert_threshold: 1000,
  },
  classic_compute_policies: {
    allow_unrestricted_cluster_creation: false,
    default_node_type: "standard_d4s_v5",
    max_nodes: 8,
    auto_termination_minutes: 60,
    cluster_tags: {
      ManagedBy: "CompassX",
      Tier: "Workspace",
    },
  },
};

const getStorageKey = (slug: string) => `compassx_workspace_settings_${slug}`;

export async function fetchWorkspaceSettings(slug: string): Promise<WorkspaceSettings> {
  try {
    const { data } = await api.get<WorkspaceSettings>(`/api/w/${slug}/api/workspace/settings`, {
      baseURL: "",
    });
    if (data && typeof data === "object") {
      try {
        localStorage.setItem(getStorageKey(slug), JSON.stringify(data));
      } catch {}
      return data;
    }
  } catch (err) {
    console.warn("Could not fetch remote workspace settings, falling back to local/default:", err);
  }

  // Fallback to localStorage or defaults
  try {
    const cached = localStorage.getItem(getStorageKey(slug));
    if (cached) {
      return { ...DEFAULT_SETTINGS, ...JSON.parse(cached) };
    }
  } catch {}

  return DEFAULT_SETTINGS;
}

export async function updateWorkspaceSettings(
  slug: string,
  updates: Partial<WorkspaceSettings>
): Promise<WorkspaceSettings> {
  try {
    const { data } = await api.patch<WorkspaceSettings>(
      `/api/w/${slug}/api/workspace/settings`,
      updates,
      { baseURL: "" }
    );
    try {
      localStorage.setItem(getStorageKey(slug), JSON.stringify(data));
    } catch {}
    return data;
  } catch (err) {
    console.warn("Could not patch remote workspace settings, saving locally:", err);
    let current = DEFAULT_SETTINGS;
    try {
      const cached = localStorage.getItem(getStorageKey(slug));
      if (cached) current = { ...DEFAULT_SETTINGS, ...JSON.parse(cached) };
    } catch {}
    const updated = { ...current, ...updates };
    try {
      localStorage.setItem(getStorageKey(slug), JSON.stringify(updated));
    } catch {}
    return updated;
  }
}

export function useWorkspaceSettings(slug?: string) {
  return useQuery<WorkspaceSettings>({
    queryKey: ["workspace-settings", slug],
    queryFn: () => fetchWorkspaceSettings(slug || "default"),
    enabled: !!slug,
    staleTime: 60_000,
  });
}

export function useUpdateWorkspaceSettings(slug?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (updates: Partial<WorkspaceSettings>) =>
      updateWorkspaceSettings(slug || "default", updates),
    onSuccess: (data) => {
      qc.setQueryData(["workspace-settings", slug], data);
      qc.invalidateQueries({ queryKey: ["workspace-settings", slug] });
    },
  });
}
