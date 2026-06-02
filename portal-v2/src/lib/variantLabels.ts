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
