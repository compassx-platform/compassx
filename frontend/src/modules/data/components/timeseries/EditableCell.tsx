/**
 * EditableCell – inline editable number cell for TanStack Table.
 *
 * Behaviour:
 *  - Displays value as plain text when not focused
 *  - On click/focus: shows an <input type="number">
 *  - On blur / Enter: commits the new value via onCommit callback
 *  - On Escape: reverts to original value
 *  - Highlights cell yellow when value differs from original_value
 */

import { useEffect, useRef, useState } from "react";

interface EditableCellProps {
  value: number | null;
  originalValue?: number | null;
  isDirty?: boolean;
  onCommit: (newValue: number) => void;
}

export default function EditableCell({
  value,
  originalValue,
  isDirty,
  onCommit,
}: EditableCellProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<string>(value != null ? String(value) : "");
  const inputRef = useRef<HTMLInputElement>(null);

  // Sync draft when value prop changes (e.g. after save)
  useEffect(() => {
    if (!editing) {
      setDraft(value != null ? String(value) : "");
    }
  }, [value, editing]);

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing]);

  const commit = () => {
    const parsed = parseFloat(draft);
    if (!isNaN(parsed) && parsed !== value) {
      onCommit(parsed);
    }
    setEditing(false);
  };

  const revert = () => {
    setDraft(value != null ? String(value) : "");
    setEditing(false);
  };

  const dirty = isDirty ?? (originalValue !== undefined && value !== originalValue);

  if (editing) {
    return (
      <input
        ref={inputRef}
        type="number"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") commit();
          if (e.key === "Escape") revert();
        }}
        style={{
          width: "100%",
          background: "var(--color-surface, #1e1e2e)",
          color: "var(--color-text, #cdd6f4)",
          border: "1px solid var(--color-primary, #6366f1)",
          borderRadius: 4,
          padding: "2px 6px",
          fontSize: "inherit",
          outline: "none",
        }}
      />
    );
  }

  return (
    <div
      onClick={() => setEditing(true)}
      title={dirty ? `Original: ${originalValue}` : undefined}
      style={{
        cursor: "text",
        padding: "2px 6px",
        borderRadius: 4,
        background: dirty ? "rgba(234,179,8,0.15)" : "transparent",
        color: dirty ? "#facc15" : "inherit",
        border: dirty ? "1px solid rgba(234,179,8,0.4)" : "1px solid transparent",
        minWidth: 60,
        userSelect: "none",
      }}
    >
      {value != null ? value.toLocaleString() : <span style={{ opacity: 0.4 }}>—</span>}
    </div>
  );
}