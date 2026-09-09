/**
 * D-10: Friendly display labels for artifact variant values stored in public.artifacts.
 * Keys match the variant column values exactly.
 */
export const VARIANT_LABELS: Record<string, string> = {
  '': 'Primary',
  helper: 'Helper',
  vac_crew: 'VAC Crew',
  _AEPBillable: 'AEP Billable (Sub)',
  _ReducedSub: 'Reduced Sub',
  // Phase 14 plan 05: keyed on the snake_case token normalize_variant()
  // writes today (scripts/publish_artifacts_to_supabase.py), NOT the
  // underscore-capitalized convention used by the two entries above.
  // 14-RESEARCH.md Assumption A5 (which convention historical
  // public.artifacts.variant rows actually use) is unresolved and is
  // deliberately NOT fixed here -- only these three new keys are added.
  helper2: 'Helper 2',
  aep_billable_helper2: 'AEP Billable · Helper 2',
  reduced_sub_helper2: 'Reduced Sub · Helper 2',
};

/**
 * Returns a human-readable label for a variant string.
 * Falls back to de-prefixed form for unknown variants.
 */
export function getVariantLabel(variant: string): string {
  if (variant in VARIANT_LABELS) return VARIANT_LABELS[variant];
  if (variant.startsWith('_AEPBillable_Helper')) return 'AEP Billable · Helper';
  if (variant.startsWith('_ReducedSub_Helper')) return 'Reduced Sub · Helper';
  return variant.replace(/^_/, '').replace(/_/g, ' ');
}
