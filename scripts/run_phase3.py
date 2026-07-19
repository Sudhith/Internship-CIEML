#!/usr/bin/env python
"""Run CIEML 2.0 Phase 3 (Stages 4-5)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cieml.pipeline import run_phase3


def main() -> None:
    p = argparse.ArgumentParser(description="CIEML 2.0 Phase 3 runner")
    p.add_argument("--data-dir", type=Path, default=None)
    p.add_argument("--phase1-dir", type=Path, default=None)
    p.add_argument("--phase2-dir", type=Path, default=None)
    p.add_argument("--output-dir", type=Path, default=None)
    args = p.parse_args()
    run_phase3(
        data_dir=args.data_dir,
        phase1_dir=args.phase1_dir,
        phase2_dir=args.phase2_dir,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
