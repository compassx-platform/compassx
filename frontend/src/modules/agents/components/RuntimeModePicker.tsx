import React, { useEffect, useRef, useState } from 'react';
import { ChevronDown } from 'lucide-react';

export type RuntimeMode = 'agent' | 'ask' | 'plan' | 'debug';

const MODES: { id: RuntimeMode; label: string }[] = [
  { id: 'agent', label: 'Agent' },
  { id: 'ask', label: 'Ask' },
  { id: 'plan', label: 'Plan' },
  { id: 'debug', label: 'Debug' },
];

const MODE_KEY = 'agent-runtime-mode';

export function readRuntimeMode(): RuntimeMode {
  try {
    const value = sessionStorage.getItem(MODE_KEY);
    if (value === 'ask' || value === 'plan' || value === 'debug' || value === 'agent') return value;
  } catch {
    /* sessionStorage can be unavailable */
  }
  return 'agent';
}

export function writeRuntimeMode(mode: RuntimeMode) {
  try {
    sessionStorage.setItem(MODE_KEY, mode);
  } catch {
    /* sessionStorage can be unavailable */
  }
}

export function rememberTurnMode(sessionId: string, mode: RuntimeMode = readRuntimeMode()) {
  try {
    sessionStorage.setItem(`agent-runtime-turn-mode:${sessionId}`, mode);
  } catch {
    /* sessionStorage can be unavailable */
  }
}

export function takeTurnMode(sessionId: string): RuntimeMode | undefined {
  try {
    const key = `agent-runtime-turn-mode:${sessionId}`;
    const value = sessionStorage.getItem(key);
    sessionStorage.removeItem(key);
    if (value === 'ask' || value === 'plan' || value === 'debug' || value === 'agent') return value;
  } catch {
    /* sessionStorage can be unavailable */
  }
  return undefined;
}

export function RuntimeModePicker({ upward = false }: { upward?: boolean }) {
  const [mode, setMode] = useState<RuntimeMode>(readRuntimeMode);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLSpanElement>(null);
  const label = MODES.find((item) => item.id === mode)?.label || 'Agent';

  useEffect(() => {
    if (!open) return undefined;
    const close = (event: MouseEvent) => {
      const target = event.target;
      if (target instanceof Node && rootRef.current?.contains(target)) return;
      setOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [open]);

  return (
    <span ref={rootRef} style={{ position: 'relative' }}>
      <button
        type="button"
        aria-label="Select mode"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 4,
          border: 'none',
          background: open ? '#f4f4f5' : 'transparent',
          color: '#3f3f46',
          borderRadius: 6,
          padding: '4px 6px',
          fontSize: 13,
          cursor: 'pointer',
        }}
      >
        <span>{label}</span>
        <ChevronDown size={13} strokeWidth={1.75} />
      </button>
      {open && (
        <div
          role="menu"
          style={{
            position: 'absolute',
            top: upward ? undefined : '100%',
            bottom: upward ? '100%' : undefined,
            left: 0,
            zIndex: 30,
            minWidth: 140,
            marginTop: upward ? undefined : 6,
            marginBottom: upward ? 6 : undefined,
            background: '#ffffff',
            border: '1px solid #e4e4e7',
            borderRadius: 10,
            boxShadow: '0 12px 32px rgba(15, 23, 42, 0.12)',
            padding: 4,
          }}
        >
          {MODES.map((item) => (
            <button
              key={item.id}
              type="button"
              role="menuitem"
              onClick={() => {
                setMode(item.id);
                writeRuntimeMode(item.id);
                setOpen(false);
              }}
              style={{
                display: 'block',
                width: '100%',
                textAlign: 'left',
                border: 'none',
                background: item.id === mode ? '#f4f4f5' : 'transparent',
                color: '#18181b',
                borderRadius: 6,
                padding: '7px 8px',
                fontSize: 13,
                cursor: 'pointer',
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </span>
  );
}
