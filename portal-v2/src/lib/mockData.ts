/**
 * Mock data layer for v0 preview / demo mode.
 * When VITE_API_BASE_URL is not set, this provides sample data so the UI
 * can be fully explored without a running Express backend.
 */
import type {
  WorkflowRun,
  Artifact,
  ArtifactFile,
  ParsedWorkbook,
  ParsedExcelSheet,
  TextPreview,
  SearchHit,
  Job,
} from './types';

export const USE_MOCK = !import.meta.env.VITE_API_BASE_URL;

// ---------------------------------------------------------------------------
// Sample Runs
// ---------------------------------------------------------------------------
const now = new Date();
const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);
const oneDayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);
const twoDaysAgo = new Date(now.getTime() - 48 * 60 * 60 * 1000);

export const MOCK_RUNS: WorkflowRun[] = [
  {
    id: 12001,
    name: 'Generate Weekly Reports',
    head_branch: 'main',
    head_sha: 'abc1234',
    status: 'completed',
    conclusion: 'success',
    run_number: 142,
    event: 'schedule',
    created_at: oneHourAgo.toISOString(),
    updated_at: oneHourAgo.toISOString(),
    html_url: 'https://github.com/example/repo/actions/runs/12001',
    actor: { login: 'github-actions[bot]', avatar_url: '' },
  },
  {
    id: 12000,
    name: 'Generate Weekly Reports',
    head_branch: 'main',
    head_sha: 'def5678',
    status: 'completed',
    conclusion: 'success',
    run_number: 141,
    event: 'workflow_dispatch',
    created_at: oneDayAgo.toISOString(),
    updated_at: oneDayAgo.toISOString(),
    html_url: 'https://github.com/example/repo/actions/runs/12000',
    actor: { login: 'jflo21', avatar_url: '' },
  },
  {
    id: 11999,
    name: 'Generate Weekly Reports',
    head_branch: 'main',
    head_sha: 'ghi9012',
    status: 'completed',
    conclusion: 'failure',
    run_number: 140,
    event: 'schedule',
    created_at: twoDaysAgo.toISOString(),
    updated_at: twoDaysAgo.toISOString(),
    html_url: 'https://github.com/example/repo/actions/runs/11999',
    actor: { login: 'github-actions[bot]', avatar_url: '' },
  },
];

// ---------------------------------------------------------------------------
// Sample Artifacts (Excel files)
// ---------------------------------------------------------------------------
export const MOCK_ARTIFACTS: Record<number, Artifact[]> = {
  12001: [
    {
      id: 90001,
      name: 'weekly-reports-2026-04-16.zip',
      size_in_bytes: 524288,
      archive_download_url: '',
      expired: false,
      created_at: oneHourAgo.toISOString(),
      expires_at: new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000).toISOString(),
    },
  ],
  12000: [
    {
      id: 90000,
      name: 'weekly-reports-2026-04-15.zip',
      size_in_bytes: 498000,
      archive_download_url: '',
      expired: false,
      created_at: oneDayAgo.toISOString(),
      expires_at: new Date(now.getTime() + 29 * 24 * 60 * 60 * 1000).toISOString(),
    },
  ],
  11999: [
    {
      id: 89999,
      name: 'weekly-reports-2026-04-14.zip',
      size_in_bytes: 0,
      archive_download_url: '',
      expired: true,
      created_at: twoDaysAgo.toISOString(),
      expires_at: twoDaysAgo.toISOString(),
    },
  ],
};

// ---------------------------------------------------------------------------
// Sample Files inside an artifact zip
// ---------------------------------------------------------------------------
export const MOCK_FILES: Record<number, ArtifactFile[]> = {
  90001: [
    { name: 'DSR_Weekly_Report.xlsx', size: 245760, isExcel: true, isText: false, isImage: false, isJson: false, isMarkdown: false, isCsv: false, isLog: false },
    { name: 'Resiliency_Summary.xlsx', size: 184320, isExcel: true, isText: false, isImage: false, isJson: false, isMarkdown: false, isCsv: false, isLog: false },
    { name: 'VAC_Crew_Hours.xlsx', size: 94208, isExcel: true, isText: false, isImage: false, isJson: false, isMarkdown: false, isCsv: false, isLog: false },
    { name: 'build.log', size: 8192, isExcel: false, isText: true, isImage: false, isJson: false, isMarkdown: false, isCsv: false, isLog: true },
    { name: 'manifest.json', size: 1024, isExcel: false, isText: false, isImage: false, isJson: true, isMarkdown: false, isCsv: false, isLog: false },
  ],
  90000: [
    { name: 'DSR_Weekly_Report.xlsx', size: 235520, isExcel: true, isText: false, isImage: false, isJson: false, isMarkdown: false, isCsv: false, isLog: false },
    { name: 'Resiliency_Summary.xlsx', size: 176128, isExcel: true, isText: false, isImage: false, isJson: false, isMarkdown: false, isCsv: false, isLog: false },
    { name: 'manifest.json', size: 1024, isExcel: false, isText: false, isImage: false, isJson: true, isMarkdown: false, isCsv: false, isLog: false },
  ],
  89999: [],
};

