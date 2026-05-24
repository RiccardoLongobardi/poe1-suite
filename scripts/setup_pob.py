"""Fetch the Path of Building runtime for the local/offline tree optimiser.

The Theorycrafter's "deep" optimiser (Steps 50+) evaluates candidate
builds with PoB's *own* calc engine for exact stats. PoB ships a complete
runtime (LuaJIT `lua51.dll` + native modules like `lua-utf8.dll`) that we
drive via ctypes — see `scripts/pob_eval.py`.

This script does a shallow clone of PathOfBuildingCommunity into
``.pob_runtime/`` (gitignored, ~800 MB, Windows DLLs). It is **only** used
by the local optimiser — the deployed app never touches PoB. Re-run after
a league to refresh the runtime + data.

    uv run python scripts/setup_pob.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/PathOfBuildingCommunity/PathOfBuilding.git"
DEST = Path(".pob_runtime")
SENTINEL = DEST / "src" / "HeadlessWrapper.lua"


def main() -> int:
    if SENTINEL.exists():
        print(f"PoB runtime already present at {DEST}/ (skip). Delete it to refresh.")
        return 0
    if DEST.exists():
        sys.stderr.write(
            f"{DEST}/ exists but is incomplete (no {SENTINEL}). Remove it and re-run.\n"
        )
        return 1
    print(f"Shallow-cloning {REPO_URL} -> {DEST}/ (~800 MB, one-time) ...")
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", REPO_URL, str(DEST)],
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        sys.stderr.write(f"setup_pob: clone failed: {exc}\n")
        return 1
    if not SENTINEL.exists():
        sys.stderr.write(f"setup_pob: clone finished but {SENTINEL} missing — aborting.\n")
        return 1
    print(f"PoB runtime ready at {DEST}/. Validate with: uv run python scripts/pob_eval.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
