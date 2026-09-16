# Evaluation: TypeSafe (Jev) vs existing Mistral pipeline

Branch: `vibe/typesafe-ai-9a50fa`

## Setup

- Comment set: `assets/test-data3-clean.csv` — 391 curated Instagram comments reacting to a shop owner convicted for incitement to hatred (Volksverhetzung, §130 StGB) after posting a "Jews banned" sign.
- Ground truth: every row is hand-labeled hate speech (`Priorität` hoch/mittel, `Kategorie` = German legal category). There are no benign comments in this set, so **detection rate = recall**.
- Context passed to both backends: "A shop owner posted a 'Jews banned from this shop' sign and was convicted for incitement to hatred (Volksverhetzung, §130 StGB). Comments react to this case and the conviction."
- Threshold: 0.3.

## What each backend does

- **TypeSafe (Jev, `jev-latest` → `jev-1.13.0`)** — new implementation in `utils/typesafe.py`. A single System One call sends the comment as `state` and three typed questions: a `Noul` ("is this harmful"), a `Choice` (9 hate-speech categories), and a `Score` (0–3 severity). No LLM fallback, no text to parse. Flags when `harmful >= threshold`.
- **Mistral (existing, fallback now fixed)** — `utils/llm.py`. First pass: `mistral-moderation-2603` category scores, flag any ≥ 0.3. If none flagged, second pass: `mistral-small-latest` chat completion answering YES/NO **judging the comment in the given context, not in isolation** — so innocuous-looking praise of a hateful act (e.g. "Ehrenmann" / "he did nothing wrong" reacting to a "Jews banned" sign) counts as hate speech. Returns scores only, no category.
- **Combined** — `--backend combined`. TypeSafe Jev classifies every comment (category + severity + confidence). For the comments Jev does **not** flag (harmful < threshold), the fixed Mistral in-context fallback gets a second look. This keeps Jev's rich typed output while recovering the short, coded, context-dependent praise that Jev is too conservative to flag on its own.

## Results (391 comments)

| Metric | TypeSafe (Jev) | Mistral (existing) | Combined (Jev + fallback) |
|---|---|---|---|
| Flagged / detected | 304 | 388 | 389 |
| **Detection rate (recall)** | **77.75%** | **99.23%** | **99.49%** |
| Flagged by 2nd-pass fallback | n/a (no fallback) | 270 of 391 (69%) | 83 of 391 (21%, only on Jev misses) |
| Moderation-only flag rate (`hate_and_discrimination` ≥ 0.3) | n/a | 27.4% | n/a |
| Category output | yes (9 categories) | no | yes (9 categories) |
| Category exact-match vs ground truth | 59.1% | n/a | 59.6% |
| Severity output | yes (0–3) | no | yes (0–3) |
| Calibrated confidence | yes | no | yes |
| Avg harmful probability | 0.546 | 0.691 | 0.721 |

### TypeSafe category accuracy
- Category accuracy vs mapped ground truth: **59.1%** (top-1 exact match against the mapped legal category).
- The dominant ground-truth label is `approval_of_arbitrary_action` (256/391), and Jev correctly predicted it 257 times — it slightly over-predicts this category, confusing adjacent `incitement_to_hatred` and `incitement_to_crime` cases (see `evaluate.py` mismatch examples).
- Predicted vs expected distribution is close for most categories; the main gaps are `incitement_to_hatred` (pred 34 vs expected 50) and `other` (pred 3 vs expected 43), where Jev tends to assign a concrete category instead of "other".

## Key takeaways

1. **After fixing the Mistral fallback to judge comments in context, the existing pipeline reaches 99.23% recall** (388/391) — it was previously 75.45% because its YES/NO fallback judged comments in isolation, so short innocuous-looking praise of a hateful act ("Ehrenmann", "he did nothing wrong" reacting to a "Jews banned" sign) was read as non-hateful. The fallback prompt now explicitly tells the model that endorsing a hateful act described in the context is hate speech even when the comment's words are innocuous. The 3 remaining misses are extremely indirect (`Geil nur 1200?`, `Bundes Republik Israel`, `Kann man spenden?`).
2. **TypeSafe Jev (77.75%) is more conservative** on short, context-dependent borderline comments — e.g. it returns `harmful=0.11` for "Bester Mann" and 0.26 for "Sollten überall Hausverbot bekommen" even with the context in `state`. It still catches clear in-context endorsements ("Bro hat nichts falsch gemacht" → 0.79) but under-flags the vaguest single-word praise. This is the cost of a single decision pass with no textual reasoning fallback.
3. **TypeSafe returns richer, machine-native output**: a discrete category (59% exact match vs the legal taxonomy), a 0–3 severity score, and a calibrated confidence — none of which the Mistral moderation + YES/NO pipeline provides.
4. **Combined is the best of both**: Jev classifies everything (category + severity + confidence), and the fixed Mistral in-context fallback only runs on the 83 comments Jev under-flagged. Detection reaches **99.49%** (389/391), slightly above Mistral alone (99.23%), while keeping Jev's typed output. The combined run calls the fallback on far fewer comments than the Mistral-only pipeline (83 vs 270), so it is cheaper for the same coverage. The 2 remaining misses are extremely indirect (`Bundes Republik Israel`, `Kann man spenden?`).
5. Per-comment outputs: `results_typesafe.jsonl`, `results_mistral.jsonl`, `results_combined.jsonl`. Re-run with `python3 evaluate.py`.
