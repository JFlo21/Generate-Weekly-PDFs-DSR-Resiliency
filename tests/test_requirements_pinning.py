from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SENTRY_REQUIREMENT = "sentry-sdk==2.35.0"


def test_sentry_sdk_is_exactly_pinned_in_requirements() -> None:
    lines = (
        REPO_ROOT / "requirements.txt"
    ).read_text(encoding="utf-8").splitlines()

    sentry_lines = [
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith("#")
        and line.strip().startswith("sentry-sdk")
    ]

    assert sentry_lines == [EXPECTED_SENTRY_REQUIREMENT]
