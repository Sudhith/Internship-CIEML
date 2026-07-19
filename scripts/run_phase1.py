#!/usr/bin/env python
"""Run CIEML 2.0 Phase 1 (Stages -1, 0, 1)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cieml.pipeline import run_phase1


def main() -> None:
    p = argparse.ArgumentParser(description="CIEML 2.0 Phase 1 runner")
    p.add_argument("--data-dir", type=Path, default=None, help="Path to raw DATA folder")
    p.add_argument("--output-dir", type=Path, default=None, help="Path for Phase 1 outputs")
    args = p.parse_args()
    run_phase1(data_dir=args.data_dir, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
