#!/usr/bin/env python
"""Run CIEML 2.0 Phase 2 (Stages 2-3)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cieml.pipeline import run_phase2


def main() -> None:
    p = argparse.ArgumentParser(description="CIEML 2.0 Phase 2 runner")
    p.add_argument("--data-dir", type=Path, default=None)
    p.add_argument("--phase1-dir", type=Path, default=None)
    p.add_argument("--output-dir", type=Path, default=None)
    args = p.parse_args()
    run_phase2(data_dir=args.data_dir, phase1_dir=args.phase1_dir, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
