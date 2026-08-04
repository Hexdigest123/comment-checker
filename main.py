#!/usr/bin/env python3

from utils import csv
import os
import argparse
import json

from utils.llm import LLMClient
from utils.consts import LLM_LABELS
from utils.train import (
    Classifier,
    MODEL_ID,
    TRAIN_ROWS,
    VAL_ROWS,
    BATCH_SIZE,
    EPOCHS,
    MAX_LEN,
    LR,
)

parser = argparse.ArgumentParser(
    prog="Comment Checker",
    description="A tool to check and classify comments using a pretrainer classification model and LLM",
)


def main(file_path: str):
    data = csv.CSVReader(os.path.join(os.getcwd(), file_path), ",").df
    client = LLMClient()

    classifier = Classifier(model_id=args.model)
    data = data.iloc[args.offset : args.offset + args.max]

    translated_comments = []
    for idx, row in data.iterrows():
        translated_comments.append(client.translate(str(row["Comment"])))

    probs = classifier.predict(translated_comments)

    output_mode = "a" if args.offset else "w"
    output = open(args.output, output_mode, encoding="utf-8") if args.output else None
    try:
        for idx, comment in enumerate(translated_comments):
            row = data.iloc[idx]
            classifier_flags = {
                label: prob >= args.threshold for label, prob in probs[idx].items()
            }
            llm_scores = client.classify(comment)
            flags = {
                label: bool(
                    classifier_flags.get(label, False)
                    or llm_scores.get(label, 0.0) >= args.threshold
                )
                for label in LLM_LABELS
            }
            result = {
                "row": args.offset + idx + 1,
                "comment_id": str(row.get("Comment ID", "")),
                "evaluation_group": str(row.get("Evaluation Group", "")),
                "expected_relevant": str(row.get("Expected Relevant", "")),
                "expected_discrimination": str(
                    row.get("Expected Discrimination", "")
                ),
                "original_comment": str(row["Comment"]),
                "translated_comment": comment,
                "prediction": flags,
                "classifier_probs": probs[idx],
                "llm_scores": llm_scores,
            }
            if output:
                output.write(json.dumps(result, ensure_ascii=False) + "\n")
                output.flush()
            print(
                f"Comment: {comment}\nPrediction: {flags}\nSource: classifier+llm\nProbs: {probs[idx]}\nLLM Scores: {llm_scores}"
            )
    finally:
        if output:
            output.close()


if __name__ == "__main__":
    parser.add_argument(
        "--predict",
        "-p",
        nargs="?",
        const="assets/test-data.csv",
        metavar="FILE",
        help="Classify a CSV file with the trained model (default: assets/test-data.csv)",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=20,
        help="Maximum number of comments to classify (default: 20)",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Number of comments to skip before classification (default: 0)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.3,
        help="Flagging probability threshold for each label (default: 0.3)",
    )
    parser.add_argument(
        "--output",
        metavar="FILE",
        help="Write machine-readable prediction results as JSONL",
    )
    parser.add_argument(
        "--train",
        "-t",
        action="store_true",
        help="Train the civil comments model",
    )
    parser.add_argument(
        "--model",
        default=MODEL_ID,
        help=f"Pretrained model to fine-tune (default: {MODEL_ID})",
    )
    parser.add_argument(
        "--train-rows",
        type=int,
        default=TRAIN_ROWS,
        help=f"Number of training rows (default: {TRAIN_ROWS})",
    )
    parser.add_argument(
        "--val-rows",
        type=int,
        default=VAL_ROWS,
        help=f"Number of validation rows (default: {VAL_ROWS})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help=f"Training batch size (default: {BATCH_SIZE})",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=EPOCHS,
        help=f"Number of epochs (default: {EPOCHS})",
    )
    parser.add_argument(
        "--max-len",
        type=int,
        default=MAX_LEN,
        help=f"Maximum token length (default: {MAX_LEN})",
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=LR,
        help=f"Learning rate (default: {LR})",
    )
    parser.add_argument(
        "--bf16",
        action="store_true",
        help="Use bfloat16 mixed precision (faster, ~50%% less VRAM)",
    )
    args = parser.parse_args()
    if args.predict:
        main(args.predict)
    elif args.train:
        Classifier(
            retrain=True,
            model_id=args.model,
            train_rows=args.train_rows,
            val_rows=args.val_rows,
            batch_size=args.batch_size,
            epochs=args.epochs,
            max_len=args.max_len,
            lr=args.lr,
            bf16=args.bf16,
        )
