import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Settings, X } from 'lucide-react';

interface OntologyConfigMenuProps {
  themeMode?: 'dark' | 'light';
  onToggleTheme?: () => void;
  view3d?: boolean;
  onToggle3D?: () => void;
  mapArrangement?: string;
  onToggleArrangement?: () => void;
  expandedAll?: boolean;
  onToggleExpandAll?: () => void;
  onAutoArrange?: () => void;
  onFitView?: () => void;
  onOpenYamlEditor?: () => void;
  onResetDefaultData?: () => void;
  nodeCount?: number;
  edgeCount?: number;
}

export type ConfigTab = 'about' | 'sources' | 'instructions' | 'examples';

export const OntologyConfigMenu: React.FC<OntologyConfigMenuProps> = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<ConfigTab>('examples');

  // Default to a wide panel, adjustable via left-border dragging
  const [panelWidth, setPanelWidth] = useState(() => {
    if (typeof window !== 'undefined') {
      return Math.min(520, window.innerWidth - 40);
    }
    return 480;
  });
  const [isDragging, setIsDragging] = useState(false);
  const isDraggingRef = useRef(false);
  const panelRef = useRef<HTMLDivElement>(null);

  // Resize handler by dragging left border
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isDraggingRef.current = true;
    setIsDragging(true);
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'ew-resize';

    const handleMouseMove = (moveEvent: MouseEvent) => {
      if (!isDraggingRef.current) return;
      const rightEdge = window.innerWidth - 10;
      const newWidth = rightEdge - moveEvent.clientX;
      const minWidth = 280;
      const maxWidth = window.innerWidth - 24;
      setPanelWidth(Math.max(minWidth, Math.min(maxWidth, newWidth)));
    };

    const handleMouseUp = () => {
      isDraggingRef.current = false;
      setIsDragging(false);
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  }, []);

  // Close on Escape key
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  const tabs: { id: ConfigTab; label: string }[] = [
    { id: 'about', label: 'About' },
    { id: 'sources', label: 'Sources' },
    { id: 'instructions', label: 'Instructions' },
    { id: 'examples', label: 'Examples' },
  ];

  return (
    <>
      {/* Top Right Configure Trigger Button */}
      <div className={`ontology-config-container ${isOpen ? 'active' : ''}`}>
        <button
          onClick={() => setIsOpen(prev => !prev)}
          className="ontology-toolbar-btn"
          title="Toggle Configuration Panel"
        >
          <Settings
            size={13}
            className={`text-[#818cf8] transition-transform duration-300 ${isOpen ? 'rotate-90' : ''}`}
          />
          <span>Configure</span>
        </button>
      </div>

      {/* Drag-resizable Configuration Panel Styled from Reference */}
      {isOpen && (
        <div
          ref={panelRef}
          className="ontology-config-panel animate-in fade-in slide-in-from-right-4 duration-150"
          style={{ width: `${panelWidth}px`, maxWidth: 'calc(100vw - 20px)' }}
        >
          {/* Left-edge Drag Resize Handle */}
          <div
            onMouseDown={handleMouseDown}
            className={`ontology-config-resize-handle ${isDragging ? 'dragging' : ''}`}
            title="Drag to resize panel width"
          />

          {/* Tabbed Header Matching Reference Image */}
          <div className="ontology-config-header-tabs select-none">
            <div className="flex items-center gap-1">
              {tabs.map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`ontology-config-tab-btn ${activeTab === tab.id ? 'active' : ''}`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Close Button */}
            <button
              onClick={() => setIsOpen(false)}
              className="p-1.5 rounded-full text-[#94a3b8] hover:text-[#0f172a] dark:hover:text-white hover:bg-[#f1f5f9] dark:hover:bg-[#20273c] transition-colors"
              title="Close panel"
            >
              <X size={15} />
            </button>
          </div>

          {/* Clean Content Area (No Dummy Elements) */}
          <div className="flex-1 w-full p-6 overflow-y-auto min-h-0" />
        </div>
      )}
    </>
  );
};
