import { useEffect, useState } from 'react';
import { Download, ExternalLink, FileText, Image as ImageIcon, Sparkles, Table as TableIcon } from 'lucide-react';
import { api } from '../../lib/api';
import type { ArtifactFile, ParsedExcelSheet } from '../../lib/types';
import { formatSize, cn } from '../../lib/utils';
import { Skeleton } from '../ui/Skeleton';
import { StyledExcelView } from './StyledExcelView';
import { InteractiveExcelView } from './InteractiveExcelView';

interface FilePreviewProps {
  artifactId: number;
  file: ArtifactFile | null;
}

type ExcelMode = 'styled' | 'interactive';
const MODE_STORAGE_KEY = 'linetec.excel-mode';

function useExcelMode(): [ExcelMode, (m: ExcelMode) => void] {
  const [mode, setMode] = useState<ExcelMode>(() => {
    if (typeof window === 'undefined') return 'styled';
    const stored = window.localStorage.getItem(MODE_STORAGE_KEY);
    return stored === 'interactive' ? 'interactive' : 'styled';
  });
  const update = (m: ExcelMode) => {
    setMode(m);
    try {
      window.localStorage.setItem(MODE_STORAGE_KEY, m);
    } catch {
      // ignore
    }
  };
  return [mode, update];
}

function EmptyState() {
  return (
    <div className="h-full flex flex-col items-center justify-center text-center px-6">
      <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mb-3">
        <Sparkles size={20} className="text-slate-400" />
      </div>
      <p className="text-sm font-medium text-slate-700">Select a file to preview</p>
      <p className="text-xs text-slate-400 mt-1 max-w-xs">
        Pick any file on the left. Excel files render inline; logs, JSON, Markdown
        and images get their own viewers.
      </p>
    </div>
  );
}

export function FilePreview({ artifactId, file }: FilePreviewProps) {
  if (!file) return <EmptyState />;

  const ext = file.name.split('.').pop()?.toLowerCase() ?? '';

  return (
    <div className="h-full flex flex-col min-h-0">
      <PreviewHeader artifactId={artifactId} file={file} ext={ext} />
      <div className="flex-1 min-h-0 overflow-hidden">
        <PreviewBody artifactId={artifactId} file={file} />
      </div>
    </div>
  );
}

function PreviewHeader({
  artifactId,
  file,
  ext,
}: {
  artifactId: number;
  file: ArtifactFile;
  ext: string;
}) {
  const baseName = file.name.split('/').pop() ?? file.name;
  return (
    <div className="flex items-center justify-between gap-3 px-4 py-2.5 border-b border-slate-100 bg-white shrink-0">
      <div className="flex items-center gap-2.5 min-w-0">
        <FileIcon file={file} />
        <div className="min-w-0">
          <p className="text-sm font-semibold text-slate-800 truncate">{baseName}</p>
          <p className="text-[11px] text-slate-400 truncate">
            {file.name} • {formatSize(file.size)} • {ext.toUpperCase() || 'FILE'}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <button
          onClick={() => api.downloadFile(artifactId, file.name)}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-brand-red text-white hover:bg-brand-red/90 transition-colors"
          title="Download original file"
        >
          <Download size={12} />
          Download
        </button>
        <a
          href={api.getFileInlineUrl(artifactId, file.name)}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors"
          title="Open in new tab"
        >
          <ExternalLink size={12} />
          Open
        </a>
      </div>
    </div>
  );
}

function FileIcon({ file }: { file: ArtifactFile }) {
  const cls = 'w-8 h-8 rounded-lg flex items-center justify-center shrink-0';
  if (file.isExcel) {
    return (
      <div className={cn(cls, 'bg-emerald-50 text-emerald-600')}>
        <TableIcon size={16} />
      </div>
    );
  }
  if (file.isImage) {
    return (
      <div className={cn(cls, 'bg-violet-50 text-violet-600')}>
        <ImageIcon size={16} />
      </div>
    );
  }
  return (
    <div className={cn(cls, 'bg-slate-100 text-slate-500')}>
      <FileText size={16} />
    </div>
  );
}

function PreviewBody({
  artifactId,
  file,
}: {
  artifactId: number;
  file: ArtifactFile;
}) {
  if (file.isExcel) return <ExcelPreview artifactId={artifactId} file={file} />;
  if (file.isImage) return <ImagePreview artifactId={artifactId} file={file} />;
  if (file.isJson) return <JsonPreview artifactId={artifactId} file={file} />;
  if (file.isText || file.isLog || file.isMarkdown || file.isCsv)
    return <TextPreviewView artifactId={artifactId} file={file} />;
  return <UnsupportedPreview file={file} />;
}

