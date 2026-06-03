"""Static verifier for Task 2 (Sentry cron + run-mode tags) and Task 3 (ledger).

Run:  python .planning/quick/260603-mmc-fix-missing-old-rates-csv-default-fileno/verify_sentry_mods.py
Optional flag --with-ledger also asserts the Living Ledger entry exists.
Exit 0 = all assertions pass.  Used by Task 2 / Task 3 <verify> and final <verification>.
"""
import re
import sys

s = open("generate_weekly_pdfs.py", encoding="utf-8").read()

checks = [
    ("corrected cron schedule present",
     "0 13,15,17,19,21,23,1 * * 1-5" in s),
    ("corrected timezone present",
     "America/Chicago" in s),
    ("stale timezone removed",
     "America/Phoenix" not in s),
    ("stale Monday-only schedule removed",
     '"30 17 * * 1"' not in s),
    ("run-mode tag res_grouping_mode added",
     'set_tag("res_grouping_mode"' in s),
    ("wr_filter_active is a BOOL (no raw WR list leak)",
     'set_tag("wr_filter_active", str(bool(WR_FILTER)))' in s),
    ("force_generation tag added",
     'set_tag("force_generation"' in s),
    ("existing run-summary set_context preserved (not re-added)",
     s.count('set_context("session_summary"') == 1),
    ("existence guard added to loaders",
     s.count("os.path.isfile") >= 2),
    ("benign skip path uses INFO, not error, for absent CSV",
     "Rate CSV not present, skipping load" in s),
    ("fingerprinted rate-load failure",
     '"rate-csv-load-failure"' in s),
    ("redaction used for exception text in context",
     "_redact_exception_message(e)" in s),
    ("sentry-sdk floor NOT bumped / no banned APIs",
     "set_measurement" not in s),
    # PART D: confirm the pre-existing PII leak (raw WR list -> Sentry) is closed.
    # The old key must not appear as live code (a comment explaining the old value is ok).
    # Regex: no non-comment line has "wr_filter": WR_FILTER as a dict entry.
    ("raw WR list no longer in set_context configuration (PII leak closed)",
     not any(
         line.strip() and not line.strip().startswith('#')
         and '"wr_filter": WR_FILTER' in line
         for line in s.splitlines()
     )),
    ("wr_filter_active bool present in configuration context",
     '"wr_filter_active": bool(WR_FILTER)' in s),
    ("wr_filter_count int present in configuration context",
     '"wr_filter_count": len(WR_FILTER)' in s),
]

if "--with-ledger" in sys.argv:
    led = open("memory-bank/living-ledger.md", encoding="utf-8").read()
    checks.append((
        "Living Ledger has a dated entry mentioning the rate CSV change",
        ("rate csv" in led.lower())
        and bool(re.search(r"\[20\d\d-\d\d-\d\d \d\d:\d\d\]", led))
        and ("os.path.isfile" in led or "optional" in led.lower()),
    ))

failed = [name for name, ok in checks if not ok]
for name, ok in checks:
    print(("PASS" if ok else "FAIL"), "-", name)
if failed:
    print("\nFAILED:", len(failed))
    sys.exit(1)
print("\nALL PASS")
