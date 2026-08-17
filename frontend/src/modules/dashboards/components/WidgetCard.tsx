/**
 * WidgetCard — wrapper for every widget on the canvas.
 * Provides drag handle, title, context menu, selection border.
 * Reference: Databricks dashboard widget card with kebab menu.
 */

import { useState } from 'react';
import { MoreVertical, Copy, Trash2, GripVertical, Download } from 'lucide-react';
import { useDashboardStore } from '@/modules/dashboards/stores/dashboardStore';
import type { Widget } from '@/types/dashboard';

interface Props {
  widget: Widget;
  children: React.ReactNode;
}

export default function WidgetCard({ widget, children }: Props) {
  const { activeDashboard, editMode, selectedWidgetId, setSelectedWidget, deleteWidget, cloneWidget } = useDashboardStore();
  const [openMenu, setOpenMenu] = useState(false);
  const theme = activeDashboard?.settings?.theme;

  const isSelected = selectedWidgetId === widget.id;
  function stopDragPropagation(e: React.MouseEvent | React.TouchEvent) {
    e.stopPropagation();
  }

  const selectionBorderColor = theme?.selectionColor ?? '#2272B4';
  const customBorder = theme?.widgetBorder && theme.widgetBorder !== 'Auto' ? theme.widgetBorder : 'var(--color-border)';

  return (
    <div
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: theme?.widgetBg && theme.widgetBg !== 'Auto' ? theme.widgetBg : 'var(--color-surface)',
        borderRadius: theme?.cornerRadius !== undefined ? `${theme.cornerRadius}px` : 'var(--radius-lg)',
        border: isSelected && editMode
          ? `2px solid ${selectionBorderColor}`
          : `1px solid ${customBorder}`,
        overflow: 'visible',
        boxShadow: theme?.shadow !== undefined ? `0 ${theme.shadow}px ${theme.shadow * 2 + 1}px rgba(0,0,0,0.06)` : 'var(--shadow-sm)',
        transition: 'border-color 0.15s, background-color 0.15s',
        position: 'relative',
      }}
      onClick={() => editMode && setSelectedWidget(widget.id)}
    >
      {editMode && (
        <>
          <div className="widget-drag-handle" style={{
            position: 'absolute',
            top: 0,
            left: 24,
            right: 24,
            height: 8,
            cursor: 'grab',
            zIndex: 5,
          }} />
          <div className="widget-drag-handle" style={{
            position: 'absolute',
            bottom: 0,
            left: 24,
            right: 24,
            height: 8,
            cursor: 'grab',
            zIndex: 5,
          }} />
          <div className="widget-drag-handle" style={{
            position: 'absolute',
            left: 0,
            top: 24,
            bottom: 24,
            width: 8,
            cursor: 'grab',
            zIndex: 5,
          }} />
          <div className="widget-drag-handle" style={{
            position: 'absolute',
            right: 0,
            top: 24,
            bottom: 24,
            width: 8,
            cursor: 'grab',
            zIndex: 5,
          }} />
        </>
      )}

      {/* Card header */}
      {(editMode || (widget.title && widget.title.trim() !== '')) && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          padding: '6px 10px 4px',
          flexShrink: 0,
          minHeight: 30,
        }}>
          {/* Drag handle — only in edit mode */}
          {editMode && (
            <div
              className="widget-drag-handle"
              style={{
                cursor: 'grab',
                color: 'var(--color-text-subtle)',
                display: 'flex',
                alignItems: 'center',
                flexShrink: 0,
              }}
            >
              <GripVertical size={13} />
            </div>
          )}

          {/* Title */}
          <span style={{
            fontSize: '0.78rem',
            fontWeight: 600,
            color: 'var(--color-text)',
            flex: 1,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            textAlign: theme?.titleAlignment ?? 'left',
          }}>
            {widget.title ?? ''}
          </span>

          {/* Context menu */}
          {editMode && (
            <div style={{ position: 'relative', flexShrink: 0 }} onClick={(e) => e.stopPropagation()}>
              <button
                className="btn-icon"
                style={{ opacity: 0.5, padding: '2px' }}
                onClick={() => setOpenMenu(!openMenu)}
              >
                <MoreVertical size={13} />
              </button>
              {openMenu && (
                <div className="dropdown-menu" style={{ right: 0, top: 26, minWidth: 140, zIndex: 300 }}>
                  <button className="dropdown-item" onClick={() => { setOpenMenu(false); cloneWidget(widget.id); }}>
                    <Copy size={12} style={{ marginRight: 6 }} /> Clone widget
                  </button>
                  <button className="dropdown-item" onClick={() => { setOpenMenu(false); }}>
                    <Download size={12} style={{ marginRight: 6 }} /> Download PNG
                  </button>
                  <div className="dropdown-divider" />
                  <button className="dropdown-item dropdown-item-danger" onClick={() => { setOpenMenu(false); deleteWidget(widget.id); }}>
                    <Trash2 size={12} style={{ marginRight: 6 }} /> Delete
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Widget content */}
      <div
        className="widget-content-interactive"
        style={{
          flex: 1,
          overflow: 'hidden',
          position: 'relative',
          borderRadius: theme?.cornerRadius !== undefined ? `0 0 ${theme.cornerRadius}px ${theme.cornerRadius}px` : '0 0 var(--radius-lg) var(--radius-lg)',
          padding: theme?.padding !== undefined ? `${theme.padding}px` : undefined,
        }}
        onMouseDown={stopDragPropagation}
        onTouchStart={stopDragPropagation}
        onPointerDown={stopDragPropagation as any}
      >
        {children}
      </div>

      {editMode && (
        <style>{`
          .react-resizable-handle {
            background-image: none !important;
            opacity: 1;
          }
          .react-resizable-handle::after {
            content: '';
            position: absolute;
            border: 2px solid #1b6ef3;
            background: #fff;
            border-radius: 999px;
            box-sizing: border-box;
          }
          .react-resizable-handle-n,
          .react-resizable-handle-s {
            left: 50%;
            transform: translateX(-50%);
            width: 34px !important;
            height: 14px !important;
            z-index: 8;
          }
          .react-resizable-handle-n { top: -8px; cursor: ns-resize !important; }
          .react-resizable-handle-s { bottom: -8px; cursor: ns-resize !important; }
          .react-resizable-handle-n::after,
          .react-resizable-handle-s::after {
            width: 34px;
            height: 12px;
            left: 0;
            top: 0;
          }
          .react-resizable-handle-e,
          .react-resizable-handle-w {
            top: 50%;
            transform: translateY(-50%);
            width: 14px !important;
            height: 34px !important;
            z-index: 8;
          }
          .react-resizable-handle-e { right: -8px; cursor: ew-resize !important; }
          .react-resizable-handle-w { left: -8px; cursor: ew-resize !important; }
          .react-resizable-handle-e::after,
          .react-resizable-handle-w::after {
            width: 12px;
            height: 34px;
            left: 0;
            top: 0;
          }
          .react-resizable-handle-ne,
          .react-resizable-handle-nw,
          .react-resizable-handle-se,
          .react-resizable-handle-sw {
            width: 14px !important;
            height: 14px !important;
            z-index: 8;
          }
          .react-resizable-handle-ne { top: -8px; right: -8px; cursor: nesw-resize !important; }
          .react-resizable-handle-nw { top: -8px; left: -8px; cursor: nwse-resize !important; }
          .react-resizable-handle-se { bottom: -8px; right: -8px; cursor: nwse-resize !important; }
          .react-resizable-handle-sw { bottom: -8px; left: -8px; cursor: nesw-resize !important; }
          .react-resizable-handle-ne::after,
          .react-resizable-handle-nw::after,
          .react-resizable-handle-se::after,
          .react-resizable-handle-sw::after {
            width: 12px;
            height: 12px;
            left: 1px;
            top: 1px;
          }
        `}</style>
      )}
    </div>
  );
}