// ---------------------------------------------------------------------------
// Sample Excel Preview Data
// ---------------------------------------------------------------------------
function generateSampleSheet(name: string, rows: number, cols: number): ParsedExcelSheet {
  const sampleRows = [];
  for (let r = 0; r < rows; r++) {
    const cells = [];
    for (let c = 0; c < cols; c++) {
      cells.push({
        col: c,
        value: r === 0 ? `Column ${c + 1}` : `R${r}C${c + 1}`,
        style: r === 0 ? { bold: true, bgColor: '#E2E8F0' } : undefined,
      });
    }
    sampleRows.push({ rowNumber: r + 1, cells });
  }
  return { name, rowCount: rows, columnCount: cols, rows: sampleRows };
}

const DSR_SHEET: ParsedExcelSheet = {
  name: 'Weekly DSR',
  rowCount: 12,
  columnCount: 6,
  rows: [
    { rowNumber: 1, cells: [
      { col: 0, value: 'Job #', style: { bold: true, bgColor: '#1E3A5F', color: '#FFFFFF' } },
      { col: 1, value: 'Customer', style: { bold: true, bgColor: '#1E3A5F', color: '#FFFFFF' } },
      { col: 2, value: 'Status', style: { bold: true, bgColor: '#1E3A5F', color: '#FFFFFF' } },
      { col: 3, value: 'Hours', style: { bold: true, bgColor: '#1E3A5F', color: '#FFFFFF' } },
      { col: 4, value: 'Revenue', style: { bold: true, bgColor: '#1E3A5F', color: '#FFFFFF' } },
      { col: 5, value: 'Notes', style: { bold: true, bgColor: '#1E3A5F', color: '#FFFFFF' } },
    ]},
    { rowNumber: 2, cells: [
      { col: 0, value: 'DSR-2024-001' },
      { col: 1, value: 'Acme Corp' },
      { col: 2, value: 'Complete', style: { color: '#059669' } },
      { col: 3, value: 24 },
      { col: 4, value: '$4,800.00' },
      { col: 5, value: 'Delivered on time' },
    ]},
    { rowNumber: 3, cells: [
      { col: 0, value: 'DSR-2024-002' },
      { col: 1, value: 'Beta Industries' },
      { col: 2, value: 'In Progress', style: { color: '#D97706' } },
      { col: 3, value: 16 },
      { col: 4, value: '$3,200.00' },
      { col: 5, value: 'Awaiting materials' },
    ]},
    { rowNumber: 4, cells: [
      { col: 0, value: 'DSR-2024-003' },
      { col: 1, value: 'Gamma LLC' },
      { col: 2, value: 'Complete', style: { color: '#059669' } },
      { col: 3, value: 32 },
      { col: 4, value: '$6,400.00' },
      { col: 5, value: '' },
    ]},
    { rowNumber: 5, cells: [
      { col: 0, value: 'DSR-2024-004' },
      { col: 1, value: 'Delta Systems' },
      { col: 2, value: 'Pending', style: { color: '#6B7280' } },
      { col: 3, value: 0 },
      { col: 4, value: '$0.00' },
      { col: 5, value: 'Scheduled for next week' },
    ]},
  ],
};

