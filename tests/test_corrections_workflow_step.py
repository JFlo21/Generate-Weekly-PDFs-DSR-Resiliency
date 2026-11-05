"""Regression fence for the weekly workflow's "Stage reporting corrections"
step (PR #453).

The step's ``run:`` block is read out of
``.github/workflows/weekly-excel-generation.yml`` as text and executed
under bash against a synthetic corrections file, so a later edit that
lets a missing required secret, a broken decode or a failed validation
reach "Generate reports" fails here. Fake data only
(``tests/_reporting_corrections_fixture.py``).
"""

from __future__ import annotations

import base64
import gzip
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests import _reporting_corrections_fixture as fx

_REPO = Path(__file__).resolve().parents[1]
_WORKFLOW = _REPO / '.github' / 'workflows' / 'weekly-excel-generation.yml'
_RUNBOOK = (_REPO / 'website' / 'docs' / 'runbook'
            / 'reporting-corrections.md')
_STEP = '      - name: Stage reporting corrections\n'
_NEXT = '      - name: Generate reports\n'
_PREV = '      - name: Parse advanced options\n'
_RUN = '        run: |\n'
_FILE = 'reporting_corrections.json'


def _text(path: Path) -> str:
    return path.read_text(encoding='utf-8').replace('\r\n', '\n')


def _step_text() -> str:
    """The step exactly as written, up to the next step."""
    workflow = _text(_WORKFLOW)
    start = workflow.index(_STEP)
    return workflow[start:workflow.index(_NEXT, start)]


def _step_script() -> str:
    """The ``run: |`` block, de-indented."""
    body = _step_text().split(_RUN, 1)[1]
    return ''.join(
        (line[10:] if line.startswith(' ' * 10) else line.lstrip(' '))
        for line in body.splitlines(keepends=True))


def _bash() -> str | None:
    """A POSIX bash. On Windows only Git's (``System32\\bash.exe`` is the
    WSL launcher and cannot see this checkout the same way)."""
    if os.name != 'nt':
        return shutil.which('bash')
    git = shutil.which('git')
    if not git:
        return None
    for rel in ('../bin/bash.exe', '../../bin/bash.exe',
                '../usr/bin/bash.exe', '../../usr/bin/bash.exe'):
        cand = (Path(git).parent / rel).resolve()
        if cand.exists():
            return str(cand)
    return None


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode('ascii')


_VALID = json.dumps(fx.correction_doc(), indent=1).encode('utf-8')
_INVALID = b'{"schema_version": 1, "corrections": "nope"}'


class StageStepStructureTests(unittest.TestCase):
    """What the step is wired to, read from the workflow text."""

    def test_step_sits_between_parse_options_and_generate_reports(self):
        workflow = _text(_WORKFLOW)
        self.assertEqual(workflow.count(_STEP), 1)
        names = [line for line in workflow.splitlines(keepends=True)
                 if line.startswith('      - name: ')]
        at = names.index(_STEP)
        self.assertEqual(names[at - 1], _PREV)
        self.assertEqual(names[at + 1], _NEXT)

    def test_step_runs_exactly_when_generate_reports_runs(self):
        workflow = _text(_WORKFLOW)
        after = workflow[workflow.index(_NEXT):].splitlines()
        cond = "        if: steps.exec.outputs.should_run == 'true'"
        self.assertEqual(after[1], cond)
        self.assertIn(cond + '\n', _step_text())

    def test_secret_and_variable_reach_the_script_through_env_only(self):
        step = _step_text()
        self.assertIn(
            '          CORRECTIONS_B64: '
            '${{ secrets.REPORTING_CORRECTIONS_JSON_B64 }}\n', step)
        self.assertIn(
            '          CORRECTIONS_REQUIRED: '
            '${{ vars.REPORTING_CORRECTIONS_REQUIRED }}\n', step)
        script = _step_script()
        self.assertNotIn('${{', script)
        self.assertNotIn('set -x', script)
        self.assertIn('set -euo pipefail', script)

    def test_validate_output_never_reaches_the_job_log(self):
        script = ' '.join(_step_script().split())
        self.assertIn(
            'python -m pipeline.reporting_corrections validate \\ '
            '--file "${path}" > /dev/null 2>&1 || status=$?', script)

    def test_runbook_carries_the_step_verbatim(self):
        runbook = _text(_RUNBOOK)
        head = '   ```yaml\n   ' + _STEP
        self.assertEqual(runbook.count(head), 1)
        start = runbook.index(head) + len('   ```yaml\n')
        block = runbook[start:runbook.index('   ```\n', start)]
        dedented = ''.join(
            line[3:] if line.startswith('   ') else line
            for line in block.splitlines(keepends=True))
        self.assertEqual(dedented, _step_text())


