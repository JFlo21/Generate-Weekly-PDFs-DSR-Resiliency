"""pipeline.utils -- pure utility helpers for the billing pipeline.

These functions have no Smartsheet API dependency and no side effects; they
are relocated byte-for-byte from ``generate_weekly_pdfs.py`` (Phase 09 Wave 1,
D-05 relocation-only). ``_resolve_rate_recalc_cutoff_date`` and
``_weekly_would_trigger_fallback`` take the cutoff date as a parameter -- they
reference no module-level config constant -- so no ``_cfg.`` qualification is
required.

Symbols relocated from ``generate_weekly_pdfs.py``:
  is_checked, excel_serial_to_date,
  _resolve_rate_recalc_cutoff_date, _weekly_would_trigger_fallback
"""
from __future__ import annotations

import datetime
import logging

from dateutil import parser  # type: ignore[import-untyped]  # untyped third-party (matches facade)

from pipeline import config as _cfg  # noqa: F401  (declared W1 config dependency)

logger = logging.getLogger(__name__)



def is_checked(value: bool | int | str | None) -> bool:
    """Check if a checkbox value is considered checked/true.
    
    Args:
        value: Checkbox value in various formats
    
    Returns:
        bool: True if the value represents a checked state
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in ('true', 'checked', 'yes', '1', 'on')
    return False


def excel_serial_to_date(value):
    """Strict date parsing: return datetime or None. No numeric/serial fallbacks.
    
    PERFORMANCE: Fast-path for ISO format dates (YYYY-MM-DD) before falling back
    to the slower dateutil.parser.parse() for other formats.
    """
    if value in (None, ""):
        return None
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.date):
        return datetime.datetime.combine(value, datetime.time.min)
    s = str(value).strip()
    # PERFORMANCE: Fast-path for ISO date format (most common in Smartsheet)
    if len(s) >= 10 and s[4] == '-' and s[7] == '-':
        try:
            # Try ISO format first (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
            date_part = s[:10]
            return datetime.datetime.strptime(date_part, '%Y-%m-%d')
        except ValueError:
            pass  # Fall through to general parser
    try:
        dt = parser.parse(s)
        if isinstance(dt, datetime.datetime):
            return dt
        return datetime.datetime.combine(dt, datetime.time.min)
    except Exception:
        return None


def _resolve_rate_recalc_cutoff_date(
    row_data,
    cutoff_date,
    *,
    weekly_fallback_enabled: bool = True,
):
    """Return the effective cutoff date for a row's pre-acceptance recalc.

    The snapshot-keyed business rule remains primary: any row with a
    populated ``Snapshot Date`` is gated on that date alone. The
    Weekly-Ref-Date fallback only activates when ``Snapshot Date`` is
    blank or unparseable — it rescues current-week rows that would
    otherwise silently skip recalc because Smartsheet's snapshot
    automation has not fired yet (the observed VAC crew failure mode).

    Args:
        row_data: Mapping that may contain ``'Snapshot Date'`` and
            ``'Weekly Reference Logged Date'`` entries.
        cutoff_date: ``datetime.date`` used as the ``>=`` threshold.
        weekly_fallback_enabled: Set False to reproduce the legacy
            snapshot-only behaviour (the ``RATE_RECALC_WEEKLY_FALLBACK``
            env var wires this in production).

    Returns:
        ``(effective_cutoff_date, used_fallback)``. Returns
        ``(None, False)`` when recalc should not run.
    """
    if cutoff_date is None:
        return (None, False)

    snapshot_raw = row_data.get('Snapshot Date')
    snap_date = None
    if snapshot_raw:
        snap_dt = excel_serial_to_date(snapshot_raw)
        if snap_dt:
            snap_date = (
                snap_dt.date() if hasattr(snap_dt, 'date') else snap_dt
            )

    if snap_date is not None and snap_date >= cutoff_date:
        return (snap_date, False)

    if snap_date is None and weekly_fallback_enabled:
        weekly_raw = row_data.get('Weekly Reference Logged Date')
        if weekly_raw:
            weekly_dt = excel_serial_to_date(weekly_raw)
            if weekly_dt:
                weekly_date = (
                    weekly_dt.date()
                    if hasattr(weekly_dt, 'date')
                    else weekly_dt
                )
                if weekly_date >= cutoff_date:
                    return (weekly_date, True)

    return (None, False)


def _weekly_would_trigger_fallback(weekly_raw, cutoff_date) -> bool:
    """Return True if a blank/unparseable Snapshot Date row would be
    rescued by flipping ``RATE_RECALC_WEEKLY_FALLBACK`` on.

    Mirrors the secondary branch of
    ``_resolve_rate_recalc_cutoff_date``: the fallback only fires when
    the weekly date parses AND is ``>= cutoff_date``. Used to gate the
    fallback-disabled operator note so it doesn't misleadingly suggest
    enabling the env var for rows whose weekly date is also blank,
    unparseable, or pre-cutoff (where flipping the gate wouldn't
    change anything).
    """
    if cutoff_date is None or not weekly_raw:
        return False
    dt = excel_serial_to_date(weekly_raw)
    if dt is None:
        return False
    wdate = dt.date() if hasattr(dt, 'date') else dt
    return wdate >= cutoff_date
