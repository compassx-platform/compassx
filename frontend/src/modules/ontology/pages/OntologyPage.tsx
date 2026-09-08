import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Sparkles, X, Target, Settings } from 'lucide-react';
import {
  TopologyMapV2,
  type TopologyV2Node,
  type TopologyV2Edge,
} from '../atlas-engine';
import { clearTopologyV2TokensCache } from '../atlas-engine/tokens/read-topology-v2-tokens';
import {
  processRawOntologyData,
  toTopologyV2Format,
  getDefaultDataset,
} from '../lib/ontologyParser';
import {
  fetchOntologyTypes,
  fetchTypeRelations,
  fetchActiveKnowledgeGraph,
  addGraphNode,
  updateGraphNode,
  deleteGraphNode,
  addGraphEdge,
  deleteGraphEdge,
} from '../api/ontologyApi';
import {
  OntologyConfigPanel,
  loadKindsConfig,
  saveKindsConfig,
  type KindConfig,
  loadTypeRelations,
  saveTypeRelations,
  type TypeRelationConfig,
} from '../config';
import { OntologyToolbar } from '../components/OntologyToolbar';
import { OntologySideDrawer } from '../components/OntologySideDrawer';
import { OntologySearchModal } from '../components/OntologySearchModal';
import { OntologyAddNodeModal } from '../components/OntologyAddNodeModal';
import { OntologyLegend } from '../components/OntologyLegend';
import type { MapArrangement } from '../shared/appearance-preferences';
import '../ontology.css';

