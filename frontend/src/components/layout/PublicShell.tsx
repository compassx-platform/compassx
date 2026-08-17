/**
 * PublicShell — bare layout for user-facing pages.
 * No sidebar, no nav, no chrome. Just the page.
 */
import { Outlet } from 'react-router-dom';

export default function PublicShell() {
  return (
    <div style={{ minHeight: '100vh', background: 'var(--color-surface)' }}>
      <div style={{ padding: '1.75rem 2rem' }}>
        <Outlet />
      </div>
    </div>
  );
}