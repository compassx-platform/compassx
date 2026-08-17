import React, { useState, useEffect } from "react";
import { ChevronDown, ChevronRight, Folder, FolderOpen, FileCode } from "lucide-react";
import type { FileMeta } from "../lib/appsApi";

const STATUS_COLOR: Record<string, string> = {
  clean: "var(--color-text-muted)",
  modified: "var(--color-warning)",
  untracked: "var(--color-success)",
  deleted: "var(--color-danger)",
};

const STATUS_SYMBOL: Record<string, string> = {
  clean: "",
  modified: "M",
  untracked: "U",
  deleted: "D",
};

interface TreeNode {
  name: string;
  path: string;
  isFolder: boolean;
  children: TreeNode[];
  fileMeta?: FileMeta;
}

interface Props {
  files: FileMeta[];
  selectedPath: string | null;
  onSelect: (path: string) => void;
}

/**
 * Collapsible & Expandable File Tree Component.
 * Builds and renders a proper hierarchical directory tree with folder icons
 * and Git status markers.
 */
export default function FileTree({ files, selectedPath, onSelect }: Props) {
  const [expandedPaths, setExpandedPaths] = useState<Record<string, boolean>>({});

  // Auto-expand top-level folders on first load
  useEffect(() => {
    const defaultExpanded: Record<string, boolean> = {};
    for (const f of files) {
      const parts = f.path.split("/");
      if (parts.length > 1) {
        defaultExpanded[parts[0]] = true;
      }
    }
    setExpandedPaths((prev) => ({ ...defaultExpanded, ...prev }));
  }, [files]);

  const toggleExpand = (path: string) => {
    setExpandedPaths((prev) => ({
      ...prev,
      [path]: !prev[path],
    }));
  };

  const tree = buildTree(files);

  const renderNode = (node: TreeNode, depth: number) => {
    const isExpanded = expandedPaths[node.path];
    const isSelected = node.path === selectedPath;

    if (node.isFolder) {
      return (
        <div key={node.path}>
          <div
            onClick={() => toggleExpand(node.path)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "4px 12px",
              paddingLeft: `${depth * 12 + 12}px`,
              cursor: "pointer",
              userSelect: "none",
              color: "var(--color-text-muted)",
              fontSize: "13px",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--color-surface-hover)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
            }}
          >
            {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            {isExpanded ? (
              <FolderOpen size={14} color="var(--color-primary)" />
            ) : (
              <Folder size={14} color="var(--color-primary)" />
            )}
            <span style={{ fontWeight: 500 }}>{node.name}</span>
          </div>
          {isExpanded && node.children.map((child) => renderNode(child, depth + 1))}
        </div>
      );
    } else {
      const status = node.fileMeta?.status ?? "clean";
      return (
        <div
          key={node.path}
          id={`file-tree-item-${node.path.replace(/\//g, "-")}`}
          onClick={() => {
            console.log("FileTree clicked path:", node.path);
            onSelect(node.path);
          }}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "4px 12px",
            paddingLeft: `${depth * 12 + 12}px`,
            cursor: "pointer",
            background: isSelected ? "var(--color-primary-bg)" : "transparent",
            color: isSelected ? "var(--color-primary)" : "var(--color-text)",
            fontSize: "13px",
          }}
          onMouseEnter={(e) => {
            if (!isSelected)
              (e.currentTarget as HTMLDivElement).style.background = "var(--color-surface-hover)";
          }}
          onMouseLeave={(e) => {
            if (!isSelected)
              (e.currentTarget as HTMLDivElement).style.background = "transparent";
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "6px", overflow: "hidden" }}>
            <FileCode size={14} style={{ flexShrink: 0, opacity: 0.8 }} />
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {node.name}
            </span>
          </div>
          {status !== "clean" && (
            <span
              style={{
                fontSize: "11px",
                fontWeight: 700,
                color: STATUS_COLOR[status] ?? "var(--color-text)",
                paddingLeft: "6px",
              }}
            >
              {STATUS_SYMBOL[status]}
            </span>
          )}
        </div>
      );
    }
  };

  return (
    <div
      id="file-tree"
      style={{
        height: "100%",
        overflowY: "auto",
        padding: "8px 0",
        fontFamily: "var(--font-family)",
      }}
    >
      {tree.map((node) => renderNode(node, 0))}
    </div>
  );
}

function buildTree(files: FileMeta[]): TreeNode[] {
  const root: TreeNode = {
    name: "",
    path: "",
    isFolder: true,
    children: [],
  };

  const nodeMap: Record<string, TreeNode> = { "": root };

  // 1. Create all folder nodes
  for (const file of files) {
    const parts = file.path.split("/");
    for (let i = 0; i < parts.length - 1; i++) {
      const folderPath = parts.slice(0, i + 1).join("/");
      if (!nodeMap[folderPath]) {
        const folderName = parts[i];
        const parentPath = parts.slice(0, i).join("/");
        const folderNode: TreeNode = {
          name: folderName,
          path: folderPath,
          isFolder: true,
          children: [],
        };
        nodeMap[folderPath] = folderNode;
        nodeMap[parentPath].children.push(folderNode);
      }
    }
  }

  // 2. Create all file nodes as leaves
  for (const file of files) {
    const parts = file.path.split("/");
    const fileName = parts[parts.length - 1];
    const parentPath = parts.slice(0, parts.length - 1).join("/");

    if (nodeMap[file.path]) {
      continue; // Skip if it's already a folder
    }

    const fileNode: TreeNode = {
      name: fileName,
      path: file.path,
      isFolder: false,
      children: [],
      fileMeta: file,
    };
    nodeMap[parentPath].children.push(fileNode);
  }

  // 3. Recursive sort
  const sortTree = (nodes: TreeNode[]) => {
    for (const node of nodes) {
      if (node.isFolder) {
        sortTree(node.children);
      }
    }
    nodes.sort((a, b) => {
      if (a.isFolder && !b.isFolder) return -1;
      if (!a.isFolder && b.isFolder) return 1;
      return a.name.localeCompare(b.name);
    });
  };

  sortTree(root.children);
  return root.children;
}
