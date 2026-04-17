import { useMemo } from 'react';
import { api } from '../../lib/api';

interface StyledExcelViewProps {
  artifactId: number;
  file: string;
  sheet?: string;
}

/**
 * Renders the server-produced HTML snapshot of an Excel sheet inside a
 * sandboxed iframe. This preserves Excel formatting (bold, color, bgColor,
 * alignment) and renders instantly even for large sheets because the
 * browser doesn't have to JSON-parse + re-virtualize thousands of rows.
 */
export function StyledExcelView({ artifactId, file, sheet }: StyledExcelViewProps) {
  const src = useMemo(
    () => api.getExcelHtmlUrl(artifactId, file, sheet),
    [artifactId, file, sheet]
  );

  return (
    <iframe
      key={src}
      title={file}
      src={src}
      sandbox="allow-same-origin"
      className="w-full h-full border-0 rounded-xl bg-slate-50"
    />
  );
}
