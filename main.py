#!/usr/bin/env python3

import os
import sys
import argparse
import json
import pandas as pd

from utils.csv import CSVReader
from utils.llm import LLMClient
from utils import logger
from utils.exportcomments import ExportCommentsClient


parser = argparse.ArgumentParser(
    prog="Comment Checker",
    description="Classify comments using Mistral pipeline or export directly from social media URLs",
)


def classify_mistral(client, comment: str, threshold: float, fallback: bool = True):
    """Run the Mistral Moderation 2 pipeline.

    With fallback (default), comments not flagged by moderation get a
    second in-context check with a chat model.
    """
    scores = client.classify(comment)
    flags = {label: score >= threshold for label, score in scores.items()}
    flagged_by = None
    if any(flags.values()):
        flagged_by = "mistral_moderation"
    elif fallback:
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



def load_comments_from_url(
    url: str,
    api_key: str = None,
    include_replies: bool = False,
    wait: bool = True,
    timeout: int = 300,
    poll_interval: float = 2.0,
) -> str:
    """Export comments from a social media URL using ExportComments API.
    
    Args:
        url: The URL of the social media post.
        api_key: ExportComments API key (defaults to env var).
        include_replies: Whether to include reply threads.
        wait: Whether to wait for completion.
        timeout: Maximum seconds to wait.
        poll_interval: Seconds between status checks.
        
    Returns:
        Path to the temporary CSV file with exported comments.
    """
    client = ExportCommentsClient(api_key=api_key)
    
    # Create a temporary file for the CSV
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.csv',
        delete=False,
        encoding='utf-8'
    ) as tmp_file:
        tmp_path = tmp_file.name
    
    try:
        logger.info(f"Exporting comments from: {url}")
        client.export_to_csv(
            url=url,
            output_path=tmp_path,
            include_replies=include_replies,
            wait=wait,
            timeout=timeout,
            poll_interval=poll_interval,
        )
        logger.info(f"Comments exported to temporary file: {tmp_path}")
        return tmp_path
    except Exception as e:
        # Clean up temp file if it exists
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        logger.fatal(f"Failed to export comments from URL: {e}")


def load_comments(
    file_path: str = None,
    url: str = None,
    api_key: str = None,
    **export_kwargs,
) -> pd.DataFrame:
    """Load comments from either a CSV file or a social media URL.
    
    Args:
        file_path: Path to a CSV file.
        url: URL of a social media post to export.
        api_key: ExportComments API key for URL exports.
        **export_kwargs: Additional arguments for the export client.
        
    Returns:
        DataFrame with comments in the expected format.
    """
    if url:
        # Export from URL
        csv_path = load_comments_from_url(url, api_key=api_key, **export_kwargs)
        reader = CSVReader(csv_path, auto_map=True)
        df = reader.df
        
        # Clean up the temporary file
        try:
            os.unlink(csv_path)
        except OSError:
            pass
        
    elif file_path:
        # Load from CSV file
        full_path = os.path.join(os.getcwd(), file_path) if not os.path.isabs(file_path) else file_path
        if not os.path.exists(full_path):
            logger.fatal(f"Input file not found: {full_path}")
        
        reader = CSVReader(full_path, auto_map=True)
        df = reader.df
        
    else:
        logger.fatal("Either --predict (CSV file) or --export-url (social media URL) is required")
    
    return df


def main():
    """Main classification function."""
    # Load comments from either file or URL
    df = load_comments(
        file_path=args.predict,
        url=args.export_url,
        api_key=os.environ.get("EXPORTCOMMENTS_API_KEY"),
        include_replies=args.include_replies,
        wait=args.wait,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
    )

    client = LLMClient(context=args.context)

    df = df.head(args.max)

    out_path = args.out or f"results_{args.backend}.jsonl"
    records = []

    with open(out_path, "w", encoding="utf-8") as out_file:
        for idx, row in df.iterrows():
            comment = str(row.get("Comment", row.get("text", row.get("comment", ""))))
            
            if not comment or comment.strip() == "":
                logger.warning(f"Skipping empty comment at index {idx}")
                continue
                
            result = classify_mistral(client, comment, args.threshold, args.fallback)

            record = {
                "idx": int(idx),
                "comment": comment,
                "ground_truth": str(row["Kategorie"]) if "Kategorie" in df.columns else None,
                "priority": str(row["Priorität"]) if "Priorität" in df.columns else 
                           str(row.get("priority", row.get("Priority", None))),
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
        "--export-url",
        "-u",
        type=str,
        default=None,
        metavar="URL",
        help="Export comments directly from a social media URL using ExportComments API",
    )
    
    parser.add_argument(
        "--include-replies",
        action="store_true",
        default=False,
        help="Include reply threads when exporting from URL (ExportComments feature)",
    )
    
    parser.add_argument(
        "--wait",
        action="store_true",
        default=True,
        help="Wait for export to complete before processing (default: True)",
    )
    
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        metavar="SECONDS",
        help="Maximum seconds to wait for export completion (default: 300)",
    )
    
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        metavar="SECONDS",
        help="Seconds between status checks when waiting for export (default: 2.0)",
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
        required=not (len(sys.argv) > 1 and ("--help" in sys.argv or "-h" in sys.argv)),
        help="Context for the model to understand the situation (REQUIRED unless using --help)",
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
        help="Run the second-pass in-context fallback for comments the first pass does not flag",
    )
    
    args = parser.parse_args()
    main()
