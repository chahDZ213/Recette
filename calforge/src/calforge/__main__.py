"""Executable entry point: ``python -m calforge`` or the ``calforge`` script."""

from __future__ import annotations

import sys


def main() -> int:
    from calforge.ui.app import run

    return run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
