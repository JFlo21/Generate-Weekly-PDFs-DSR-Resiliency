"""Regression tests for the PEP-562 facade live-proxy (Phase 09 W3, D-01 / SPEC Req#3).

The four runtime-rebound globals are EXCLUDED from the ``generate_weekly_pdfs``
facade's static namespace and served via a module-level ``__getattr__`` that
read-delegates to their owning submodule:

    SUBCONTRACTOR_SHEET_IDS       (owner: pipeline.discovery)
    _FOLDER_DISCOVERED_SUB_IDS    (owner: pipeline.discovery)
    _FOLDER_DISCOVERED_ORIG_IDS   (owner: pipeline.discovery)
    _RATES_FINGERPRINT            (owner: pipeline.fetch)

``gwp.NAME`` must therefore always reflect the owning submodule's *current*
binding (rebinds, e.g. ``SUBCONTRACTOR_SHEET_IDS = ... | ...`` after
``discover_source_sheets``) and the *same object identity* (in-place set
mutations, e.g. ``.add()/.clear()/.update()`` on ``_FOLDER_DISCOVERED_*``),
never a stale import-time copy.  Pitfall 1: a static re-export of any of these
names would bind the pre-run value and silently mis-classify subcontractor vs
original-contract billing.
"""
import generate_weekly_pdfs as gwp
import pipeline.discovery as discovery
import pipeline.fetch as fetch

LIVE_PROXY_NAMES = (
    "SUBCONTRACTOR_SHEET_IDS",
    "_FOLDER_DISCOVERED_SUB_IDS",
    "_FOLDER_DISCOVERED_ORIG_IDS",
    "_RATES_FINGERPRINT",
)


def test_subcontractor_sheet_ids_reflects_rebind():
    """A rebind of discovery.SUBCONTRACTOR_SHEET_IDS (new set object) is seen
    through the facade — this is the post-discovery merge path."""
    original = discovery.SUBCONTRACTOR_SHEET_IDS
    try:
        discovery.SUBCONTRACTOR_SHEET_IDS = original | {999_999}
        assert 999_999 in gwp.SUBCONTRACTOR_SHEET_IDS
        assert gwp.SUBCONTRACTOR_SHEET_IDS is discovery.SUBCONTRACTOR_SHEET_IDS
    finally:
        discovery.SUBCONTRACTOR_SHEET_IDS = original


def test_folder_discovered_sub_ids_inplace_mutation_propagates():
    """In-place .add()/.discard() via gwp mutates discovery's actual object
    (read-only delegation returns the object, not a copy)."""
    assert gwp._FOLDER_DISCOVERED_SUB_IDS is discovery._FOLDER_DISCOVERED_SUB_IDS
    snapshot = set(discovery._FOLDER_DISCOVERED_SUB_IDS)
    try:
        gwp._FOLDER_DISCOVERED_SUB_IDS.add(123_456)
        assert 123_456 in discovery._FOLDER_DISCOVERED_SUB_IDS
        gwp._FOLDER_DISCOVERED_SUB_IDS.discard(123_456)
        assert 123_456 not in discovery._FOLDER_DISCOVERED_SUB_IDS
    finally:
        discovery._FOLDER_DISCOVERED_SUB_IDS.clear()
        discovery._FOLDER_DISCOVERED_SUB_IDS.update(snapshot)


def test_folder_discovered_orig_ids_inplace_mutation_propagates():
    """Same in-place-mutation contract for the original-contract folder set."""
    assert gwp._FOLDER_DISCOVERED_ORIG_IDS is discovery._FOLDER_DISCOVERED_ORIG_IDS
    snapshot = set(discovery._FOLDER_DISCOVERED_ORIG_IDS)
    try:
        gwp._FOLDER_DISCOVERED_ORIG_IDS.add(654_321)
        assert 654_321 in discovery._FOLDER_DISCOVERED_ORIG_IDS
    finally:
        discovery._FOLDER_DISCOVERED_ORIG_IDS.clear()
        discovery._FOLDER_DISCOVERED_ORIG_IDS.update(snapshot)


def test_rates_fingerprint_reflects_rebind():
    """gwp._RATES_FINGERPRINT delegates to pipeline.fetch (immutable str rebind).

    Pop any facade-level shadow first: other suites (test_vac_crew,
    test_subcontractor_pricing) ASSIGN gwp._RATES_FINGERPRINT in setUp/tearDown,
    which writes a real entry into the facade __dict__ and would shadow the
    PEP-562 __getattr__.  Production never assigns on the facade, so popping the
    shadow reproduces the real delegation path (and we restore it afterwards).
    """
    had_shadow = "_RATES_FINGERPRINT" in gwp.__dict__
    shadow_val = gwp.__dict__.get("_RATES_FINGERPRINT")
    saved = fetch._RATES_FINGERPRINT
    try:
        gwp.__dict__.pop("_RATES_FINGERPRINT", None)
        fetch._RATES_FINGERPRINT = "live-proxy-sentinel"
        assert gwp._RATES_FINGERPRINT == "live-proxy-sentinel"
    finally:
        fetch._RATES_FINGERPRINT = saved
        if had_shadow:
            gwp._RATES_FINGERPRINT = shadow_val


def test_dir_includes_live_proxy_names():
    """__dir__ co-override keeps dir(gwp) + IDE autocomplete correct (D-01)."""
    names = set(dir(gwp))
    for n in LIVE_PROXY_NAMES:
        assert n in names, f"{n} missing from dir(gwp)"


def test_unknown_attribute_still_raises_attributeerror():
    """__getattr__ only delegates the four names; everything else raises."""
    import pytest

    with pytest.raises(AttributeError):
        gwp.__getattr__("this_name_does_not_exist_anywhere")
