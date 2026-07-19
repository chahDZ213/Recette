"""Executable entry point: ``python -m calforge`` or the ``calforge`` script.

Flags:
  --seed-demo   Populate realistic demo data (idempotent), then continue.
  --seed-only   Seed demo data and exit without launching the UI.
"""

from __future__ import annotations

import sys


def main() -> int:
    argv = sys.argv
    seed = "--seed-demo" in argv or "--seed-only" in argv
    seed_only = "--seed-only" in argv

    if seed_only:
        from calforge.app import ApplicationContext
        from calforge.demo import seed_demo

        ctx = ApplicationContext()
        try:
            seeded = seed_demo(ctx)
        finally:
            ctx.shutdown()
        print("Demo data seeded." if seeded else "Demo data already present.")
        return 0

    from calforge.ui.app import run

    return run([a for a in argv if a not in ("--seed-demo", "--seed-only")], seed_demo=seed)


if __name__ == "__main__":
    raise SystemExit(main())
