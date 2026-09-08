#!/usr/bin/env python3

from utils import csv
import os
import argparse

from utils.llm import LLMClient

parser = argparse.ArgumentParser(
    prog="Comment Checker",
    description="A tool to check and classify comments using Mistral Moderation 2 API with context-aware fallback",
)


def main(file_path: str):
    data = csv.CSVReader(os.path.join(os.getcwd(), file_path), ",").df
    client = LLMClient(context=args.context)

    data = data.head(args.max)

    for idx, row in data.iterrows():
        comment = str(row["Comment"])
        
        # First pass: Mistral Moderation 2 API
        scores = client.classify(comment)
        
        # Determine flags based on threshold
        flags = {
            label: score >= args.threshold for label, score in scores.items()
        }
        
        # If nothing flagged, use context-aware second check
        if not any(flags.values()):
            second_opinion = client.check_with_context(comment)
            if second_opinion:
                flags["hate_speech"] = True
                scores["hate_speech"] = 1.0
        
        print(
            f"Comment: {comment}\n"
            f"Scores: {scores}\n"
            f"Flags: {flags}"
        )


if __name__ == "__main__":
    parser.add_argument(
        "--predict",
        "-p",
        nargs="?",
        const="assets/test-data.csv",
        metavar="FILE",
        help="Classify a CSV file with Mistral Moderation 2 (default: assets/test-data.csv)",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=20,
        help="Maximum number of comments to classify (default: 20)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.3,
        help="Flagging probability threshold for each label (default: 0.3)",
    )
    parser.add_argument(
        "--context",
        type=str,
        required=True,
        help="Context for the second-stage model to understand the situation (REQUIRED)",
    )
    args = parser.parse_args()
    if args.predict:
        main(args.predict)
