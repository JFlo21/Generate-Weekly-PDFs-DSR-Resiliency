# Write-back pending (second-brain packets)

Parking spot for **Second-Brain Write-Back Packets**. When a repo-scoped subagent
produces durable, cross-session knowledge (architecture decisions, incident
root-causes, new operational rules), it drops a `<topic>.md` packet here instead
of editing the OneDrive `my-wiki` vault directly (subagents are denied vault
writes by directory scoping).

The **main session** then applies the packet to the vault via the
`global-second-brain-writeback-bridge` / `global-context-continuity` skills and
deletes it. This directory should normally be empty (just this README).

**Never** place secrets, tokens, API keys, or `.env` values in a packet — the
`audit_vault_writes.js` hook records every vault write path for audit.

## Pre-compaction checkpoint packets (`precompact-*.md`)

`.claude/hooks/precompact-vault-log.js` is a **PreCompact** hook that, before
any context compaction, appends a dated checkpoint to the second brain's
`wiki/log.md` and parks a `precompact-<YYYYMMDD>-<HHMMSS>-<session8>-<pid>.md`
packet here for the post-compaction session to apply and delete. Names are
invocation-unique and created exclusively (`wx` + retry suffix), so concurrent
sessions never overwrite each other's packet.

The hook is **intentionally local-only**: it writes to Juan's personal OneDrive
vault, so it is wired from the gitignored `.claude/settings.local.json` on each
of his machines — never from a tracked settings file, which would run it for
every collaborator and cloud agent. A fresh checkout gets the source only. To
install on a machine (idempotent; merges into an existing file):

```bash
node .claude/hooks/precompact-vault-log.js --install
```

then open `/hooks` once (or restart Claude Code) so settings reload. Dry run:
`PRECOMPACT_VAULT_DRY_RUN=1`. Without a reachable vault the hook still parks
the packet and always exits 0 (fail-open).
