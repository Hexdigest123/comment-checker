#!/usr/bin/env python3

from utils import csv
import os
import argparse
import json

from utils.typesafe import TypeSafeLLMClient
from utils.llm import LLMClient

parser = argparse.ArgumentParser(
    prog="Comment Checker",
    description="Classify comments using TypeSafe Jev (default) or the existing Mistral pipeline",
)


def build_client(backend: str, context: str):
    if backend == "typesafe":
        return TypeSafeLLMClient(context=context)
    if backend == "mistral":
        return LLMClient(context=context)
    if backend == "combined":
        return (
            TypeSafeLLMClient(context=context),
            LLMClient(context=context),
        )
    raise ValueError(f"Unknown backend: {backend}")


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


def classify_typesafe(client, comment: str, threshold: float):
    """Run the TypeSafe Jev pipeline (no LLM fallback)."""
    scores = client.classify(comment)
    harmful = float(scores.get("harmful", 0.0))
    flagged = harmful >= threshold
    return {
        "backend": "typesafe",
        "scores": scores,
        "flagged": flagged,
        "flagged_by": "typesafe" if flagged else None,
        "category": scores.get("category"),
        "confidence": scores.get("confidence"),
        "severity": scores.get("severity"),
        "harmful": harmful,
    }


def classify_combined(clients, comment: str, threshold: float, fallback: bool = True):
    """Run TypeSafe Jev for classification, then the Mistral in-context
    fallback only for the comments Jev did not flag.

    Jev provides the category, severity and confidence. The Mistral fallback
    provides the detection for short, coded, context-dependent praise that Jev
    is too conservative to flag on its own. With --no-fallback Jev runs alone.
    """
    typesafe_client, mistral_client = clients
    scores = typesafe_client.classify(comment)
    harmful = float(scores.get("harmful", 0.0))
    flagged = harmful >= threshold
    flagged_by = "typesafe"

    if not flagged and fallback:
        second_opinion = mistral_client.check_with_context(comment)
        if second_opinion:
            flagged = True
            harmful = 1.0
            flagged_by = "mistral_fallback"

    return {
        "backend": "combined",
        "scores": scores,
        "flagged": flagged,
        "flagged_by": flagged_by,
        "category": scores.get("category"),
        "confidence": scores.get("confidence"),
        "severity": scores.get("severity"),
        "harmful": harmful,
    }


def main(file_path: str):
    data = csv.CSVReader(os.path.join(os.getcwd(), file_path), ",").df
    client = build_client(args.backend, args.context)

    data = data.head(args.max)

    has_ground_truth = "Kategorie" in data.columns
    out_path = args.out or f"results_{args.backend}.jsonl"
    records = []

    with open(out_path, "w", encoding="utf-8") as out_file:
        for idx, row in data.iterrows():
            comment = str(row["Comment"])
            if args.backend == "typesafe":
                result = classify_typesafe(client, comment, args.threshold)
            elif args.backend == "combined":
                result = classify_combined(client, comment, args.threshold, args.fallback)
            else:
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
        choices=["typesafe", "mistral", "combined"],
        default="typesafe",
        help="Classification backend: typesafe (TypeSafe Jev, default), mistral (existing pipeline), or combined (Jev for classification + Mistral in-context fallback for the borderline cases Jev misses)",
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
        help="Run the second-pass in-context fallback for comments the first pass does not flag. Use --no-fallback to run only the first pass (Mistral Moderation 2 alone, or Jev alone). Default: on for mistral/combined. Ignored for typesafe.",
    )
    args = parser.parse_args()
    if args.predict:
        main(args.predict)
