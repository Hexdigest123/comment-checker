# Comment Analysis

Classifies comments as hate speech using either TypeSafe's Jev (System One)
model or the existing Mistral Moderation 2 pipeline, with an optional
in-context chat fallback. Results are written as JSONL.

## Setup

```bash
make setup          # creates .venv and installs requirements.txt
source .venv/bin/activate
```

Required environment variables:

- `TYPESAFE_API_KEY` for `--backend typesafe` and `--backend combined`
- `MISTRAL_API_KEY` for `--backend mistral` and `--backend combined`

## Usage

```bash
python main.py --predict <FILE> --context "<context>" [options]
```

`--context` is required. It describes the situation the comments react to so
the model judges them in context, not in isolation. This matters for short,
coded comments whose meaning depends on the situation.

### Options

| Option | Default | Description |
|---|---|---|
| `--predict`, `-p` | `assets/test-data.csv` | CSV file to classify |
| `--max` | `20` | Maximum number of comments to classify |
| `--threshold` | `0.3` | Probability threshold for flagging |
| `--context` | (required) | Context the comments react to |
| `--backend` | `typesafe` | `typesafe`, `mistral`, or `combined` |
| `--fallback` / `--no-fallback` | on | Run the second-pass in-context fallback |
| `--out` | `results_<backend>.jsonl` | Output JSONL path |

## Backends and variants

The `--backend` and `--fallback` flags together give four evaluation variants.

| Variant | Command | First pass | Fallback |
|---|---|---|---|
| Jev only | `--backend typesafe` | TypeSafe Jev | none (Jev has no fallback) |
| Mistral Moderation 2 only | `--backend mistral --no-fallback` | Mistral Moderation 2 | none |
| Mistral Moderation 2 + fallback | `--backend mistral` | Mistral Moderation 2 | `mistral-small-latest` in-context YES/NO |
| Jev + Mistral fallback (combined) | `--backend combined` | TypeSafe Jev | `mistral-small-latest` in-context YES/NO, only on Jev misses |

`--no-fallback` has no effect on `--backend typesafe` (Jev has no fallback by
design).

### Examples

```bash
CONTEXT="A shop owner posted a 'Jews banned' sign and was convicted for incitement to hatred. Comments react to this case."

# Jev only
TYPESAFE_API_KEY=... python main.py --predict assets/test-data3-clean.csv --max 391 --context "$CONTEXT" --backend typesafe --out results_typesafe.jsonl

# Mistral Moderation 2 only (no fallback)
MISTRAL_API_KEY=... python main.py --predict assets/test-data3-clean.csv --max 391 --context "$CONTEXT" --backend mistral --no-fallback --out results_mistral_moderation.jsonl

# Mistral Moderation 2 + fallback
MISTRAL_API_KEY=... python main.py --predict assets/test-data3-clean.csv --max 391 --context "$CONTEXT" --backend mistral --out results_mistral.jsonl

# Combined: Jev classifies, fallback handles Jev misses
TYPESAFE_API_KEY=... MISTRAL_API_KEY=... python main.py --predict assets/test-data3-clean.csv --max 391 --context "$CONTEXT" --backend combined --out results_combined.jsonl
```

## Evaluation

Summarize and compare the result files:

```bash
python evaluate.py
```

`evaluate.py` reads `results_typesafe.jsonl`, `results_mistral.jsonl`, and
`results_combined.jsonl` from the current directory and prints detection rate,
category accuracy (TypeSafe/combined), and the fallback contribution. If a
file is missing it is skipped, so you can run only the variants you need.

## LICENSE

All rights reserved.
Copyright (c) 2026
