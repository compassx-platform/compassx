import { OntologyDataset, LayoutNode, LayoutEdge, OntologyKind } from '../types/ontology';

export const BASE_RADII: Record<OntologyKind, number> = {
  project: 30,
  domain: 17,
  capability: 11,
  element: 7,
};

export const KIND_COLORS: Record<OntologyKind, { fill: string; stroke: string; glow?: string }> = {
  project: {
    fill: '#1c1b18',
    stroke: '#f59e0b', // Amber machined bezel
    glow: 'rgba(245, 158, 11, 0.25)',
  },
  domain: {
    fill: '#161926',
    stroke: '#475569',
    glow: 'rgba(100, 116, 139, 0.2)',
  },
  capability: {
    fill: '#1e2235',
    stroke: '#64748b',
  },
  element: {
    fill: '#1a1f2c',
    stroke: '#475569',
  },
};

export const RING_RADII = {
  domain: 270,
  capability: 160,
  element: 95,
};

export function computeLayout(dataset: OntologyDataset): { nodes: LayoutNode[]; edges: LayoutEdge[] } {
  const nodeMap = new Map<string, LayoutNode>();
  const childrenMap = new Map<string, string[]>();

  // Find project root
  let projectNode = dataset.nodes.find(n => n.kind === 'project');
  if (!projectNode && dataset.nodes.length > 0) {
    projectNode = dataset.nodes[0];
  }

  // Populate children
  for (const node of dataset.nodes) {
    childrenMap.set(node.id, []);
  }

  for (const node of dataset.nodes) {
    if (node.parentId && childrenMap.has(node.parentId)) {
      childrenMap.get(node.parentId)!.push(node.id);
    }
  }

  // Initialize LayoutNodes with base & render radii
  for (const node of dataset.nodes) {
    const baseR = BASE_RADII[node.kind] || 10;
    const directCount = node.directChildCount || 0;
    
    // Scale only domain and capability, capped at 1.4x
    let scale = 1.0;
    if (node.kind === 'domain' || node.kind === 'capability') {
      scale = Math.min(1.4, 1.0 + directCount * 0.04);
    }
    const renderRadius = Math.round(baseR * scale);
    const colors = KIND_COLORS[node.kind] || { fill: '#1b1e2e', stroke: '#475073' };

    nodeMap.set(node.id, {
      ...node,
      x: 0,
      y: 0,
      baseRadius: baseR,
      renderRadius,
      color: colors.fill,
      strokeColor: colors.stroke,
      targetX: 0,
      targetY: 0,
    });
  }

  // Place project at origin
  if (projectNode) {
    const proj = nodeMap.get(projectNode.id)!;
    proj.x = 0;
    proj.y = 0;
    proj.targetX = 0;
    proj.targetY = 0;
  }

  // 1. Arrange domains around the project in a circle
  const domainIds = projectNode ? (childrenMap.get(projectNode.id) || []) : [];
  // Also collect any other domain nodes
  const allDomains = dataset.nodes.filter(n => n.kind === 'domain');
  const domainsToPlace = domainIds.length > 0 ? domainIds : allDomains.map(d => d.id);
  const domainCount = domainsToPlace.length;

  domainsToPlace.forEach((dId, idx) => {
    const dNode = nodeMap.get(dId);
    if (!dNode) return;

    // Distribute angles evenly around 360 degrees
    const angle = (idx / Math.max(1, domainCount)) * Math.PI * 2 - Math.PI / 2;
    const dx = Math.cos(angle) * RING_RADII.domain;
    const dy = Math.sin(angle) * RING_RADII.domain;

    dNode.x = dx;
    dNode.y = dy;
    dNode.targetX = dx;
    dNode.targetY = dy;

    // 2. Arrange capabilities around this domain
    const capIds = childrenMap.get(dId) || [];
    const capCount = capIds.length;
    if (capCount > 0) {
      // Fan outward in the direction of the domain angle
      const spreadAngle = Math.min(1.4, 0.4 + capCount * 0.18);
      const startAngle = angle - spreadAngle / 2;
      const step = capCount > 1 ? spreadAngle / (capCount - 1) : 0;

      capIds.forEach((cId, cIdx) => {
        const cNode = nodeMap.get(cId);
        if (!cNode) return;

        const cAngle = capCount === 1 ? angle : startAngle + cIdx * step;
        const cx = dx + Math.cos(cAngle) * RING_RADII.capability;
        const cy = dy + Math.sin(cAngle) * RING_RADII.capability;

        cNode.x = cx;
        cNode.y = cy;
        cNode.targetX = cx;
        cNode.targetY = cy;

        // 3. Arrange elements around this capability
        const elemIds = childrenMap.get(cId) || [];
        const elemCount = elemIds.length;
        if (elemCount > 0) {
          const elemSpread = Math.min(1.2, 0.35 + elemCount * 0.22);
          const elemStartAngle = cAngle - elemSpread / 2;
          const elemStep = elemCount > 1 ? elemSpread / (elemCount - 1) : 0;

          elemIds.forEach((eId, eIdx) => {
            const eNode = nodeMap.get(eId);
            if (!eNode) return;

            const eAngle = elemCount === 1 ? cAngle : elemStartAngle + eIdx * elemStep;
            const ex = cx + Math.cos(eAngle) * RING_RADII.element;
            const ey = cy + Math.sin(eAngle) * RING_RADII.element;

            eNode.x = ex;
            eNode.y = ey;
            eNode.targetX = ex;
            eNode.targetY = ey;
          });
        }
      });
    }
  });

  // Relaxation pass to ensure no overlapping nodes
  const nodesList = Array.from(nodeMap.values());
  for (let iter = 0; iter < 30; iter++) {
    for (let i = 0; i < nodesList.length; i++) {
      for (let j = i + 1; j < nodesList.length; j++) {
        const n1 = nodesList[i];
        const n2 = nodesList[j];
        if (n1.kind === 'project' || n2.kind === 'project') continue; // keep root pinned

        const dx = n2.x - n1.x;
        const dy = n2.y - n1.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const minDist = n1.renderRadius + n2.renderRadius + 14;

        if (dist < minDist) {
          const overlap = (minDist - dist) / 2;
          const nx = dx / dist;
          const ny = dy / dist;

          n1.x -= nx * overlap * 0.5;
          n1.y -= ny * overlap * 0.5;
          n2.x += nx * overlap * 0.5;
          n2.y += ny * overlap * 0.5;
        }
      }
    }
  }

  // Update targets after relaxation
  for (const node of nodesList) {
    node.targetX = node.x;
    node.targetY = node.y;
  }

  // Build layout edges
  const edges: LayoutEdge[] = [];
  for (const edge of dataset.edges) {
    const sNode = nodeMap.get(edge.source);
    const tNode = nodeMap.get(edge.target);
    if (!sNode || !tNode) continue;

    const isContainment = edge.type === 'contains';
    const isDirected = edge.type === 'depends_on' || edge.type === 'relies_on' || edge.type === 'reads';
    const isSymmetric = edge.type === 'is_similar_to' || edge.type === 'relates';

    edges.push({
      ...edge,
      sourceNode: sNode,
      targetNode: tNode,
      isTapered: isDirected,
      isDashed: isDirected || isSymmetric,
      isSymmetric: isSymmetric,
    });
  }

  return { nodes: nodesList, edges };
}
