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
 *
 * CR-02: the single quote terminates the `ilike` literal — an unstripped
 * apostrophe (e.g. "O'Brien") yields a malformed `.or()` string and a 400.
 * Double-quote and `*` (the ilike wildcard the query builder adds itself) are
 * stripped in the same pass to keep the filter-injection surface closed.
 */
export function sanitizeSearchTerm(raw: string): string {
  return raw.replace(/['",()%*]/g, '').trim();
}
