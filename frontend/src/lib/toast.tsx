/**
 * Lightweight zero-dependency toast system.
 *
 * Usage:
 *   import { useToast } from '@/lib/toast';
 *   const toast = useToast();
 *   toast.success('Saved!');
 *   toast.error('Something went wrong');
 *   toast.info('Loading…');
 *
 * Mount <ToastProvider> once at the root (App.tsx).
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import { createPortal } from 'react-dom';
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react';

// ── Types ─────────────────────────────────────────────────────────────────────

type ToastVariant = 'success' | 'error' | 'info';

interface Toast {
  id: string;
  message: string;
  variant: ToastVariant;
}

interface ToastAPI {
  success: (msg: string) => void;
  error: (msg: string) => void;
  info: (msg: string) => void;
}

// ── Context ───────────────────────────────────────────────────────────────────

const ToastContext = createContext<ToastAPI | null>(null);

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useToast(): ToastAPI {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>');
  return ctx;
}

// ── Single toast item ─────────────────────────────────────────────────────────

const COLORS: Record<ToastVariant, { bg: string; border: string; text: string; icon: string }> = {
  success: { bg: 'rgba(40,167,69,0.08)', border: 'rgba(40,167,69,0.35)', text: '#28A745', icon: '#28A745' },
  error:   { bg: 'rgba(239,68,68,0.08)', border: 'rgba(239,68,68,0.35)', text: 'var(--color-danger)', icon: 'var(--color-danger)' },
  info:    { bg: 'rgba(27,110,243,0.07)', border: 'rgba(27,110,243,0.25)', text: '#1B6EF3', icon: '#1B6EF3' },
};

const ICONS: Record<ToastVariant, React.ReactNode> = {
  success: <CheckCircle2 size={15} />,
  error:   <AlertCircle size={15} />,
  info:    <Info size={15} />,
};

const AUTO_DISMISS_MS = 4500;

function getAutoDismissMs(message: string): number {
  if (message.length > 1200) return 12000;
  if (message.length > 600) return 9000;
  return AUTO_DISMISS_MS;
}

function ToastItem({
  toast,
  onDismiss,
}: {
  toast: Toast;
  onDismiss: (id: string) => void;
}) {
  const [visible, setVisible] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  // Slide in
  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 10);
    return () => clearTimeout(t);
  }, []);

  // Auto-dismiss
  useEffect(() => {
    const dismissAfter = getAutoDismissMs(toast.message);
    timerRef.current = setTimeout(() => {
      setVisible(false);
      setTimeout(() => onDismiss(toast.id), 300);
    }, dismissAfter);
    return () => clearTimeout(timerRef.current);
  }, [toast.id, toast.message, onDismiss]);

  const c = COLORS[toast.variant];

  return (
    <div
      role="alert"
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 10,
        padding: '0.7rem 0.9rem',
        borderRadius: 6,
        background: c.bg,
        border: `1px solid ${c.border}`,
        boxShadow: '0 4px 16px rgba(0,0,0,0.14)',
        color: c.text,
        fontSize: '0.875rem',
        width: 'min(30rem, calc(100vw - 2rem))',
        maxWidth: 'calc(100vw - 2rem)',
        minWidth: 'min(16.25rem, calc(100vw - 2rem))',
        maxHeight: 'min(60vh, 28rem)',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        overflow: 'hidden',
        backdropFilter: 'blur(8px)',
        transform: visible ? 'translateX(0)' : 'translateX(110%)',
        opacity: visible ? 1 : 0,
        transition: 'transform 0.28s cubic-bezier(0.22,1,0.36,1), opacity 0.28s ease',
        pointerEvents: 'auto',
      }}
    >
      <span style={{ color: c.icon, flexShrink: 0, marginTop: 1 }}>{ICONS[toast.variant]}</span>
      <span
        style={{
          flex: 1,
          lineHeight: 1.45,
          minWidth: 0,
          maxHeight: 'calc(min(60vh, 28rem) - 1.4rem)',
          overflowY: 'auto',
          overflowX: 'hidden',
          paddingRight: '0.2rem',
        }}
      >
        {toast.message}
      </span>
      <button
        type="button"
        onClick={() => {
          setVisible(false);
          setTimeout(() => onDismiss(toast.id), 300);
        }}
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          color: c.text,
          opacity: 0.6,
          padding: 0,
          display: 'flex',
          flexShrink: 0,
          marginTop: 1,
        }}
        aria-label="Dismiss"
      >
        <X size={13} />
      </button>
    </div>
  );
}

// ── Provider ──────────────────────────────────────────────────────────────────

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const add = useCallback((message: string, variant: ToastVariant) => {
    const id = `${Date.now()}-${Math.random()}`;
    setToasts((prev) => [...prev, { id, message, variant }]);
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const api: ToastAPI = {
    success: (msg) => add(msg, 'success'),
    error:   (msg) => add(msg, 'error'),
    info:    (msg) => add(msg, 'info'),
  };

  return (
    <ToastContext.Provider value={api}>
      {children}
      {createPortal(
        <div
          style={{
            position: 'fixed',
            bottom: 24,
            right: 24,
            zIndex: 9999,
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
            pointerEvents: 'none',
            width: 'min(30rem, calc(100vw - 2rem))',
            maxWidth: 'calc(100vw - 2rem)',
          }}
        >
          {toasts.map((t) => (
            <ToastItem key={t.id} toast={t} onDismiss={dismiss} />
          ))}
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  );
}

// ── Error extractor (shared utility) ─────────────────────────────────────────

export function extractApiError(err: unknown): string {
  const e = err as any;
  const detail = e?.response?.data?.detail;
  if (!detail) return e?.message ?? 'An unexpected error occurred.';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d: any) => {
        if (typeof d === 'string') return d;
        const loc = Array.isArray(d.loc)
          ? d.loc.filter((s: any) => s !== 'body').join(' → ')
          : '';
        const msg: string = d.msg ?? JSON.stringify(d);
        return loc ? `${loc}: ${msg}` : msg;
      })
      .join('\n');
  }
  try { return JSON.stringify(detail, null, 2); } catch { return String(detail); }
}