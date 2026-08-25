#!/usr/bin/env bash
# Idempotent Cloud Agent / environment-build bootstrap.
#
# Recurring dashboard installs failed after 03153c3 (2026-06-02)
# removed portal/: the saved command was
#   pip install -r requirements.txt
#   cd portal && npm install
# which exits 1 with `cd: portal: No such file or directory`.
# Only run npm when that app tree still exists.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

export PATH="${HOME}/.local/bin:${PATH}"

echo "Installing Python dependencies from requirements.txt"
python3 -m pip install --user -r requirements.txt

install_npm_tree() {
    local dir="$1"
    if [ -f "${dir}/package.json" ]; then
        echo "Installing npm dependencies in ${dir}/"
        if [ -f "${dir}/package-lock.json" ]; then
            npm --prefix "${dir}" ci
        else
            npm --prefix "${dir}" install
        fi
    else
        echo "Skipping ${dir}/ (package.json not present)"
    fi
}

install_npm_tree portal
install_npm_tree portal-v2
