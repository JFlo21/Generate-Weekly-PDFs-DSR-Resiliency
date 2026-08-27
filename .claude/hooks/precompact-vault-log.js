#!/usr/bin/env node
// project-hook: precompact-vault-log v1.0.0  (Generate-Weekly-PDFs-DSR-Resiliency)
// Event: PreCompact (auto + manual — no matcher). Wired from .claude/settings.local.json.
// Purpose: BEFORE any compaction, append a dated checkpoint entry to Juan's second
//          brain (`<vault>/wiki/log.md`) and park a write-back packet in
//          `.claude/writeback-pending/` so the post-compaction session applies the
//          fuller project-page write-back (the model cannot run inside a hook, so the
//          hook records deterministic facts only: project-state headline, files
//          touched this session, pointer to the global compact-handoff distillate).
// Complements (does not replace) the global ~/.claude/hooks/precompact-handoff.js,
// which distils transcript state to ~/.claude/compact-handoff/<session_id>.md and
// continuity-on-compact.js, which re-injects it after the compaction.
// Contract: read-only on the repo except .claude/writeback-pending/; appends only to
//           the vault log (never edits/deletes); truncated excerpts only; drops lines
//           that look like key/token material; fails OPEN (always exit 0).
// Dry run: PRECOMPACT_VAULT_DRY_RUN=1 prints what it would write and writes nothing.
// Vault override: MORPHEUS_VAULT=<path to my-wiki>.

'use strict';
const fs = require('fs');
const path = require('path');
const os = require('os');

const PROJECT_SLUG = 'Generate-Weekly-PDFs-DSR-Resiliency';
const PROJECT_DIR = process.env.CLAUDE_PROJECT_DIR || process.cwd();
const DRY = process.env.PRECOMPACT_VAULT_DRY_RUN === '1';
const MAX_FILES = 25;
const HANDOFF_WAIT_MS = 8000; // global precompact-handoff.js runs in parallel; give it a moment

function resolveVault() {
  if (process.env.MORPHEUS_VAULT) return process.env.MORPHEUS_VAULT;
  const home = os.homedir();
  const candidates = process.platform === 'win32'
    ? [path.join(home, 'OneDrive - Centuri Group, Inc', 'Documents', 'my-wiki')]
    : [path.join(home, 'Library', 'CloudStorage', 'OneDrive-CenturiGroup,Inc', 'Documents', 'my-wiki')];
  return candidates.find((p) => fs.existsSync(path.join(p, 'wiki', 'log.md'))) || null;
}

