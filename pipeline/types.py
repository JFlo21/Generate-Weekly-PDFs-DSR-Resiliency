"""pipeline.types — shared type shapes for the billing pipeline.

Holds TypedDict / dataclass definitions consumed by multiple pipeline
modules to break the grouping <-> pricing <-> discovery <->
change_detection circular-import risk: the data modules import shared
shapes from here rather than from each other.

Phase-09 Wave 0 shipped this as an empty stub. Phase 14 (Foreman Helper #2,
D-14-05) adds the first real content: a stdlib-only, import-light
fabricated-claim guard shared by ``pipeline.fetch``'s Helper #2 row
detection. Future shapes — ``SheetRow``, ``GroupKey``, ``RateTable`` — can
still land here later; this module stays free of pipeline-internal imports
so it is always safe to import from ``pipeline.fetch``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - reserved for future shared shapes
    pass

# Smartsheet formula-error tokens (D-14-05 fabricated-claim guard). These are
# the eleven error strings a Smartsheet formula cell can resolve to when its
# lookup/match fails; treating them as a non-claim value is the Helper #2
# path's day-one guard — Helper #1's own inherited "NA" quirk is left
# unchanged (out of scope, see 14-CONTEXT.md Deferred Ideas).
FORMULA_ERROR_VALUES = frozenset({
    '#BLOCKED',
    '#CALCULATING',
    '#CIRCULAR REFERENCE',
    '#INVALID COLUMN VALUE',
    '#INVALID DATA TYPE',
    '#INVALID OPERATION',
    '#INVALID REF',
    '#INVALID VALUE',
    '#NO MATCH',
    '#REF',
    '#UNPARSEABLE',
})

# The literal placeholder Smartsheet's "no match" contact-column fallback can
# leave behind (vault handoff, `wiki/projects/...` "NA" quirk note; D-14-05
# explicitly names it alongside the formula-error tokens above). Checked
# separately from ``FORMULA_ERROR_VALUES`` because it is not itself a
# Smartsheet formula-error token -- it is a literal placeholder string -- so
# the eleven-token set above stays an exact mirror of the prototype's
# reference list.
_NON_CLAIM_LITERALS = frozenset({'NA'})


def normalize_helper_value(value: object) -> str:
    """Return a safe helper-field value, treating Smartsheet formula
    errors, the ``NA`` no-match placeholder, and blank/whitespace-only
    input as blank (D-14-05). Used by the Helper #2 path only -- Helper
    #1's bare ``str(...).strip()`` truthiness check is intentionally left
    unmodified in this phase.
    """
    if value is None:
        return ''
    normalized = str(value).strip()
    if not normalized:
        return ''
    if normalized.upper() in FORMULA_ERROR_VALUES:
        return ''
    if normalized.upper() in _NON_CLAIM_LITERALS:
        return ''
    return normalized
