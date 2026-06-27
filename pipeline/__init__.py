"""pipeline — billing engine subpackage.

This package will receive the relocated modules of the production billing
engine across Phase-09 waves 1-6. It is imported by the
``generate_weekly_pdfs`` facade, which re-exports all public names.

Do NOT import from this package directly in production code — use
``import generate_weekly_pdfs`` or ``from generate_weekly_pdfs import X``.

Intentionally EMPTY: no re-exports, no ``from pipeline.X import *``, and
no import-time side effects. The facade (``generate_weekly_pdfs.py``) owns
the entire public API surface; ``pipeline/__init__.py`` staying empty
prevents implicit coupling and keeps wave imports acyclic.
"""