function looksSecret(s) {
  return /(api[_-]?key|secret|token|password|service_role|bearer\s+[a-z0-9._-]{20,}|ey[A-Za-z0-9_-]{30,})/i.test(s);
}
function clean(s, n) {
  s = String(s || '').split('\n').filter((l) => !looksSecret(l)).join('\n').replace(/\s+/g, ' ').trim();
  return s.length > n ? s.slice(0, n) + ' …' : s;
}
function pad(n) { return String(n).padStart(2, '0'); }
function localStamp(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
function dateOnly(d) { return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; }

function projectStateHeadline() {
  try {
    const t = fs.readFileSync(path.join(PROJECT_DIR, '.claude', 'project-state.md'), 'utf8');
    // project-state.md is overwritten in place each session: the "## Latest work (…)"
    // heading is the one-line current status; the "_Latest ledger entry: …_" paragraph
    // carries the fuller state with the CURRENT part at its END ("Next: …").
    const heading = clean((t.split('\n').find((l) => l.startsWith('## Latest work')) || '').replace(/^## /, ''), 300);
    const m = t.match(/_Latest ledger entry:([\s\S]*?)\n[ \t]*\n/);
    const tail = m ? clean(m[1].replace(/_\s*$/, ''), 100000) : '';
    const tailPart = tail ? (tail.length > 500 ? '… ' + tail.slice(-500) : tail) : '';
    return [heading, tailPart].filter(Boolean).join(' | ');
  } catch { return ''; }
}

function filesTouched(sessionId) {
  try {
    const lines = fs.readFileSync(path.join(PROJECT_DIR, '.claude', 'session-delta.jsonl'), 'utf8').split('\n');
    const seen = new Set();
    for (const l of lines) {
      if (!l.trim()) continue;
      try {
        const o = JSON.parse(l);
        if (sessionId && o.session && o.session !== sessionId) continue;
        if (o.file) seen.add(String(o.file).replace(/\\/g, '/'));
      } catch { /* skip */ }
    }
    return [...seen];
  } catch { return []; }
}

function nextLogId(logText, today) {
  const re = new RegExp(`^## \\[${today}([a-z])\\]`, 'gm');
  let last = '';
  let m;
  while ((m = re.exec(logText))) last = m[1];
  const next = last ? String.fromCharCode(last.charCodeAt(0) + 1) : 'a';
  return `${today}${next <= 'z' ? next : 'z'}`;
}

function waitForHandoff(sessionId) {
  const p = path.join(os.homedir(), '.claude', 'compact-handoff', `${sessionId}.md`);
  const start = Date.now();
  while (Date.now() - start < HANDOFF_WAIT_MS) {
    try {
      const st = fs.statSync(p);
      if (Date.now() - st.mtimeMs < 5 * 60 * 1000) return p; // fresh from this compaction
    } catch { /* not yet */ }
    Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 500);
  }
  return fs.existsSync(p) ? p : null;
}

function main(data) {
  const sessionId = String(data.session_id || 'unknown').replace(/[^A-Za-z0-9_-]/g, '_');
  const trigger = String(data.trigger || 'unknown');
  const now = new Date();
  const vault = resolveVault();
  const headline = projectStateHeadline();
  const files = filesTouched(sessionId);
  const handoffPath = DRY ? null : waitForHandoff(sessionId);

  const packetName = `precompact-${dateOnly(now).replace(/-/g, '')}-${pad(now.getHours())}${pad(now.getMinutes())}.md`;
  const packetPath = path.join(PROJECT_DIR, '.claude', 'writeback-pending', packetName);

  const fileList = files.slice(0, MAX_FILES).map((f) => `  - \`${f}\``).join('\n') || '  - (none recorded)';
  const more = files.length > MAX_FILES ? `\n  - … +${files.length - MAX_FILES} more` : '';

  const logBody =
    `Auto-compact checkpoint (trigger: ${trigger}, session ${sessionId.slice(0, 8)}, ${localStamp(now)} local). ` +
    `Repo state at compaction: ${headline || '(project-state.md headline unavailable)'} ` +
    `Files touched this session: ${files.length}${files.length ? ' — ' + files.slice(0, 8).map((f) => '`' + f + '`').join(', ') + (files.length > 8 ? ', …' : '') : ''}. ` +
    `Distilled task state: ${handoffPath ? '`~/.claude/compact-handoff/' + sessionId + '.md`' : '(global compact-handoff not present yet)'}; ` +
    `write-back packet parked at \`.claude/writeback-pending/${packetName}\` for the post-compaction session to apply to \`projects/${PROJECT_SLUG}.md\`.`;

  const packet = [
    `# Write-back packet — pre-compaction checkpoint`,
    ``,
    `- **Project page:** \`wiki/projects/${PROJECT_SLUG}.md\``,
    `- **Created:** ${now.toISOString()} (trigger: ${trigger}, session ${sessionId})`,
    `- **Log entry:** already appended to \`wiki/log.md\` by \`.claude/hooks/precompact-vault-log.js\` — do not duplicate it; write the project-page section, then delete this packet.`,
    `- **Distilled task state:** ${handoffPath ? '`' + handoffPath.replace(/\\/g, '/') + '`' : '(not present — reconstruct from .claude/project-state.md)'}`,
    ``,
    `## Repo state headline (from .claude/project-state.md)`,
    ``,
    headline || '(unavailable)',
    ``,
    `## Files touched this session (.claude/session-delta.jsonl)`,
    ``,
    fileList + more,
    ``,
    `## Instruction for the main session`,
    ``,
    `Synthesize what changed · why it matters · where the project stands · next actions into a dated`,
    `subsection of the project page (append before "## Related pages & skills"), bump \`updated:\`,`,
    `then remove this packet. Never paste secrets, env values, or raw chat.`,
    ``,
  ].join('\n');

  const out = { systemMessage: '' };

  if (!vault) {
    out.systemMessage = 'precompact-vault-log: vault not found — wrote write-back packet only.';
    if (!DRY) { fs.mkdirSync(path.dirname(packetPath), { recursive: true }); fs.writeFileSync(packetPath, packet, 'utf8'); }
    else process.stderr.write(`[dry-run] packet -> ${packetPath}\n${packet}\n`);
    return out;
  }

  const logPath = path.join(vault, 'wiki', 'log.md');
  const logText = fs.readFileSync(logPath, 'utf8');
  const id = nextLogId(logText, dateOnly(now));
  const entry = `\n## [${id}] project | ${PROJECT_SLUG} — auto-compact checkpoint (${trigger})\n${logBody}\n`;

  if (DRY) {
    process.stderr.write(`[dry-run] would append to ${logPath}:${entry}\n[dry-run] packet -> ${packetPath}\n${packet}\n`);
    out.systemMessage = `precompact-vault-log [dry-run]: would append [${id}] to wiki/log.md and park ${packetName}.`;
    return out;
  }

  fs.appendFileSync(logPath, entry, 'utf8');
  fs.mkdirSync(path.dirname(packetPath), { recursive: true });
  fs.writeFileSync(packetPath, packet, 'utf8');
  out.systemMessage = `Second brain checkpoint [${id}] appended to wiki/log.md; write-back packet ${packetName} parked for after compaction.`;
  return out;
}

let input = '';
const stdinTimeout = setTimeout(() => { finish({}); }, 12000);
process.stdin.setEncoding('utf8');
process.stdin.on('data', (c) => (input += c));
process.stdin.on('end', () => { clearTimeout(stdinTimeout); let d = {}; try { d = JSON.parse(input || '{}'); } catch { /* fail open */ } finish(d); });

function finish(data) {
  let out = { systemMessage: 'precompact-vault-log: skipped (error)' };
  try { out = main(data) || out; } catch (e) { out.systemMessage = `precompact-vault-log: skipped (${(e && e.message) || 'error'})`; }
  try { process.stdout.write(JSON.stringify(out)); } catch { /* ignore */ }
  process.exit(0);
}
