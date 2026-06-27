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
