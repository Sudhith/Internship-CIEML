#!/usr/bin/env python
"""Run CIEML 2.0 Phase 8 (Stage 14)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cieml.pipeline import run_phase8


def main() -> None:
    p = argparse.ArgumentParser(description="CIEML 2.0 Phase 8 runner")
    p.add_argument("--phase1-dir", type=Path, default=None)
    p.add_argument("--phase2-dir", type=Path, default=None)
    p.add_argument("--phase3-dir", type=Path, default=None)
    p.add_argument("--phase4-dir", type=Path, default=None)
    p.add_argument("--phase5-dir", type=Path, default=None)
    p.add_argument("--phase6-dir", type=Path, default=None)
    p.add_argument("--phase7-dir", type=Path, default=None)
    p.add_argument("--output-dir", type=Path, default=None)
    args = p.parse_args()
    run_phase8(
        phase1_dir=args.phase1_dir,
        phase2_dir=args.phase2_dir,
        phase3_dir=args.phase3_dir,
        phase4_dir=args.phase4_dir,
        phase5_dir=args.phase5_dir,
        phase6_dir=args.phase6_dir,
        phase7_dir=args.phase7_dir,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
