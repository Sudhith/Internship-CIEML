#!/usr/bin/env python
"""Run CIEML 2.0 Phase 5 (Stages 8-9)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cieml.pipeline import run_phase5


def main() -> None:
    p = argparse.ArgumentParser(description="CIEML 2.0 Phase 5 runner")
    p.add_argument("--phase4-dir", type=Path, default=None)
    p.add_argument("--output-dir", type=Path, default=None)
    args = p.parse_args()
    run_phase5(phase4_dir=args.phase4_dir, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
