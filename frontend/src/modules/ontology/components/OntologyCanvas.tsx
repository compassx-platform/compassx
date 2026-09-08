import React, { useRef, useEffect, useCallback } from 'react';
import { LayoutNode, LayoutEdge, CameraState, EgoFocusState } from '../types/ontology';
import { renderOntologyGraph } from '../lib/canvasRenderer';

interface OntologyCanvasProps {
  nodes: LayoutNode[];
  edges: LayoutEdge[];
  camera: CameraState;
  setCamera: React.Dispatch<React.SetStateAction<CameraState>>;
  egoFocus: EgoFocusState;
  onSelectNode: (nodeId: string | null) => void;
  hoveredNodeId: string | null;
  setHoveredNodeId: (id: string | null) => void;
  showLabels: boolean;
  expandedAll: boolean;
}

export const OntologyCanvas: React.FC<OntologyCanvasProps> = ({
  nodes,
  edges,
  camera,
  setCamera,
  egoFocus,
  onSelectNode,
  hoveredNodeId,
  setHoveredNodeId,
  showLabels,
  expandedAll,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const isPanningRef = useRef(false);
  const isDraggingNodeRef = useRef<string | null>(null);
  const lastMousePosRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const mouseScreenPosRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const animFrameIdRef = useRef<number | null>(null);

  // Convert screen coordinates to world coordinates
  const screenToWorld = useCallback((screenX: number, screenY: number, width: number, height: number, cam: CameraState) => {
    const cx = width / 2 + cam.x;
    const cy = height / 2 + cam.y;
    const tiltCos = cam.tiltAngle !== 0 ? Math.cos((cam.tiltAngle * Math.PI) / 180) : 1;

    const wx = (screenX - cx) / cam.zoom;
    const wy = (screenY - cy) / (cam.zoom * tiltCos);
    return { wx, wy };
  }, []);

  // Hit test node under world coordinates
  const hitTestNode = useCallback((wx: number, wy: number): LayoutNode | null => {
    for (let i = nodes.length - 1; i >= 0; i--) {
      const node = nodes[i];
      const dx = wx - node.x;
      const dy = wy - node.y;
      const hitRadius = Math.max(node.renderRadius + 6, 12);
      if (dx * dx + dy * dy <= hitRadius * hitRadius) {
        return node;
      }
    }
    return null;
  }, [nodes]);

  // Handle Canvas Render Loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let isRunning = true;

    const loop = () => {
      if (!isRunning) return;

      // Spring physics relaxation for dragged/free nodes
      for (const node of nodes) {
        if (node.id === isDraggingNodeRef.current) continue;
        if (node.targetX !== undefined && node.targetY !== undefined) {
          const dx = node.targetX - node.x;
          const dy = node.targetY - node.y;
          if (Math.abs(dx) > 0.05 || Math.abs(dy) > 0.05) {
            node.x += dx * 0.14;
            node.y += dy * 0.14;
          }
        }
      }

      // Render frame
      const rect = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      const w = rect.width > 0 ? rect.width : (canvas.parentElement?.clientWidth || window.innerWidth || 800);
      const h = rect.height > 0 ? rect.height : (canvas.parentElement?.clientHeight || (window.innerHeight - 48) || 600);

      if (canvas.width === 0 || canvas.height === 0) {
        canvas.width = Math.round(w * dpr);
        canvas.height = Math.round(h * dpr);
      }

      renderOntologyGraph(ctx, nodes, edges, {
        width: w,
        height: h,
        dpr,
        camera,
        egoFocus,
        hoveredNodeId,
        draggedNodeId: isDraggingNodeRef.current,
        showLabels,
        expandedAll,
      });

      animFrameIdRef.current = requestAnimationFrame(loop);
    };

    loop();

    return () => {
      isRunning = false;
      if (animFrameIdRef.current) cancelAnimationFrame(animFrameIdRef.current);
    };
  }, [nodes, edges, camera, egoFocus, hoveredNodeId, showLabels, expandedAll]);

  // Handle Canvas Resize Observer (Retina High-DPI support)
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const parent = canvas.parentElement;
    if (!parent) return;

    const resize = () => {
      const rect = parent.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.round(rect.width * dpr);
      canvas.height = Math.round(rect.height * dpr);
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
    };

    const ro = new ResizeObserver(() => resize());
    ro.observe(parent);
    resize();

    return () => ro.disconnect();
  }, []);

  // Pointer Down (Pan vs Drag Node)
  const handlePointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    canvas.setPointerCapture(e.pointerId);

    const rect = canvas.getBoundingClientRect();
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;

    lastMousePosRef.current = { x: sx, y: sy };
    mouseScreenPosRef.current = { x: sx, y: sy };

    const { wx, wy } = screenToWorld(sx, sy, rect.width, rect.height, camera);
    const hit = hitTestNode(wx, wy);

    if (hit) {
      isDraggingNodeRef.current = hit.id;
    } else {
      isPanningRef.current = true;
    }
  };

  // Pointer Move (Pan / Node Drag / Hover)
  const handlePointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;
    const dx = sx - lastMousePosRef.current.x;
    const dy = sy - lastMousePosRef.current.y;

    lastMousePosRef.current = { x: sx, y: sy };
    mouseScreenPosRef.current = { x: sx, y: sy };

    if (isDraggingNodeRef.current) {
      const draggedNode = nodes.find(n => n.id === isDraggingNodeRef.current);
      if (draggedNode && draggedNode.kind !== 'project') {
        const tiltCos = camera.tiltAngle !== 0 ? Math.cos((camera.tiltAngle * Math.PI) / 180) : 1;
        draggedNode.x += dx / camera.zoom;
        draggedNode.y += dy / (camera.zoom * tiltCos);
        draggedNode.targetX = draggedNode.x;
        draggedNode.targetY = draggedNode.y;
      }
    } else if (isPanningRef.current) {
      setCamera(prev => ({
        ...prev,
        x: prev.x + dx,
        y: prev.y + dy,
      }));
    } else {
      // Hover detection
      const { wx, wy } = screenToWorld(sx, sy, rect.width, rect.height, camera);
      const hit = hitTestNode(wx, wy);
      setHoveredNodeId(hit ? hit.id : null);
    }
  };

  // Pointer Up (Click Selection / Stop Drag)
  const handlePointerUp = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    try {
      canvas.releasePointerCapture(e.pointerId);
    } catch {
      // ignore
    }

    const rect = canvas.getBoundingClientRect();
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;

    if (isDraggingNodeRef.current) {
      const draggedId = isDraggingNodeRef.current;
      isDraggingNodeRef.current = null;
      // Also treat click as selection
      onSelectNode(draggedId);
    } else if (isPanningRef.current) {
      isPanningRef.current = false;
    } else {
      // Clicked on empty space -> clear ego focus
      const { wx, wy } = screenToWorld(sx, sy, rect.width, rect.height, camera);
      const hit = hitTestNode(wx, wy);
      if (!hit) {
        onSelectNode(null);
      }
    }
  };

  // Mouse Wheel (Zoom smoothly towards pointer)
  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;

    const zoomFactor = e.deltaY < 0 ? 1.12 : 0.89;
    setCamera(prev => {
      const newZoom = Math.min(4.0, Math.max(0.35, prev.zoom * zoomFactor));
      if (newZoom === prev.zoom) return prev;

      // Adjust camera.x, camera.y so mouse location in world remains fixed
      const cx = rect.width / 2;
      const cy = rect.height / 2;
      const mouseOffsetFromCenterX = sx - cx - prev.x;
      const mouseOffsetFromCenterY = sy - cy - prev.y;

      const scaleChange = newZoom / prev.zoom;
      const newX = prev.x - mouseOffsetFromCenterX * (scaleChange - 1);
      const newY = prev.y - mouseOffsetFromCenterY * (scaleChange - 1);

      return {
        ...prev,
        zoom: newZoom,
        x: newX,
        y: newY,
      };
    });
  };

  return (
    <div
      className="relative w-full h-full select-none overflow-hidden bg-[#090a10]"
      style={{ minHeight: '500px', height: '100%', width: '100%' }}
    >
      <canvas
        ref={canvasRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onWheel={handleWheel}
        className="w-full h-full cursor-grab active:cursor-grabbing block"
        style={{ width: '100%', height: '100%', display: 'block' }}
      />
    </div>
  );
};
