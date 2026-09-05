import React, { useState } from 'react';
import {
  X,
  Copy,
  Check,
  ExternalLink,
  Layers,
  Hexagon,
  Square,
  Circle,
  Hash,
  ArrowDownLeft,
  ArrowUpRight,
  FileText,
  Tag,
  Sparkles,
} from 'lucide-react';
import { LayoutNode, OntologyKind } from '../types/ontology';

interface OntologySideDrawerProps {
  node: LayoutNode | null;
  onClose: () => void;
  onSelectNode: (nodeId: string) => void;
  onIsolateArea: (nodeId: string) => void;
}

export const OntologySideDrawer: React.FC<OntologySideDrawerProps> = ({
  node,
  onClose,
  onSelectNode,
  onIsolateArea,
}) => {
  const [copied, setCopied] = useState(false);

  if (!node) return null;

  const handleCopyPrompt = () => {
    const aiContext = `---
concept: "${node.title}"
kind: "${node.kind}"
slug: "${node.id}"
${node.parentId ? `parent: "${node.parentId}"\n` : ''}description: "${node.description || ''}"
${node.path ? `path: "${node.path}"\n` : ''}direct_children: ${node.directChildCount || 0}
total_descendants: ${node.totalDescendantCount || 0}
inbound_uses: [${(node.inboundDependencies || []).map(d => `"${d}"`).join(', ')}]
outbound_needs: [${(node.outboundDependencies || []).map(d => `"${d}"`).join(', ')}]
---

# ${node.title} (${node.kind})
${node.description || ''}
`;
    navigator.clipboard.writeText(aiContext);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getKindBadge = (kind: OntologyKind) => {
    switch (kind) {
      case 'project':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-[#f59e0b]/15 text-[#fbbf24] border border-[#f59e0b]/30">
            <Hexagon size={12} /> Project Root
          </span>
        );
      case 'domain':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-[#6366f1]/15 text-[#a5b4fc] border border-[#6366f1]/30">
            <Square size={12} /> Domain Chip
          </span>
        );
      case 'capability':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-[#38bdf8]/15 text-[#7dd3fc] border border-[#38bdf8]/30">
            <Circle size={12} /> Capability Disc
          </span>
        );
      case 'element':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-[#94a3b8]/15 text-[#cbd5e1] border border-[#94a3b8]/30">
            <Hash size={12} /> Element Pad
          </span>
        );
    }
  };

  return (
    <div className="ontology-side-drawer absolute right-4 top-16 bottom-4 w-96 max-w-[calc(100vw-2rem)] z-30 flex flex-col rounded-2xl bg-[#0f121d]/90 backdrop-blur-xl border border-[#23293d] shadow-2xl overflow-hidden text-[#e2e8f0]">
      {/* Header */}
      <div className="p-5 border-b border-[#23293d] flex items-start justify-between gap-3 bg-[#141827]/60">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            {getKindBadge(node.kind)}
            {node.status && (
              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-[#1e2438] text-[#94a3b8]">
                {node.status}
              </span>
            )}
          </div>
          <h2 className="text-lg font-bold text-white tracking-tight leading-snug break-words">
            {node.title}
          </h2>
          <p className="text-xs font-mono text-[#64748b] mt-0.5 truncate">
            {node.id}
          </p>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg hover:bg-[#20273c] text-[#94a3b8] hover:text-white transition-colors"
          title="Close drawer"
        >
          <X size={16} />
        </button>
      </div>

      {/* Body Content */}
      <div className="flex-1 overflow-y-auto p-5 space-y-5 text-sm custom-scrollbar">
        {/* Description */}
        {node.description && (
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-[#94a3b8] mb-1.5">
              Description
            </h4>
            <p className="text-[#cbd5e1] leading-relaxed text-[13px] bg-[#141724] p-3 rounded-xl border border-[#20263c]">
              {node.description}
            </p>
          </div>
        )}

        {/* Dual Channel Metrics Cards */}
        <div className="grid grid-cols-2 gap-2.5">
          <div className="p-3 rounded-xl bg-[#141724] border border-[#20263c]">
            <div className="text-[11px] font-medium text-[#94a3b8] mb-1 flex items-center justify-between">
              <span>Direct Children</span>
              <span className="text-[9px] text-[#64748b]">Glance (Size)</span>
            </div>
            <div className="text-xl font-bold text-[#818cf8]">
              {node.directChildCount || 0}
            </div>
          </div>
          <div className="p-3 rounded-xl bg-[#141724] border border-[#20263c]">
            <div className="text-[11px] font-medium text-[#94a3b8] mb-1 flex items-center justify-between">
              <span>Descendants</span>
              <span className="text-[9px] text-[#64748b]">Depth (Number)</span>
            </div>
            <div className="text-xl font-bold text-[#fbbf24]">
              {node.totalDescendantCount || 0}
            </div>
          </div>
        </div>

        {/* Inbound & Outbound Connections */}
        <div className="space-y-3">
          {/* Outbound Needs */}
          <div>
            <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-[#94a3b8] mb-2">
              <span className="flex items-center gap-1">
                <ArrowUpRight size={13} className="text-[#818cf8]" /> Needs (Requires)
              </span>
              <span className="font-mono text-[11px] text-[#64748b]">
                {(node.outboundDependencies || []).length}
              </span>
            </div>
            {(node.outboundDependencies || []).length === 0 ? (
              <p className="text-xs text-[#64748b] italic">No direct outbound requirements.</p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {(node.outboundDependencies || []).map(depId => (
                  <button
                    key={depId}
                    onClick={() => onSelectNode(depId)}
                    className="px-2.5 py-1 text-xs rounded-lg bg-[#181d2e] hover:bg-[#252d47] text-[#93c5fd] border border-[#283250] transition-colors truncate max-w-full"
                  >
                    {depId.split('/').pop()}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Inbound Uses */}
          <div>
            <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-[#94a3b8] mb-2">
              <span className="flex items-center gap-1">
                <ArrowDownLeft size={13} className="text-[#38bdf8]" /> Uses (Depended On By)
              </span>
              <span className="font-mono text-[11px] text-[#64748b]">
                {(node.inboundDependencies || []).length}
              </span>
            </div>
            {(node.inboundDependencies || []).length === 0 ? (
              <p className="text-xs text-[#64748b] italic">No inbound dependents recorded.</p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {(node.inboundDependencies || []).map(depId => (
                  <button
                    key={depId}
                    onClick={() => onSelectNode(depId)}
                    className="px-2.5 py-1 text-xs rounded-lg bg-[#181d2e] hover:bg-[#252d47] text-[#a5b4fc] border border-[#283250] transition-colors truncate max-w-full"
                  >
                    {depId.split('/').pop()}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Source File Link */}
        {node.path && (
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-[#94a3b8] mb-1.5 flex items-center gap-1">
              <FileText size={13} /> Source Document
            </h4>
            <div className="text-xs font-mono text-[#cbd5e1] bg-[#141724] p-2.5 rounded-xl border border-[#20263c] flex items-center justify-between">
              <span className="truncate">{node.path}</span>
            </div>
          </div>
        )}

        {/* Tags */}
        {node.tags && node.tags.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-[#94a3b8] mb-1.5 flex items-center gap-1">
              <Tag size={13} /> Semantic Tags
            </h4>
            <div className="flex flex-wrap gap-1.5">
              {node.tags.map(t => (
                <span
                  key={t}
                  className="px-2 py-0.5 text-[11px] rounded-md bg-[#1b2133] text-[#94a3b8] border border-[#28304a]"
                >
                  #{t}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Footer Actions */}
      <div className="p-4 border-t border-[#23293d] bg-[#141827]/70 flex items-center gap-2">
        <button
          onClick={handleCopyPrompt}
          className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-xl bg-[#6366f1] hover:bg-[#4f46e5] text-white text-xs font-semibold shadow-lg shadow-indigo-500/20 transition-all active:scale-[0.98]"
        >
          {copied ? <Check size={14} /> : <Sparkles size={14} />}
          <span>{copied ? 'Copied AI Context!' : 'Copy for AI Agent'}</span>
        </button>

        <button
          onClick={() => onIsolateArea(node.id)}
          className="px-3 py-2 rounded-xl bg-[#1e2438] hover:bg-[#2a334d] text-[#cbd5e1] text-xs font-medium border border-[#333d5c] transition-colors"
          title="Isolate and view only this subtree"
        >
          View Area
        </button>
      </div>
    </div>
  );
};
