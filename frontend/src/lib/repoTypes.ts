export type Workspace = {
  id: string;
  root: string;
  name: string;
  created_at: string;
};

export type TreeNode = {
  name: string;
  path: string;
  type: "file" | "directory";
  language: string | null;
  children: TreeNode[];
};

export type FileTree = {
  root: TreeNode;
  truncated: boolean;
};

export type FileContent = {
  path: string;
  language: string | null;
  content: string;
  truncated: boolean;
  size_bytes: number;
};

export type SearchMatch = {
  path: string;
  line_number: number;
  line_text: string;
};

export type SearchResult = {
  query: string;
  matches: SearchMatch[];
  truncated: boolean;
};

export type LanguageBreakdown = {
  language: string;
  file_count: number;
};

export type IndexStatus = {
  workspace_id: string;
  indexed: boolean;
  chunk_count: number | null;
};

export type IndexResult = {
  workspace_id: string;
  file_count: number;
  chunk_count: number;
  skipped_file_count: number;
  duration_seconds: number;
};

export type RepositoryMetadata = {
  workspace_id: string;
  root: string;
  name: string;
  file_count: number;
  total_size_bytes: number;
  languages: LanguageBreakdown[];
  has_git: boolean;
};

export type AgentProposal = {
  workspace_id: string;
  target_path: string;
  diff: string;
  proposed_content: string;
  explanation: string;
};