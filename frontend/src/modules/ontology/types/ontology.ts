export type OntologyKind = 'project' | 'domain' | 'capability' | 'element';

export type RelationType = 'contains' | 'depends_on' | 'relies_on' | 'reads' | 'is_similar_to' | 'relates';

export interface OntologyNode {
  id: string; // Slug or unique ID
  uid?: string;
  kind: OntologyKind;
  title: string;
  description?: string;
  parentId?: string | null;
  domainId?: string; // Associated domain slug if applicable
  tags?: string[];
  path?: string;
  status?: 'active' | 'draft' | 'archived' | 'deprecated';
  lastUpdated?: string;
  // Transitive properties computed by parser
  directChildCount?: number;
  totalDescendantCount?: number;
  inboundDependencies?: string[];
  outboundDependencies?: string[];
}

export interface OntologyEdge {
  id: string;
  source: string; // node ID
  target: string; // node ID
  type: RelationType;
  description?: string;
}

export interface OntologyDataset {
  name: string;
  version?: string;
  description?: string;
  nodes: OntologyNode[];
  edges: OntologyEdge[];
}

export interface Point2D {
  x: number;
  y: number;
}

export interface LayoutNode extends OntologyNode {
  x: number;
  y: number;
  baseRadius: number;
  renderRadius: number;
  color: string;
  strokeColor: string;
  // Drag / spring physics
  vx?: number;
  vy?: number;
  fx?: number | null;
  fy?: number | null;
  targetX?: number;
  targetY?: number;
}

export interface LayoutEdge extends OntologyEdge {
  sourceNode: LayoutNode;
  targetNode: LayoutNode;
  isTapered: boolean;
  isDashed: boolean;
  isSymmetric: boolean;
}

export interface CameraState {
  x: number;
  y: number;
  zoom: number;
  tiltAngle: number; // 0 for 2D, ~25-35 deg for 3D tilt
}

export interface EgoFocusState {
  focusedNodeId: string | null;
  neighborIds: Set<string>;
  connectedEdgeIds: Set<string>;
  trail: string[]; // History of clicked nodes
}
