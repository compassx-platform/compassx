import React, { useState } from 'react';
import { HelpCircle, ChevronDown, ChevronUp, Hexagon, Square, Circle, Hash } from 'lucide-react';

export const OntologyLegend: React.FC = () => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="ontology-legend-container absolute bottom-4 right-4 z-20 rounded-2xl bg-[#121624]/90 backdrop-blur-md border border-[#262e45]/80 shadow-2xl text-[#cbd5e1] overflow-hidden text-xs transition-all">
      <button
        onClick={() => setIsExpanded(prev => !prev)}
        className="w-full flex items-center justify-between gap-3 px-3.5 py-2.5 hover:bg-[#1a2033] transition-colors"
      >
        <div className="flex items-center gap-2 font-semibold text-white">
          <HelpCircle size={14} className="text-[#818cf8]" />
          <span>Visual Legend</span>
        </div>
        {isExpanded ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
      </button>

      {isExpanded && (
        <div className="p-3.5 pt-1 space-y-3 border-t border-[#20273c] w-64">
          {/* Node Shapes */}
          <div>
            <div className="text-[10px] uppercase font-semibold tracking-wider text-[#64748b] mb-1.5">
              1. Shapes = Semantic Kind
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <Hexagon size={13} className="text-[#fbbf24]" />
                <span className="font-medium text-white">Project:</span>
                <span className="text-[#94a3b8]">Hexagonal Plate</span>
              </div>
              <div className="flex items-center gap-2">
                <Square size={13} className="text-[#a5b4fc]" />
                <span className="font-medium text-white">Domain:</span>
                <span className="text-[#94a3b8]">IC Chip (with legs)</span>
              </div>
              <div className="flex items-center gap-2">
                <Circle size={13} className="text-[#7dd3fc]" />
                <span className="font-medium text-white">Capability:</span>
                <span className="text-[#94a3b8]">Smooth Disc</span>
              </div>
              <div className="flex items-center gap-2">
                <Hash size={13} className="text-[#94a3b8]" />
                <span className="font-medium text-white">Element:</span>
                <span className="text-[#94a3b8]">Via Pad (center hole)</span>
              </div>
            </div>
          </div>

          {/* Line Grammar */}
          <div>
            <div className="text-[10px] uppercase font-semibold tracking-wider text-[#64748b] mb-1.5">
              2. Line Grammar
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="w-4 h-[2px] bg-[#64748b] inline-block" />
                <span className="text-white">Solid:</span>
                <span className="text-[#94a3b8]">Containment</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-4 h-[2px] border-b-2 border-dashed border-[#818cf8] inline-block" />
                <span className="text-white">Tapered:</span>
                <span className="text-[#94a3b8]">Directed dependency</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-4 h-[1px] border-b border-dashed border-[#64748b] inline-block" />
                <span className="text-white">Uniform:</span>
                <span className="text-[#94a3b8]">Symmetric peer</span>
              </div>
            </div>
          </div>

          {/* Sizing & Numbers */}
          <div className="pt-1 border-t border-[#20273c] text-[11px] text-[#94a3b8] leading-tight">
            <span className="text-white font-medium">Node Size:</span> Direct children (max 1.4x).<br />
            <span className="text-white font-medium">Embossed Number:</span> Total descendants.
          </div>
        </div>
      )}
    </div>
  );
};
