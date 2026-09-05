import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Sparkles, X, Target } from 'lucide-react';
import {
  TopologyMapV2,
  type TopologyV2Node,
  type TopologyV2Edge,
} from '../atlas-engine';
import { parseOntologyYaml, toTopologyV2Format, getDefaultDataset } from '../lib/ontologyParser';
import { DEFAULT_ONTOLOGY_YAML } from '../data/defaultOntologyData';
import { OntologyToolbar } from '../components/OntologyToolbar';
import { OntologySideDrawer } from '../components/OntologySideDrawer';
import { OntologySearchModal } from '../components/OntologySearchModal';
import { OntologyYamlEditorModal } from '../components/OntologyYamlEditorModal';
import { OntologyLegend } from '../components/OntologyLegend';
import type { MapArrangement } from '../shared/appearance-preferences';
import '../ontology.css';

export default function OntologyPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [yamlContent, setYamlContent] = useState<string>(DEFAULT_ONTOLOGY_YAML);
  const [dataset, setDataset] = useState(() => getDefaultDataset());

  // Tokens for forcing canvas updates
  const [fitViewToken, setFitViewToken] = useState(1);
  const [relayoutToken, setRelayoutToken] = useState(1);

  // 3D View Settings
  const [view3d, setView3d] = useState(false);
  const [mapArrangement, setMapArrangement] = useState<MapArrangement>('ownership');

  // Interactive Expansion & Search State
  const [expandedParents, setExpandedParents] = useState<ReadonlySet<string>>(new Set());
  const [expandedAll, setExpandedAll] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [yamlEditorOpen, setYamlEditorOpen] = useState(false);

  // Focus & Trail & Edge Hover
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [visitedTrail, setVisitedTrail] = useState<string[]>([]);
  const [hoverEdge, setHoverEdge] = useState<{
    edge: { sourceId: string; targetId: string; relationType: string; declaredBySlug: string | null };
    x: number;
    y: number;
  } | null>(null);

  const handleHoverEdge = useCallback(
    (
      edge: { sourceId: string; targetId: string; relationType: string; declaredBySlug: string | null } | null,
      position: { x: number; y: number } | null,
    ) => {
      setHoverEdge(edge && position ? { edge, x: position.x, y: position.y } : null);
    },
    [],
  );

  const hoverEdgeCard = useMemo(() => {
    if (!hoverEdge) return null;
    const sourceNode = dataset.nodes.find(n => n.id === hoverEdge.edge.sourceId);
    const targetNode = dataset.nodes.find(n => n.id === hoverEdge.edge.targetId);
    const sourceTitle = sourceNode?.title || hoverEdge.edge.sourceId;
    const targetTitle = targetNode?.title || hoverEdge.edge.targetId;
    const relType = hoverEdge.edge.relationType.replace(/_/g, ' ');
    return {
      title: `${sourceTitle} → ${targetTitle}`,
      relation: relType,
      x: hoverEdge.x,
      y: hoverEdge.y,
    };
  }, [hoverEdge, dataset.nodes]);

  // Convert YAML dataset to exact TopologyMapV2 engine nodes and edges
  const { nodes, edges } = useMemo(() => {
    return toTopologyV2Format(dataset);
  }, [dataset]);

  // Handle Node Selection / 1-Hop Ego Focus
  const handleSelectNode = useCallback((nodeId: string | null) => {
    setSelectedNodeId(nodeId);
    if (nodeId) {
      setVisitedTrail(prev => (prev.includes(nodeId) ? prev : [...prev.slice(-6), nodeId]));
      setSearchParams(prev => {
        const next = new URLSearchParams(prev);
        next.set('focus', nodeId);
        return next;
      }, { replace: true });
    } else {
      setSearchParams(prev => {
        const next = new URLSearchParams(prev);
        next.delete('focus');
        return next;
      }, { replace: true });
    }
  }, [setSearchParams]);

  // Read initial query param focus on initial mount only
  useEffect(() => {
    const focusParam = searchParams.get('focus');
    if (focusParam) {
      const match = nodes.find(n => n.id === focusParam || n.id.endsWith(focusParam));
      if (match) {
        setSelectedNodeId(match.id);
        setVisitedTrail([match.id]);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Toggle Cluster Expansion
  const handleToggleCluster = useCallback((parentId: string) => {
    setExpandedParents(prev => {
      const next = new Set(prev);
      if (next.has(parentId)) {
        next.delete(parentId);
      } else {
        next.add(parentId);
      }
      return next;
    });
  }, []);

  // Expand / Collapse All
  const handleToggleExpandAll = useCallback(() => {
    setExpandedAll(prev => {
      const nextState = !prev;
      if (nextState) {
        const allParentIds = new Set<string>();
        for (const n of nodes) {
          if (n.parentId) {
            allParentIds.add(n.parentId);
          }
          if (n.kind === 'project' || n.kind === 'domain' || n.kind === 'capability') {
            allParentIds.add(n.id);
          }
        }
        setExpandedParents(allParentIds);
      } else {
        setExpandedParents(new Set());
      }
      return nextState;
    });
    setFitViewToken(t => t + 1);
  }, [nodes]);

  // Auto-arrange / Reset physics
  const handleAutoArrange = () => {
    setRelayoutToken(t => t + 1);
    setFitViewToken(t => t + 1);
  };

  // Fit View
  const handleFitView = () => {
    setFitViewToken(t => t + 1);
  };

  // 3D Cycle
  const handleToggle3D = () => {
    setView3d(prev => !prev);
  };

  const handleToggleArrangement = () => {
    setMapArrangement(prev => (prev === 'ownership' ? 'coupling' : 'ownership'));
  };

  // Apply new YAML content
  const handleApplyYaml = (newYaml: string): boolean => {
    const parsed = parseOntologyYaml(newYaml);
    setYamlContent(newYaml);
    setDataset(parsed);
    setSelectedNodeId(null);
    setVisitedTrail([]);
    setExpandedParents(new Set());
    setRelayoutToken(t => t + 1);
    setFitViewToken(t => t + 1);
    return true;
  };

  // Currently focused node object for drawer
  const focusedNode = useMemo(() => {
    if (!selectedNodeId) return null;
    return dataset.nodes.find(n => n.id === selectedNodeId) || null;
  }, [dataset.nodes, selectedNodeId]);

  return (
    <div
      className="ontology-page-root relative w-full h-full flex flex-col bg-[#090a10] overflow-hidden select-none"
    >
      {/* Top Left Title & Breadcrumbs Trail Pill */}
      <div className="ontology-header-pills absolute top-4 left-4 z-20 flex items-center gap-3">
        <div className="ontology-pill flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#131722]/85 backdrop-blur-md border border-[#2b334a]/80 shadow-xl text-white">
          <Sparkles size={14} className="text-[#fbbf24]" />
          <span className="text-xs font-bold tracking-tight">Ontology Topology Map</span>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#1e2438] text-[#94a3b8]">
            {nodes.length} nodes · {edges.length} relations
          </span>
        </div>

        {/* Trail Indicator Pill */}
        {selectedNodeId && (
          <div className="ontology-pill-trail flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#1e2338]/90 backdrop-blur-md border border-[#3b476e] shadow-xl text-xs font-medium text-[#c7d2fe] animate-in fade-in duration-200">
            <Target size={13} className="text-[#818cf8]" />
            <span>Trail · {visitedTrail.length}</span>
            <button
              onClick={() => handleSelectNode(null)}
              className="p-0.5 rounded-full hover:bg-[#2b3452] text-[#94a3b8] hover:text-white transition-colors"
              title="Clear focus"
            >
              <X size={12} />
            </button>
          </div>
        )}
      </div>

      {/* Top Floating Toolbar */}
      <OntologyToolbar
        expandedAll={expandedAll}
        onToggleExpandAll={handleToggleExpandAll}
        onOpenSearch={() => setSearchOpen(true)}
        onOpenYamlEditor={() => setYamlEditorOpen(true)}
        onAutoArrange={handleAutoArrange}
        onFitView={handleFitView}
        view3d={view3d}
        mapArrangement={mapArrangement}
        onToggle3D={handleToggle3D}
        onToggleArrangement={handleToggleArrangement}
      />

      {/* Verbatim Ported TopologyMapV2 Canvas Engine */}
      <div className="flex-1 w-full h-full min-h-0 relative">
        <TopologyMapV2
          nodes={nodes}
          edges={edges}
          focus={{ selectedSlug: selectedNodeId }}
          fitViewToken={fitViewToken}
          relayoutToken={relayoutToken}
          onSelect={handleSelectNode}
          onHoverEdge={handleHoverEdge}
          onPaneClick={() => handleSelectNode(null)}
          expandedParents={expandedParents}
          onToggleCluster={handleToggleCluster}
          view3d={view3d}
          mapArrangement={mapArrangement}
          visitedTrail={visitedTrail}
          walkNoticeLabel="No further connection in this direction"
          canvasLabel="Ontology Architecture Map"
          canvasBackground="dot"
        />
      </div>

      {/* Edge Hover Microcard Tooltip */}
      {hoverEdgeCard && (
        <div
          className="fixed z-30 pointer-events-none transform -translate-x-1/2 -translate-y-full mb-3 px-3 py-1.5 rounded-lg bg-[#141824]/95 backdrop-blur-md border border-[#3b476e] shadow-2xl text-xs text-white transition-opacity duration-150"
          style={{
            left: hoverEdgeCard.x,
            top: hoverEdgeCard.y - 12,
          }}
        >
          <div className="font-semibold text-[#818cf8] flex items-center gap-1.5 capitalize">
            <span>{hoverEdgeCard.relation}</span>
          </div>
          <div className="text-[11px] text-[#94a3b8] mt-0.5 whitespace-nowrap">
            {hoverEdgeCard.title}
          </div>
        </div>
      )}

      {/* Side Inspector Drawer */}
      <OntologySideDrawer
        node={focusedNode as any}
        onClose={() => handleSelectNode(null)}
        onSelectNode={handleSelectNode}
        onIsolateArea={handleSelectNode}
      />

      {/* Floating Bottom-Right Grammar Legend */}
      <OntologyLegend />

      {/* Quick Search Modal (Ctrl+K) */}
      <OntologySearchModal
        isOpen={searchOpen}
        onClose={() => setSearchOpen(false)}
        nodes={dataset.nodes as any}
        onSelectNode={handleSelectNode}
      />

      {/* YAML Editor & Uploader Modal */}
      <OntologyYamlEditorModal
        isOpen={yamlEditorOpen}
        onClose={() => setYamlEditorOpen(false)}
        yamlContent={yamlContent}
        onApplyYaml={handleApplyYaml}
      />
    </div>
  );
}

