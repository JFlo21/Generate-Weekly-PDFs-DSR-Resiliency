import { useInfiniteQuery } from '@tanstack/react-query';
import { supabase } from '../lib/supabase';
import { normalizeSearchTerm, sanitizeSearchTerm } from '../lib/searchNormalize';
import type { BillingArtifact } from '../lib/types';

export const PAGE_SIZE = 75; // ~30 visible rows/viewport; tunable (RESEARCH A2)

export interface ArtifactsQueryParams {
  search: string;
  variants: string[];
  sortColumn: 'week_ending' | 'work_request' | 'size_bytes' | 'created_at';
  sortAscending: boolean;
}

interface ArtifactsPage {
  rows: BillingArtifact[];
  count: number;
}

export function useArtifactsInfinite(params: ArtifactsQueryParams) {
  return useInfiniteQuery<ArtifactsPage>({
    queryKey: [
      'artifacts',
      params.search,
      params.variants,
      params.sortColumn,
      params.sortAscending,
    ],
    queryFn: async ({ pageParam }) => {
      const page = pageParam as number;
      const from = page * PAGE_SIZE;
      const to = from + PAGE_SIZE - 1;

      let query = supabase
        .from('artifacts')
        .select(
          'id,work_request,week_ending,week_ending_fmt,variant,filename,storage_path,size_bytes,created_at',
          { count: 'exact' }
        );

      // Server-side OR search (WR# OR week-ending). Sanitize THEN normalize (Pitfall 4 + D-08).
      const raw = params.search.trim();
      if (raw) {
        const term = normalizeSearchTerm(sanitizeSearchTerm(raw));
        if (term) {
          query = query.or(
            `work_request.ilike.%${term}%,week_ending_fmt.ilike.%${term}%`
          );
        }
      }

      // Server-side variant filter (AND with search). Omit entirely when empty.
      if (params.variants.length > 0) {
        query = query.in('variant', params.variants);
      }

      // Server-side sort (D-06 default week_ending DESC supplied by caller).
      query = query.order(params.sortColumn, { ascending: params.sortAscending });

      // Inclusive .range(): range(0, 74) => 75 rows.
      const { data, error, count } = await query.range(from, to);
      if (error) throw error;
      return { rows: (data ?? []) as BillingArtifact[], count: count ?? 0 };
    },
    initialPageParam: 0, // REQUIRED in v5 — omitting => runtime NaN (Pitfall 1)
    getNextPageParam: (_lastPage, allPages) => {
      const loaded = allPages.flatMap((p) => p.rows).length;
      const total = allPages[0]?.count ?? 0;
      return loaded < total ? allPages.length : undefined;
    },
  });
}
