"""Placeholder script for first-pass empirical analysis.

Expected inputs:
- Processed event panel
- Basic analysis choices such as benchmark and output directory

Expected outputs:
- Descriptive tables
- Simple figures
- Optional regression summaries
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze competitor market reactions.")
    parser.add_argument("--panel", required=True, help="Path to processed event panel.")
    parser.add_argument("--benchmark", default="SPY", help="Benchmark ticker label.")
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Directory for tables and figures.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir)

    plan = {
        "status": "placeholder",
        "panel": args.panel,
        "benchmark": args.benchmark,
        "output_dir": str(output_dir),
        "todo": [
            "Summarize event counts by industry, scope, and competitor effect.",
            "Compare average competitor reactions across label buckets.",
            "Export basic tables and figures to the outputs folder.",
            "Add simple regressions only after data quality checks pass.",
        ],
    }

    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
