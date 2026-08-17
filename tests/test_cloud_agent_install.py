"""Guards the Cloud Agent install script against the portal/ cd footgun."""

from pathlib import Path
import json
import stat

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "cloud-agent-install.sh"
ENV_JSON = REPO_ROOT / ".cursor" / "environment.json"


def test_install_script_exists_and_is_executable() -> None:
    """The bootstrap script must be present and executable."""
    assert SCRIPT.is_file()
    mode = SCRIPT.stat().st_mode
    assert mode & stat.S_IXUSR


def test_install_script_does_not_unconditionally_cd_portal() -> None:
    """Unconditional ``cd portal`` is what failed bld-20260817-c08508ed."""
    text = SCRIPT.read_text(encoding="utf-8")
    code_lines = [
        line
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert all("cd portal" not in line for line in code_lines)
    assert "install_npm_tree portal" in text
    assert "package.json" in text
    assert "requirements.txt" in text
    assert "set -euo pipefail" in text


def test_environment_json_points_at_install_script() -> None:
    """Repo-managed Cloud Agent install must call the skip-safe script."""
    environment = json.loads(ENV_JSON.read_text(encoding="utf-8"))
    assert environment["install"] == "./scripts/cloud-agent-install.sh"
    assert "cd portal" not in environment["install"]
