import React, { useEffect, useRef } from "react";
import { Terminal } from "xterm";
import { FitAddon } from "@xterm/addon-fit";
import "xterm/css/xterm.css";
import { openTerminalSocket } from "../lib/appsApi";

interface Props {
  appId: string;
  branchId: string;
  enabled: boolean;
}

const isUuid = (str: string) =>
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(str);

/**
 * Integrated terminal panel powered by xterm.js.
 * Connects directly to the branch pod's terminal WebSocket (or local shell fallback)
 * and supports responsive sizing, ANSI styles, colors, and direct input.
 */
export default function TerminalPanel({ appId, branchId, enabled }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const terminalRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const isValidUuid = isUuid(branchId);
  const isEnabled = enabled && isValidUuid;

  useEffect(() => {
    if (!isEnabled || !containerRef.current) return;

    // 1. Initialize xterm.js Terminal with theme support
    const isDarkTheme = document.documentElement.getAttribute("data-theme") === "dark";
    const term = new Terminal({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: "monospace",
      theme: {
        background: isDarkTheme ? "#1e1e1e" : "#f5f5f5",
        foreground: isDarkTheme ? "#d4d4d4" : "#333333",
        cursor: isDarkTheme ? "#ffffff" : "#000000",
        selectionBackground: isDarkTheme ? "rgba(255, 255, 255, 0.3)" : "rgba(0, 0, 0, 0.2)",
      },
    });
    terminalRef.current = term;

    // Support standard clipboard copy (Ctrl+C) and paste (Ctrl+V) shortcuts
    term.attachCustomKeyEventHandler((arg) => {
      if (arg.ctrlKey && arg.code === "KeyC" && arg.type === "keydown") {
        const selection = term.getSelection();
        if (selection) {
          navigator.clipboard.writeText(selection);
          return false; // Prevent sending Ctrl+C to the running process
        }
      }
      if (arg.ctrlKey && arg.code === "KeyV" && arg.type === "keydown") {
        navigator.clipboard.readText().then((text) => {
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: "input", data: text }));
          }
        });
        return false; // Prevent sending Ctrl+V to the running process
      }
      return true;
    });

    // 2. Setup Fit addon to keep term responsive
    const fitAddon = new FitAddon();
    fitAddonRef.current = fitAddon;
    term.loadAddon(fitAddon);

    // 3. Open WebSocket connection
    const ws = openTerminalSocket(appId, branchId);
    wsRef.current = ws;

    ws.onopen = () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: "resize",
          cols: term.cols,
          rows: term.rows
        }));
      }
    };

    // 4. Open terminal layout on the container
    term.open(containerRef.current);
    try {
      fitAddon.fit();
    } catch (e) {
      // Ignore initial fit issues if rendering hidden
    }

    // 5. Send keystrokes and inputs directly to WebSocket as JSON
    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "input", data }));
      }
    });

    // 6. Output socket messages to terminal
    ws.onmessage = (e) => {
      term.write(e.data);
    };

    ws.onerror = () => {
      term.write("\r\n[CompassX: terminal connection error]\r\n");
    };

    ws.onclose = () => {
      term.write("\r\n[CompassX: terminal disconnected]\r\n");
    };

    // 7. Watch for container resize to automatically adjust terminal grid columns/rows
    const resizeObserver = new ResizeObserver(() => {
      try {
        fitAddon.fit();
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({
            type: "resize",
            cols: term.cols,
            rows: term.rows
          }));
        }
      } catch (err) {
        // Catch resize exceptions if element is detached
      }
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      term.dispose();
      ws.close();
      terminalRef.current = null;
      wsRef.current = null;
    };
  }, [appId, branchId, isEnabled]);

  if (!isEnabled) {
    return (
      <div
        id="terminal-panel-disabled"
        style={{
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--color-text-muted)",
          fontSize: "13px",
          background: "var(--color-bg)",
        }}
      >
        {!isValidUuid ? "Initializing terminal..." : "Terminal is disabled for this pod"}
      </div>
    );
  }

  return (
    <div
      id="terminal-panel"
      ref={containerRef}
      style={{
        height: "100%",
        width: "100%",
        padding: "8px",
        background: "var(--color-bg)",
        boxSizing: "border-box",
      }}
    />
  );
}
