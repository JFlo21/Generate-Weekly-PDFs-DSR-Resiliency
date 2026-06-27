"""Direct-execution entry-point regression test (Phase 09 / Greptile P1).

Running ``python generate_weekly_pdfs.py`` loads the file as ``__main__``, so
``sys.modules['generate_weekly_pdfs']`` is unset. The facade-read prelude in
``pipeline.orchestrate`` (``import generate_weekly_pdfs as _gwp``, executed when
``main()`` runs) would then re-import the facade from scratch and re-run every
top-level startup banner + ``init_sentry()`` — a duplicate-log / observability
regression introduced by the engine split. The entry block aliases the
already-initialized ``__main__`` module under its import name to prevent the
re-import; this test pins that the startup banner is emitted exactly once.
"""

import os
import subprocess
import sys
import unittest


class TestEntrypointNoDoubleImport(unittest.TestCase):

    def test_startup_banner_printed_once(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = dict(os.environ)
        env['TEST_MODE'] = 'true'          # synthetic in-memory dataset
        env['SKIP_UPLOAD'] = 'true'        # no Smartsheet writes
        env['PYTHONUTF8'] = '1'            # emoji banners on Windows cp1252
        env['PYTHONIOENCODING'] = 'utf-8'
        env.pop('SMARTSHEET_API_TOKEN', None)  # force the synthetic path

        result = subprocess.run(
            [sys.executable, 'generate_weekly_pdfs.py'],
            cwd=repo_root, env=env,
            capture_output=True, text=True, timeout=180,
        )
        combined = result.stdout + result.stderr
        count = combined.count('CRITICAL FIXES APPLIED')
        self.assertEqual(
            count, 1,
            f'startup banner printed {count}x (expected 1) -- the facade is '
            f'being re-imported when run as __main__.\n'
            f'--- tail of output ---\n{combined[-1500:]}',
        )


if __name__ == '__main__':
    unittest.main()
