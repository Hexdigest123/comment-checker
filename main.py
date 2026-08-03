#!/usr/bin/env python3

from utils import csv
import os
import argparse

from utils.llm import LLMClient
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
    data = data.head(args.max)

    translated_comments = []
    for idx, row in data.iterrows():
        translated_comments.append([client.translate([str(row["Comment"])])])

    probs = classifier.predict(translated_comments)

    for idx in range(len(translated_comments)):
        comment = translated_comments[idx]
        classifier_flags = {
            label: prob >= args.threshold for label, prob in probs[idx].items()
        }
        flags = classifier_flags
        source = "classifier"
        if not any(classifier_flags.values()):
            llm_flags = client.classify(comment)
            flags = {
                label: bool(classifier_flags[label] or llm_flags.get(label, False))
                for label in classifier_flags
            }
            source = "classifier+llm"
        print(
            f"Comment: {comment}\nPrediction: {flags}\nSource: {source}\nProbs: {probs[idx]}"
        )


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
        "--threshold",
        type=float,
        default=0.3,
        help="Flagging probability threshold for each label (default: 0.3)",
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