function ExcelPreview({ artifactId, file }: { artifactId: number; file: ArtifactFile }) {
  const [mode, setMode] = useExcelMode();
  const [sheets, setSheets] = useState<ParsedExcelSheet[]>([]);
  const [activeSheet, setActiveSheet] = useState<string | undefined>(undefined);

  // When file changes, reset sheet selection and fetch sheet metadata once.
  useEffect(() => {
    let cancelled = false;
    setActiveSheet(undefined);
    setSheets([]);
    api
      .getExcelPreview(artifactId, file.name)
      .then((wb) => {
        if (cancelled) return;
        setSheets(wb.sheets);
        if (wb.sheets.length > 0) setActiveSheet(wb.sheets[0].name);
      })
      .catch(() => {
        // Swallow — the preview body will surface its own error.
      });
    return () => {
      cancelled = true;
    };
  }, [artifactId, file.name]);

  return (
    <div className="h-full flex flex-col min-h-0 bg-slate-50">
      <div className="flex items-center gap-1 px-3 py-2 bg-white border-b border-slate-100 shrink-0 overflow-x-auto">
        {sheets.length > 1 && (
          <div className="flex items-center gap-1 mr-4">
            {sheets.map((s) => (
              <button
                key={s.name}
                onClick={() => setActiveSheet(s.name)}
                className={cn(
                  'px-3 py-1 rounded-md text-xs font-medium whitespace-nowrap transition-colors',
                  activeSheet === s.name
                    ? 'bg-slate-900 text-white'
                    : 'text-slate-500 hover:text-slate-800 hover:bg-slate-100'
                )}
              >
                {s.name}
              </button>
            ))}
          </div>
        )}
        <div className="ml-auto flex items-center gap-1 bg-slate-100 p-0.5 rounded-lg">
          <button
            onClick={() => setMode('styled')}
            className={cn(
              'px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors',
              mode === 'styled'
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            )}
            title="Rendered snapshot preserving original formatting"
          >
            Styled
          </button>
          <button
            onClick={() => setMode('interactive')}
            className={cn(
              'px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors',
              mode === 'interactive'
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            )}
            title="Interactive table with hover + row numbers"
          >
            Interactive
          </button>
        </div>
      </div>
      <div className="flex-1 min-h-0">
        {mode === 'styled' ? (
          <StyledExcelView
            artifactId={artifactId}
            file={file.name}
            sheet={activeSheet}
          />
        ) : (
          <InteractiveExcelView
            artifactId={artifactId}
            file={file.name}
            activeSheetName={activeSheet}
          />
        )}
      </div>
    </div>
  );
}

function ImagePreview({ artifactId, file }: { artifactId: number; file: ArtifactFile }) {
  return (
    <div className="h-full overflow-auto p-4 bg-slate-100 flex items-center justify-center">
      <img
        src={api.getFileInlineUrl(artifactId, file.name)}
        alt={file.name}
        className="max-w-full max-h-full rounded-lg shadow-md bg-white"
      />
    </div>
  );
}

function TextPreviewView({
  artifactId,
  file,
}: {
  artifactId: number;
  file: ArtifactFile;
}) {
  const [text, setText] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [truncated, setTruncated] = useState(false);
  const [filter, setFilter] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .getTextPreview(artifactId, file.name)
      .then((p) => {
        if (cancelled) return;
        setText(p.text);
        setTruncated(p.truncated);
      })
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [artifactId, file.name]);

  if (loading) {
    return (
      <div className="p-4 space-y-1.5">
        {Array.from({ length: 12 }).map((_, i) => (
          <Skeleton key={i} className="h-4 w-full" />
        ))}
      </div>
    );
  }
  if (error) return <div className="p-6 text-sm text-red-500">{error}</div>;
  if (!text) return <div className="p-6 text-sm text-slate-400">Empty file.</div>;

  const lines = text.split('\n');
  const needle = filter.toLowerCase();
  const visible = needle ? lines.filter((l) => l.toLowerCase().includes(needle)) : lines;

  return (
    <div className="h-full flex flex-col min-h-0 bg-slate-900">
      <div className="px-3 py-2 flex items-center gap-2 border-b border-slate-700 shrink-0">
        <input
          type="search"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter lines..."
          className="flex-1 px-2.5 py-1.5 rounded-md text-xs bg-slate-800 text-slate-100 placeholder-slate-500 border border-slate-700 focus:outline-none focus:border-slate-500"
        />
        <span className="text-[10px] text-slate-500 tabular-nums">
          {visible.length.toLocaleString()} / {lines.length.toLocaleString()} lines
        </span>
      </div>
      <div className="flex-1 overflow-auto font-mono text-[12px] leading-5">
        <table className="w-full">
          <tbody>
            {visible.map((line, i) => (
              <tr key={i} className="hover:bg-slate-800/50">
                <td className="select-none text-right text-slate-600 pr-3 pl-3 py-0.5 w-12 border-r border-slate-800 tabular-nums">
                  {i + 1}
                </td>
                <td className="py-0.5 pl-3 pr-4 text-slate-200 whitespace-pre">
                  {line || '\u00A0'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {truncated && (
          <p className="px-4 py-3 text-xs text-amber-400 bg-slate-800/50 border-t border-slate-700">
            Truncated to the first 2 MB. Download the file to see the rest.
          </p>
        )}
      </div>
    </div>
  );
}

function JsonPreview({
  artifactId,
  file,
}: {
  artifactId: number;
  file: ArtifactFile;
}) {
  const [text, setText] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getTextPreview(artifactId, file.name)
      .then((p) => !cancelled && setText(p.text))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : 'Failed'))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [artifactId, file.name]);

  if (loading) {
    return (
      <div className="p-4 space-y-1.5">
        {Array.from({ length: 10 }).map((_, i) => (
          <Skeleton key={i} className="h-4 w-full" />
        ))}
      </div>
    );
  }
  if (error) return <div className="p-6 text-sm text-red-500">{error}</div>;
  if (!text) return null;

  let pretty = text;
  try {
    pretty = JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    // keep raw
  }
  return (
    <pre className="h-full overflow-auto p-4 bg-slate-900 text-slate-100 font-mono text-xs leading-5 whitespace-pre">
      {pretty}
    </pre>
  );
}

function UnsupportedPreview({ file }: { file: ArtifactFile }) {
  return (
    <div className="h-full flex items-center justify-center text-center p-6">
      <div>
        <p className="text-sm font-medium text-slate-700">
          No inline preview for .{file.name.split('.').pop()}
        </p>
        <p className="text-xs text-slate-400 mt-1">
          Use the Download button to fetch the original file.
        </p>
      </div>
    </div>
  );
}
