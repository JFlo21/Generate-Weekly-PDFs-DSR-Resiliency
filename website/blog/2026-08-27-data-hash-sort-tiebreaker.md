---
slug: data-hash-sort-tiebreaker
title: "Change detection: deterministic row order ends the every-run re-upload of tie groups"
authors: [runbook-bot]
tags: [github, project, python, tests]
date: 2026-08-27T22:00:00+00:00
---

**Component:** Python billing pipeline (`generate_weekly_pdfs.py` →
`pipeline/change_detection.py`). **Change type:** change-detection
primitive — sort-order determinism only; the hashed content is unchanged.
**PR:** #359, following #358 (parity comparator) and #356 (client init).

<!-- truncate -->

## What changed

`calculate_data_hash()` sorts a group's rows before hashing them. In
extended mode (the production default) the sort key now ends with the
row's own hashed-field string and its foreman as a **tiebreaker**, so two
rows that share the whole `(WR, Snapshot Date, CU, Pole/Point, Quantity)`
key are ordered by their content instead of by whichever source sheet
happened to finish fetching first. Legacy mode
(`EXTENDED_CHANGE_DETECTION=0`) is untouched, as its rollback-stability
guarantee requires.

## Why

`WR 17451333 / week 080226` was regenerated, its prior attachment
deleted, and a new file uploaded on **every** run since 2026-08-25 — 12
consecutive runs — while nothing in its data changed. Its 142 rows come
from three source sheets; two of them tie on the sort key but differ in a
hashed field, and Python's stable sort kept the parallel fetch's arrival
order, so the group's hash alternated between two values with thread
timing. The durable hash store is rewritten each run, so the next run
always saw a "change".

Besides the wasted delete + upload, this blocked Phase 11: the shadow
parity comparator saw a group the full path regenerated that the
row-hash-driven incremental path never would — a permanent
`only_in_actual`, so the five-run `pass` streak could not start even after
#358. The VAC-crew tiebreaker added earlier had closed the same failure
class for crew fields only.

## What operators will see

- **First run after merge:** a one-time bump in "hash changed"
  regenerations, bounded by the groups that were already flipping
  (`billing_audit.pipeline_run` shows them as alternating hashes with a
  constant `assignment_fp`). Each is uploaded once more and then stable.
  A bump materially larger than that population is the signal to revert.
- **Second run onward:** `⏩ Skip (unchanged + attachment exists) primary
  WR 17451333 week 080226`, and `pipeline_memory.group_state.content_hash`
  for such groups stops changing between runs.
- Groups that never had a tie are unaffected — byte-identical hashes, no
  regeneration. A test pins that guarantee against the pre-fix ordering.

## Rollback

Revert #359. Hashes return to the previous (order-dependent) values; tie
groups resume flipping, everything else is unchanged.
