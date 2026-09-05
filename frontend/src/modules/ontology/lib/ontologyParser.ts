import { load } from 'js-yaml';
import { OntologyDataset, OntologyNode, OntologyEdge, OntologyKind } from '../types/ontology';
import { DEFAULT_ONTOLOGY_YAML } from '../data/defaultOntologyData';

export function parseOntologyYaml(yamlContent: string): OntologyDataset {
  let raw: any;
  try {
    raw = load(yamlContent);
  } catch (err) {
    console.error('Failed to parse YAML ontology string:', err);
    throw new Error('Invalid YAML format: ' + (err as Error).message);
  }

  if (!raw || typeof raw !== 'object') {
    throw new Error('YAML must contain a top-level object with nodes and edges');
  }

  const nodes: OntologyNode[] = Array.isArray(raw.nodes) ? raw.nodes : [];
  const edges: OntologyEdge[] = Array.isArray(raw.edges) ? raw.edges : [];

  // Build adjacency map
  const childMap = new Map<string, string[]>();
  const parentMap = new Map<string, string>();
  const nodeMap = new Map<string, OntologyNode>();

  for (const node of nodes) {
    nodeMap.set(node.id, { ...node, inboundDependencies: [], outboundDependencies: [] });
    childMap.set(node.id, []);
    if (node.parentId) {
      parentMap.set(node.id, node.parentId);
    }
  }

  // Populate children from explicit edges and parentId
  for (const edge of edges) {
    if (edge.type === 'contains') {
      const children = childMap.get(edge.source) || [];
      if (!children.includes(edge.target)) {
        children.push(edge.target);
        childMap.set(edge.source, children);
      }
      if (!parentMap.has(edge.target)) {
        parentMap.set(edge.target, edge.source);
      }
    } else {
      // Inbound / outbound dependencies
      const sourceNode = nodeMap.get(edge.source);
      const targetNode = nodeMap.get(edge.target);
      if (sourceNode && !sourceNode.outboundDependencies?.includes(edge.target)) {
        sourceNode.outboundDependencies?.push(edge.target);
      }
      if (targetNode && !targetNode.inboundDependencies?.includes(edge.source)) {
        targetNode.inboundDependencies?.push(edge.source);
      }
    }
  }

  // Also check parentId directly
  for (const node of nodes) {
    if (node.parentId && nodeMap.has(node.parentId)) {
      const children = childMap.get(node.parentId) || [];
      if (!children.includes(node.id)) {
        children.push(node.id);
        childMap.set(node.parentId, children);
      }
    }
  }

  // Helper to compute total transitive descendants
  const memoDescendants = new Map<string, number>();

  function countDescendants(nodeId: string, visited: Set<string> = new Set()): number {
    if (memoDescendants.has(nodeId)) return memoDescendants.get(nodeId)!;
    if (visited.has(nodeId)) return 0;
    visited.add(nodeId);

    const children = childMap.get(nodeId) || [];
    let total = children.length;
    for (const childId of children) {
      total += countDescendants(childId, new Set(visited));
    }
    memoDescendants.set(nodeId, total);
    return total;
  }

  // Update processed node properties
  const processedNodes: OntologyNode[] = Array.from(nodeMap.values()).map(node => {
    const directChildren = childMap.get(node.id) || [];
    const directChildCount = directChildren.length;
    const totalDescendantCount = countDescendants(node.id);

    return {
      ...node,
      parentId: parentMap.get(node.id) || node.parentId || null,
      directChildCount,
      totalDescendantCount,
    };
  });

  return {
    name: raw.name || 'Ontology Map',
    version: raw.version || '1.0.0',
    description: raw.description || '',
    nodes: processedNodes,
    edges,
  };
}

export function toTopologyV2Format(dataset: OntologyDataset): {
  nodes: import('../atlas-engine').TopologyV2Node[];
  edges: import('../atlas-engine').TopologyV2Edge[];
} {
  // Compute degrees
  const degreeMap = new Map<string, number>();
  for (const node of dataset.nodes) {
    degreeMap.set(node.id, 0);
  }
  for (const edge of dataset.edges) {
    degreeMap.set(edge.source, (degreeMap.get(edge.source) || 0) + 1);
    degreeMap.set(edge.target, (degreeMap.get(edge.target) || 0) + 1);
  }

  const kindSize: Record<string, number> = {
    project: 30,
    domain: 17,
    capability: 11,
    element: 7,
  };

  const nodes = dataset.nodes.map(node => {
    const deg = degreeMap.get(node.id) || 0;
    const kind = (node.kind as any) || 'element';
    const baseSize = kindSize[kind] || 10;
    return {
      id: node.id,
      label: node.title || node.id,
      kind,
      size: baseSize,
      x: 0,
      y: 0,
      isHub: node.kind === 'project' || deg >= 8,
      ownerKey: null,
      recentlyUpdated: false,
      fullDegree: deg,
      descendantCount: node.totalDescendantCount || 0,
    };
  });

  const edges = dataset.edges.map(edge => {
    const isContains = edge.type === 'contains';
    return {
      id: edge.id || `${edge.source}->${edge.target}`,
      source: edge.source,
      target: edge.target,
      relationType: edge.type || (isContains ? 'contains' : 'depends_on'),
      relationQuality: ('strong' as const),
      evidenceCount: 1,
      kind: isContains ? ('contains' as const) : ('depends' as const),
      declaredBySlug: null,
    };
  });

  return { nodes, edges };
}

export function getDefaultDataset(): OntologyDataset {
  try {
    return parseOntologyYaml(DEFAULT_ONTOLOGY_YAML);
  } catch (err) {
    console.error('Error in getDefaultDataset, using fallback:', err);
    return {
      name: 'CompassX Ontology',
      version: '1.0.0',
      description: 'Platform Meaning Layer',
      nodes: [
        { id: 'ontology-atlas', kind: 'project', title: 'Ontology Atlas', description: 'Root Meaning Layer' },
        { id: 'domains/agent-integration', kind: 'domain', title: 'AI Agent Integration', parentId: 'ontology-atlas' },
        { id: 'domains/codebase-architecture', kind: 'domain', title: 'Codebase Architecture', parentId: 'ontology-atlas' },
      ],
      edges: [
        { id: 'e1', source: 'ontology-atlas', target: 'domains/agent-integration', type: 'contains' },
        { id: 'e2', source: 'ontology-atlas', target: 'domains/codebase-architecture', type: 'contains' },
      ],
    };
  }
}