export default function OntologyPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [dataset, setDataset] = useState(() => getDefaultDataset());
  const [addNodeOpen, setAddNodeOpen] = useState(false);
  const [addNodeParentId, setAddNodeParentId] = useState<string | null>(null);

  // Light / Dark Theme Mode
  const [themeMode, setThemeMode] = useState<'dark' | 'light'>(() => {
    if (typeof window === 'undefined') return 'dark';
    const stored = localStorage.getItem('ontology_theme_mode');
    if (stored === 'light' || stored === 'dark') return stored;
    return 'dark';
  });

  const handleToggleTheme = useCallback(() => {
    setThemeMode(prev => {
      const next = prev === 'dark' ? 'light' : 'dark';
      localStorage.setItem('ontology_theme_mode', next);
      clearTopologyV2TokensCache();
      return next;
    });
  }, []);

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

  // Focus & Trail & Edge Hover
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [visitedTrail, setVisitedTrail] = useState<string[]>([]);

  // Unified Side Drawer State: 'config' | 'node' | null
  const [drawerMode, setDrawerMode] = useState<'config' | 'node' | null>(null);

  const handleToggleConfig = useCallback(() => {
    setDrawerMode(prev => (prev === 'config' ? null : 'config'));
  }, []);

  const handleCloseDrawer = useCallback(() => {
    setDrawerMode(null);
    setSelectedNodeId(null);
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      next.delete('focus');
      return next;
    }, { replace: true });
  }, [setSearchParams]);

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

  // Dynamic Kinds Configuration (Isolated Configuration Subsystem)
  const [kindsConfig, setKindsConfig] = useState<KindConfig[]>(() => loadKindsConfig());

  const handleUpdateKindsConfig = useCallback((newKinds: KindConfig[]) => {
    setKindsConfig(newKinds);
    saveKindsConfig(newKinds);
    setRelayoutToken(t => t + 1);
    setFitViewToken(t => t + 1);
  }, []);

  // Dynamic Type Relationships (Metamodel Schema)
  const [typeRelations, setTypeRelations] = useState<TypeRelationConfig[]>(() => loadTypeRelations());

  const handleUpdateTypeRelations = useCallback((newRelations: TypeRelationConfig[]) => {
    setTypeRelations(newRelations);
    saveTypeRelations(newRelations);
  }, []);

  // Convert Knowledge Graph dataset to exact TopologyMapV2 engine nodes and edges
  const { nodes, edges } = useMemo(() => {
    return toTopologyV2Format(dataset, kindsConfig);
  }, [dataset, kindsConfig]);

  // Handle Node Selection / 1-Hop Ego Focus & Switch Drawer to Node Details
  const handleSelectNode = useCallback((nodeId: string | null) => {
    setSelectedNodeId(nodeId);
    if (nodeId) {
      setDrawerMode('node');
      setVisitedTrail(prev => (prev.includes(nodeId) ? prev : [...prev.slice(-6), nodeId]));
      setSearchParams(prev => {
        const next = new URLSearchParams(prev);
        next.set('focus', nodeId);
        return next;
      }, { replace: true });
    } else {
      setDrawerMode(prev => (prev === 'node' ? null : prev));
      setSearchParams(prev => {
        const next = new URLSearchParams(prev);
        next.delete('focus');
        return next;
      }, { replace: true });
    }
  }, [setSearchParams]);

  // Initial load from Database (Metamodel Types + Active Knowledge Graph)
  useEffect(() => {
    let isMounted = true;

    async function loadInitialData() {
      try {
        // Load entity types from metamodel DB
        const remoteTypes = await fetchOntologyTypes().catch(() => null);
        if (remoteTypes && remoteTypes.length > 0 && isMounted) {
          setKindsConfig(remoteTypes);
          saveKindsConfig(remoteTypes);
        }

        // Load type relations from metamodel DB
        const remoteRelations = await fetchTypeRelations().catch(() => null);
        if (remoteRelations && remoteRelations.length > 0 && isMounted) {
          setTypeRelations(remoteRelations);
          saveTypeRelations(remoteRelations);
        }

        // Load active Knowledge Graph from DB
        const remoteGraph = await fetchActiveKnowledgeGraph().catch(() => null);
        if (remoteGraph && remoteGraph.nodes && remoteGraph.nodes.length > 0 && isMounted) {
          const processed = processRawOntologyData(remoteGraph);
          setDataset(processed);
        }
      } catch (err) {
        console.warn('Could not load ontology from DB, using fallback dataset:', err);
      }
    }

    loadInitialData();

    return () => {
      isMounted = false;
    };
  }, []);

  // Read initial query param focus on initial mount only
  useEffect(() => {
    const focusParam = searchParams.get('focus');
    if (focusParam) {
      const match = nodes.find(n => n.id === focusParam || n.id.endsWith(focusParam));
      if (match) {
        setSelectedNodeId(match.id);
        setDrawerMode('node');
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
        for (const n of dataset.nodes) {
          if (n.parentId) {
            allParentIds.add(n.parentId);
          }
          if (n.kind === 'org' || n.kind === 'project' || n.kind === 'domain' || n.kind === 'subdomain' || n.kind === 'capability') {
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
  }, [dataset.nodes]);

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

  // Add a new node (Entity) into the active Knowledge Graph DB
  const handleAddNode = async (nodeData: {
    id: string;
    kind: string;
    title: string;
    description?: string;
    parentId?: string | null;
    tags?: string[];
    status?: string;
  }): Promise<boolean> => {
    const updatedGraph = await addGraphNode(nodeData);
    const processed = processRawOntologyData(updatedGraph);
    setDataset(processed);
    setSelectedNodeId(nodeData.id);
    setRelayoutToken(t => t + 1);
    setFitViewToken(t => t + 1);
    return true;
  };

  // Update an existing node in the active Knowledge Graph DB
  const handleUpdateNode = async (
    nodeId: string,
    updates: { title?: string; description?: string; tags?: string[]; status?: string }
  ): Promise<boolean> => {
    const updatedGraph = await updateGraphNode(nodeId, updates);
    const processed = processRawOntologyData(updatedGraph);
    setDataset(processed);
    return true;
  };

  // Delete a node from the active Knowledge Graph DB
  const handleDeleteNode = async (nodeId: string): Promise<boolean> => {
    const updatedGraph = await deleteGraphNode(nodeId);
    const processed = processRawOntologyData(updatedGraph);
    setDataset(processed);
    if (selectedNodeId === nodeId) {
      setSelectedNodeId(null);
    }
    setRelayoutToken(t => t + 1);
    setFitViewToken(t => t + 1);
    return true;
  };

  // Add a new relationship edge into the active Knowledge Graph DB
  const handleAddEdge = async (edgeData: {
    source: string;
    target: string;
    type: string;
    description?: string;
  }): Promise<boolean> => {
    const updatedGraph = await addGraphEdge(edgeData);
    const processed = processRawOntologyData(updatedGraph);
    setDataset(processed);
    setRelayoutToken(t => t + 1);
    return true;
  };

  // Currently focused node object for drawer
  const focusedNode = useMemo(() => {
    if (!selectedNodeId) return null;
    return dataset.nodes.find(n => n.id === selectedNodeId) || null;
  }, [dataset.nodes, selectedNodeId]);

  return (
    <div
      className="ontology-page-root relative w-full h-full flex flex-col overflow-hidden select-none"
      data-theme={themeMode}
    >
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
          theme={themeMode}
        />
      </div>

      {/* Top Left Title & Breadcrumbs Trail Pill */}
      <div className="ontology-header-pills absolute top-1.5 left-2.5 z-30 flex items-center gap-2 pointer-events-auto">
        <div className="ontology-pill flex items-center gap-2 px-2.5 py-0.5 rounded-full bg-[#131722]/85 backdrop-blur-md border border-[#2b334a]/80 shadow-xl text-white">
          <Sparkles size={14} className="text-[#fbbf24]" />
          <span className="text-xs font-bold tracking-tight">Ontology Topology Map</span>
          <span className="ontology-pill-count text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#1e2438] text-[#94a3b8]">
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

      {/* Top Center Floating Toolbar */}
      <OntologyToolbar
        expandedAll={expandedAll}
        onToggleExpandAll={handleToggleExpandAll}
        onOpenSearch={() => setSearchOpen(true)}
        onOpenAddNode={() => {
          setAddNodeParentId(null);
          setAddNodeOpen(true);
        }}
        onAutoArrange={handleAutoArrange}
        onFitView={handleFitView}
        view3d={view3d}
        mapArrangement={mapArrangement}
        onToggle3D={handleToggle3D}
        onToggleArrangement={handleToggleArrangement}
        themeMode={themeMode}
        onToggleTheme={handleToggleTheme}
      />

      {/* Top Right Configure Trigger Button */}
      <div className={`cx-ontology-config-trigger ${drawerMode === 'config' ? 'is-active' : ''}`}>
        <button
          type="button"
          onClick={handleToggleConfig}
          className="cx-ontology-config-trigger-btn"
          title="Toggle Configuration Panel"
        >
          <Settings
            size={13}
            style={{
              transition: 'transform 0.25s ease',
              transform: drawerMode === 'config' ? 'rotate(90deg)' : 'none',
            }}
          />
          <span>Configure</span>
        </button>
      </div>

      {/* Unified Side Drawer: Configuration Mode */}
      {drawerMode === 'config' && (
        <OntologyConfigPanel
          isOpen={true}
          hideTrigger={true}
          onClose={handleCloseDrawer}
          kindsConfig={kindsConfig}
          onUpdateKindsConfig={handleUpdateKindsConfig}
          typeRelations={typeRelations}
          onUpdateTypeRelations={handleUpdateTypeRelations}
          themeMode={themeMode}
          onToggleTheme={handleToggleTheme}
          view3d={view3d}
          onToggle3D={handleToggle3D}
          mapArrangement={mapArrangement}
          onToggleArrangement={handleToggleArrangement}
          expandedAll={expandedAll}
          onToggleExpandAll={handleToggleExpandAll}
          onAutoArrange={handleAutoArrange}
          onFitView={handleFitView}
          nodeCount={nodes.length}
          edgeCount={edges.length}
        />
      )}

      {/* Edge Hover Microcard Tooltip */}
      {hoverEdgeCard && (
        <div
          className="ontology-edge-tooltip fixed z-30 pointer-events-none transform -translate-x-1/2 -translate-y-full mb-3 px-3 py-1.5 rounded-lg bg-[#141824]/95 backdrop-blur-md border border-[#3b476e] shadow-2xl text-xs text-white transition-opacity duration-150"
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

      {/* Unified Side Drawer: Node Details Mode */}
      {drawerMode === 'node' && focusedNode && (
        <OntologySideDrawer
          node={focusedNode as any}
          onClose={handleCloseDrawer}
          onSelectNode={handleSelectNode}
          onIsolateArea={handleSelectNode}
          onOpenAddChildNode={(parentId) => {
            setAddNodeParentId(parentId);
            setAddNodeOpen(true);
          }}
          onUpdateNode={handleUpdateNode}
          onDeleteNode={handleDeleteNode}
          onAddEdge={handleAddEdge}
          kindsConfig={kindsConfig}
          allNodes={dataset.nodes as any}
        />
      )}

      {/* Floating Bottom-Right Grammar Legend */}
      <OntologyLegend />

      {/* Quick Search Modal (Ctrl+K) */}
      <OntologySearchModal
        isOpen={searchOpen}
        onClose={() => setSearchOpen(false)}
        nodes={dataset.nodes as any}
        onSelectNode={handleSelectNode}
      />

      {/* Add Entity Modal */}
      <OntologyAddNodeModal
        isOpen={addNodeOpen}
        onClose={() => {
          setAddNodeOpen(false);
          setAddNodeParentId(null);
        }}
        kindsConfig={kindsConfig}
        typeRelations={typeRelations}
        existingNodes={dataset.nodes}
        initialParentId={addNodeParentId}
        onAddNode={handleAddNode}
      />
    </div>
  );
}

