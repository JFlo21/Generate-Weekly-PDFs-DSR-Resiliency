export type UserRole = 'admin' | 'viewer' | 'biller';

export interface WorkflowRun {
  id: number;
  name: string;
  status: string;
  conclusion: string | null;
  run_number: number;
  created_at: string;
  updated_at: string;
  html_url: string;
  head_branch: string;
  head_sha: string;
  isNew?: boolean;
}

export interface Artifact {
  id: number;
  name: string;
  size_in_bytes: number;
  archive_download_url: string;
  expired: boolean;
  created_at: string;
  expires_at: string;
}

export interface Profile {
  id: string;
  email: string;
  display_name: string | null;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ActivityLog {
  id: string;
  user_id: string;
  action: string;
  resource: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
  profiles?: Pick<Profile, 'email' | 'display_name'>;
}

export interface ArtifactDownload {
  id: string;
  user_id: string;
  artifact_name: string;
  artifact_url: string;
  file_size_bytes: number;
  downloaded_at: string;
}

export type ToastType = 'success' | 'error' | 'info';

export interface Toast {
  id: string;
  type: ToastType;
  message: string;
}

export interface ExcelSheet {
  name: string;
  rows: (string | number | null)[][];
}

/** Cell format as returned by the backend /view and /preview endpoints. */
export interface ParsedExcelCell {
  col: number;
  value: string | number | null;
  style?: {
    bold?: boolean;
    fontSize?: number;
    color?: string;
    bgColor?: string;
    align?: string;
  };
}

export interface ParsedExcelRow {
  rowNumber: number;
  cells: ParsedExcelCell[];
}

export interface ParsedExcelSheet {
  name: string;
  rowCount: number;
  columnCount: number;
  rows: ParsedExcelRow[];
  merges?: Array<{ top: number; left: number; bottom: number; right: number }>;
}

export interface ParsedWorkbook {
  filename?: string;
  sheetCount: number;
  sheets: ParsedExcelSheet[];
}

/** Entry in an artifact zip, as returned by /api/artifacts/:id/files. */
export interface ArtifactFile {
  name: string;
  size: number;
  isExcel: boolean;
  isText: boolean;
  isImage: boolean;
  isJson: boolean;
  isMarkdown: boolean;
  isCsv: boolean;
  isLog: boolean;
}

export type PreviewMode = 'json' | 'html' | 'csv' | 'text';

export interface TextPreview {
  filename: string;
  text: string;
  truncated: boolean;
  totalSize: number;
}

/** Hit shape returned by /api/search for the Cmd+K palette. */
export interface SearchHit {
  kind: 'run' | 'artifact' | 'file';
  runId?: number;
  artifactId?: number;
  file?: string;
  title: string;
  subtitle: string;
  score: number;
  meta?: Record<string, unknown>;
}

export interface JobStep {
  name: string;
  status: string;
  conclusion: string | null;
  number: number;
  startedAt: string | null;
  completedAt: string | null;
}

export interface Job {
  id: number;
  name: string;
  status: string;
  conclusion: string | null;
  startedAt: string | null;
  completedAt: string | null;
  htmlUrl: string;
  steps: JobStep[];
}
