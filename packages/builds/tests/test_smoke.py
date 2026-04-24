"""Smoke test — package imports & version exposed."""

from __future__ import annotations

import poe1_builds


def test_package_imports() -> None:
    assert poe1_builds.__version__ == "0.1.0"
