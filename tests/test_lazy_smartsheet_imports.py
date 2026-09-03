"""WR-01 (Phase 12 plan 02, dated 2026-09-03):

``pipeline/orchestrate.py`` previously imported the deep Smartsheet SDK
enum path ``smartsheet.models.enums.attachment_parent_type`` at module
scope, so a future SDK relocation would break import of the production
entry module instead of degrading one helper. The import now lives
inside ``_is_row_attachment``'s own body, function-local and guarded,
mirroring ``pipeline/discovery.py``'s guarded function-local
``smartsheet.models.*`` import pattern.

This module pins both halves of the fix with a structural test (the
import is gone from the module preamble and present in the function
body) and behavioral tests exercising ``_is_row_attachment`` against a
real enum member, the plain string spelling, ``None``, and non-ROW
parent types.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.test_billing_audit_shadow import (  # noqa: E402
    _collapse_ws,
    _ensure_smartsheet_mocked,
    _read_source,
)

_ensure_smartsheet_mocked()

import pipeline.orchestrate as orchestrate  # noqa: E402


def _preamble_source() -> str:
    """Everything above the first top-level ``def`` in orchestrate.py."""
    src = _read_source("pipeline/orchestrate.py")
    lines = src.splitlines(keepends=True)
    preamble: list[str] = []
    for line in lines:
        if line.startswith("def "):
            break
        preamble.append(line)
    return "".join(preamble)


def _function_source(func_name: str) -> str:
    """Source of one top-level function, from its ``def`` line to the
    next top-level ``def`` (or end of file)."""
    src = _read_source("pipeline/orchestrate.py")
    lines = src.splitlines(keepends=True)
    start = None
    for idx, line in enumerate(lines):
        if line.startswith(f"def {func_name}("):
            start = idx
            break
    assert start is not None, f"{func_name} not found in orchestrate.py"
    end = len(lines)
    for idx in range(start + 1, len(lines)):
        if lines[idx].startswith("def "):
            end = idx
            break
    return "".join(lines[start:end])


class StructuralImportPlacementTests(unittest.TestCase):
    def test_preamble_has_no_module_level_attachment_parent_type_import(self) -> None:
        preamble = _collapse_ws(_preamble_source())
        self.assertNotIn(
            "from smartsheet.models.enums.attachment_parent_type import",
            preamble,
        )

    def test_is_row_attachment_body_imports_attachment_parent_type_locally(self) -> None:
        body = _collapse_ws(_function_source("_is_row_attachment"))
        self.assertIn(
            "from smartsheet.models.enums.attachment_parent_type import",
            body,
        )
        self.assertIn("noqa: PLC0415", body)


class _FakeAttachment:
    def __init__(self, parent_type):
        self.parent_type = parent_type


class IsRowAttachmentBehaviorTests(unittest.TestCase):
    def test_true_for_real_enum_member(self) -> None:
        from smartsheet.models.enums.attachment_parent_type import (
            AttachmentParentType,
        )
        att = _FakeAttachment(AttachmentParentType.ROW)
        self.assertTrue(orchestrate._is_row_attachment(att))

    def test_true_for_plain_string_row(self) -> None:
        att = _FakeAttachment('ROW')
        self.assertTrue(orchestrate._is_row_attachment(att))

    def test_false_for_none_parent_type(self) -> None:
        att = _FakeAttachment(None)
        self.assertFalse(orchestrate._is_row_attachment(att))

    def test_false_for_sheet_parent_type(self) -> None:
        att = _FakeAttachment('SHEET')
        self.assertFalse(orchestrate._is_row_attachment(att))

    def test_false_for_comment_parent_type(self) -> None:
        att = _FakeAttachment('COMMENT')
        self.assertFalse(orchestrate._is_row_attachment(att))

    def test_degrades_to_string_comparison_when_import_unavailable(self) -> None:
        """If the deep SDK path is unavailable, _is_row_attachment must
        degrade to the plain string comparison instead of raising, and
        the module must still import (WR-01 fail-safe)."""
        import builtins

        real_import = builtins.__import__

        def _blocking_import(name, *args, **kwargs):
            if name == "smartsheet.models.enums.attachment_parent_type":
                raise ImportError("simulated SDK relocation")
            return real_import(name, *args, **kwargs)

        att_row_string = _FakeAttachment('ROW')
        att_sheet_string = _FakeAttachment('SHEET')
        with mock.patch.object(
            builtins, "__import__", side_effect=_blocking_import
        ):
            self.assertTrue(orchestrate._is_row_attachment(att_row_string))
            self.assertFalse(orchestrate._is_row_attachment(att_sheet_string))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
