/**
 * D-08: Normalize a raw search term toward the week_ending_fmt column (MMDDYY).
 * Accepts MMDDYY, MM/DD/YY, or ISO YYYY-MM-DD; leaves WR# and other strings intact.
 */
export function normalizeSearchTerm(raw: string): string {
  const trimmed = raw.trim();
  const isoMatch = trimmed.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (isoMatch) {
    const [, yyyy, mm, dd] = isoMatch;
    return `${mm}${dd}${yyyy.slice(2)}`;
  }
  return trimmed.replace(/\//g, '');
}

/**
 * RESEARCH Pitfall 4: PostgREST .or() takes RAW syntax with NO auto-escaping.
 * Strip chars that break the filter string before interpolation into a query.
 */
export function sanitizeSearchTerm(raw: string): string {
  return raw.replace(/[,()%]/g, '').trim();
}
