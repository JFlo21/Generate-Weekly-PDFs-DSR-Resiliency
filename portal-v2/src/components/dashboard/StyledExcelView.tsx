import { useEffect, useState } from 'react';
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
  const [html, setHtml] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setHtml(null);
    setError(null);
    api
      .getExcelHtml(artifactId, file, sheet)
      .then((value) => {
        if (!cancelled) setHtml(value);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load preview');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [artifactId, file, sheet]);

  if (error) {
    return <div className="p-6 text-sm text-red-500">{error}</div>;
  }

  if (!html) {
    return <div className="p-6 text-sm text-slate-400">Loading preview...</div>;
  }

  return (
    <iframe
      key={`${artifactId}:${file}:${sheet ?? ''}`}
      title={file}
      srcDoc={html}
      sandbox="allow-same-origin"
      className="w-full h-full border-0 rounded-xl bg-slate-50"
    />
  );
}
