#!/usr/bin/env python3
"""Import Opt Out episode transcripts from intel-layer into data/transcripts/.

Reads   <intel-layer>/sources/transcripts/optout/<slug>.md  (read-only)
Writes  data/transcripts/<slug>.json, one per episode page in content/episodes/

Each output file holds the transcript split into 10-minute chunks and readable
paragraphs, with proper-noun fixes from scripts/transcript-corrections.tsv
applied, plus the episode's audio enclosure and duration from the Buzzsprout
feed. layouts/partials/transcript.html renders it on the episode page and
layouts/partials/podcast_episode_schema.html puts it in the JSON-LD.

Python 3 stdlib only. See scripts/README.md.
"""

import argparse
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EPISODES = REPO / "content" / "episodes"
OUT = REPO / "data" / "transcripts"
CORRECTIONS = REPO / "scripts" / "transcript-corrections.tsv"
DEFAULT_INTEL = Path(os.environ.get("INTEL_LAYER", "~/repos/personal/intel-layer")).expanduser()
FEED_URL = "https://feeds.buzzsprout.com/1790481.rss"

STAMP = re.compile(r"^\[(\d+):00\]\s?")
YOUTUBE_ID = re.compile(r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|live/))([A-Za-z0-9_-]{11})")
BUZZSPROUT_ID = re.compile(r"buzzsprout-player-(\d+)")

# Paragraphing: Whisper emits one line per speech segment. A paragraph closes at
# the first segment that ends a sentence once it has MIN_PARA characters, or at
# any segment once it reaches MAX_PARA (some speakers rarely end a sentence).
MIN_PARA = 450
MAX_PARA = 1000
SENTENCE_END = re.compile(r"""[.?!]["')\]]*$""")


def parse_front_matter(text):
    """Split '---' YAML front matter from the body. Values are scalars or
    JSON-style lists, which is all intel-layer writes."""
    if not text.startswith("---\n"):
        return {}, text
    head, body = text[4:].split("\n---\n", 1)
    meta = {}
    for line in head.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.split(" #", 1)[0].strip()
        try:
            meta[key.strip()] = json.loads(value)
        except ValueError:
            meta[key.strip()] = value.strip("'\"")
    return meta, body


def load_corrections(path):
    rules = []
    for n, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            sys.exit(f"{path}:{n}: expected pattern<TAB>replacement[<TAB>slugs]")
        pattern, replacement = parts[0], parts[1]
        slugs = {s.strip() for s in parts[2].split(",")} if len(parts) > 2 and parts[2].strip() else None
        regex = re.compile(r"\b(?:" + pattern + r")\b", re.IGNORECASE)
        rules.append({"line": n, "pattern": pattern, "regex": regex, "replacement": replacement, "slugs": slugs, "hits": 0})
    return rules


def correct(text, slug, rules):
    for rule in rules:
        if rule["slugs"] and slug not in rule["slugs"]:
            continue
        text, n = rule["regex"].subn(rule["replacement"], text)
        rule["hits"] += n
    return text


def paragraphs(segments):
    paras, current = [], ""
    for seg in segments:
        current = f"{current} {seg}" if current else seg
        if (len(current) >= MIN_PARA and SENTENCE_END.search(seg)) or len(current) >= MAX_PARA:
            paras.append(current)
            current = ""
    if current:
        paras.append(current)
    return paras


def chunks(body, slug, rules):
    out = []
    for line in body.splitlines():
        m = STAMP.match(line)
        if m:
            out.append({"t": int(m.group(1)) * 60, "segments": []})
            line = line[m.end():]
        seg = " ".join(line.split())
        if seg and out:
            out[-1]["segments"].append(correct(seg, slug, rules))
    return [{"t": c["t"], "paragraphs": paragraphs(c["segments"])} for c in out if c["segments"]]


