"""Guards the Cloud Agent install script against the portal/ cd footgun."""

from pathlib import Path
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
    assert "cd portal" not in text
    assert "install_npm_tree portal" in text
    assert "package.json" in text
    assert "requirements.txt" in text
    assert "set -euo pipefail" in text


def test_environment_json_points_at_install_script() -> None:
    """Repo-managed Cloud Agent install must call the skip-safe script."""
    text = ENV_JSON.read_text(encoding="utf-8")
    assert "cloud-agent-install.sh" in text
    assert "cd portal" not in text
