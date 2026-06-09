#!/usr/bin/env python3
"""
Rotate GitHub Webhook Secret

Generates a new cryptographically secure webhook secret and updates it on
the specified GitHub repository webhook via the GitHub REST API.

Usage:
    GITHUB_TOKEN=ghp_xxx python scripts/rotate_webhook_secret.py
    GITHUB_TOKEN=ghp_xxx python scripts/rotate_webhook_secret.py --hook-id 570410297

Requirements:
    - GITHUB_TOKEN environment variable with admin:repo_hook scope
    - No external dependencies (stdlib only)

Background:
    Created in response to GitHub security notification GH-9951654-7992-a1
    regarding webhook secret exposure via X-GitHub-Encoded-Secret header
    (September-December 2025). See: https://docs.github.com/en/webhooks/using-webhooks/editing-webhooks
"""

import argparse
import json
import os
import secrets
import stat
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

OWNER = "JFlo21"
REPO = "Generate-Weekly-PDFs-DSR-Resiliency"
DEFAULT_HOOK_ID = "570410297"


def rotate_webhook_secret(hook_id, token, owner, repo):
    """Rotate the webhook secret for the given hook ID.

    Returns the new secret on success, or exits on failure.
    """
    new_secret = secrets.token_hex(32)

    # Use the /config endpoint for partial updates to avoid overwriting
    # the webhook's url, content_type, or insecure_ssl settings
    url = f"https://api.github.com/repos/{owner}/{repo}/hooks/{hook_id}/config"

    payload = json.dumps({
        "secret": new_secret,
    }).encode("utf-8")

    req = Request(url, data=payload, method="PATCH", headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
        "User-Agent": "LinetecWebhookRotation/1.0",
    })

    try:
        with urlopen(req, timeout=30) as resp:
            if resp.status == 200:
                return new_secret
            body = resp.read().decode("utf-8", errors="replace")
            print(f"Unexpected response status {resp.status}: {body}", file=sys.stderr)
            sys.exit(1)
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        if e.code == 404:
            print(f"Webhook {hook_id} not found. Verify the hook ID and that the "
                  f"token has admin:repo_hook scope.", file=sys.stderr)
        elif e.code == 401 or e.code == 403:
            print(f"Authentication failed (HTTP {e.code}). Ensure GITHUB_TOKEN has "
                  f"admin:repo_hook scope.", file=sys.stderr)
        else:
            print(f"GitHub API error (HTTP {e.code}): {body}", file=sys.stderr)
        sys.exit(1)
    except (URLError, TimeoutError) as e:
        print(f"Network error: {e}", file=sys.stderr)
        print("Check your internet connection and try again.", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Rotate the webhook secret for a GitHub repository webhook."
    )
    parser.add_argument(
        "--hook-id",
        default=DEFAULT_HOOK_ID,
        help=f"Webhook hook ID to rotate (default: {DEFAULT_HOOK_ID})",
    )
    parser.add_argument(
        "--owner",
        default=OWNER,
        help=f"Repository owner (default: {OWNER})",
    )
    parser.add_argument(
        "--repo",
        default=REPO,
        help=f"Repository name (default: {REPO})",
    )
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("Error: GITHUB_TOKEN environment variable is required.", file=sys.stderr)
        print("The token must have admin:repo_hook scope.", file=sys.stderr)
        sys.exit(1)

    owner = args.owner
    repo = args.repo

    print(f"Rotating webhook secret for {owner}/{repo} hook {args.hook_id}...")
    new_secret = rotate_webhook_secret(args.hook_id, token, owner, repo)

    # Write the new secret to a temporary file with owner-only read permissions
    # to avoid leaking it in terminal scrollback, CI logs, or shell history
    fd, secret_path = tempfile.mkstemp(prefix="webhook_secret_", suffix=".txt")
    try:
        os.write(fd, new_secret.encode("utf-8"))
    finally:
        os.close(fd)
    os.chmod(secret_path, stat.S_IRUSR)

    print()
    print("=" * 64)
    print("  Webhook secret rotated successfully!")
    print("=" * 64)
    print()
    print(f"  New secret saved to: {secret_path}")
    print(f"  Read it with: cat {secret_path}")
    print()
    print("  Next steps:")
    print("  1. Copy the secret from the file above into your password manager")
    print("  2. Update WEBHOOK_SECRET in your .env file if applicable")
    print("  3. Update any systems that validate webhook signatures")
    print(f"  4. Delete the file: rm {secret_path}")
    print("  5. Do NOT commit the secret to version control")
    print()
    print("=" * 64)


if __name__ == "__main__":
    main()
