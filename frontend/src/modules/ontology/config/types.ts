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
  color?: string;
  icon?: string;
  is_system?: boolean;
}

export interface TypeRelationConfig {
  id?: number;
  source_type_id: string;
  relation_type: string;
  target_type_id: string;
  is_hierarchical?: boolean;
  description?: string;
  is_system?: boolean;
}

export type ConfigTab = 'kinds' | 'relations';

export interface GraphValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  node_count: number;
  edge_count: number;
}

export interface OntologyConfigPanelProps {
  isOpen?: boolean;
  onClose?: () => void;
  onToggleOpen?: () => void;
  hideTrigger?: boolean;
  kindsConfig?: KindConfig[];
  onUpdateKindsConfig?: (newKinds: KindConfig[]) => void;
  typeRelations?: TypeRelationConfig[];
  onUpdateTypeRelations?: (newRelations: TypeRelationConfig[]) => void;
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
  nodeCount?: number;
  edgeCount?: number;
}