const RESILIENCY_SHEET: ParsedExcelSheet = {
  name: 'Resiliency Metrics',
  rowCount: 8,
  columnCount: 5,
  rows: [
    { rowNumber: 1, cells: [
      { col: 0, value: 'Metric', style: { bold: true, bgColor: '#1E3A5F', color: '#FFFFFF' } },
      { col: 1, value: 'Target', style: { bold: true, bgColor: '#1E3A5F', color: '#FFFFFF' } },
      { col: 2, value: 'Actual', style: { bold: true, bgColor: '#1E3A5F', color: '#FFFFFF' } },
      { col: 3, value: 'Variance', style: { bold: true, bgColor: '#1E3A5F', color: '#FFFFFF' } },
      { col: 4, value: 'Status', style: { bold: true, bgColor: '#1E3A5F', color: '#FFFFFF' } },
    ]},
    { rowNumber: 2, cells: [
      { col: 0, value: 'Uptime %' },
      { col: 1, value: '99.9%' },
      { col: 2, value: '99.95%' },
      { col: 3, value: '+0.05%', style: { color: '#059669' } },
      { col: 4, value: 'On Track', style: { color: '#059669', bold: true } },
    ]},
    { rowNumber: 3, cells: [
      { col: 0, value: 'Response Time' },
      { col: 1, value: '200ms' },
      { col: 2, value: '185ms' },
      { col: 3, value: '-15ms', style: { color: '#059669' } },
      { col: 4, value: 'On Track', style: { color: '#059669', bold: true } },
    ]},
    { rowNumber: 4, cells: [
      { col: 0, value: 'Error Rate' },
      { col: 1, value: '0.1%' },
      { col: 2, value: '0.08%' },
      { col: 3, value: '-0.02%', style: { color: '#059669' } },
      { col: 4, value: 'On Track', style: { color: '#059669', bold: true } },
    ]},
  ],
};

const VAC_SHEET: ParsedExcelSheet = {
  name: 'Crew Hours',
  rowCount: 6,
  columnCount: 4,
  rows: [
    { rowNumber: 1, cells: [
      { col: 0, value: 'Employee', style: { bold: true, bgColor: '#1E3A5F', color: '#FFFFFF' } },
      { col: 1, value: 'Regular Hours', style: { bold: true, bgColor: '#1E3A5F', color: '#FFFFFF' } },
      { col: 2, value: 'Overtime', style: { bold: true, bgColor: '#1E3A5F', color: '#FFFFFF' } },
      { col: 3, value: 'Total', style: { bold: true, bgColor: '#1E3A5F', color: '#FFFFFF' } },
    ]},
    { rowNumber: 2, cells: [
      { col: 0, value: 'John Smith' },
      { col: 1, value: 40 },
      { col: 2, value: 8 },
      { col: 3, value: 48, style: { bold: true } },
    ]},
    { rowNumber: 3, cells: [
      { col: 0, value: 'Jane Doe' },
      { col: 1, value: 40 },
      { col: 2, value: 4 },
      { col: 3, value: 44, style: { bold: true } },
    ]},
    { rowNumber: 4, cells: [
      { col: 0, value: 'Bob Wilson' },
      { col: 1, value: 36 },
      { col: 2, value: 0 },
      { col: 3, value: 36, style: { bold: true } },
    ]},
  ],
};

export const MOCK_WORKBOOKS: Record<string, ParsedWorkbook> = {
  'DSR_Weekly_Report.xlsx': {
    filename: 'DSR_Weekly_Report.xlsx',
    sheetCount: 2,
    sheets: [DSR_SHEET, generateSampleSheet('Raw Data', 20, 8)],
  },
  'Resiliency_Summary.xlsx': {
    filename: 'Resiliency_Summary.xlsx',
    sheetCount: 1,
    sheets: [RESILIENCY_SHEET],
  },
  'VAC_Crew_Hours.xlsx': {
    filename: 'VAC_Crew_Hours.xlsx',
    sheetCount: 1,
    sheets: [VAC_SHEET],
  },
};

