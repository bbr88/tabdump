#!/usr/bin/env python3
"""Compatibility shim for postprocess CLI/module.

Canonical implementation now lives at core.postprocess.cli.
"""

import sys
from pathlib import Path


def _find_root(path: Path) -> Path:
    candidates = [
        path.parent,
        path.parent.parent,
        path.parent.parent.parent,
    ]
    for candidate in candidates:
        if (candidate / "core" / "renderer" / "renderer_v3.py").exists():
            return candidate
    return path.parent.parent


ROOT = _find_root(Path(__file__).resolve())
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

if __name__ == "__main__":
    from core.postprocess.cli import main

    raise SystemExit(main(sys.argv))

from core.postprocess import cli as _cli

# Alias the old module path to the new implementation module so existing
# imports and monkeypatches continue to behave the same way.
sys.modules[__name__] = _cli
