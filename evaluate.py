#!/usr/bin/env python3
"""Evaluate Mistral pipeline outputs against ground-truth labels.

Ground truth: every row in test-data3-clean.csv is curated hate speech (Priorität
hoch/mittel, Kategorie = legal category). So:
  - Detection rate = fraction flagged (all are harmful, so higher is better).
The Mistral pipeline returns no category, so it is only evaluated on detection.
"""
import json
from collections import Counter

GROUND_TRUTH_ALL_HARMFUL = True


def load(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def evaluate(path, backend):
    try:
        rows = load(path)
    except FileNotFoundError:
        return None
    n = len(rows)
    detected = sum(1 for r in rows if r.get("flagged"))
    detection_rate = detected / n if n else 0.0

    summary = {
        "backend": backend,
        "n": n,
        "detected_flagged": detected,
        "detection_rate": round(detection_rate, 4),
    }

    avg_harmful = [r.get("harmful") or 0.0 for r in rows]
    summary["avg_harmful"] = round(sum(avg_harmful) / n, 4)
    flagged_by = Counter(r.get("flagged_by") for r in rows)
    summary["flagged_by_mistral_moderation"] = flagged_by.get("mistral_moderation", 0)
    summary["flagged_by_context_fallback"] = flagged_by.get("mistral_fallback", 0)
    scores_keys = ["hate_and_discrimination", "violence_and_threats", "criminal", "dangerous"]
    summary["moderation_flag_rate"] = {}
    for k in scores_keys:
        hit = sum(1 for r in rows if (r.get("scores") or {}).get(k, 0) >= 0.3)
        summary["moderation_flag_rate"][k] = round(hit / n, 4)

    return summary


if __name__ == "__main__":
    import sys

    def print_summary(title, summary):
        if summary is None:
            return
        print("=" * 70)
        print(title)
        print("=" * 70)
        for k, v in summary.items():
            if k == "mismatch_examples":
                print(f"  mismatch_examples: {len(v)} shown (first 15)")
                for m in v[:8]:
                    print(f"    - gt={m['gt']!r} expected={m['expected']} predicted={m['predicted']} "
                          f"harmful={m['harmful']} conf={m['confidence']}")
                    print(f"      {m['comment']}")
            else:
                print(f"  {k}: {v}")
        print()

    ms = evaluate("results_mistral.jsonl", "mistral")

    print_summary("MISTRAL (Moderation 2 + context fallback) SUMMARY", ms)
