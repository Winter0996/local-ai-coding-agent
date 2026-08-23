import { useState } from "react";

import type { TreeNode } from "../lib/repoTypes";

type FileTreeViewProps = {
  node: TreeNode;
  depth?: number;
  selectedPath: string | null;
  onSelectFile: (path: string) => void;
};

export function FileTreeView({
  node,
  depth = 0,
  selectedPath,
  onSelectFile,
}: FileTreeViewProps) {
  // Root directory (empty path) starts expanded; everything else starts
  // collapsed so a large repo doesn't render its entire tree at once.
  const [expanded, setExpanded] = useState(node.path === "");

  if (node.type === "file") {
    const isSelected = node.path === selectedPath;
    return (
      <button
        type="button"
        className={`tree-row tree-file${isSelected ? " tree-row-selected" : ""}`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={() => onSelectFile(node.path)}
      >
        <span className="tree-icon">□</span>
        {node.name}
        {node.language && <span className="tree-lang">{node.language}</span>}
      </button>
    );
  }

  return (
    <div>
      {node.path !== "" && (
        <button
          type="button"
          className="tree-row tree-dir"
          style={{ paddingLeft: `${depth * 16 + 8}px` }}
          onClick={() => setExpanded((value) => !value)}
        >
          <span className="tree-icon">{expanded ? "▾" : "▸"}</span>
          {node.name}
        </button>
      )}
      {expanded &&
        node.children.map((child) => (
          <FileTreeView
            key={child.path || child.name}
            node={child}
            depth={node.path === "" ? depth : depth + 1}
            selectedPath={selectedPath}
            onSelectFile={onSelectFile}
          />
        ))}
    </div>
  );
}