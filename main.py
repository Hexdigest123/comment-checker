#!/usr/bin/env python3

from utils import csv
import os
import argparse
import json

from utils.llm import LLMClient

parser = argparse.ArgumentParser(
    prog="Comment Checker",
    description="Classify comments using Mistral pipeline",
)


def build_client(backend: str, context: str):
    return LLMClient(context=context)


def classify_mistral(client, comment: str, threshold: float, fallback: bool = True):
    """Run the Mistral Moderation 2 pipeline.

    With fallback (default), comments not flagged by moderation get a
    second in-context check with a chat model.
    """
    scores = client.classify(comment)
    flags = {label: score >= threshold for label, score in scores.items()}
    flagged_by = "mistral_moderation"
    if not any(flags.values()) and fallback:
        second_opinion = client.check_with_context(comment)
        if second_opinion:
            flags["hate_speech"] = True
            scores["hate_speech"] = 1.0
            flagged_by = "mistral_fallback"
    flagged = any(flags.values())
    return {
        "backend": "mistral",
        "scores": scores,
        "flags": flags,
        "flagged": flagged,
        "flagged_by": flagged_by,
        "category": None,
        "confidence": None,
        "severity": None,
        "harmful": float(flags.get("hate_speech", False)),
    }








def main(file_path: str):
    data = csv.CSVReader(os.path.join(os.getcwd(), file_path), ",").df
    client = build_client(args.backend, args.context)

    data = data.head(args.max)

    has_ground_truth = "Kategorie" in data.columns
    out_path = args.out or "results_mistral.jsonl"
    records = []

    with open(out_path, "w", encoding="utf-8") as out_file:
        for idx, row in data.iterrows():
            comment = str(row["Comment"])
            result = classify_mistral(client, comment, args.threshold, args.fallback)

            record = {
                "idx": int(idx),
                "comment": comment,
                "ground_truth": str(row["Kategorie"]) if has_ground_truth else None,
                "priority": str(row["Priorität"]) if "Priorität" in data.columns else None,
                **result,
            }
            out_file.write(json.dumps(record, ensure_ascii=False) + "\n")
            records.append(record)

            print(
                f"Comment: {comment}\n"
                f"Result: {json.dumps(result, ensure_ascii=False)}\n"
            )

    print(f"\nWrote {len(records)} results to {out_path}")


if __name__ == "__main__":
    parser.add_argument(
        "--predict",
        "-p",
        nargs="?",
        const="assets/test-data.csv",
        metavar="FILE",
        help="Classify a CSV file (default: assets/test-data.csv)",
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
        help="Flagging probability threshold (default: 0.3)",
    )
    parser.add_argument(
        "--context",
        type=str,
        required=True,
        help="Context for the model to understand the situation (REQUIRED)",
    )
    parser.add_argument(
        "--backend",
        choices=["mistral"],
        default="mistral",
        help="Classification backend: mistral (only option)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output JSONL path (default: results_<backend>.jsonl)",
    )
    parser.add_argument(
        "--fallback",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run the second-pass in-context fallback for comments the first pass does not flag. Use --no-fallback to run only Mistral Moderation 2.",
    )
    args = parser.parse_args()
    if args.predict:
        main(args.predict)
