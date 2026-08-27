#!/usr/bin/env node
// project-hook: precompact-vault-log v1.1.1  (Generate-Weekly-PDFs-DSR-Resiliency)
// Event: PreCompact (auto + manual — no matcher).
// Installation: INTENTIONALLY LOCAL-ONLY. This hook writes to Juan's personal
//          second brain (OneDrive `my-wiki`), so it is wired from the gitignored
//          `.claude/settings.local.json` on each of Juan's machines — never from a
//          tracked settings file, which would run it for every collaborator and
//          cloud agent that clones the repo. A fresh checkout gets the source only.
//          To install on a machine (idempotent, merges into an existing file):
//              node .claude/hooks/precompact-vault-log.js --install
//          then open `/hooks` once (or restart) so Claude Code reloads settings.
//          See .claude/writeback-pending/README.md.
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
// Packets: `precompact-<YYYYMMDD>-<HHMMSS>-<session8>-<pid>[-N].md`, created with
//          exclusive `wx` semantics and a retry suffix, so two PreCompact events
//          (parallel sessions, or auto + manual within the same minute) can never
//          overwrite each other's pending context (Greptile, PR #355).
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

// Reserve a packet path exclusively (O_EXCL) so a concurrent invocation can
// never truncate ours: on EEXIST, try `-1`, `-2`, ... The content is written
// later into the file we own. Returns the reserved path.
function reservePacket(dir, base) {
  fs.mkdirSync(dir, { recursive: true });
  for (let i = 0; i < 100; i++) {
    const p = path.join(dir, `${base}${i ? '-' + i : ''}.md`);
    try {
      fs.closeSync(fs.openSync(p, 'wx'));
      return p;
    } catch (e) {
      if (!e || e.code !== 'EEXIST') throw e;
    }
  }
  throw new Error('could not reserve a unique packet name after 100 attempts');
}

function timeStamp(d) { return `${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`; }

