# generated_docs

Runtime output directory for generated weekly Excel reports and audit/cache artifacts.

Not committed artifacts (ignored by .gitignore):
- *.xlsx (report files)
- audit_state.json (rolling audit state)
- discovery_cache.json (ephemeral sheet discovery cache)

Safe to clear; pipeline recreates as needed.
