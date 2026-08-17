import React from "react";

interface Props {
  previewUrl: string;
}

/**
 * Live preview iframe pointing at the branch's preview URL.
 * Shown in the side/tab panel of the editor (§9).
 */
export default function LivePreviewPane({ previewUrl }: Props) {
  const [refreshKey, setRefreshKey] = React.useState(0);

  return (
    <div
      id="live-preview-pane"
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        background: "var(--color-bg)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          background: "var(--color-surface)",
          borderBottom: "1px solid var(--color-border)",
          padding: "6px 12px",
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: "12px", color: "var(--color-text-muted)", fontFamily: "monospace", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {previewUrl}
        </span>
        <button
          id="preview-refresh-btn"
          onClick={() => setRefreshKey((k) => k + 1)}
          title="Refresh preview"
          style={{
            background: "transparent",
            border: "none",
            color: "var(--color-text-muted)",
            cursor: "pointer",
            fontSize: "14px",
            padding: "2px 6px",
          }}
        >
          ↺
        </button>
      </div>
      <iframe
        key={refreshKey}
        src={previewUrl}
        title="App Preview"
        style={{ flex: 1, border: "none" }}
        sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
      />
    </div>
  );
}
