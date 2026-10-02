#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Download every footage clip the plan needs, straight from the Pexels API.

Run this on a machine with normal internet access:

    python3 download_footage.py --key YOUR_PEXELS_API_KEY

or export the key instead of passing it on the command line:

    export PEXELS_API_KEY=YOUR_PEXELS_API_KEY
    python3 download_footage.py

The key is read from, in order: --key, $PEXELS_API_KEY, brand/pexels_key.txt.
brand/pexels_key.txt is gitignored so the key never reaches the repository.

For every scene in video.json that needs footage it:
  1. searches Pexels with the scene's English `footage_query`
  2. picks the best landscape mp4 (prefers 4K, then 1080p, then whatever fits)
  3. downloads it to brand/footage/scene-NN.mp4

Re-runnable: files that already exist are skipped, so an interrupted run
resumes where it stopped.
"""
import argparse
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REPO = os.path.dirname(os.path.abspath(__file__))
API = "https://api.pexels.com/videos/search"
OUT_DIR = os.path.join(REPO, "brand", "footage")
KEY_FILE = os.path.join(REPO, "brand", "pexels_key.txt")


def resolve_key(cli_key):
    if cli_key:
        return cli_key
    env = os.environ.get("PEXELS_API_KEY")
    if env:
        return env.strip()
    if os.path.exists(KEY_FILE):
        with io.open(KEY_FILE, encoding="utf-8") as f:
            return f.read().strip()
    return None


def api_get(url, key, tries=4):
    """GET with the Pexels auth header, retrying on transient failures."""
    for attempt in range(tries):
        req = urllib.request.Request(url, headers={"Authorization": key})
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise SystemExit("ERROR: Pexels rejected the key (HTTP %d). "
                                 "Check it at https://www.pexels.com/api/" % e.code)
            if e.code == 429:
                wait = 15 * (attempt + 1)
                print("      rate limited, waiting %ds" % wait)
                time.sleep(wait)
                continue
            if 500 <= e.code < 600:
                time.sleep(3 * (attempt + 1))
                continue
            raise
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    return None


def pick_file(video):
    """Best mp4 for a 16:9 timeline: 4K > 1440p > 1080p > anything."""
    files = [f for f in video.get("video_files", [])
             if (f.get("file_type") or "").endswith("mp4")]
    if not files:
        return None
    landscape = [f for f in files
                 if (f.get("width") or 0) >= (f.get("height") or 1)]
    pool = landscape or files

    def score(f):
        w = f.get("width") or 0
        if w >= 3840:
            return (4, w)
        if w >= 2560:
            return (3, w)
        if w >= 1920:
            return (2, w)
        return (1, w)

    return max(pool, key=score)


def download(url, dest, tries=4):
    tmp = dest + ".part"
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
            with urllib.request.urlopen(req, timeout=180) as r, \
                    open(tmp, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            os.replace(tmp, dest)
            return os.path.getsize(dest)
        except Exception:
            if attempt == tries - 1:
                if os.path.exists(tmp):
                    os.remove(tmp)
                raise
            time.sleep(3 * (attempt + 1))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", help="Pexels API key (or set PEXELS_API_KEY)")
    ap.add_argument("--per-page", type=int, default=10)
    ap.add_argument("--only", type=int, action="append", default=[],
                    help="download only this scene id (repeatable)")
    ap.add_argument("--dry-run", action="store_true",
                    help="show the searches without downloading")
    args = ap.parse_args()

    key = resolve_key(args.key)
    if not key:
        raise SystemExit("ERROR: no Pexels key.\n"
                         "  pass --key, export PEXELS_API_KEY, or put it in "
                         "brand/pexels_key.txt")

    with io.open(os.path.join(REPO, "video.json"), encoding="utf-8") as f:
        plan = json.load(f)

    todo = [s for s in plan["scenes"] if not s.get("visuals")]
    if args.only:
        todo = [s for s in todo if s["id"] in args.only]
    os.makedirs(OUT_DIR, exist_ok=True)

    ok, skipped, failed = 0, 0, []
    for i, sc in enumerate(todo, 1):
        sid = sc["id"]
        dest = os.path.join(OUT_DIR, "scene-%02d.mp4" % sid)
        if os.path.exists(dest) and os.path.getsize(dest) > 10000:
            skipped += 1
            print("[%2d/%2d] scene %02d already present" % (i, len(todo), sid))
            continue

        query = sc.get("footage_query", "")
        if not query:
            failed.append((sid, "no footage_query in video.json"))
            print("[%2d/%2d] scene %02d NO QUERY" % (i, len(todo), sid))
            continue

        print("[%2d/%2d] scene %02d  search: %s" % (i, len(todo), sid, query))
        if args.dry_run:
            continue

        url = ("%s?query=%s&per_page=%d&orientation=landscape"
               % (API, urllib.parse.quote(query), args.per_page))
        data = api_get(url, key)
        videos = (data or {}).get("videos") or []
        if not videos:
            failed.append((sid, "no results for %r" % query))
            print("      !! no results")
            continue

        chosen = None
        for v in videos:
            f = pick_file(v)
            if f:
                chosen = (v, f)
                break
        if not chosen:
            failed.append((sid, "no mp4 in results for %r" % query))
            print("      !! no mp4 in results")
            continue

        v, f = chosen
        try:
            size = download(f["link"], dest)
        except Exception as e:
            failed.append((sid, "download failed: %s" % e))
            print("      !! download failed: %s" % e)
            continue

        ok += 1
        print("      -> %dx%d  %.1f MB  (pexels id %s)"
              % (f.get("width") or 0, f.get("height") or 0,
                 size / 1048576.0, v.get("id")))
        time.sleep(0.4)          # be polite to the API

    print()
    print("=" * 62)
    print("downloaded : %d" % ok)
    print("already had: %d" % skipped)
    print("failed     : %d" % len(failed))
    for sid, why in failed:
        print("   scene %02d: %s" % (sid, why))
    print("=" * 62)
    if failed:
        print("Re-run the same command to retry only what failed.")
    else:
        print("All footage present. Build with:")
        print("    python3 build_video.py video.json")


if __name__ == "__main__":
    main()
