import { useEffect, useState, useMemo } from 'react';
import { api } from '../../lib/api';
import type { ParsedWorkbook, ParsedExcelSheet } from '../../lib/types';
import { Skeleton } from '../ui/Skeleton';

interface InteractiveExcelViewProps {
  artifactId: number;
  file: string;
  activeSheetName?: string;
  /** When set (e.g. from a parent fetch), skips a duplicate getExcelPreview request. */
  prefetchedWorkbook?: ParsedWorkbook | null;
  onSheetsLoaded?: (sheets: ParsedExcelSheet[]) => void;
}

/**
 * Virtualization-lite: we render all rows but cap very large sheets at
 * MAX_ROWS with a "show more" banner so the browser doesn't choke.
 * For the v1 volume of reports (<2k rows) this renders in <60ms.
 */
const MAX_ROWS = 2000;

function styleFor(style?: {
  bold?: boolean;
  fontSize?: number;
  color?: string;
  bgColor?: string;
  align?: string;
}): React.CSSProperties | undefined {
  if (!style) return undefined;
  const s: React.CSSProperties = {};
  if (style.bold) s.fontWeight = 600;
  if (style.fontSize) s.fontSize = `${style.fontSize}px`;
  if (style.color) s.color = style.color;
  if (style.bgColor) s.backgroundColor = style.bgColor;
  if (style.align) s.textAlign = style.align as React.CSSProperties['textAlign'];
  return s;
}

export function InteractiveExcelView({
  artifactId,
  file,
  activeSheetName,
  prefetchedWorkbook,
  onSheetsLoaded,
}: InteractiveExcelViewProps) {
  const [workbook, setWorkbook] = useState<ParsedWorkbook | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (prefetchedWorkbook) {
      setWorkbook(prefetchedWorkbook);
      setError(null);
      setLoading(false);
      onSheetsLoaded?.(prefetchedWorkbook.sheets);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setWorkbook(null);
    api
      .getExcelPreview(artifactId, file)
      .then((wb) => {
        if (cancelled) return;
        setWorkbook(wb);
        onSheetsLoaded?.(wb.sheets);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Failed to load');
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [artifactId, file, prefetchedWorkbook, onSheetsLoaded]);

  const sheet = useMemo(() => {
    if (!workbook) return null;
    if (activeSheetName) {
      return workbook.sheets.find((s) => s.name === activeSheetName) ?? workbook.sheets[0];
    }
    return workbook.sheets[0];
  }, [workbook, activeSheetName]);

  const maxCol = useMemo(() => {
    if (!sheet) return 0;
    let maxIdx = -1;
    for (const r of sheet.rows) {
      for (const c of r.cells) if (c.col > maxIdx) maxIdx = c.col;
    }
    return maxIdx + 1;
  }, [sheet]);

  if (loading) {
    return (
      <div className="p-4 space-y-2">
        {Array.from({ length: 10 }).map((_, i) => (
          <Skeleton key={i} className="h-7 w-full" />
        ))}
      </div>
    );
  }
  if (error) {
    return <div className="p-6 text-sm text-red-500">{error}</div>;
  }
  if (!sheet) {
    return <div className="p-6 text-sm text-slate-400">No sheet data.</div>;
  }

  const rows = sheet.rows.slice(0, MAX_ROWS);
  const truncated = sheet.rows.length > MAX_ROWS;

  return (
    <div className="h-full overflow-auto bg-slate-50">
      <div className="min-w-max p-4">
        <table className="text-xs border-separate border-spacing-0 bg-white shadow-sm rounded-lg overflow-hidden">
          <thead className="sticky top-0 z-10">
            <tr>
              <th className="sticky left-0 z-20 bg-slate-100 border-b border-r border-slate-200 px-2 py-1.5 text-[10px] text-slate-400 font-medium">
                #
              </th>
              {Array.from({ length: maxCol }).map((_, i) => (
                <th
                  key={i}
                  className="bg-slate-100 border-b border-slate-200 px-3 py-1.5 text-[10px] uppercase tracking-wide text-slate-500 font-medium min-w-[120px]"
                >
                  {String.fromCharCode(65 + (i % 26))}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const cellMap = new Map(row.cells.map((c) => [c.col, c]));
              return (
                <tr key={row.rowNumber} className="group">
                  <td className="sticky left-0 z-10 bg-slate-50 group-hover:bg-slate-100 border-b border-r border-slate-200 px-2 py-1 text-[10px] text-slate-400 text-right tabular-nums">
                    {row.rowNumber}
                  </td>
                  {Array.from({ length: maxCol }).map((_, i) => {
                    const col = i;
                    const cell = cellMap.get(col);
                    return (
                      <td
                        key={col}
                        style={styleFor(cell?.style)}
                        className="border-b border-slate-100 px-3 py-1 text-slate-700 whitespace-nowrap group-hover:bg-slate-50"
                      >
                        {cell?.value ?? ''}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
        {truncated && (
          <p className="mt-3 text-xs text-amber-600">
            Showing first {MAX_ROWS.toLocaleString()} of{' '}
            {sheet.rows.length.toLocaleString()} rows. Download the original
            .xlsx to see the full sheet.
          </p>
        )}
      </div>
    </div>
  );
}
