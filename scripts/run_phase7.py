#!/usr/bin/env python
"""Run CIEML 2.0 Phase 7 (Stages 12-13)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cieml.pipeline import run_phase7


def main() -> None:
    p = argparse.ArgumentParser(description="CIEML 2.0 Phase 7 runner")
    p.add_argument("--phase1-dir", type=Path, default=None, help="For CEAM (Stage 12) Stage 1/2 QA context")
    p.add_argument("--phase2-dir", type=Path, default=None, help="For CEAM (Stage 12) Stage 2/3 QA/physical context")
    p.add_argument("--phase4-dir", type=Path, default=None)
    p.add_argument("--phase5-dir", type=Path, default=None)
    p.add_argument("--phase6-dir", type=Path, default=None)
    p.add_argument("--output-dir", type=Path, default=None)
    args = p.parse_args()
    run_phase7(
        phase1_dir=args.phase1_dir,
        phase2_dir=args.phase2_dir,
        phase4_dir=args.phase4_dir,
        phase5_dir=args.phase5_dir,
        phase6_dir=args.phase6_dir,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
