import React, { useEffect, useState } from 'react';
import { X } from 'lucide-react';

type Box = { left: number; top: number; width: number; height: number };

export type BrowserTarget = {
  label: string;
  detail: string;
  box: Box;
};

export function BrowserAnnotate({
  viewRef,
  stageRef,
  pageWidth,
  pageHeight,
  onInspect,
  onSend,
  onExit,
}: {
  viewRef: React.RefObject<HTMLImageElement | null>;
  stageRef: React.RefObject<HTMLDivElement | null>;
  pageWidth: number;
  pageHeight: number;
  onInspect: (x: number, y: number) => Promise<BrowserTarget | null>;
  onSend: (box: Box, instruction: string) => Promise<void>;
  onExit: () => void;
}) {
  const [hover, setHover] = useState<BrowserTarget | null>(null);
  const [draftBox, setDraftBox] = useState<Box | null>(null);
  const [note, setNote] = useState<{ target: BrowserTarget; text: string } | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const drag = React.useRef<{ x: number; y: number; moved: boolean } | null>(null);
  const inspectSeq = React.useRef(0);
  const hoverAt = React.useRef(0);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      if (note) {
        setNote(null);
        return;
      }
      onExit();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [note, onExit]);

  const toPage = (clientX: number, clientY: number) => {
    const view = viewRef.current?.getBoundingClientRect();
    if (!view || !pageWidth || !pageHeight || view.width < 1 || view.height < 1) return null;
    return {
      x: ((clientX - view.left) / view.width) * pageWidth,
      y: ((clientY - view.top) / view.height) * pageHeight,
    };
  };

  const place = (box: Box): Box => {
    const stage = stageRef.current?.getBoundingClientRect();
    const view = viewRef.current?.getBoundingClientRect();
    if (!stage || !view || !pageWidth || !pageHeight) return box;
    const scaleX = view.width / pageWidth;
    const scaleY = view.height / pageHeight;
    return {
      left: view.left - stage.left + box.left * scaleX,
      top: view.top - stage.top + box.top * scaleY,
      width: box.width * scaleX,
      height: box.height * scaleY,
    };
  };

  const onPointerDown = (event: React.PointerEvent) => {
    if (note) return;
    const point = toPage(event.clientX, event.clientY);
    if (!point) return;
    drag.current = { x: point.x, y: point.y, moved: false };
    setDraftBox({ left: point.x, top: point.y, width: 0, height: 0 });
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const onPointerMove = (event: React.PointerEvent) => {
    const point = toPage(event.clientX, event.clientY);
    if (!point) return;
    if (drag.current) {
      const left = Math.min(drag.current.x, point.x);
      const top = Math.min(drag.current.y, point.y);
      const width = Math.abs(point.x - drag.current.x);
      const height = Math.abs(point.y - drag.current.y);
      if (width > 4 || height > 4) drag.current.moved = true;
      setDraftBox({ left, top, width, height });
      return;
    }
    if (Date.now() - hoverAt.current < 160) return;
    hoverAt.current = Date.now();
    const seq = ++inspectSeq.current;
    onInspect(point.x, point.y).then((target) => {
      if (seq === inspectSeq.current) setHover(target);
    }).catch(() => undefined);
  };

  const onPointerUp = (event: React.PointerEvent) => {
    const start = drag.current;
    drag.current = null;
    const point = toPage(event.clientX, event.clientY);
    if (!start || !point) return;
    if (start.moved) {
      const left = Math.min(start.x, point.x);
      const top = Math.min(start.y, point.y);
      const width = Math.abs(point.x - start.x);
      const height = Math.abs(point.y - start.y);
      setNote({
        target: {
          label: 'Area',
          detail: '',
          box: { left, top, width, height },
        },
        text: '',
      });
      setDraftBox(null);
      setHover(null);
      return;
    }
    onInspect(point.x, point.y).then((target) => {
      if (!target) return;
      setNote({ target, text: '' });
      setDraftBox(null);
    }).catch((err: any) => {
      setError(err?.response?.data?.detail || err?.message || 'Could not read the element');
    });
  };

  const send = async () => {
    const instruction = note?.text.trim();
    if (!note || !instruction || sending) return;
    setSending(true);
    setError('');
    try {
      await onSend(note.target.box, instruction);
      setNote(null);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Could not send the note');
    } finally {
      setSending(false);
    }
  };

  const outline = note?.target.box || draftBox || hover?.box || null;
  const chip = !note && !drag.current?.moved ? hover : null;

  return (
    <>
      <div style={{ position: 'absolute', top: 8, left: 8, right: 8, zIndex: 4, display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', borderRadius: 8, background: '#18181b', color: '#ffffff', fontSize: '0.75rem' }}>
        <span style={{ flex: 1 }}>Click to select or drag to create an area</span>
        <button type="button" aria-label="Exit annotate" onClick={onExit} style={{ border: 'none', background: 'transparent', color: '#ffffff', cursor: 'pointer', display: 'inline-flex' }}>
          <X size={14} />
        </button>
      </div>
      <div
        style={{ position: 'absolute', inset: 0, zIndex: 3, cursor: 'crosshair' }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
      />
      {outline && (
        <div style={{ position: 'absolute', zIndex: 3, pointerEvents: 'none', border: '2px solid #2563eb', background: 'rgba(37, 99, 235, 0.12)', ...place(outline) }} />
      )}
      {chip && (
        <div style={{ position: 'absolute', zIndex: 5, pointerEvents: 'none', left: place(chip.box).left, top: Math.max(36, place(chip.box).top - 22), padding: '2px 6px', borderRadius: 4, background: '#2563eb', color: '#ffffff', fontSize: '0.68rem', whiteSpace: 'nowrap' }}>
          {chip.label}
        </div>
      )}
      {note && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            send();
          }}
          style={noteStyle(place(note.target.box), stageRef.current)}
        >
          <div style={{ fontSize: '0.72rem', fontWeight: 650, color: '#18181b', marginBottom: 6 }}>{note.target.label}</div>
          <textarea
            autoFocus
            value={note.text}
            onChange={(event) => setNote({ ...note, text: event.target.value })}
            placeholder="Describe the change"
            rows={3}
            style={{ width: '100%', resize: 'none', border: '1px solid #e4e4e7', borderRadius: 6, padding: 6, font: 'inherit', fontSize: '0.78rem' }}
          />
          {error && <div style={{ color: '#b91c1c', fontSize: '0.68rem', marginTop: 4 }}>{error}</div>}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 6, marginTop: 6 }}>
            <button type="button" onClick={() => setNote(null)} style={{ border: 'none', background: 'transparent', color: '#52525b', cursor: 'pointer', fontSize: '0.75rem' }}>Cancel</button>
            <button type="submit" disabled={sending || !note.text.trim()} style={{ border: 'none', borderRadius: 6, background: '#18181b', color: '#ffffff', padding: '4px 8px', cursor: 'pointer', fontSize: '0.75rem' }}>
              {sending ? 'Sending…' : 'Send note'}
            </button>
          </div>
        </form>
      )}
    </>
  );
}

function noteStyle(box: Box, stage: HTMLDivElement | null): React.CSSProperties {
  const width = Math.min(240, Math.max(180, (stage?.clientWidth || 280) - 16));
  const left = Math.max(8, Math.min(box.left, (stage?.clientWidth || width + 16) - width - 8));
  const top = Math.max(40, Math.min(box.top + box.height + 8, (stage?.clientHeight || 400) - 150));
  return {
    position: 'absolute',
    zIndex: 5,
    left,
    top,
    width,
    padding: 8,
    borderRadius: 10,
    background: '#ffffff',
    border: '1px solid #e4e4e7',
    boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
  };
}
