"""pipeline.discovery — Smartsheet source-sheet discovery (Phase 09 W3).

Owns the three runtime-rebound live-proxy globals delegated from the
``generate_weekly_pdfs`` facade via PEP-562 ``__getattr__`` (D-01):

    SUBCONTRACTOR_SHEET_IDS      (set)
    _FOLDER_DISCOVERED_SUB_IDS   (set[int])
    _FOLDER_DISCOVERED_ORIG_IDS  (set[int])

GUARD: these three names MUST NOT be added to the facade's static
``from pipeline.discovery import ...`` block — doing so binds the pre-run
value and shadows ``__getattr__``, re-introducing the stale-read bug that
silently mis-classifies subcontractor vs original-contract billing
(RESEARCH Pitfall 1). ``discover_source_sheets`` rebinds
``SUBCONTRACTOR_SHEET_IDS`` (= ... | ...) and the two ``_FOLDER_DISCOVERED_*``
sets on each run; the facade always fetches the current binding.

Nested defs inside ``discover_source_sheets`` (``_validate_single_sheet``,
``_get_sample_rows``, ``_extract_col_samples``) are CLOSURES — they stay
nested (Pitfall 7), never hoisted to module level.

Symbols relocated from ``generate_weekly_pdfs.py`` (W3):
  discover_folder_sheets, _title, _normalize_column_title_for_vac_crew,
  discover_source_sheets,
  SUBCONTRACTOR_SHEET_IDS, _FOLDER_DISCOVERED_SUB_IDS, _FOLDER_DISCOVERED_ORIG_IDS
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import sentry_sdk

from pipeline.config import (
    DISCOVERY_CACHE_PATH,
    DISCOVERY_CACHE_TTL_MIN,
    DISCOVERY_CACHE_VERSION,
    PARALLEL_WORKERS_DISCOVERY,
    _parse_sheet_ids,
)
from pipeline.observability import (
    sentry_add_breadcrumb,
    sentry_capture_sheet_drop,
)
from pipeline.retry import smartsheet_call_with_retry

logger = logging.getLogger(__name__)

# ── Live-proxy globals (D-01) — served to the facade via __getattr__ ─────────
# GUARD: do NOT statically re-export these from the facade (see module docstring).
SUBCONTRACTOR_SHEET_IDS = set(_parse_sheet_ids(os.getenv('SUBCONTRACTOR_SHEET_IDS', '')))
# Module-level sets populated at runtime by discover_folder_sheets()
_FOLDER_DISCOVERED_SUB_IDS: set[int] = set()
_FOLDER_DISCOVERED_ORIG_IDS: set[int] = set()


def discover_folder_sheets(client, folder_ids: list[int], label: str) -> set[int]:
    """Discover all sheet IDs inside the given Smartsheet folders (recursively including subfolders).

    Args:
        client: Authenticated Smartsheet client instance.
        folder_ids: List of Smartsheet folder IDs to enumerate.
        label: Human-readable label for logging (e.g. 'subcontractor', 'original contract').

    Returns:
        Set of sheet IDs found across all folders and their subfolders.
    """
    discovered: set[int] = set()
    if not folder_ids:
        return discovered

    def _fetch_folder_recursive(fid, depth=0, max_depth=5):
        """Fetch sheets from a single folder, recursing into subfolders."""
        if depth > max_depth:
            logging.warning(f"⚠️ Max folder recursion depth ({max_depth}) reached for {label} folder {fid}")
            return set()
        try:
            with sentry_sdk.start_span(op="smartsheet.api", name=f"Get folder {fid} ({label} depth={depth})") as span:
                from smartsheet.models.sheet import Sheet as _SmartsheetSheet
                from smartsheet.models.folder import Folder as _SmartsheetFolder
                sheets: list = []
                subfolders: list = []
                last_key = None
                # Safety caps: guard against a misbehaving API that perpetually
                # returns a non-falsy or repeated last_key, which would otherwise
                # create a large API burst (amplifying Smartsheet 300 req/min limits).
                max_pages = 100
                pages_fetched = 0
                page_start_time = time.monotonic()
                seen_last_keys: set = set()
                for _page_num in range(max_pages):
                    page = smartsheet_call_with_retry(
                        client.Folders.get_folder_children,
                        fid,
                        children_resource_types=["sheets", "folders"],
                        last_key=last_key,
                        label=f"folder children {fid}",
                    )
                    pages_fetched += 1
                    for item in getattr(page, 'data', None) or []:
                        if isinstance(item, _SmartsheetSheet):
                            sheets.append(item)
                        elif isinstance(item, _SmartsheetFolder):
                            subfolders.append(item)
                    next_last_key = getattr(page, 'last_key', None)
                    if not next_last_key:
                        break
                    if next_last_key in seen_last_keys:
                        elapsed = time.monotonic() - page_start_time
                        logging.warning(
                            f"⚠️ Repeated pagination token detected for {label} folder {fid}; "
                            f"stopping after {pages_fetched} page(s) in {elapsed:.2f}s "
                            f"with {len(sheets)} sheet(s)"
                        )
                        break
                    seen_last_keys.add(next_last_key)
                    last_key = next_last_key
                else:
                    elapsed = time.monotonic() - page_start_time
                    logging.warning(
                        f"⚠️ Pagination safety cap ({max_pages}) reached for {label} folder {fid}; "
                        f"stopping after {pages_fetched} page(s) in {elapsed:.2f}s "
                        f"with {len(sheets)} sheet(s)"
                    )
                ids = {s.id for s in sheets}
                span.set_data("folder_id", fid)
                span.set_data("sheets_found", len(sheets))
                span.set_data("depth", depth)
            logging.info(f"{'  ' * depth}📂 Folder {fid} ({label}): found {len(sheets)} direct sheet(s)")
            # Recurse into subfolders to discover ALL sheets in the hierarchy
            for subfolder in subfolders:
                sub_id = subfolder.id
                sub_ids = _fetch_folder_recursive(sub_id, depth + 1, max_depth)
                if sub_ids:
                    logging.info(f"{'  ' * (depth + 1)}📁 Subfolder {sub_id}: contributed {len(sub_ids)} sheet(s)")
                ids |= sub_ids

            return ids
        except Exception as e:
            logging.warning(f"⚠️ Could not read {label} folder {fid}: {e}")
            sentry_add_breadcrumb("folder_discovery", f"Failed to read folder {fid}", level="error", data={
                "folder_id": fid, "label": label, "depth": depth, "error": str(e)[:200],
            })
            return set()

    with ThreadPoolExecutor(max_workers=min(len(folder_ids), PARALLEL_WORKERS_DISCOVERY)) as executor:
        for ids in executor.map(lambda fid: _fetch_folder_recursive(fid), folder_ids):
            discovered |= ids

    logging.info(f"📂 Total {label} folder discovery (recursive): {len(discovered)} unique sheet(s)")
    return discovered


def _title(t):
    return (t or "").strip().lower()


def _normalize_column_title_for_vac_crew(t):
    """Normalize a Smartsheet column title for fuzzy VAC Crew matching.

    Lowercases, canonicalises hyphenated (``vac-crew``) and joined-word
    (``vaccrew``) variants into the ``vac crew`` token, collapses runs of
    whitespace to a single space, and strips decorative trailing ``?`` or
    ``#`` (with optional surrounding spaces) so that operator-introduced
    variants like ``'Vac Crew Helping ?'``, ``'VAC CREW Helping?'``,
    ``'vac  crew helping'``, ``'Vac-Crew Helping?'``, ``'VacCrew Dept#'``
    or ``'Vac Crew Dept#'`` collapse to the same key as the canonical
    ``'VAC Crew Helping?'`` / ``'VAC Crew Dept #'``. Scoped intentionally
    narrow — only used by the VAC Crew fuzzy fallback in
    ``_validate_single_sheet`` — so primary/helper exact-match behaviour
    is preserved.
    """
    s = (t or "").strip().lower()
    # Hyphenated variants ('vac-crew') → space-separated.
    s = s.replace("-", " ")
    # Joined-word variants ('vaccrew') → space-separated. Word-boundary
    # guarded so unrelated tokens that happen to contain 'vaccrew' as a
    # substring are left untouched.
    s = re.sub(r"\bvaccrew\b", "vac crew", s)
    # Collapse any whitespace runs introduced by the substitutions above.
    s = re.sub(r"\s+", " ", s).strip()
    # Strip decorative trailing '?' / '#' with optional surrounding spaces.
    s = re.sub(r"\s*[\?#]+\s*$", "", s)
    return s


def discover_source_sheets(client):
    """Strict deterministic discovery: anchored keywords + type filtered. Skips sheets missing Weekly Reference Logged Date."""
    global _FOLDER_DISCOVERED_SUB_IDS, _FOLDER_DISCOVERED_ORIG_IDS, SUBCONTRACTOR_SHEET_IDS
    # Phase 09 W3 (D-01): bind the runtime-mutable discovery inputs from the
    # facade so test-time rebinds on generate_weekly_pdfs.NAME are honoured
    # (USE_DISCOVERY_CACHE / FORCE_REDISCOVERY / SUBCONTRACTOR_FOLDER_IDS /
    # ORIGINAL_CONTRACT_FOLDER_IDS are test-poked on the facade). The three set
    # globals (SUBCONTRACTOR_SHEET_IDS / _FOLDER_DISCOVERED_*) are this module's
    # own live-proxy globals, rebound above via the `global` statement.
    import generate_weekly_pdfs as _gwp  # noqa: PLC0415
    FORCE_REDISCOVERY = _gwp.FORCE_REDISCOVERY
    ORIGINAL_CONTRACT_FOLDER_IDS = _gwp.ORIGINAL_CONTRACT_FOLDER_IDS
    SUBCONTRACTOR_FOLDER_IDS = _gwp.SUBCONTRACTOR_FOLDER_IDS
    USE_DISCOVERY_CACHE = _gwp.USE_DISCOVERY_CACHE

    # ── ALWAYS run folder discovery FIRST (detects new sheets every run) ──────────
    # Folder listing is cheap (2-4 API calls + subfolder recursion).  Running it
    # unconditionally ensures sheets added to configured folders between runs are
    # detected even when the discovery cache is still within TTL.
    if SUBCONTRACTOR_FOLDER_IDS:
        _FOLDER_DISCOVERED_SUB_IDS = discover_folder_sheets(client, SUBCONTRACTOR_FOLDER_IDS, 'subcontractor')
        SUBCONTRACTOR_SHEET_IDS = SUBCONTRACTOR_SHEET_IDS | _FOLDER_DISCOVERED_SUB_IDS
        logging.info(f"📂 Subcontractor sheet IDs after folder merge: {len(SUBCONTRACTOR_SHEET_IDS)}")
    if ORIGINAL_CONTRACT_FOLDER_IDS:
        _FOLDER_DISCOVERED_ORIG_IDS = discover_folder_sheets(client, ORIGINAL_CONTRACT_FOLDER_IDS, 'original contract')
    _all_folder_discovered_ids = _FOLDER_DISCOVERED_SUB_IDS | _FOLDER_DISCOVERED_ORIG_IDS

    # ── Attempt cache load (skip when forced rediscovery requested) ──
    _cached_sheets = []          # previously-validated sheets from cache (used for incremental mode)
    _cached_sheet_ids = set()    # IDs of sheets already validated in cache
    _incremental = False         # True when cache expired but sheets can be reused
    if FORCE_REDISCOVERY:
        logging.info("🔄 FORCE_REDISCOVERY=true — bypassing discovery cache")
    elif USE_DISCOVERY_CACHE and os.path.exists(DISCOVERY_CACHE_PATH):
        try:
            with open(DISCOVERY_CACHE_PATH,'r') as f:
                cache = json.load(f)
            # Check cache schema version — invalidate if column synonyms have changed
            cached_version = cache.get('schema_version', 1)
            if cached_version < DISCOVERY_CACHE_VERSION:
                logging.info(f"🔄 Discovery cache schema outdated (v{cached_version} < v{DISCOVERY_CACHE_VERSION}) — forcing full rediscovery")
                raise ValueError('cache schema outdated')
            ts = datetime.datetime.fromisoformat(cache.get('timestamp'))
            age_min = (datetime.datetime.now() - ts).total_seconds()/60.0
            # Schema guard: each cached sheet must be a dict with an
            # integer ``id`` and a dict ``column_mapping`` — anything
            # else would crash ``_fetch_and_process_sheet`` when it
            # reads ``source['column_mapping']`` / ``source['id']``.
            # Drop malformed entries and WARN so operators can see
            # a corrupted cache immediately rather than debugging a
            # later AttributeError / KeyError.
            _raw_cached_sheets = cache.get('sheets', []) or []
            _valid_cached_sheets = [
                s for s in _raw_cached_sheets
                if isinstance(s, dict)
                and isinstance(s.get('id'), int)
                and isinstance(s.get('column_mapping'), dict)
                and isinstance(s.get('name'), str)
            ]
            if len(_valid_cached_sheets) != len(_raw_cached_sheets):
                logging.warning(
                    f"⚠️ Discovery cache contains "
                    f"{len(_raw_cached_sheets) - len(_valid_cached_sheets)} "
                    f"malformed sheet entry(ies); dropping them "
                    f"(keeping {len(_valid_cached_sheets)} valid). "
                    f"Delete {DISCOVERY_CACHE_PATH} to force a clean rediscovery."
                )
                # If *every* cached entry was malformed, the fresh-cache
                # return path below would otherwise hand back an empty
                # source list and the run would silently process zero
                # sheets. Escalate to the outer cache-load-failed handler
                # so we fall through to a full rediscovery from
                # ``base_sheet_ids`` — same behaviour as an outdated
                # schema or unreadable JSON.
                if _raw_cached_sheets and not _valid_cached_sheets:
                    raise ValueError(
                        f"all {len(_raw_cached_sheets)} cached sheet "
                        f"entries malformed; forcing full rediscovery"
                    )
            _cached_sheet_ids_from_file = {s['id'] for s in _valid_cached_sheets}
            # Compare folder-discovered sheet IDs against cache to detect new sheets
            _new_from_folders = _all_folder_discovered_ids - _cached_sheet_ids_from_file
            # Codex P2 guardrail: if the schema filter dropped ANY
            # entry, skip the fresh-cache fast path. A dropped entry
            # may have been a required static base sheet that isn't
            # in _all_folder_discovered_ids, so _new_from_folders
            # wouldn't flag it. Falling through to incremental mode
            # forces base_sheet_ids to be re-validated and the
            # dropped sheet to be rediscovered on this run instead
            # of waiting until cache expiry (up to
            # DISCOVERY_CACHE_TTL_MIN — default 7 days).
            _partial_cache_corruption = bool(_raw_cached_sheets) and (
                len(_valid_cached_sheets) != len(_raw_cached_sheets)
            )
            if (
                age_min <= DISCOVERY_CACHE_TTL_MIN
                and not _new_from_folders
                and not _partial_cache_corruption
            ):
                # Cache is fresh AND no new sheets in folders AND no
                # malformed entries were dropped → safe to use cache
                cached_sub_ids = cache.get('subcontractor_sheet_ids', [])
                if cached_sub_ids:
                    SUBCONTRACTOR_SHEET_IDS = SUBCONTRACTOR_SHEET_IDS | set(cached_sub_ids)
                    logging.info(f"📂 Restored {len(cached_sub_ids)} subcontractor sheet IDs from cache (total: {len(SUBCONTRACTOR_SHEET_IDS)})")
                logging.info(f"⚡ Using cached discovery ({age_min:.1f} min old) with {len(_valid_cached_sheets)} sheets (folders unchanged)")
                return _valid_cached_sheets
            else:
                # Cache expired OR new sheets found in folders → incremental mode
                _cached_sheets = _valid_cached_sheets
                _cached_sheet_ids = _cached_sheet_ids_from_file
                cached_sub_ids = cache.get('subcontractor_sheet_ids', [])
                if cached_sub_ids:
                    SUBCONTRACTOR_SHEET_IDS = SUBCONTRACTOR_SHEET_IDS | set(cached_sub_ids)
                _incremental = True
                if _partial_cache_corruption:
                    _dropped_count = (
                        len(_raw_cached_sheets) - len(_valid_cached_sheets)
                    )
                    logging.info(
                        f"🛡️ {_dropped_count} malformed cached entry(ies) "
                        f"dropped — forcing incremental revalidation against "
                        f"base_sheet_ids so any required sheet among the "
                        f"dropped entries is rediscovered this run instead "
                        f"of waiting until cache expiry."
                    )
                elif _new_from_folders:
                    logging.info(f"🆕 {len(_new_from_folders)} new sheet(s) detected in folders — "
                                 f"cache invalidated, using incremental mode "
                                 f"(keeping {len(_cached_sheets)} cached + validating new sheets)")
                else:
                    logging.info(f"ℹ️ Discovery cache expired ({age_min:.1f} min old); using incremental mode — "
                                 f"keeping {len(_cached_sheets)} cached sheets, scanning for new IDs only")
        except Exception as e:
            logging.info(f"Cache load failed, refreshing discovery: {e}")
    base_sheet_ids = [
        3239244454645636, 2230129632694148, 1732945426468740, 4126460034895748,
        7899446718189444, 1964558450118532, 5905527830695812, 820644963897220,
        8002920231423876, 2308525217763204,  # Added per user request
        5892629871939460, 
        3756603854507908, # Added Intake Promax
        5833510251089796,  # Added per user request
        5291853336235908,  # Added per user request
        6399146438119300, # Added per user request
        2582148201533316, # Added Resiliency Promax Database 16
        589443900592004, # Added Resiliency Promax Database 17
        7112742503665540, # Added Resiliency Promax Database 18
        8882702989086596, #Added Resiliency Promax Database 19
        2329343909908356, #Added Resiliency Promax Database 20
        5635469074190212, #Added Resiliency Promax Database 21
        5962351384678276, #Added Resiliency Promax Database 22
        3892736567496580, #Added Resiliency Promax Database 23
        4973034927509380, #Added Resiliency Promax Database 24
        1705871626162052, # Added Resiliency Promax Database 25
        5214601672085380, #  Added Resiliency Promax Database 26
        8551186744430468, # Added Resiliency Promax Database 27
        7820299006332804, # Added Resiliency Promax Database 28
        1153867531112324, # Added Resiliency Promax Database 29
        6692045306417028, # Added Resiliency Promax Database 30
        249276132183940, # Added Intake Promax 2
        2126238714908548, # Added Promax Database 31
        366100316376964, # Added Promax Database 32
        1207776467439492, # Added Promax Database 33
        342733613911940, # Added Promax Database 34
        6658677403504516, # Added Promax Database 35
        7043847386255236, # Added Promax Database 36
        2920263713771396, # Added Intake Promax 3
        4317397608517508, # Added Resiliency Promax 37
        277473162907524, # Added Resiliency Promax (New)
        1697214691757956, # Added Resiliency Promax 38
        8823469929090948, # Added Resiliency Promax 39
        692599695298436, #Added Resiliency Promax 40
        2183127494512516, #Added Resiliency Promax 42
        4774094567329668, #Added Resiliency Promax 41
        5067039388422020, #Adde Resiliency Promax 44
        888996134604676, #Added Resiliency Promax 43
        6920127724343172, #Added Resiliency Promax 45
        6587491768291204, #Added Intake Promax 4
        1804369797271428, #Added Resiliency Promax Database 46
        2873734244290436, #Added Resiliency Promax Database 47
        8153606260739972, #Added Resiliency Promax Database 48
        7630927397080964, #Added Resiliency Promax Database 49
        4017481216642948, #Added Resiliency Promax Database 50
        1326553209196420, #Added Resiliency Promax Database 51
        6479287751233412, #Added Resiliency Promax Database 52
        2672627970690948, #Added Resiliency Promax Database 53
        3800355386118020, #Added Intake Promax Database 5
        6123743714692996, #Added Resiliency Promax Database 54
        3804822152105860, #Added Resiliency Promax Database 55
        5065263654326148, #Added Resiliency Promax Database 56
        5417244814167940, #Added Resiliency Promax Database 57
        2431001297899396, #Added Resiliency Promax Database 58
        4085014678425476, #Added Intake Promax 6
        1080481698238340, #Added Resiliency Promax Database 59
        8391967734976388, #Added Resiliency Promax Database 60
        2233624515530628, #Added Resiliency Promax Database 61
        2780425391918980 #Added Resiliency Promax Database 62
        
        

    ]

    # OPTIONAL SPEED-UP FOR TESTING: allow overriding sheet list via env LIMITED_SHEET_IDS
    # Comma-separated list of numeric sheet IDs. If provided, we restrict discovery to only these.
    _limited_ids_raw = os.getenv('LIMITED_SHEET_IDS')
    if _limited_ids_raw:
        try:
            limited_ids = [int(x.strip()) for x in _limited_ids_raw.split(',') if x.strip()]
            if limited_ids:
                logging.info(f"⏩ LIMITED_SHEET_IDS override active ({len(limited_ids)} IDs); restricting discovery to provided list")
                base_sheet_ids = limited_ids
        except Exception as e:
            logging.warning(f"⚠️ LIMITED_SHEET_IDS parse failed '{_limited_ids_raw}': {e}")
    
    # Merge folder-discovered sheet IDs (populated unconditionally at top of function)
    _folder_ids = _FOLDER_DISCOVERED_SUB_IDS | _FOLDER_DISCOVERED_ORIG_IDS
    if _folder_ids:
        existing = set(base_sheet_ids)
        new_ids = _folder_ids - existing
        if new_ids:
            base_sheet_ids.extend(sorted(new_ids))
            logging.info(f"📂 Merged {len(new_ids)} folder-discovered sheet(s) into discovery list (total: {len(base_sheet_ids)})")
        else:
            logging.info(f"📂 All {len(_folder_ids)} folder-discovered sheet(s) already in base list")

    discovered = []

    def _validate_single_sheet(sid):
        """Validate a single sheet and return its discovery dict (or None if invalid)."""
        try:
            # PERFORMANCE FIX: Fetch only column metadata initially (no row data needed yet)
            # This prevents Error 4000 for large sheets during discovery phase
            # RESILIENCE FIX: retry transient API errors (residual 4000, server
            # timeout, network drop) so a single blip does not silently drop a
            # whole source sheet (and its billing rows). Bounded backoff.
            sheet = smartsheet_call_with_retry(
                client.Sheets.get_sheet, sid, include='columns',
                label=f"validate sheet {sid}",
            )
            cols = sheet.columns
            mapping = {}
            by_title = { _title(c.title): c for c in cols }
            # Exact matches
            w_exact = by_title.get(_title('Weekly Reference Logged Date'))
            s_exact = by_title.get(_title('Snapshot Date'))
            if w_exact: mapping['Weekly Reference Logged Date'] = w_exact.id
            if s_exact: mapping['Snapshot Date'] = s_exact.id
            # Date candidates
            date_candidates = [c for c in cols if str(c.type).upper() in ('DATE','DATETIME')]
            if 'Weekly Reference Logged Date' not in mapping:
                keyed = [c for c in date_candidates if 'date' in _title(c.title) and any(k in _title(c.title) for k in ('weekly','reference','logged','week ending'))]
                if keyed:
                    mapping['Weekly Reference Logged Date'] = keyed[0].id
            if 'Snapshot Date' not in mapping:
                keyed = [c for c in date_candidates if 'date' in _title(c.title) and 'snapshot' in _title(c.title)]
                if keyed:
                    mapping['Snapshot Date'] = keyed[0].id
            # Sample fallback — fetch sample rows ONCE for all column checks
            _sample_rows_cache = None
            def _get_sample_rows():
                nonlocal _sample_rows_cache
                if _sample_rows_cache is None:
                    try:
                        _sample_sheet = client.Sheets.get_sheet(sid, row_numbers=list(range(1, 4)))
                        _sample_rows_cache = _sample_sheet.rows if _sample_sheet.rows else []
                    except Exception:
                        _sample_rows_cache = []
                return _sample_rows_cache

            def _extract_col_samples(col_id):
                """Extract sample values for a column from the cached sample rows."""
                vals = []
                for row in _get_sample_rows():
                    for cell in row.cells:
                        if cell.column_id == col_id:
                            val = getattr(cell, 'value', None)
                            if val is None:
                                val = getattr(cell, 'display_value', None)
                            if val is not None:
                                vals.append(str(val))
                            break
                return vals

            if 'Weekly Reference Logged Date' not in mapping:
                for c in date_candidates:
                    t = _title(c.title)
                    if 'date' in t and any(k in t for k in ('weekly','reference','logged','week ending')):
                        samples = _extract_col_samples(c.id)
                        if any(re.match(r'^\d{4}-\d{2}-\d{2}', v) for v in samples):
                            mapping['Weekly Reference Logged Date'] = c.id
                            break
            if 'Snapshot Date' not in mapping:
                for c in date_candidates:
                    t = _title(c.title)
                    if 'date' in t and 'snapshot' in t:
                        samples = _extract_col_samples(c.id)
                        if any(re.match(r'^\d{4}-\d{2}-\d{2}', v) for v in samples):
                            mapping['Snapshot Date'] = c.id
                            break
            # Non-date synonyms
            synonyms = {
                'Foreman':'Foreman','Work Request #':'Work Request #','Dept #':'Dept #','Customer Name':'Customer Name','Work Order #':'Work Order #','Area':'Area',
                'Pole #':'Pole #','Point #':'Pole #','Point Number':'Pole #','CU':'CU','Billable Unit Code':'CU','Work Type':'Work Type','CU Description':'CU Description',
                'Unit Description':'CU Description','Unit of Measure':'Unit of Measure','UOM':'Unit of Measure','Quantity':'Quantity','Qty':'Quantity','# Units':'Quantity',
                'Units Total Price':'Units Total Price','Total Price':'Units Total Price','Redlined Total Price':'Units Total Price','Scope #':'Scope #','Scope ID':'Scope #',
                'Job #':'Job #','Units Completed?':'Units Completed?','Units Completed':'Units Completed?',
                # Helper variant columns (exact names with brackets as authoritative)
                'Helper Job [#]':'Helper Job #',  # Exact spelling with brackets
                'Helper Job':'Helper Job #',      # Fallback synonym
                'Helper Job #':'Helper Job #',    # Ensure direct exact match is captured
                'Helper Dept #':'Helper Dept #',
                'Foreman Helping?':'Foreman Helping?',
                'Helping Foreman Completed Unit?':'Helping Foreman Completed Unit?',
                # VAC Crew variant columns (row-level detection — mirrors helper pattern)
                'VAC Crew Helping?':'VAC Crew Helping?',
                'Vac Crew Helping?':'VAC Crew Helping?',          # Case variant
                'Vac Crew Completed Unit?':'Vac Crew Completed Unit?',
                'VAC Crew Completed Unit?':'Vac Crew Completed Unit?',  # Case variant
                'VAC Crew Dept #':'VAC Crew Dept #',
                'Vac Crew Dept #':'VAC Crew Dept #',              # Case variant
                'Vac Crew Job #':'Vac Crew Job #',
                'VAC Crew Job #':'Vac Crew Job #',                # Case variant
                'Vac Crew Email Address':'Vac Crew Email Address',
                'VAC Crew Email Address':'Vac Crew Email Address', # Case variant
            }
            # COLUMN MAPPING DEBUG: Log all column titles to verify helper and VAC Crew columns
            helper_columns_found = []
            vac_crew_columns_found = []
            for c in cols:
                # Check for helper-related columns specifically
                if 'Helper' in c.title or 'Helping' in c.title:
                    helper_columns_found.append(c.title)
                # Check for VAC Crew-related columns (case-insensitive so lowercase
                # or hyphenated variants like 'vac crew' / 'vac-crew' still surface
                # in logs and feed the fuzzy fallback pass below).
                _ct_lower = (c.title or '').lower()
                if 'vac crew' in _ct_lower or 'vaccrew' in _ct_lower or 'vac-crew' in _ct_lower:
                    vac_crew_columns_found.append(c.title)

                if c.title in synonyms and synonyms[c.title] not in mapping:
                    mapping[synonyms[c.title]] = c.id
                    # Log helper column mappings specifically
                    if 'Helper' in c.title:
                        logging.info(f"🔧 MAPPED HELPER COLUMN: '{c.title}' -> '{synonyms[c.title]}' (column ID: {c.id})")
                    # Log VAC Crew column mappings
                    if 'Vac Crew' in c.title or 'VAC Crew' in c.title:
                        logging.info(f"🚐 MAPPED VAC CREW COLUMN: '{c.title}' -> '{synonyms[c.title]}' (column ID: {c.id})")

            # ── VAC Crew column fuzzy fallback ──
            # The exact-match pass above only catches the two literal case variants
            # declared in `synonyms` (e.g. 'VAC Crew Helping?' and 'Vac Crew Helping?').
            # Operators occasionally introduce subtle variants on a new sheet —
            # trailing / leading whitespace, missing or extra '?', double internal
            # spaces, all-caps 'VAC CREW', all-lowercase 'vac crew' — and any such
            # variant silently fails to map. When the two KEY columns
            # ('VAC Crew Helping?' and 'Vac Crew Completed Unit?') aren't in
            # `mapping`, `sheet_has_vac_crew_columns` in _fetch_and_process_sheet
            # evaluates False and the row-level VAC Crew detection block is
            # skipped wholesale — the sheet produces zero _VacCrew Excel files
            # regardless of row content. This fallback runs ONLY when a canonical
            # VAC Crew key is missing, so helper/primary mappings are unaffected
            # and existing exact-match behaviour is preserved.
            _vac_crew_fuzzy_canonicals = [
                'VAC Crew Helping?',
                'Vac Crew Completed Unit?',
                'VAC Crew Dept #',
                'Vac Crew Job #',
                'Vac Crew Email Address',
            ]
            _already_mapped_ids = set(mapping.values())
            for _canonical in _vac_crew_fuzzy_canonicals:
                if _canonical in mapping:
                    continue
                _target_norm = _normalize_column_title_for_vac_crew(_canonical)
                for c in cols:
                    if c.id in _already_mapped_ids:
                        continue
                    if _normalize_column_title_for_vac_crew(c.title) == _target_norm:
                        mapping[_canonical] = c.id
                        _already_mapped_ids.add(c.id)
                        logging.warning(
                            f"🚐 VAC Crew column FUZZY-MATCHED on sheet ID {sid}: "
                            f"'{c.title}' -> '{_canonical}'. Consider adding '{c.title}' "
                            f"as an explicit synonym if this variant is permanent."
                        )
                        break

            # Log summary of helper columns found
            if helper_columns_found:
                logging.info(f"🔧 All helper/helping columns found in sheet: {helper_columns_found}")
            # Log summary of VAC Crew columns found
            if vac_crew_columns_found:
                logging.info(f"🚐 VAC Crew columns found in sheet: {vac_crew_columns_found}")

            # Actionable WARNING: VAC Crew-looking columns exist but the two key
            # mappings still didn't resolve after the fuzzy pass — detection will
            # be DISABLED for this sheet until the column titles are aligned with
            # `_vac_crew_fuzzy_canonicals`. Surface the raw titles so operators
            # can see exactly which variant is on the sheet.
            if vac_crew_columns_found and not (
                'VAC Crew Helping?' in mapping
                and 'Vac Crew Completed Unit?' in mapping
            ):
                logging.warning(
                    f"🚐⚠️ VAC Crew columns visible on sheet ID {sid} but key "
                    f"mappings incomplete after fuzzy pass: "
                    f"titles_seen={vac_crew_columns_found}, "
                    f"mapped_vac_crew_keys={[k for k in _vac_crew_fuzzy_canonicals if k in mapping]}. "
                    f"VAC Crew row detection will be DISABLED for this sheet until "
                    f"titles match a canonical form in _vac_crew_fuzzy_canonicals."
                )


            if 'Weekly Reference Logged Date' in mapping:
                w_id = mapping['Weekly Reference Logged Date']
                s_id = mapping.get('Snapshot Date')
                w_samples = _extract_col_samples(w_id)
                s_samples = _extract_col_samples(s_id) if s_id else []
                logging.info(f"Sheet {sheet.name} (ID {sid}) date columns:")
                logging.info(f"  Weekly Reference Logged Date (ID {w_id}) samples: {w_samples}")
                if s_id:
                    logging.info(f"  Snapshot Date (ID {s_id}) samples: {s_samples}")
                logging.info(f"✅ Added sheet: {sheet.name} (ID: {sid})")
                return {'id': sid,'name': sheet.name,'column_mapping': mapping}
            else:
                logging.warning(f"❌ Skipping sheet {sheet.name} (ID {sid}) - Weekly Reference Logged Date not found (strict mode)")
                return None
        except Exception as e:
            # Loud failure: a dropped source sheet = missing billing rows.
            # Transient errors were already retried (get_sheet above is wrapped
            # in smartsheet_call_with_retry), so a failure here is persistent.
            # Escalate to a SANITIZED Sentry capture (frame locals stripped) so
            # the drop is loud WITHOUT exfiltrating sampled row PII held in this
            # frame's locals (_sample_rows_cache etc.) — a raw capture_exception
            # would ship those because the SDK runs include_local_variables=True.
            logging.warning(f"⚡ Failed to validate sheet {sid}: {e}")
            sentry_capture_sheet_drop(sid, e)
            return None

    # ── Incremental mode: only validate NEW sheet IDs, keep cached ones ──
    if _incremental:
        all_base_ids = set(base_sheet_ids)
        new_ids_to_validate = sorted(all_base_ids - _cached_sheet_ids)
        if new_ids_to_validate:
            logging.info(f"🆕 Incremental discovery: {len(new_ids_to_validate)} new sheet ID(s) to validate "
                         f"(skipping {len(_cached_sheet_ids)} already-cached sheets)")
            _discovery_start = datetime.datetime.now()
            with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS_DISCOVERY) as executor:
                futures = {executor.submit(_validate_single_sheet, sid): sid for sid in new_ids_to_validate}
                for i, future in enumerate(as_completed(futures), 1):
                    sid = futures[future]
                    result = future.result()
                    if result is not None:
                        discovered.append(result)
                        logging.info(f"   ✅ [{i}/{len(futures)}] NEW Discovered: {result['name']} (ID: {sid})")
                    else:
                        logging.info(f"   ❌ [{i}/{len(futures)}] Skipped new sheet ID {sid}")
            _discovery_elapsed = (datetime.datetime.now() - _discovery_start).total_seconds()
            logging.info(f"⚡ Incremental discovery: {len(discovered)} new sheet(s) validated in {_discovery_elapsed:.1f}s")
        else:
            logging.info(f"⚡ Incremental discovery: no new sheet IDs found — all {len(_cached_sheet_ids)} sheets already cached")
        # Merge: cached sheets + newly discovered sheets
        discovered = _cached_sheets + discovered
        logging.info(f"📋 Total sheets after incremental merge: {len(discovered)} ({len(_cached_sheets)} cached + {len(discovered) - len(_cached_sheets)} new)")
    else:
        # Full discovery: validate all sheets from scratch
        logging.info(f"🚀 Starting parallel discovery with {PARALLEL_WORKERS_DISCOVERY} workers for {len(base_sheet_ids)} sheets...")
        _discovery_start = datetime.datetime.now()
        with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS_DISCOVERY) as executor:
            futures = {executor.submit(_validate_single_sheet, sid): sid for sid in base_sheet_ids}
            for i, future in enumerate(as_completed(futures), 1):
                sid = futures[future]
                result = future.result()
                if result is not None:
                    discovered.append(result)
                    logging.info(f"   ✅ [{i}/{len(futures)}] Discovered: {result['name']} (ID: {sid})")
                else:
                    logging.info(f"   ❌ [{i}/{len(futures)}] Skipped sheet ID {sid}")
        _discovery_elapsed = (datetime.datetime.now() - _discovery_start).total_seconds()
        logging.info(f"⚡ Discovery complete: {len(discovered)} sheets validated in {_discovery_elapsed:.1f}s (parallel w/{PARALLEL_WORKERS_DISCOVERY} workers)")
    # Save cache
    if USE_DISCOVERY_CACHE:
        try:
            with open(DISCOVERY_CACHE_PATH,'w') as f:
                json.dump({
                    'schema_version': DISCOVERY_CACHE_VERSION,
                    'timestamp': datetime.datetime.now().isoformat(),
                    'sheets': discovered,
                    'subcontractor_sheet_ids': sorted(SUBCONTRACTOR_SHEET_IDS),
                }, f)
        except Exception as e:
            logging.warning(f"Failed to write discovery cache: {e}")
    return discovered
