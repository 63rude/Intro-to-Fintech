"""Placeholder script for linking labeled news to competitor outcomes.

Expected inputs:
- Labeled news records
- Daily price panel
- Competitor group definitions

Expected outputs:
- Event-level panel ready for descriptive analysis or regressions
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build an event panel for competitor reactions.")
    parser.add_argument("--news", required=True, help="Path to labeled news data.")
    parser.add_argument("--prices", required=True, help="Path to daily price data.")
    parser.add_argument(
        "--config",
        default="config/competitor_groups.yaml",
        help="Competitor group configuration file.",
    )
    parser.add_argument(
        "--event-window-days",
        type=int,
        default=3,
        help="Short event window length for reaction variables.",
    )
    parser.add_argument(
        "--output",
        default="data/processed/event_panel.csv",
        help="Relative output path for the event panel.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    plan = {
        "status": "placeholder",
        "news": args.news,
        "prices": args.prices,
        "config": args.config,
        "event_window_days": args.event_window_days,
        "output": args.output,
        "todo": [
            "Map each focal-firm article to a peer group.",
            "Exclude the focal firm from competitor outcome rows.",
            "Compute next-day and short-window competitor return measures.",
            "Add benchmark-adjusted returns and volume change variables.",
        ],
    }

    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
