# Episode transcripts

Each episode page shows a full transcript under the show notes, collapsed in a
`<details>` element but rendered server-side, so it's in the HTML that search
engines and answer engines fetch. The transcript text also goes into the page's
schema.org `PodcastEpisode` JSON-LD.

## Where things live

| Path | What |
|---|---|
| `data/transcripts/<slug>.json` | Generated transcript data, one file per `content/episodes/<slug>.md`. Don't edit by hand. |
| `scripts/import-transcripts.py` | Regenerates `data/transcripts/` from intel-layer (Python 3 stdlib only). |
| `scripts/transcript-corrections.tsv` | The one reviewable list of proper-noun fixes for Whisper mishearings. |
| `layouts/partials/transcript.html` | Renders the transcript on the episode page. |
| `layouts/partials/podcast_episode_schema.html` | `PodcastEpisode` JSON-LD (via `layouts/partials/extend_head.html`). |
| `layouts/episodes/single.html` | Copy of PaperMod's `single.html` plus the transcript partial. Re-copy it if the theme's version changes. |
| `assets/css/extended/transcript.css` | Styles. |

The canonical transcripts are in intel-layer (`git.privacy.family/seth/intel-layer`),
under `sources/transcripts/optout/<slug>.md`. They were made with Whisper
large-v3-turbo, with a `[mm:00]` stamp per 10-minute chunk and no speaker labels.
Treat intel-layer as read-only from here. Fix transcript text there.

## Importing

```bash
python3 scripts/import-transcripts.py --report
```

- By default it reads `~/repos/personal/intel-layer`. Override this with `--intel-layer PATH` or `INTEL_LAYER=PATH`.
- It fetches the Buzzsprout RSS feed for each episode's mp3 URL and duration (used in the JSON-LD). Use `--no-feed` to work offline and keep the audio data already in `data/transcripts/`.
- To import specific episodes, pass their slugs: `python3 scripts/import-transcripts.py s3e03-new-episode`.
- Transcripts without an episode page (such as the "Welcome to Opt Out" trailer) are skipped and listed.
- `--report` prints how often each correction rule fired. Check that output whenever you add a rule.

For a new episode: publish the episode page, run `make optout-new` in intel-layer to transcribe it, then re-run the import here and commit `data/transcripts/<slug>.json`.

## What the import does

1. Groups each 10-minute chunk under its stamp. The stamp becomes a timestamp that links to the YouTube video at `&t=<seconds>s` (the video ID comes from the transcript's `source_url`, or from the episode page).
2. Joins Whisper's speech segments into paragraphs. A paragraph ends at the first segment that closes a sentence once it reaches about 450 characters, and is force-split at about 1,000 characters. Some chunks have no punctuation, so the force-split is needed.
3. Applies `transcript-corrections.tsv`. Use this file only for names Whisper reliably mishears, not for editing what was said. Rules can be limited to specific episodes.

## Search

Transcripts are deliberately left out of `index.json`, the Fuse.js search index. Including them grew the index from 43 KB to 1.05 MB gzipped. Each keystroke then took 100–300 ms on a fast laptop (vs about 10 ms), and fuzzy matching over that much text returned most episodes for most queries. Transcripts reach search engines through the episode pages instead.
