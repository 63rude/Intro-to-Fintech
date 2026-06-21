"""Placeholder script for LLM-based news classification.

Expected inputs:
- Raw or cleaned news records
- Prompt template path
- Model choice and API credentials

Expected outputs:
- Labeled news file with competitor-oriented classification fields
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Classify news using an LLM prompt.")
    parser.add_argument("--input", required=True, help="Input news file to classify.")
    parser.add_argument(
        "--prompt-file",
        default="prompts/news_classification_prompt.md",
        help="Prompt template path.",
    )
    parser.add_argument("--model", default="", help="Model name to use.")
    parser.add_argument("--limit", type=int, default=20, help="Max rows for a pilot run.")
    parser.add_argument(
        "--output",
        default="data/interim/news_labeled.jsonl",
        help="Relative output path for labeled news.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input)
    prompt_path = Path(args.prompt_file)
    output_path = Path(args.output)

    plan = {
        "status": "placeholder",
        "input_exists": input_path.exists(),
        "prompt_exists": prompt_path.exists(),
        "model": args.model,
        "limit": args.limit,
        "output": str(output_path),
        "todo": [
            "Load input news records and map them into the prompt input schema.",
            "Call the chosen LLM API with deterministic settings for classification.",
            "Validate that outputs contain only allowed labels and scales.",
            "Store both labels and short reasoning for manual audit.",
        ],
    }

    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
