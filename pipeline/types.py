"""pipeline.types — shared type shapes for the billing pipeline.

Holds TypedDict / dataclass definitions consumed by multiple pipeline
modules to break the grouping <-> pricing <-> discovery <->
change_detection circular-import risk: the data modules import shared
shapes from here rather than from each other.

Phase-09 Wave 0 ships this as a STUB. No shared dataclasses/TypedDicts
exist in the current engine to relocate (RESEARCH Assumption A4), so this
module is intentionally empty of definitions. Future shapes —
``SheetRow``, ``GroupKey``, ``RateTable`` — land here in a follow-on PR if
and when real types are extracted; this phase is relocation-only and adds
no new types.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

# Stub: no shared dataclasses/TypedDicts yet (RESEARCH Assumption A4).
# Future shapes: SheetRow, GroupKey, RateTable.

if TYPE_CHECKING:  # pragma: no cover - reserved for future shared shapes
    pass
