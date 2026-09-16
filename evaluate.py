#!/usr/bin/env python3
"""Evaluate TypeSafe vs Mistral pipeline outputs against ground-truth labels.

Ground truth: every row in test-data3-clean.csv is curated hate speech (Priorität
hoch/mittel, Kategorie = legal category). So:
  - Detection rate = fraction flagged (all are harmful, so higher is better).
  - For TypeSafe, category-accuracy is measured against a normalized mapping
    from the German legal Kategorie to the Jev choice set.
The Mistral pipeline returns no category, so it is only evaluated on detection.
"""
import json
import re
from collections import Counter

GROUND_TRUTH_ALL_HARMFUL = True

CATEGORY_MAP = {
    "aufstacheln zum hass": "incitement_to_hatred",
    "aufstacheln zum hass/verschwörungsideologie": "incitement_to_hatred",
    "kollektivschuld/aufstacheln zum hass": "incitement_to_hatred",
    "verschwörungsnarrativ/aufstacheln zum hass": "incitement_to_hatred",
    "aufforderung zu straftaten": "incitement_to_crime",
    "billigung willkürmaßnahme": "approval_of_arbitrary_action",
    "billigung willkürmaßnahme/aufstacheln zum hass": "approval_of_arbitrary_action",
    "verhetzende beleidigung": "insult",
    "bedrohung": "threat",
    "ns-verherrlichung": "glorification_of_nazism",
    "religionsbeschimpfung": "religious_defamation",
    "religionsbeschimpfung/sonstiges": "religious_defamation",
    "kollektivschuldkollektivschuld": "incitement_to_hatred",
    "kollektivschuld/sonstiges": "incitement_to_hatred",
    "kollektivschuld": "incitement_to_hatred",
    "sonstiges": "other",
    "holocaustleugnung/-verharmlosung": "glorification_of_nazism",
}


def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def expected_category(gt):
    return CATEGORY_MAP.get(norm(gt), "other")


def load(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def evaluate(path, backend):
    rows = load(path)
    n = len(rows)
    detected = sum(1 for r in rows if r.get("flagged"))
    detection_rate = detected / n if n else 0.0

    summary = {
        "backend": backend,
        "n": n,
        "detected_flagged": detected,
        "detection_rate": round(detection_rate, 4),
    }

    if backend == "typesafe":
        correct = 0
        mappable = 0
        cat_dist = Counter()
        gt_dist = Counter()
        mismatch_examples = []
        avg_severity = []
        avg_confidence = []
        avg_harmful = []
        for r in rows:
            gt = r.get("ground_truth")
            exp = expected_category(gt)
            pred = r.get("category")
            cat_dist[pred] += 1
            gt_dist[exp] += 1
            avg_severity.append(r.get("severity") or 0.0)
            avg_confidence.append(r.get("confidence") or 0.0)
            avg_harmful.append(r.get("harmful") or 0.0)
            if pred == exp:
                correct += 1
                mappable += 1
            else:
                mismatch_examples.append(
                    {
                        "comment": (r.get("comment") or "")[:120],
                        "gt": gt,
                        "expected": exp,
                        "predicted": pred,
                        "harmful": r.get("harmful"),
                        "confidence": r.get("confidence"),
                    }
                )
        summary["category_accuracy"] = round(correct / n, 4)
        summary["avg_harmful_prob"] = round(sum(avg_harmful) / n, 4)
        summary["avg_severity"] = round(sum(avg_severity) / n, 4)
        summary["avg_confidence"] = round(sum(avg_confidence) / n, 4)
        summary["predicted_category_dist"] = dict(cat_dist)
        summary["expected_category_dist"] = dict(gt_dist)
        summary["mismatch_examples"] = mismatch_examples[:15]
    else:
        avg_harmful = [r.get("harmful") or 0.0 for r in rows]
        summary["avg_harmful"] = round(sum(avg_harmful) / n, 4)
        flagged_by_fallback = sum(
            1 for r in rows if (r.get("flags") or {}).get("hate_speech") and not any(
                v for k, v in (r.get("flags") or {}).items() if k != "hate_speech"
            )
        )
        summary["flagged_by_context_fallback"] = flagged_by_fallback
        scores_keys = ["hate_and_discrimination", "violence_and_threats", "criminal", "dangerous"]
        summary["moderation_flag_rate"] = {}
        for k in scores_keys:
            hit = sum(1 for r in rows if (r.get("scores") or {}).get(k, 0) >= 0.3)
            summary["moderation_flag_rate"][k] = round(hit / n, 4)

    return summary


if __name__ == "__main__":
    import sys

    ts = evaluate("results_typesafe.jsonl", "typesafe")
    ms = evaluate("results_mistral.jsonl", "mistral")
    print("=" * 70)
    print("TYPESAFE (Jev) SUMMARY")
    print("=" * 70)
    for k, v in ts.items():
        if k == "mismatch_examples":
            print(f"  mismatch_examples: {len(v)} shown (first 15)")
            for m in v[:8]:
                print(f"    - gt={m['gt']!r} expected={m['expected']} predicted={m['predicted']} "
                      f"harmful={m['harmful']} conf={m['confidence']}")
                print(f"      {m['comment']}")
        else:
            print(f"  {k}: {v}")

    print()
    print("=" * 70)
    print("MISTRAL (Moderation 2 + context fallback) SUMMARY")
    print("=" * 70)
    for k, v in ms.items():
        print(f"  {k}: {v}")
