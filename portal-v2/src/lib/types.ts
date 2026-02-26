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
