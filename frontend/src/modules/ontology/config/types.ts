/**
 * Ontology Configuration Subsystem - Type Definitions
 * 
 * Separated from core ontology rendering and graph topology engine
 * to ensure that configuration updates do not alter canvas behavior unexpectedly.
 */

export type NodeShapeType = 'hexagon' | 'chip' | 'circle' | 'pad';

export interface KindConfig {
  id: string; // e.g. 'project', 'domain', 'capability', 'element', or custom slug
  label: string; // display name e.g. 'Project Root'
  description?: string;
  shape: NodeShapeType;
  baseRadius: number; // radius in px (e.g. 7 to 40)
  tier: number; // 0 = root, 1 = inner, 2 = mid, 3 = outer cluster
}

export type ConfigTab = 'kinds';

export interface OntologyConfigPanelProps {
  kindsConfig?: KindConfig[];
  onUpdateKindsConfig?: (newKinds: KindConfig[]) => void;
  themeMode?: 'dark' | 'light';
  onToggleTheme?: () => void;
  view3d?: boolean;
  onToggle3D?: () => void;
  mapArrangement?: string;
  onToggleArrangement?: () => void;
  expandedAll?: boolean;
  onToggleExpandAll?: () => void;
  onAutoArrange?: () => void;
  onFitView?: () => void;
  onOpenYamlEditor?: () => void;
  onResetDefaultData?: () => void;
  nodeCount?: number;
  edgeCount?: number;
}