// `--install`: merge the PreCompact declaration into .claude/settings.local.json
// (gitignored, per-machine). Idempotent; never clobbers a file it cannot parse.
function installHook() {
  const settingsPath = path.join(PROJECT_DIR, '.claude', 'settings.local.json');
  const command = 'node "${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/precompact-vault-log.js"';
  let settings = {};
  if (fs.existsSync(settingsPath)) {
    try { settings = JSON.parse(fs.readFileSync(settingsPath, 'utf8')) || {}; }
    catch (e) {
      process.stdout.write(`precompact-vault-log --install: ${settingsPath} is not valid JSON (${e.message}); not touching it.\n`);
      return;
    }
  }
  settings.hooks = settings.hooks && typeof settings.hooks === 'object' ? settings.hooks : {};
  const pre = Array.isArray(settings.hooks.PreCompact) ? settings.hooks.PreCompact : [];
  const already = pre.some((g) => Array.isArray(g && g.hooks) && g.hooks.some((h) => typeof (h && h.command) === 'string' && h.command.includes('precompact-vault-log.js')));
  if (already) {
    process.stdout.write(`precompact-vault-log --install: already wired in ${settingsPath}; nothing to do.\n`);
    return;
  }
  pre.push({ hooks: [{ type: 'command', command, timeout: 30, statusMessage: 'Logging checkpoint to second brain before compaction…' }] });
  settings.hooks.PreCompact = pre;
  fs.mkdirSync(path.dirname(settingsPath), { recursive: true });
  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2) + '\n', 'utf8');
  process.stdout.write(`precompact-vault-log --install: PreCompact hook added to ${settingsPath}. Open /hooks once (or restart) to reload.\n`);
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

  // Invocation-unique name, reserved exclusively BEFORE the text that cites it
  // is composed (the retry suffix, if any, must appear in the log entry too).
  const packetDir = path.join(PROJECT_DIR, '.claude', 'writeback-pending');
  const packetBase = `precompact-${dateOnly(now).replace(/-/g, '')}-${timeStamp(now)}-${sessionId.slice(0, 8)}-${process.pid}`;
  const packetPath = DRY ? path.join(packetDir, `${packetBase}.md`) : reservePacket(packetDir, packetBase);
  const packetName = path.basename(packetPath);

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
    if (!DRY) fs.writeFileSync(packetPath, packet, 'utf8'); // path reserved exclusively above
    else process.stderr.write(`[dry-run] packet -> ${packetPath}\n${packet}\n`);
    return out;
  }

  const logPath = path.join(vault, 'wiki', 'log.md');
  const makeEntry = (logText, idSuffix = '') => {
    const id = nextLogId(logText, dateOnly(now)) + idSuffix;
    return { id, entry: `\n## [${id}] project | ${PROJECT_SLUG} — auto-compact checkpoint (${trigger})\n${logBody}\n` };
  };

  if (DRY) {
    const { id, entry } = makeEntry(fs.readFileSync(logPath, 'utf8'));
    process.stderr.write(`[dry-run] would append to ${logPath}:${entry}\n[dry-run] packet -> ${packetPath}\n${packet}\n`);
    out.systemMessage = `precompact-vault-log [dry-run]: would append [${id}] to wiki/log.md and park ${packetName}.`;
    return out;
  }

  // The letter-suffix id is derived from the log's current tail, so the
  // read-id + append pair must be atomic across concurrent sessions or two
  // compactions in the same second both claim e.g. [2026-08-27a]. Serialize
  // with a `wx` lock file (orphaned locks are reclaimed after
  // LOG_LOCK_STALE_MS). Still fail OPEN if the lock cannot be owned within
  // LOG_LOCK_WAIT_MS -- but then a letter id read without the lock could
  // duplicate another session's, so the entry gets a collision-proof id
  // (`-unlocked-<pid>` suffix) instead of a possibly-duplicate one
  // (Greptile, PR #355). Such ids never advance the letter sequence.
  const { id, unlocked } = withLogLock(logPath, (locked) => {
    const made = makeEntry(fs.readFileSync(logPath, 'utf8'), locked ? '' : `-unlocked-${process.pid}`);
    fs.appendFileSync(logPath, made.entry, 'utf8');
    return { ...made, unlocked: !locked };
  });
  fs.writeFileSync(packetPath, packet, 'utf8'); // path reserved exclusively above
  out.systemMessage = `Second brain checkpoint [${id}] appended to wiki/log.md; write-back packet ${packetName} parked for after compaction.`
    + (unlocked ? ' (log lock could not be owned — id made collision-proof)' : '');
  return out;
}

// Budget: the hook runs under a 30 s timeout; HANDOFF_WAIT_MS (8 s) + this
// wait + I/O stays inside it. A holder's critical section is milliseconds,
// so any lock older than LOG_LOCK_STALE_MS is an orphan and is reclaimed
// inside the wait loop -- the timeout path is reachable only when the
// filesystem refuses both creation and reclaim.
const LOG_LOCK_WAIT_MS = 15000;
const LOG_LOCK_STALE_MS = 10000;
// Calls fn(held): held === true means this invocation OWNS the lock; false
// means the wait expired (or an unexpected FS error) and fn must not assume
// serialization.
function withLogLock(logPath, fn) {
  const lockPath = logPath + '.precompact.lock';
  const start = Date.now();
  let held = false;
  while (!held && Date.now() - start < LOG_LOCK_WAIT_MS) {
    try {
      fs.closeSync(fs.openSync(lockPath, 'wx'));
      held = true;
    } catch (e) {
      if (!e || e.code !== 'EEXIST') break; // unexpected FS error: proceed unlocked
      try { // orphaned lock (crashed holder): reclaim and retry immediately
        if (Date.now() - fs.statSync(lockPath).mtimeMs > LOG_LOCK_STALE_MS) { fs.unlinkSync(lockPath); continue; }
      } catch { /* vanished or unreadable: retry */ }
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 50);
    }
  }
  try { return fn(held); }
  finally { if (held) { try { fs.unlinkSync(lockPath); } catch { /* ignore */ } } }
}

if (process.argv.includes('--install')) {
  try { installHook(); } catch (e) { process.stdout.write(`precompact-vault-log --install: failed (${(e && e.message) || 'error'})\n`); }
  process.exit(0);
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
