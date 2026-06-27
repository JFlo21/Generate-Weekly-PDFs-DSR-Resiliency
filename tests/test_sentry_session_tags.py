"""Phase 09 Wave 1 (post-review regression): guard the Sentry-CONFIGURED path
of ``pipeline.observability._set_sentry_session_tags``.

The Wave 1 relocation (commit ``0a945b7``) mis-indented
``from pipeline import config as _cfg`` *under* the ``if not SENTRY_DSN:
return`` guard, making the import unreachable whenever Sentry IS configured.
On that path the function then evaluates ``_cfg.TEST_MODE`` with ``_cfg``
undefined -> ``NameError`` (shielded by the call-site ``try`` in the facade,
so session tags silently never apply).

The original 6-gate oracle missed it: every other Sentry test forces
``SENTRY_DSN`` empty, so the early ``return`` fires and the buggy path never
runs. This test forces ``SENTRY_DSN`` truthy and asserts the three session
tags are applied from ``pipeline.config`` without raising -- closing the
oracle blind spot.
"""
from datetime import datetime
from unittest import mock

import pipeline.config as cfg
import pipeline.observability as obs


def test_set_sentry_session_tags_applies_config_tags_when_dsn_configured():
    """With SENTRY_DSN set, the function must import pipeline.config and tag the
    isolation scope (session_start/test_mode/github_actions) without NameError."""
    captured: dict[str, str] = {}

    class _RecordingScope:
        def set_tag(self, key, value):
            captured[key] = value

    dsn = "https://examplePublicKey@o0.ingest.sentry.io/0"
    session_start = datetime(2026, 1, 1, 12, 0, 0)
    with mock.patch.object(obs, "SENTRY_DSN", dsn), mock.patch.object(
        obs.sentry_sdk, "get_isolation_scope", return_value=_RecordingScope()
    ):
        obs._set_sentry_session_tags(session_start)

    assert captured["session_start"] == session_start.isoformat()
    assert captured["test_mode"] == str(cfg.TEST_MODE)
    assert captured["github_actions"] == str(cfg.GITHUB_ACTIONS_MODE)


def test_set_sentry_session_tags_noops_when_dsn_absent():
    """When SENTRY_DSN is empty the function returns early and touches no scope."""
    with mock.patch.object(obs, "SENTRY_DSN", ""), mock.patch.object(
        obs.sentry_sdk, "get_isolation_scope"
    ) as m_scope:
        obs._set_sentry_session_tags(datetime(2026, 1, 1, 12, 0, 0))
    m_scope.assert_not_called()
