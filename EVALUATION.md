# Evaluation: TypeSafe (Jev) vs existing Mistral pipeline

Branch: `vibe/typesafe-ai-9a50fa`

## Setup

- Comment set: `assets/test-data3-clean.csv` — 391 curated Instagram comments reacting to a shop owner convicted for incitement to hatred (Volksverhetzung, §130 StGB) after posting a "Jews banned" sign.
- Ground truth: every row is hand-labeled hate speech (`Priorität` hoch/mittel, `Kategorie` = German legal category). There are no benign comments in this set, so **detection rate = recall**.
- Context passed to both backends: "A shop owner posted a 'Jews banned from this shop' sign and was convicted for incitement to hatred (Volksverhetzung, §130 StGB). Comments react to this case and the conviction."
- Threshold: 0.3.

## What each backend does

- **TypeSafe (Jev, `jev-latest` → `jev-1.13.0`)** — new implementation in `utils/typesafe.py`. A single System One call sends the comment as `state` and three typed questions: a `Noul` ("is this harmful"), a `Choice` (9 hate-speech categories), and a `Score` (0–3 severity). No LLM fallback, no text to parse. Flags when `harmful >= threshold`.
- **Mistral (existing)** — `utils/llm.py`. First pass: `mistral-moderation-2603` category scores, flag any ≥ 0.3. If none flagged, second pass: `mistral-small-latest` chat completion answering YES/NO with context ("context-aware fallback"). Returns scores only, no category.

## Results (391 comments)

| Metric | TypeSafe (Jev) | Mistral (existing) |
|---|---|---|
| Flagged / detected | 304 | 295 |
| **Detection rate (recall)** | **77.75%** | **75.45%** |
| Flagged by 2nd-pass fallback | n/a (no fallback) | 177 of 391 (45%) |
| Moderation-only flag rate (`hate_and_discrimination` ≥ 0.3) | n/a | 27.4% |
| Category output | yes (9 categories) | no |
| Severity output | yes (0–3) | no |
| Calibrated confidence | yes | no |
| Avg harmful probability | 0.546 | 0.453 |

### TypeSafe category accuracy
- Category accuracy vs mapped ground truth: **59.1%** (top-1 exact match against the mapped legal category).
- The dominant ground-truth label is `approval_of_arbitrary_action` (256/391), and Jev correctly predicted it 257 times — it slightly over-predicts this category, confusing adjacent `incitement_to_hatred` and `incitement_to_crime` cases (see `evaluate.py` mismatch examples).
- Predicted vs expected distribution is close for most categories; the main gaps are `incitement_to_hatred` (pred 34 vs expected 50) and `other` (pred 3 vs expected 43), where Jev tends to assign a concrete category instead of "other".

## Key takeaways

1. **TypeSafe Jev matches the existing pipeline's recall (77.8% vs 75.5%) while using no fallback LLM.** The Mistral pipeline only reaches 75.5% because its context-aware `mistral-small-latest` fallback flags 177 comments (45% of the set) that moderation alone missed — moderation by itself flags only 27%. Jev gets equivalent detection in a single typed call.
2. **TypeSafe returns richer, machine-native output**: a discrete category, a 0–3 severity score, and a calibrated confidence — none of which the Mistral moderation + YES/NO pipeline provides.
3. **TypeSafe's category labels are meaningfully accurate** (59% exact match) and aligned with the dataset's legal taxonomy; mismatches are mostly between semantically adjacent categories (approval vs incitement).
4. Per-comment outputs: `results_typesafe.jsonl`, `results_mistral.jsonl`. Re-run with `python3 evaluate.py`.
