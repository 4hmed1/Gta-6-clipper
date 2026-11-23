"""Resolve bundled config assets regardless of how MaxClipper is installed.

The three scoring modules (nlp, selection, stream_clipper) used to load
``config/...`` relative to the *current working directory*. That breaks
when the app runs from a different directory or is installed as a wheel.
Every caller resolves paths through :func:`package_config`.
"""

import os as _os
from pathlib import Path

# This file lives at <pkg>/maxclipper/_config.py, so the bundled assets are
# at <pkg>/maxclipper/../config and <pkg>/maxclipper/../static.
_PKG_DIR = Path(__file__).resolve().parent


def package_config(*parts: str) -> Path:
    """Return the path to a file bundled under the repo ``config/`` tree.

    Search order:
      1. <pkg>/../config/<parts>            (source tree / editable install)
      2. <pkg>/config/<parts>               (wheel install layout)
      3. <pkg>/../maxclipper/config/<parts>  (legacy layout)
    """
    rel = Path(*parts)
    # Search order covers every layout pip/setuptools may produce:
    #   1. <site-packages>/config/<parts>            (source tree / editable)
    #   2. <site-packages>/maxclipper/config/<parts>  (data-files in pkg)
    #   3. <prefix>/maxclipper/config/<parts>          (data-files at venv root)
    #   4. <site-packages>/maxclipper/../config/<parts>
    for base in (
        _PKG_DIR.parent / "config",
        _PKG_DIR / "config",
        _PKG_DIR.parent / "maxclipper" / "config",
    ):
        candidate = base / rel
        if candidate.exists():
            return candidate
    # Walk the whole venv for a sibling config/ folder (last resort —
    # data-files layouts vary between pip versions). Use sys.prefix so we
    # cover the venv root even when the interpreter is a symlink.
    import sys as _sys
    for _start in (Path(_sys.prefix), _PKG_DIR.parent.parent.parent.parent.parent):
        if not _start.exists():
            continue
        for _root, _dirs, _files in _os.walk(_start):
            if _root.endswith("config") and rel.name in _files:
                return Path(_root) / rel
    # Return the most likely path even if it does not exist yet; callers
    # fall back to built-in defaults when the file is missing.
    return _PKG_DIR.parent / "config" / rel