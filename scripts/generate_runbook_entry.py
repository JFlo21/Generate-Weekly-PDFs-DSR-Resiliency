#!/usr/bin/env python3
"""Generate a Docusaurus blog post summarizing a push to master.

Invoked by .github/workflows/docs-changelog.yml. Reads the push range from
environment variables, buckets the changed files by area, lists commit
subjects, and writes a Markdown file under website/blog/.

Exits 0 on success (post written) and 0 with no post when there is nothing
to report (empty diff, merge skip marker, initial push with no `before`
SHA). Non-zero exit is reserved for genuine failures so the workflow
surfaces them.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BLOG_DIR = REPO_ROOT / "website" / "blog"
SKIP_MARKERS = ("[skip docs]", "[docs skip]")

# (label, predicate) — first match wins, so ordering matters.
BUCKETS: list[tuple[str, Callable[[str], bool]]] = [
    ("Workflows & CI", lambda p: p.startswith(".github/workflows/") or p == "azure-pipelines.yml"),
    ("GitHub config", lambda p: p.startswith(".github/") and not p.startswith(".github/workflows/")),
    ("Python — entry points", lambda p: p in {
        "generate_weekly_pdfs.py",
        "audit_billing_changes.py",
        "run_info.py",
        "validate_system_health.py",
    }),
    ("Python — diagnostics", lambda p: p.endswith(".py") and p.startswith(("analyze_", "diagnose_", "cleanup_", "test_"))),
    ("Python — scripts/", lambda p: p.startswith("scripts/") and p.endswith(".py")),
    ("Tests", lambda p: p.startswith("tests/")),
    ("Portal (Express)", lambda p: p.startswith("portal/")),
    ("Portal v2 (React)", lambda p: p.startswith("portal-v2/")),
    ("Docs site", lambda p: p.startswith("website/")),
    ("Project docs", lambda p: p.endswith(".md") or p.startswith("docs/")),
    ("Configuration", lambda p: p.endswith((".yml", ".yaml", ".json", ".toml", ".ini", ".cfg", ".env.example", ".env.template"))),
    ("Data files", lambda p: p.endswith((".csv", ".xlsx", ".png", ".jpg", ".jpeg", ".gif"))),
]


@dataclass
class PushContext:
    before: str
    after: str
    branch: str
    repo: str
    run_url: str | None
    pusher: str | None


def load_context() -> PushContext:
    return PushContext(
        before=os.environ.get("GITHUB_EVENT_BEFORE", "").strip(),
        after=os.environ.get("GITHUB_SHA", "").strip(),
        branch=os.environ.get("GITHUB_REF_NAME", "master").strip(),
        repo=os.environ.get("GITHUB_REPOSITORY", "").strip(),
        run_url=os.environ.get("GITHUB_RUN_URL") or None,
        pusher=os.environ.get("GITHUB_ACTOR") or None,
    )


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def is_zero_sha(sha: str) -> bool:
    return not sha or set(sha) <= {"0"}


def resolve_range(before: str, after: str) -> tuple[str | None, str]:
    """Resolve the base/head pair used for diff + log across the push.

    - A real `before` SHA is used as-is.
    - When `before` is empty/zero (e.g. `workflow_dispatch`, where
      `github.event.before` is undefined), fall back to the first parent
      of `after` so merge commits enumerate the PR's actual changes.
    - If `after` is a root commit with no parent, return `(None, after)`
      so callers can pick a sensible fallback.
    """
    if not is_zero_sha(before):
        return before, after
    try:
        parent = run_git("rev-parse", f"{after}^1")
    except subprocess.CalledProcessError:
        return None, after
    return parent, after


def changed_files(before: str, after: str) -> list[str]:
    base, head = resolve_range(before, after)
    if base is None:
        # Root commit — list the whole tree so the caller still has a
        # usable file set to bucket and report on.
        diff = run_git("ls-tree", "-r", "--name-only", head)
    else:
        diff = run_git("diff", "--name-only", f"{base}..{head}")
    return sorted({line for line in diff.splitlines() if line.strip()})


def commits_in_range(before: str, after: str) -> list[tuple[str, str]]:
    base, head = resolve_range(before, after)
    if base is None:
        log = run_git("log", "--pretty=format:%h%x1f%s", "-n", "1", head)
    else:
        log = run_git("log", "--pretty=format:%h%x1f%s", f"{base}..{head}")
    commits: list[tuple[str, str]] = []
    for line in log.splitlines():
        if "\x1f" not in line:
            continue
        sha, subject = line.split("\x1f", 1)
        commits.append((sha.strip(), subject.strip()))
    return commits


def skip_markers_in_range(before: str, after: str) -> bool:
    """Scan commit messages in the resolved push range for a skip marker."""
    base, head = resolve_range(before, after)
    if base is None:
        messages = run_git("log", "-n", "1", "--pretty=%B", head)
    else:
        messages = run_git("log", "--pretty=%B", f"{base}..{head}")
    return any(marker in messages for marker in SKIP_MARKERS)


def bucket_files(files: list[str]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {label: [] for label, _ in BUCKETS}
    buckets["Other"] = []
    for f in files:
        placed = False
        for label, matches in BUCKETS:
            if matches(f):
                buckets[label].append(f)
                placed = True
                break
        if not placed:
            buckets["Other"].append(f)
    return {k: v for k, v in buckets.items() if v}


def slugify(text: str, max_len: int = 40) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\s-]", "", text).strip().lower()
    cleaned = re.sub(r"[\s-]+", "-", cleaned)
    return cleaned[:max_len].strip("-") or "update"


def build_post(ctx: PushContext, files: list[str], commits: list[tuple[str, str]]) -> tuple[Path, str]:
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    short_sha = ctx.after[:7] or "unknown"
    headline_subject = commits[0][1] if commits else "Repository update"
    slug = f"{short_sha}-{slugify(headline_subject)}"
    filename = BLOG_DIR / f"{date_str}-{slug}.md"

    buckets = bucket_files(files)

    tags = sorted({label.lower().split()[0] for label in buckets.keys()})

    lines: list[str] = []
    lines.append("---")
    lines.append(f"slug: {slug}")
    title = f"{headline_subject} ({short_sha})"
    # YAML double-quoted strings interpret backslashes as escape characters,
    # so escape `\` first and then `"` to keep the frontmatter valid for
    # commit subjects that contain either.
    title_safe = title.replace("\\", "\\\\").replace('"', '\\"')
    lines.append(f'title: "{title_safe}"')
    lines.append("authors: [runbook-bot]")
    if tags:
        lines.append(f"tags: [{', '.join(tags)}]")
    lines.append(f"date: {now.isoformat()}")
    lines.append("---")
    lines.append("")
    lines.append(f"**Branch:** `{ctx.branch}` &middot; **Commit:** "
                 f"[`{short_sha}`](https://github.com/{ctx.repo}/commit/{ctx.after})"
                 + (f" &middot; **Pusher:** `{ctx.pusher}`" if ctx.pusher else ""))
    if ctx.run_url:
        lines.append(f"  \n[View the workflow run]({ctx.run_url}).")
    lines.append("")
    lines.append("<!-- truncate -->")
    lines.append("")

    if commits:
        lines.append("## Commits in this push")
        lines.append("")
        for sha, subject in commits:
            subject_md = subject.replace("|", "\\|")
            lines.append(
                f"- [`{sha}`](https://github.com/{ctx.repo}/commit/{sha}) — {subject_md}"
            )
        lines.append("")

    if buckets:
        lines.append("## Changed files")
        lines.append("")
        for label, paths in buckets.items():
            lines.append(f"### {label}")
            lines.append("")
            for p in paths:
                lines.append(f"- `{p}`")
            lines.append("")
    else:
        lines.append("_No file-level changes detected in this push._")
        lines.append("")

    return filename, "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ctx = load_context()
    if not ctx.after:
        print("GITHUB_SHA is empty; nothing to document.", file=sys.stderr)
        return 0

    # Check every commit in the resolved push range for a skip marker so
    # that `[skip docs]` on any non-HEAD commit is honored — but the scan
    # is scoped to the same range as `changed_files`, not the branch's
    # last 20 commits.
    if skip_markers_in_range(ctx.before, ctx.after):
        print("Skip marker present in push range; not writing a post.")
        return 0

    files = changed_files(ctx.before, ctx.after)
    # Don't churn a post for commits that only touch the blog itself.
    meaningful = [f for f in files if not f.startswith("website/blog/")]
    if not meaningful:
        print("Push only touched website/blog/; skipping to avoid a feedback loop.")
        return 0

    commits = commits_in_range(ctx.before, ctx.after)
    BLOG_DIR.mkdir(parents=True, exist_ok=True)
    path, body = build_post(ctx, files, commits)
    path.write_text(body, encoding="utf-8")
    rel_path = path.relative_to(REPO_ROOT)
    print(f"Wrote {rel_path}")

    # Emit the post path on stdout so the caller (the workflow) can forward
    # it to $GITHUB_OUTPUT. Writing to $GITHUB_OUTPUT from Python opens a
    # filesystem path sourced from an environment variable, which static
    # analyzers flag even though the runner controls that path.
    print(f"POST_PATH={rel_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