@unittest.skipIf(_bash() is None, 'no POSIX bash available')
class StageStepBehaviourTests(unittest.TestCase):
    """The step script executed under bash."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.script = self.root / 'step.sh'
        self.script.write_bytes(_step_script().encode('utf-8'))

    def _run(self, secret: str, required: str = ''):
        """Return (exit code, exported path or None, files left, log)."""
        runner_temp = self.root / f'rt{len(list(self.root.iterdir()))}'
        runner_temp.mkdir()
        github_env = runner_temp.with_suffix('.env')
        github_env.write_bytes(b'')
        env = {k: v for k, v in os.environ.items()
               if k != 'REPORTING_CORRECTIONS_FILE'}
        env.update({
            'RUNNER_TEMP': runner_temp.as_posix(),
            'GITHUB_ENV': github_env.as_posix(),
            'CORRECTIONS_B64': secret,
            'CORRECTIONS_REQUIRED': required,
            'PYTHONUTF8': '1',
            # the step calls bare ``python``: make it this interpreter
            'PATH': (os.path.dirname(sys.executable) + os.pathsep
                     + env.get('PATH', '')),
        })
        bash = _bash()
        assert bash is not None
        proc = subprocess.run(
            [bash, self.script.as_posix()], cwd=str(_REPO), env=env,
            capture_output=True, text=True, encoding='utf-8',
            errors='replace', timeout=120, check=False)
        exported = None
        for line in github_env.read_text(encoding='utf-8').splitlines():
            if line.startswith('REPORTING_CORRECTIONS_FILE='):
                exported = line.split('=', 1)[1]
        left = sorted(p.name for p in runner_temp.iterdir())
        return (proc.returncode, exported, left,
                proc.stdout + proc.stderr, runner_temp)

    def test_empty_secret_is_feature_off_unless_required(self):
        for required, code in (('', 0), ('false', 0), ('no', 0),
                               ('true', 1), ('TRUE', 1), ('True', 1)):
            with self.subTest(required=required):
                rc, exported, left, log, _ = self._run('', required)
                self.assertEqual(rc, code, log)
                self.assertIsNone(exported)
                self.assertEqual(left, [])
                marker = '::error::' if code else 'feature off'
                self.assertIn(marker, log)

    def test_valid_file_is_staged_plain_gzipped_and_line_wrapped(self):
        packed = _b64(gzip.compress(_VALID))
        wrapped = '\r\n'.join(
            packed[i:i + 76] for i in range(0, len(packed), 76)) + '\r\n'
        for label, secret in (('plain', _b64(_VALID)),
                              ('gzip', packed),
                              ('gzip wrapped', wrapped)):
            with self.subTest(secret=label):
                rc, exported, left, log, runner_temp = self._run(
                    secret, 'true')
                self.assertEqual(rc, 0, log)
                self.assertEqual(left, [_FILE])
                staged = runner_temp / _FILE
                self.assertEqual(staged.read_bytes(), _VALID)
                self.assertEqual(exported, staged.as_posix())
                self.assertIn('file validated and staged', log)
                self.assertNotIn(fx.WR, log)

    def test_unusable_secret_fails_and_exports_nothing(self):
        packed = gzip.compress(_VALID)
        cases = (
            ('not base64', '@@@not-base64@@@',
             'secret is not valid base64'),
            ('invalid file', _b64(_INVALID), 'validate failed'),
            ('invalid file gzipped', _b64(gzip.compress(_INVALID)),
             'validate failed'),
            ('truncated base64', _b64(_VALID)[:400], 'validate failed'),
            ('truncated gzip', _b64(packed[:len(packed) // 2]),
             'validate failed'),
        )
        for label, secret, message in cases:
            for required in ('', 'true'):
                with self.subTest(secret=label, required=required):
                    rc, exported, left, log, _ = self._run(
                        secret, required)
                    self.assertEqual(rc, 1, log)
                    self.assertIsNone(exported)
                    self.assertEqual(left, [])
                    self.assertIn('::error::Reporting corrections: '
                                  + message, log)
                    self.assertNotIn(fx.WR, log)


if __name__ == '__main__':
    unittest.main()
