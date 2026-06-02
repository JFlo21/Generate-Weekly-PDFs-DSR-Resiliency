import { useState, useCallback } from 'react';
import { supabase } from '../lib/supabase';
import type { ToastType } from '../lib/types';

const BUCKET = 'excel-artifacts';
const SIGNED_URL_TTL = 300; // 5 min, single-object (Phase 03 D-10 / DATA-05 / SEC-05)

export function useDownloadArtifact(
  addToast: (type: ToastType, message: string) => void
) {
  const [downloading, setDownloading] = useState<string | undefined>(undefined);

  const download = useCallback(
    async (rowId: string, storagePath: string, filename: string) => {
      setDownloading(rowId);
      try {
        const { data, error } = await supabase.storage
          .from(BUCKET)
          .createSignedUrl(storagePath, SIGNED_URL_TTL);
        if (error || !data?.signedUrl) {
          throw new Error(error?.message ?? 'Failed to generate download link');
        }
        const a = document.createElement('a');
        a.href = data.signedUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      } catch (err) {
        addToast('error', err instanceof Error ? err.message : 'Download failed');
      } finally {
        setDownloading(undefined);
      }
    },
    [addToast]
  );

  return { download, downloading };
}
