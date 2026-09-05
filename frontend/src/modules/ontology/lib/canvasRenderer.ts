import { LayoutNode, LayoutEdge, CameraState, EgoFocusState, OntologyKind } from '../types/ontology';

export interface RenderOptions {
  width: number;
  height: number;
  dpr?: number;
  camera: CameraState;
  egoFocus: EgoFocusState;
  hoveredNodeId: string | null;
  draggedNodeId: string | null;
  showLabels: boolean;
  expandedAll: boolean;
}

// Fixed Starfield background particles
const STARFIELD_COUNT = 70;
const starfieldParticles: { x: number; y: number; size: number; alpha: number }[] = [];
for (let i = 0; i < STARFIELD_COUNT; i++) {
  starfieldParticles.push({
    x: (Math.random() - 0.5) * 3000,
    y: (Math.random() - 0.5) * 3000,
    size: Math.random() * 1.5 + 0.5,
    alpha: Math.random() * 0.4 + 0.1,
  });
}

/**
 * Draw 6-sided flat-top regular hexagon points
 */
function getHexPoints(cx: number, cy: number, r: number): { x: number; y: number }[] {
  const points: { x: number; y: number }[] = [];
  for (let i = 0; i < 6; i++) {
    const angle = ((i * 60 - 90) * Math.PI) / 180;
    points.push({ x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) });
  }
  return points;
}

/**
 * Draw rounded rectangle path
 */
function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  const radius = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.arcTo(x + w, y, x + w, y + h, radius);
  ctx.arcTo(x + w, y + h, x, y + h, radius);
  ctx.arcTo(x, y + h, x, y, radius);
  ctx.arcTo(x, y, x + w, y, radius);
  ctx.closePath();
}

/**
 * Primary 60fps HTML5 Canvas rendering routine
 */
export function renderOntologyGraph(
  ctx: CanvasRenderingContext2D,
  nodes: LayoutNode[],
  edges: LayoutEdge[],
  options: RenderOptions
) {
  const { width, height, camera, egoFocus, hoveredNodeId, draggedNodeId, showLabels } = options;
  const dpr = options.dpr || 1;
  const zoom = camera.zoom;
  const hasEgo = egoFocus.focusedNodeId !== null;

  // 1. Clear background
  ctx.save();
  ctx.scale(dpr, dpr);
  ctx.fillStyle = '#090a10';
  ctx.fillRect(0, 0, width, height);

  // 2. Setup Camera Transform (Translate to Center + Pan + Zoom + 3D Tilt perspective)
  ctx.translate(width / 2 + camera.x, height / 2 + camera.y);
  if (camera.tiltAngle !== 0) {
    ctx.scale(zoom, zoom * Math.cos((camera.tiltAngle * Math.PI) / 180));
  } else {
    ctx.scale(zoom, zoom);
  }

  // 3. Render Dot Grid & Starfield
  renderBackdrop(ctx, camera);

  // 4. Semantic Zoom Alpha calculations
  // Capability fade: from zoom 1.0x to 1.6x
  const capabilityAlpha = Math.min(1.0, Math.max(0.15, (zoom - 0.75) / 0.75));
  // Element fade: from zoom 1.6x to 2.4x
  const elementAlpha = Math.min(1.0, Math.max(0.0, (zoom - 1.4) / 0.8));

  // 5. Draw Edges
  for (const edge of edges) {
    const s = edge.sourceNode;
    const t = edge.targetNode;

    // Check visibility based on zoom
    if (s.kind === 'element' || t.kind === 'element') {
      if (elementAlpha <= 0.05 && !hasEgo) continue;
    } else if (s.kind === 'capability' || t.kind === 'capability') {
      if (capabilityAlpha <= 0.1 && !hasEgo) continue;
    }

    // Determine edge focus status
    let edgeAlpha = 0.22;
    let strokeColor = '#334155';
    let isConnectedToFocus = false;

    if (hasEgo) {
      const isSrcFocused = s.id === egoFocus.focusedNodeId;
      const isTgtFocused = t.id === egoFocus.focusedNodeId;
      if (isSrcFocused || isTgtFocused) {
        edgeAlpha = 0.95;
        strokeColor = '#818cf8'; // Electric indigo connection
        isConnectedToFocus = true;
      } else {
        edgeAlpha = 0.06; // Dim background edges
      }
    }

    drawEdge(ctx, s, t, edge, edgeAlpha, strokeColor, isConnectedToFocus);
  }

  // 6. Draw Nodes
  // Sort nodes so elements draw first, then capabilities, then domains, then project on top
  const sortedNodes = [...nodes].sort((a, b) => {
    const rank: Record<OntologyKind, number> = { element: 1, capability: 2, domain: 3, project: 4 };
    return rank[a.kind] - rank[b.kind];
  });

  for (const node of sortedNodes) {
    // Visibility LOD
    let nodeAlpha = 1.0;
    if (node.kind === 'element') {
      nodeAlpha = elementAlpha;
      if (nodeAlpha <= 0.05 && !hasEgo) continue;
    } else if (node.kind === 'capability') {
      nodeAlpha = capabilityAlpha;
      if (nodeAlpha <= 0.1 && !hasEgo) continue;
    }

    // Ego focus states
    const isCenter = node.id === egoFocus.focusedNodeId;
    const isNeighbor = egoFocus.neighborIds.has(node.id);
    const isHovered = node.id === hoveredNodeId;
    const isDragged = node.id === draggedNodeId;

    if (hasEgo) {
      if (isCenter) {
        nodeAlpha = 1.0;
      } else if (isNeighbor) {
        nodeAlpha = 0.95;
      } else {
        nodeAlpha = Math.min(nodeAlpha, 0.12); // Dim non-connected
      }
    }

    drawNode(ctx, node, {
      zoom,
      alpha: nodeAlpha,
      isCenter,
      isNeighbor,
      isHovered,
      isDragged,
      showLabels,
    });
  }

  ctx.restore();
}

