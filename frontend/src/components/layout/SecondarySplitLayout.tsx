import { type PointerEvent as ReactPointerEvent, type ReactNode, useEffect, useRef, useState } from 'react';

type SecondarySplitLayoutProps = {
  storageKey: string;
  sidebarHeader?: ReactNode;
  sidebar: ReactNode;
  mainHeader?: ReactNode;
  children: ReactNode;
  className?: string;
  defaultSidebarWidth?: number;
  minSidebarWidth?: number;
  maxSidebarWidth?: number;
};

function clampWidth(width: number, minWidth: number, maxWidth: number) {
  return Math.min(Math.max(width, minWidth), maxWidth);
}

export function SecondarySplitLayout({
  storageKey,
  sidebarHeader,
  sidebar,
  mainHeader,
  children,
  className,
  defaultSidebarWidth = 440,
  minSidebarWidth = 280,
  maxSidebarWidth = 620,
}: SecondarySplitLayoutProps) {
  const [sidebarWidth, setSidebarWidth] = useState(defaultSidebarWidth);
  const startX = useRef(0);
  const startWidth = useRef(defaultSidebarWidth);
  const currentWidth = useRef(defaultSidebarWidth);

  useEffect(() => {
    const storedWidth = Number(window.localStorage.getItem(storageKey));
    if (Number.isFinite(storedWidth) && storedWidth > 0) {
      const nextWidth = clampWidth(storedWidth, minSidebarWidth, maxSidebarWidth);
      currentWidth.current = nextWidth;
      setSidebarWidth(nextWidth);
    }
  }, [maxSidebarWidth, minSidebarWidth, storageKey]);

  function handlePointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    event.preventDefault();
    startX.current = event.clientX;
    startWidth.current = sidebarWidth;

    const handlePointerMove = (moveEvent: PointerEvent) => {
      const nextWidth = clampWidth(
        startWidth.current + moveEvent.clientX - startX.current,
        minSidebarWidth,
        maxSidebarWidth,
      );
      currentWidth.current = nextWidth;
      setSidebarWidth(nextWidth);
    };

    const handlePointerUp = () => {
      window.localStorage.setItem(storageKey, String(currentWidth.current));
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
    };

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
  }

  return (
    <div className={`secondary-split-layout${className ? ` ${className}` : ''}`}>
      <aside className="secondary-split-sidebar" style={{ width: sidebarWidth }}>
        {sidebarHeader && <div className="secondary-split-sidebar-header">{sidebarHeader}</div>}
        <div className="secondary-split-sidebar-body">{sidebar}</div>
        <div
          className="secondary-split-resize-handle"
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize secondary sidebar"
          onPointerDown={handlePointerDown}
        />
      </aside>
      <main className="secondary-split-main">
        {mainHeader && <div className="secondary-split-main-header">{mainHeader}</div>}
        <div className="secondary-split-main-body">{children}</div>
      </main>
    </div>
  );
}