// ---------------------------------------------------------------------------
// Sample Text Preview
// ---------------------------------------------------------------------------
export const MOCK_LOG: TextPreview = {
  filename: 'build.log',
  text: `[2026-04-16 08:00:01] INFO  Starting weekly report generation...
[2026-04-16 08:00:02] INFO  Connecting to Smartsheet API...
[2026-04-16 08:00:03] INFO  Fetching DSR data from sheet ID 12345...
[2026-04-16 08:00:05] INFO  Retrieved 142 rows from DSR sheet
[2026-04-16 08:00:06] INFO  Processing Resiliency metrics...
[2026-04-16 08:00:08] INFO  Retrieved 28 rows from Resiliency sheet
[2026-04-16 08:00:09] INFO  Processing VAC Crew hours...
[2026-04-16 08:00:11] INFO  Retrieved 15 crew members
[2026-04-16 08:00:12] INFO  Generating Excel reports...
[2026-04-16 08:00:15] INFO  Created DSR_Weekly_Report.xlsx (245 KB)
[2026-04-16 08:00:17] INFO  Created Resiliency_Summary.xlsx (184 KB)
[2026-04-16 08:00:18] INFO  Created VAC_Crew_Hours.xlsx (94 KB)
[2026-04-16 08:00:19] INFO  Packaging artifacts...
[2026-04-16 08:00:20] SUCCESS Report generation completed successfully!`,
  truncated: false,
  totalSize: 892,
};

export const MOCK_MANIFEST = {
  version: '1.0.0',
  generated_at: oneHourAgo.toISOString(),
  files: [
    { name: 'DSR_Weekly_Report.xlsx', size: 245760, sheets: 2 },
    { name: 'Resiliency_Summary.xlsx', size: 184320, sheets: 1 },
    { name: 'VAC_Crew_Hours.xlsx', size: 94208, sheets: 1 },
  ],
  source: 'Generate Weekly Reports workflow',
};

// ---------------------------------------------------------------------------
// Mock Jobs
// ---------------------------------------------------------------------------
export const MOCK_JOBS: Record<number, Job[]> = {
  12001: [
    {
      id: 1,
      name: 'generate-reports',
      status: 'completed',
      conclusion: 'success',
      startedAt: oneHourAgo.toISOString(),
      completedAt: new Date(oneHourAgo.getTime() + 120000).toISOString(),
      htmlUrl: 'https://github.com/example/repo/actions/runs/12001/jobs/1',
      steps: [
        { name: 'Checkout', status: 'completed', conclusion: 'success', number: 1, startedAt: null, completedAt: null },
        { name: 'Setup Python', status: 'completed', conclusion: 'success', number: 2, startedAt: null, completedAt: null },
        { name: 'Install dependencies', status: 'completed', conclusion: 'success', number: 3, startedAt: null, completedAt: null },
        { name: 'Generate reports', status: 'completed', conclusion: 'success', number: 4, startedAt: null, completedAt: null },
        { name: 'Upload artifacts', status: 'completed', conclusion: 'success', number: 5, startedAt: null, completedAt: null },
      ],
    },
  ],
};

// ---------------------------------------------------------------------------
// Mock Search
// ---------------------------------------------------------------------------
export function mockSearch(q: string): SearchHit[] {
  const lower = q.toLowerCase();
  const hits: SearchHit[] = [];

  for (const run of MOCK_RUNS) {
    if (run.name.toLowerCase().includes(lower) || run.head_branch.toLowerCase().includes(lower)) {
      hits.push({
        kind: 'run',
        runId: run.id,
        title: `Run #${run.run_number}`,
        subtitle: run.name,
        score: 1,
      });
    }
  }

  for (const [runIdStr, arts] of Object.entries(MOCK_ARTIFACTS)) {
    const runId = Number(runIdStr);
    for (const art of arts) {
      if (art.name.toLowerCase().includes(lower)) {
        hits.push({
          kind: 'artifact',
          runId,
          artifactId: art.id,
          title: art.name,
          subtitle: `Run #${MOCK_RUNS.find(r => r.id === runId)?.run_number ?? runId}`,
          score: 0.9,
        });
      }
    }
  }

  for (const [artIdStr, files] of Object.entries(MOCK_FILES)) {
    const artifactId = Number(artIdStr);
    for (const file of files) {
      if (file.name.toLowerCase().includes(lower)) {
        const art = Object.values(MOCK_ARTIFACTS).flat().find(a => a.id === artifactId);
        const run = MOCK_RUNS.find(r => MOCK_ARTIFACTS[r.id]?.some(a => a.id === artifactId));
        hits.push({
          kind: 'file',
          runId: run?.id,
          artifactId,
          file: file.name,
          title: file.name,
          subtitle: art?.name ?? `Artifact #${artifactId}`,
          score: 0.8,
        });
      }
    }
  }

  return hits.slice(0, 10);
}
