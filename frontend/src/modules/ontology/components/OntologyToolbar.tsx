import React from 'react';
import {
  Search,
  Maximize2,
  Minimize2,
  RotateCcw,
  Box,
  FileCode,
  Scan,
  Layers,
} from 'lucide-react';
import type { MapArrangement } from '../shared/appearance-preferences';

interface OntologyToolbarProps {
  expandedAll: boolean;
  onToggleExpandAll: () => void;
  onOpenSearch: () => void;
  onOpenYamlEditor: () => void;
  onAutoArrange: () => void;
  onFitView: () => void;
  view3d: boolean;
  mapArrangement: MapArrangement;
  onToggle3D: () => void;
  onToggleArrangement: () => void;
}

export const OntologyToolbar: React.FC<OntologyToolbarProps> = ({
  expandedAll,
  onToggleExpandAll,
  onOpenSearch,
  onOpenYamlEditor,
  onAutoArrange,
  onFitView,
  view3d,
  mapArrangement,
  onToggle3D,
  onToggleArrangement,
}) => {
  return (
    <div className="ontology-toolbar-container absolute top-4 left-1/2 -translate-x-1/2 z-20 flex items-center gap-1.5 p-1.5 rounded-full bg-[#131722]/85 backdrop-blur-md border border-[#2b334a]/80 shadow-2xl text-[#cbd5e1]">
      {/* Expand / Collapse All */}
      <button
        onClick={onToggleExpandAll}
        className="ontology-toolbar-btn flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium hover:bg-[#20273c] hover:text-white transition-colors"
        title="Toggle expand all child elements"
      >
        {expandedAll ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
        <span>{expandedAll ? 'Collapse all' : 'Expand all'}</span>
      </button>

      <div className="ontology-toolbar-divider w-[1px] h-4 bg-[#2e374f]" />

      {/* Auto Arrange */}
      <button
        onClick={onAutoArrange}
        className="ontology-toolbar-btn flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium hover:bg-[#20273c] hover:text-white transition-colors"
        title="Reset physics & auto arrange"
      >
        <RotateCcw size={13} />
        <span>Auto-arrange</span>
      </button>

      <div className="ontology-toolbar-divider w-[1px] h-4 bg-[#2e374f]" />

      {/* Fit View */}
      <button
        onClick={onFitView}
        className="ontology-toolbar-btn flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium hover:bg-[#20273c] hover:text-white transition-colors"
        title="Fit map to visible screen"
      >
        <Scan size={13} />
        <span>Fit view</span>
      </button>

      <div className="ontology-toolbar-divider w-[1px] h-4 bg-[#2e374f]" />

      {/* 3D Mode & Arrangement Toggle */}
      <div className="flex items-center gap-1">
        <button
          onClick={onToggle3D}
          className={`ontology-toolbar-btn flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
            view3d
              ? 'active bg-[#3b82f6]/20 text-[#93c5fd] border border-[#3b82f6]/40'
              : 'hover:bg-[#20273c] hover:text-white'
          }`}
          title="Toggle 2D Flat / 3D Mode"
        >
          <Box size={13} />
          <span>{view3d ? (mapArrangement === 'ownership' ? '3D Cone' : '3D Cloud') : '2D Map'}</span>
        </button>

        {view3d && (
          <button
            onClick={onToggleArrangement}
            className="ontology-toolbar-btn flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-mono bg-[#1e2538] hover:bg-[#2b3452] text-[#cbd5e1] border border-[#334155]/60 transition-colors"
            title="Switch 3D Tree (Ownership) vs 3D Force (Coupling)"
          >
            <Layers size={11} />
            <span>{mapArrangement === 'ownership' ? 'Cone' : 'Cloud'}</span>
          </button>
        )}
      </div>

      <div className="ontology-toolbar-divider w-[1px] h-4 bg-[#2e374f]" />

      {/* Search Button with CTRL K badge */}
      <button
        onClick={onOpenSearch}
        className="ontology-toolbar-btn flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium hover:bg-[#20273c] hover:text-white transition-colors"
      >
        <Search size={13} className="text-[#94a3b8]" />
        <span>Search</span>
        <kbd className="ontology-kbd-badge px-1.5 py-0.5 text-[10px] font-mono tracking-wider rounded bg-[#1e2538] text-[#94a3b8] border border-[#334155]/60">
          CTRL K
        </kbd>
      </button>

      <div className="ontology-toolbar-divider w-[1px] h-4 bg-[#2e374f]" />

      {/* YAML Source Editor */}
      <button
        onClick={onOpenYamlEditor}
        className="ontology-toolbar-btn flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium hover:bg-[#20273c] hover:text-white transition-colors"
        title="View or upload custom YAML ontology"
      >
        <FileCode size={13} className="text-[#a5b4fc]" />
        <span>YAML</span>
      </button>
    </div>
  );
};

