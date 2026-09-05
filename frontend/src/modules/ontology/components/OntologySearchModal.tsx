import React, { useState, useEffect, useRef } from 'react';
import { Search, X, Hexagon, Square, Circle, Hash, ArrowRight } from 'lucide-react';
import { LayoutNode, OntologyKind } from '../types/ontology';

interface OntologySearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  nodes: LayoutNode[];
  onSelectNode: (nodeId: string) => void;
}

export const OntologySearchModal: React.FC<OntologySearchModalProps> = ({
  isOpen,
  onClose,
  nodes,
  onSelectNode,
}) => {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  // Global Ctrl+K / Cmd+K listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (isOpen) onClose();
      } else if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const filteredNodes = nodes.filter(n => {
    const q = query.toLowerCase().trim();
    if (!q) return true;
    return (
      n.title.toLowerCase().includes(q) ||
      n.id.toLowerCase().includes(q) ||
      n.kind.toLowerCase().includes(q) ||
      (n.tags && n.tags.some(t => t.toLowerCase().includes(q))) ||
      (n.description && n.description.toLowerCase().includes(q))
    );
  }).slice(0, 10);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => (prev + 1) % Math.max(1, filteredNodes.length));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => (prev - 1 + filteredNodes.length) % Math.max(1, filteredNodes.length));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filteredNodes[selectedIndex]) {
        onSelectNode(filteredNodes[selectedIndex].id);
        onClose();
      }
    }
  };

  const getKindIcon = (kind: OntologyKind) => {
    switch (kind) {
      case 'project':
        return <Hexagon size={14} className="text-[#fbbf24]" />;
      case 'domain':
        return <Square size={14} className="text-[#a5b4fc]" />;
      case 'capability':
        return <Circle size={14} className="text-[#7dd3fc]" />;
      case 'element':
        return <Hash size={14} className="text-[#94a3b8]" />;
    }
  };

  return (
    <div className="ontology-modal-overlay fixed inset-0 z-50 flex items-start justify-center pt-24 px-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="ontology-modal-content w-full max-w-xl rounded-2xl bg-[#0f121d] border border-[#262e45] shadow-2xl overflow-hidden text-[#e2e8f0]">
        {/* Search Input */}
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-[#23293d] bg-[#141827]">
          <Search size={18} className="text-[#818cf8]" />
          <input
            ref={inputRef}
            value={query}
            onChange={e => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            onKeyDown={handleKeyDown}
            placeholder="Search concepts, domains, capabilities, tags..."
            className="flex-1 bg-transparent text-sm text-white placeholder-[#64748b] focus:outline-none"
          />
          <kbd className="px-2 py-0.5 text-[10px] font-mono rounded bg-[#1e2438] text-[#94a3b8] border border-[#334155]/60">
            ESC
          </kbd>
          <button onClick={onClose} className="p-1 rounded hover:bg-[#20273c] text-[#94a3b8] hover:text-white">
            <X size={16} />
          </button>
        </div>

        {/* Results List */}
        <div className="max-h-80 overflow-y-auto p-2 space-y-1 custom-scrollbar">
          {filteredNodes.length === 0 ? (
            <div className="p-8 text-center text-xs text-[#64748b]">
              No ontology nodes matching "{query}"
            </div>
          ) : (
            filteredNodes.map((n, idx) => {
              const isSelected = idx === selectedIndex;
              return (
                <div
                  key={n.id}
                  onClick={() => {
                    onSelectNode(n.id);
                    onClose();
                  }}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`flex items-center justify-between gap-3 px-3 py-2.5 rounded-xl cursor-pointer transition-colors ${
                    isSelected ? 'bg-[#1e2538] text-white border border-[#3b476b]' : 'hover:bg-[#141827] text-[#cbd5e1]'
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="p-1.5 rounded-lg bg-[#141724]">
                      {getKindIcon(n.kind)}
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-semibold truncate leading-tight">
                        {n.title}
                      </div>
                      <div className="text-[11px] font-mono text-[#64748b] truncate">
                        {n.id}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-[#141724] text-[#94a3b8] border border-[#20263c]">
                      {n.kind}
                    </span>
                    {isSelected && <ArrowRight size={14} className="text-[#818cf8]" />}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer info */}
        <div className="px-4 py-2 bg-[#090b12] border-t border-[#1e2438] flex items-center justify-between text-[11px] text-[#64748b]">
          <span>Navigate with <kbd className="font-mono bg-[#141724] px-1 py-0.5 rounded">↑</kbd> <kbd className="font-mono bg-[#141724] px-1 py-0.5 rounded">↓</kbd></span>
          <span>Press <kbd className="font-mono bg-[#141724] px-1 py-0.5 rounded">↵</kbd> to select</span>
        </div>
      </div>
    </div>
  );
};
