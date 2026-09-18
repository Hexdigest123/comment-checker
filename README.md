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
- `EXPORTCOMMENTS_API_KEY` for direct URL export (optional, requires ExportComments Premium/Business plan)

## Usage

### Option 1: Classify from CSV File

```bash
python main.py --predict <FILE> --context "<context>" [options]
```

### Option 2: Direct Export from Social Media URL (NEW)

```bash
python main.py --export-url <URL> --context "<context>" [options]
```

This uses the ExportComments.com API to automatically export comments from
20+ social media platforms (Instagram, YouTube, Facebook, TikTok, Twitter/X, etc.)
and then classify them using the Mistral pipeline.

### Common Options

| Option | Default | Description |
|---|---|---|
| `--predict`, `-p` | `assets/test-data.csv` | CSV file to classify |
| `--export-url`, `-u` | None | Social media URL to export and classify |
| `--max` | `20` | Maximum number of comments to classify |
| `--threshold` | `0.3` | Probability threshold for flagging |
| `--context` | (required) | Context the comments react to |
| `--backend` | `mistral` | `mistral` (only option currently) |
| `--fallback` / `--no-fallback` | on | Run the second-pass in-context fallback |
| `--out` | `results_<backend>.jsonl` | Output JSONL path |

### ExportComments Options (for --export-url)

| Option | Default | Description |
|---|---|---|
| `--include-replies` | False | Include reply threads in export |
| `--wait` | True | Wait for export to complete before processing |
| `--timeout` | `300` | Maximum seconds to wait for export (default: 5 min) |
| `--poll-interval` | `2.0` | Seconds between status checks when waiting |

## Backends and variants

The `--backend` and `--fallback` flags together give four evaluation variants.

| Variant | Command | First pass | Fallback |
|---|---|---|---|
| Mistral Moderation 2 only | `--backend mistral --no-fallback` | Mistral Moderation 2 | none |
| Mistral Moderation 2 + fallback | `--backend mistral` | Mistral Moderation 2 | `mistral-small-latest` in-context YES/NO |

## Examples

### CSV File Classification

```bash
CONTEXT="A shop owner posted a 'Jews banned' sign and was convicted for incitement to hatred. Comments react to this case."

# Classify from CSV file
MISTRAL_API_KEY=... python main.py --predict assets/test-data3-clean.csv --max 391 --context "$CONTEXT" --backend mistral --out results_mistral.jsonl
```

### Direct URL Export and Classification (NEW)

```bash
# Set your ExportComments API key
EXPORTCOMMENTS_API_KEY=your_exportcomments_api_key
MISTRAL_API_KEY=your_mistral_api_key

CONTEXT="A shop owner posted a 'Jews banned' sign and was convicted for incitement to hatred. Comments react to this case."

# Export and classify from Instagram post
EXPORTCOMMENTS_API_KEY=... MISTRAL_API_KEY=... python main.py \
  --export-url "https://www.instagram.com/p/DZDH8YstgWl/" \
  --context "$CONTEXT" \
  --max 100 \
  --out results_instagram.jsonl

# Export with replies included
EXPORTCOMMENTS_API_KEY=... MISTRAL_API_KEY=... python main.py \
  --export-url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" \
  --include-replies \
  --context "$CONTEXT" \
  --out results_youtube.jsonl

# Export and classify from Facebook post
EXPORTCOMMENTS_API_KEY=... MISTRAL_API_KEY=... python main.py \
  --export-url "https://www.facebook.com/..." \
  --context "$CONTEXT" \
  --timeout 600 \
  --out results_facebook.jsonl
```

### CSV Export Fallback

If you have a CSV file exported from ExportComments.com, you can use it directly:

```bash
# Using a previously exported CSV from ExportComments
MISTRAL_API_KEY=... python main.py \
  --predict exported_comments.csv \
  --context "$CONTEXT" \
  --out results.csv
```

The system automatically detects ExportComments CSV format and maps columns
(Comment, Username, Date, Likes, etc.) to the internal format.

## Evaluation

Summarize and compare the result files:

```bash
python evaluate.py
```

`evaluate.py` reads `results_typesafe.jsonl`, `results_mistral.jsonl`, and
`results_combined.jsonl` from the current directory and prints detection rate,
category accuracy (TypeSafe/combined), and the fallback contribution. If a
file is missing it is skipped, so you can run only the variants you need.

## CSV Format Support

The system supports multiple CSV formats:

### Internal Format (Original)
```csv
Priorit\u00e4t,Straftatbestand (Verdacht),Kategorie,Begr\u00fcndung,Name,Username,Profile ID,Date,Likes,Comment,User Verified,Comment ID,Profile URL,Comment URL,Thumbnail,Lfd. Nr. (Original-Export)
```

### ExportComments Format (Automatically Mapped)
```csv
text,username,author,timestamp,likes,url,permalink,profile_url,user_id,comment_id,avatar
```

The system automatically maps ExportComments columns to internal format:
- `text` -> `Comment`
- `username` / `author` -> `Username`
- `timestamp` / `created_at` -> `Date`
- `likes` -> `Likes`
- `url` / `permalink` -> `Comment URL`
- `profile_url` -> `Profile URL`
- etc.

## ExportComments Integration

### Requirements for Direct API Integration

1. **ExportComments Account**: Sign up at https://app.exportcomments.com
2. **Premium or Business Plan**: Required for API access
3. **API Key**: Obtain from the API dashboard at https://app.exportcomments.com/api
4. **Environment Variable**: Set `EXPORTCOMMENTS_API_KEY`

### Supported Platforms

The ExportComments API supports 20+ platforms:
- Instagram (posts, reels, stories)
- YouTube (videos, shorts)
- Facebook (posts, pages, groups)
- TikTok (videos)
- Twitter/X (tweets)
- Reddit (posts, comments)
- And many more...

### API Features Used

- **Job Creation**: `POST /api/v3/job`
- **Status Polling**: `GET /api/v3/job/{id}`
- **Result Download**: `GET /api/v3/job/{id}/download`
- **Format Options**: CSV, Excel, JSON
- **Reply Inclusion**: Optional nested comment threads

For more information on ExportComments API, see: https://exportcomments.com/api

## LICENSE

All rights reserved.
Copyright (c) 2026