def load_feed(source):
    """Map Buzzsprout episode id -> {url, duration, size} from the podcast RSS."""
    if re.match(r"https?://", source):
        req = urllib.request.Request(source, headers={"User-Agent": "optoutpod.com transcript import"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
    else:
        data = Path(source).read_bytes()
    itunes = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
    feed = {}
    for item in ET.fromstring(data).iter("item"):
        guid = (item.findtext("guid") or "").removeprefix("Buzzsprout-")
        enc = item.find("enclosure")
        if not guid or enc is None:
            continue
        duration = item.findtext(f"{itunes}duration") or ""
        if ":" in duration:  # hh:mm:ss form
            duration = sum(int(p) * 60 ** i for i, p in enumerate(reversed(duration.split(":"))))
        feed[guid] = {
            "url": enc.get("url"),
            "type": enc.get("type") or "audio/mpeg",
            "duration": int(duration) if str(duration).isdigit() else None,
            "size": int(enc.get("length")) if (enc.get("length") or "").isdigit() else None,
        }
    return feed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--intel-layer", type=Path, default=DEFAULT_INTEL,
                    help="intel-layer checkout (default: $INTEL_LAYER or ~/repos/personal/intel-layer)")
    ap.add_argument("--feed", default=FEED_URL, help="podcast RSS URL or local file, for audio URLs and durations")
    ap.add_argument("--no-feed", action="store_true", help="skip the feed and keep audio data already in data/transcripts/")
    ap.add_argument("--report", action="store_true", help="print how many times each correction rule fired")
    ap.add_argument("slugs", nargs="*", help="only import these episode slugs (default: all)")
    args = ap.parse_args()

    src = args.intel_layer.expanduser() / "sources" / "transcripts" / "optout"
    if not src.is_dir():
        sys.exit(f"transcripts not found: {src} (pass --intel-layer or set INTEL_LAYER)")
    rules = load_corrections(CORRECTIONS)

    feed = {}
    if not args.no_feed:
        try:
            feed = load_feed(args.feed)
        except Exception as e:  # keep going: audio data from the last import is reused below
            print(f"warning: feed unavailable ({e}); keeping existing audio data", file=sys.stderr)

    OUT.mkdir(parents=True, exist_ok=True)
    slugs = args.slugs or sorted(p.stem for p in src.glob("*.md"))
    written, skipped = 0, []
    for slug in slugs:
        page, transcript = EPISODES / f"{slug}.md", src / f"{slug}.md"
        if not page.exists() or not transcript.exists():
            skipped.append(slug)
            continue
        meta, body = parse_front_matter(transcript.read_text())
        page_text = page.read_text()
        out_path = OUT / f"{slug}.json"
        previous = json.loads(out_path.read_text()) if out_path.exists() else {}

        yt = YOUTUBE_ID.search(str(meta.get("source_url", ""))) or YOUTUBE_ID.search(page_text)
        bz = BUZZSPROUT_ID.search(page_text)
        audio = feed.get(bz.group(1)) if bz else None
        if not audio:
            audio = previous.get("audio")
            if not args.no_feed and feed:
                print(f"warning: {slug}: no feed item for its Buzzsprout player", file=sys.stderr)

        doc = {
            "_comment": "Generated by scripts/import-transcripts.py from intel-layer. Do not edit by hand; "
                        "fix the source or scripts/transcript-corrections.tsv and re-run.",
            "source": f"intel-layer/sources/transcripts/optout/{slug}.md",
            "model": meta.get("model"),
            "transcribed": meta.get("transcribed"),
            "repaired_chunks": meta.get("repaired_chunks") or [],
            "youtube_id": yt.group(1) if yt else None,
            "audio": audio,
            "chunks": chunks(body, slug, rules),
        }
        doc["word_count"] = sum(len(p.split()) for c in doc["chunks"] for p in c["paragraphs"])
        out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
        written += 1

    print(f"wrote {written} transcript(s) to {OUT.relative_to(REPO)}/")
    if skipped:
        print(f"skipped (no episode page or no transcript): {', '.join(skipped)}")
    if args.report:
        for rule in rules:
            scope = f"  [{','.join(sorted(rule['slugs']))}]" if rule["slugs"] else ""
            print(f"{rule['hits']:5d}  line {rule['line']:3d}  {rule['pattern']} -> {rule['replacement']}{scope}")


if __name__ == "__main__":
    main()