/**
 * Draw background starfield & subtle grid
 */
function renderBackdrop(ctx: CanvasRenderingContext2D, camera: CameraState) {
  // Starfield
  for (const star of starfieldParticles) {
    ctx.fillStyle = `rgba(226, 232, 240, ${star.alpha * 0.6})`;
    ctx.beginPath();
    ctx.arc(star.x, star.y, star.size, 0, Math.PI * 2);
    ctx.fill();
  }

  // Dot Grid
  const gridSize = 140;
  const gridRange = 1600;
  ctx.fillStyle = 'rgba(71, 85, 105, 0.18)';
  for (let x = -gridRange; x <= gridRange; x += gridSize) {
    for (let y = -gridRange; y <= gridRange; y += gridSize) {
      ctx.beginPath();
      ctx.arc(x, y, 1.2, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}

/**
 * Draw individual graph edge (solid containment or tapered dashed dependency)
 */
function drawEdge(
  ctx: CanvasRenderingContext2D,
  source: LayoutNode,
  target: LayoutNode,
  edge: LayoutEdge,
  alpha: number,
  baseColor: string,
  isConnectedToFocus: boolean
) {
  ctx.save();
  ctx.globalAlpha = alpha;

  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const dist = Math.sqrt(dx * dx + dy * dy) || 1;

  // Offset line start/end to node boundaries
  const sOffset = source.renderRadius;
  const tOffset = target.renderRadius;

  const startX = source.x + (dx / dist) * sOffset;
  const startY = source.y + (dy / dist) * sOffset;
  const endX = target.x - (dx / dist) * tOffset;
  const endY = target.y - (dy / dist) * tOffset;

  if (edge.isTapered) {
    // Tapered dashed line (directed dependency from source -> target)
    ctx.strokeStyle = isConnectedToFocus ? '#a5b4fc' : '#64748b';
    ctx.lineWidth = isConnectedToFocus ? 2.5 : 1.5;
    ctx.setLineDash([6, 4]);

    ctx.beginPath();
    ctx.moveTo(startX, startY);
    ctx.lineTo(endX, endY);
    ctx.stroke();

    // Draw small directional marker at target
    ctx.setLineDash([]);
    ctx.fillStyle = isConnectedToFocus ? '#a5b4fc' : '#64748b';
    ctx.beginPath();
    ctx.arc(endX, endY, 2.5, 0, Math.PI * 2);
    ctx.fill();
  } else if (edge.isSymmetric) {
    // Symmetric peer relation (uniform dashed)
    ctx.strokeStyle = isConnectedToFocus ? '#818cf8' : '#475569';
    ctx.lineWidth = 1.2;
    ctx.setLineDash([4, 4]);

    ctx.beginPath();
    ctx.moveTo(startX, startY);
    ctx.lineTo(endX, endY);
    ctx.stroke();
  } else {
    // Solid containment hierarchy line
    ctx.strokeStyle = isConnectedToFocus ? '#6366f1' : 'rgba(100, 116, 139, 0.35)';
    ctx.lineWidth = isConnectedToFocus ? 2.0 : 1.0;
    ctx.setLineDash([]);

    ctx.beginPath();
    ctx.moveTo(startX, startY);
    ctx.lineTo(endX, endY);
    ctx.stroke();
  }

  ctx.restore();
}

/**
 * Draw custom shape node with tactile depth, halos, and embossed numerals
 */
function drawNode(
  ctx: CanvasRenderingContext2D,
  node: LayoutNode,
  state: {
    zoom: number;
    alpha: number;
    isCenter: boolean;
    isNeighbor: boolean;
    isHovered: boolean;
    isDragged: boolean;
    showLabels: boolean;
  }
) {
  const { x, y, renderRadius, kind } = node;
  const { zoom, alpha, isCenter, isNeighbor, isHovered, showLabels } = state;
  const r = renderRadius;

  ctx.save();
  ctx.globalAlpha = alpha;

  // 1. Halo / Selection Rings
  if (isCenter) {
    // Outer electric indigo ring
    ctx.strokeStyle = 'rgba(99, 102, 241, 0.4)';
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.arc(x, y, r + 8, 0, Math.PI * 2);
    ctx.stroke();

    // Inner bright indigo ring
    ctx.strokeStyle = '#818cf8';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(x, y, r + 4, 0, Math.PI * 2);
    ctx.stroke();
  } else if (isNeighbor) {
    // 1-hop connected neighbor ring
    ctx.strokeStyle = 'rgba(129, 140, 248, 0.6)';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(x, y, r + 4, 0, Math.PI * 2);
    ctx.stroke();
  } else if (isHovered) {
    // Hover preview ring
    ctx.strokeStyle = 'rgba(148, 163, 184, 0.8)';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(x, y, r + 3, 0, Math.PI * 2);
    ctx.stroke();
  }

  // 2. Specific Geometry per Kind
  if (kind === 'project') {
    // ==========================================
    // PROJECT: Hexagonal Plate (R=30)
    // ==========================================
    const hex = getHexPoints(x, y, r);

    // Chassis pin ticks at 4 cardinal positions
    ctx.strokeStyle = '#d97706';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(x - r - 4, y); ctx.lineTo(x - r + 2, y);
    ctx.moveTo(x + r - 2, y); ctx.lineTo(x + r + 4, y);
    ctx.moveTo(x, y - r - 4); ctx.lineTo(x, y - r + 2);
    ctx.moveTo(x, y + r - 2); ctx.lineTo(x, y + r + 4);
    ctx.stroke();

    // Main Hexagon body
    ctx.beginPath();
    hex.forEach((p, idx) => {
      if (idx === 0) ctx.moveTo(p.x, p.y);
      else ctx.lineTo(p.x, p.y);
    });
    ctx.closePath();

    // Subtle metallic dark gradient fill
    const grad = ctx.createLinearGradient(x, y - r, x, y + r);
    grad.addColorStop(0, '#26241e');
    grad.addColorStop(1, '#151411');
    ctx.fillStyle = grad;
    ctx.fill();

    // Machined Amber Bezel Outer Stroke
    ctx.strokeStyle = '#f59e0b';
    ctx.lineWidth = 2.5;
    ctx.stroke();

    // Inner machined bezel hairline
    const innerHex = getHexPoints(x, y, r - 4);
    ctx.beginPath();
    innerHex.forEach((p, idx) => {
      if (idx === 0) ctx.moveTo(p.x, p.y);
      else ctx.lineTo(p.x, p.y);
    });
    ctx.closePath();
    ctx.strokeStyle = 'rgba(251, 191, 36, 0.4)';
    ctx.lineWidth = 1;
    ctx.stroke();

    // Amber Crosshair Glyph in center
    ctx.strokeStyle = '#fbbf24';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(x, y, 7, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x - 10, y); ctx.lineTo(x + 10, y);
    ctx.moveTo(x, y - 10); ctx.lineTo(x, y + 10);
    ctx.stroke();

    // Embossed Total Descendants Numeral
    if (r * zoom >= 13 && node.totalDescendantCount !== undefined) {
      ctx.font = 'bold 11px system-ui, -apple-system, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = '#fef3c7';
      ctx.fillText(String(node.totalDescendantCount), x, y + 15);
    }
  } else if (kind === 'domain') {
    // ==========================================
    // DOMAIN: Square IC Chip with corner pin legs (R=17)
    // ==========================================
    const s = r;

    // Corner pin tick legs (2 ticks per side, IC chip look)
    ctx.strokeStyle = '#64748b';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    // Left legs
    ctx.moveTo(x - s - 4, y - s * 0.4); ctx.lineTo(x - s, y - s * 0.4);
    ctx.moveTo(x - s - 4, y + s * 0.4); ctx.lineTo(x - s, y + s * 0.4);
    // Right legs
    ctx.moveTo(x + s, y - s * 0.4); ctx.lineTo(x + s + 4, y - s * 0.4);
    ctx.moveTo(x + s, y + s * 0.4); ctx.lineTo(x + s + 4, y + s * 0.4);
    // Top legs
    ctx.moveTo(x - s * 0.4, y - s - 4); ctx.lineTo(x - s * 0.4, y - s);
    ctx.moveTo(x + s * 0.4, y - s - 4); ctx.lineTo(x + s * 0.4, y - s);
    // Bottom legs
    ctx.moveTo(x - s * 0.4, y + s); ctx.lineTo(x - s * 0.4, y + s + 4);
    ctx.moveTo(x + s * 0.4, y + s); ctx.lineTo(x + s * 0.4, y + s + 4);
    ctx.stroke();

    // Rounded square body
    roundRect(ctx, x - s, y - s, s * 2, s * 2, 4);

    const grad = ctx.createLinearGradient(x, y - s, x, y + s);
    grad.addColorStop(0, '#23283c');
    grad.addColorStop(1, '#141724');
    ctx.fillStyle = grad;
    ctx.fill();

    ctx.strokeStyle = isCenter ? '#818cf8' : '#475569';
    ctx.lineWidth = isCenter ? 2 : 1.5;
    ctx.stroke();

    // Embossed Number (transitive descendants)
    if (r * zoom >= 11 && node.totalDescendantCount !== undefined) {
      ctx.font = 'bold 10px system-ui, -apple-system, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = '#cbd5e1';
      ctx.fillText(String(node.totalDescendantCount), x, y);
    }
  } else if (kind === 'capability') {
    // ==========================================
    // CAPABILITY: Smooth Circle / Disc (R=11)
    // ==========================================
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);

    // Directional lighting depth shading (Sun & Perona 1998)
    const shade = ctx.createRadialGradient(
      x - r * 0.35, y - r * 0.35, r * 0.1,
      x, y, r * 1.2
    );
    shade.addColorStop(0, '#384260');
    shade.addColorStop(0.7, '#1e2438');
    shade.addColorStop(1, '#111422');

    ctx.fillStyle = shade;
    ctx.fill();

    ctx.strokeStyle = isCenter ? '#818cf8' : '#475569';
    ctx.lineWidth = 1.2;
    ctx.stroke();
  } else if (kind === 'element') {
    // ==========================================
    // ELEMENT: Square copper pad with drilled center via hole (R=7)
    // ==========================================
    const s = r;
    roundRect(ctx, x - s, y - s, s * 2, s * 2, 2);
    ctx.fillStyle = '#1e2536';
    ctx.fill();

    ctx.strokeStyle = '#475569';
    ctx.lineWidth = 1;
    ctx.stroke();

    // Center drilled via hole
    ctx.beginPath();
    ctx.arc(x, y, r * 0.35, 0, Math.PI * 2);
    ctx.fillStyle = '#090a10';
    ctx.fill();
    ctx.strokeStyle = '#334155';
    ctx.stroke();
  }

  // 3. Node Label
  if (showLabels) {
    let shouldRenderLabel = true;
    if (kind === 'element' && zoom < 1.9) shouldRenderLabel = false;
    if (kind === 'capability' && zoom < 1.2) shouldRenderLabel = false;

    if (shouldRenderLabel) {
      const labelY = y + r + 13;
      ctx.font = kind === 'project'
        ? 'bold 13px system-ui, -apple-system, sans-serif'
        : kind === 'domain'
        ? '600 11px system-ui, -apple-system, sans-serif'
        : '500 10px system-ui, -apple-system, sans-serif';

      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';

      // Truncate long labels for capabilities/elements
      let labelText = node.title;
      if (kind === 'capability' && labelText.length > 28) {
        labelText = labelText.substring(0, 26) + '...';
      } else if (kind === 'element' && labelText.length > 22) {
        labelText = labelText.substring(0, 20) + '...';
      }

      // Backdrop shadow for legibility
      ctx.fillStyle = 'rgba(9, 10, 16, 0.85)';
      const metrics = ctx.measureText(labelText);
      ctx.fillRect(x - metrics.width / 2 - 4, labelY - 2, metrics.width + 8, 14);

      // Label Text color
      if (kind === 'project') {
        ctx.fillStyle = '#fbbf24'; // Warm amber gold
      } else if (kind === 'domain') {
        ctx.fillStyle = isCenter ? '#a5b4fc' : '#e2e8f0';
      } else {
        ctx.fillStyle = isCenter ? '#c7d2fe' : '#94a3b8';
      }
      ctx.fillText(labelText, x, labelY);
    }
  }

  ctx.restore();
}
