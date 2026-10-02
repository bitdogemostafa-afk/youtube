#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Download every footage clip the plan needs, from Pexels or Pixabay.

    python3 download_footage.py --provider pixabay --key YOUR_KEY
    python3 download_footage.py --provider pexels   --key YOUR_KEY

The key is read from, in order: --key, then the provider's env var
(PIXABAY_API_KEY / PEXELS_API_KEY), then brand/<provider>_key.txt.
Those key files are gitignored so a key never reaches the repository.

For every scene in video.json that needs footage it:
  1. searches with the scene's English `footage_query`
  2. if that returns nothing, retries with progressively shorter queries
     (Pixabay's library is much smaller than Pexels')
  3. picks the best landscape mp4 (largest resolution available)
  4. downloads it to brand/footage/scene-NN.mp4

Re-runnable: existing files are skipped, so an interrupted run resumes.
"""
import argparse
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

REPO = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(REPO, "brand", "footage")

PEXELS_API = "https://api.pexels.com/videos/search"
PIXABAY_API = "https://pixabay.com/api/videos/"

ENV_VAR = {"pexels": "PEXELS_API_KEY", "pixabay": "PIXABAY_API_KEY"}
KEY_FILE = {"pexels": "pexels_key.txt", "pixabay": "pixabay_key.txt"}

# Pixabay quality tiers, best first
PIXABAY_TIERS = ("large", "medium", "small", "tiny")


def resolve_key(provider, cli_key):
    if cli_key:
        return cli_key
    env = os.environ.get(ENV_VAR[provider])
    if env:
        return env.strip()
    path = os.path.join(REPO, "brand", KEY_FILE[provider])
    if os.path.exists(path):
        with io.open(path, encoding="utf-8") as f:
            return f.read().strip()
    return None


def http_get(url, headers=None, tries=4, timeout=45):
    for attempt in range(tries):
        req = urllib.request.Request(url, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                body = ""
                try:
                    body = e.read().decode("utf-8", "replace")[:200]
                except Exception:
                    pass
                raise SystemExit("ERROR: the API rejected the key (HTTP %d) %s\n"
                                 "  -> check the key at the provider's dashboard"
                                 % (e.code, body))
            if e.code == 429:
                wait = 20 * (attempt + 1)
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


def api_json(url, headers=None):
    return json.loads(http_get(url, headers).decode("utf-8"))


# ---------------------------------------------------------------- providers

def search_pexels(query, key, per_page):
    url = ("%s?query=%s&per_page=%d&orientation=landscape"
           % (PEXELS_API, urllib.parse.quote(query), per_page))
    data = api_json(url, {"Authorization": key})
    out = []
    for v in data.get("videos", []):
        files = [f for f in v.get("video_files", [])
                 if (f.get("file_type") or "").endswith("mp4")]
        if not files:
            continue
        best = max(files, key=lambda f: f.get("width") or 0)
        out.append({"url": best["link"],
                    "w": best.get("width") or 0,
                    "h": best.get("height") or 0,
                    "id": v.get("id"),
                    "tags": ""})
    return out


def search_pixabay(query, key, per_page):
    url = ("%s?key=%s&q=%s&video_type=all&per_page=%d&safesearch=true"
           % (PIXABAY_API, urllib.parse.quote(key),
              urllib.parse.quote(query), per_page))
    data = api_json(url)
    out = []
    for h in data.get("hits", []):
        vids = h.get("videos") or {}
        chosen = None
        for tier in PIXABAY_TIERS:
            f = vids.get(tier)
            if f and f.get("url"):
                chosen = f
                break
        if not chosen:
            continue
        out.append({"url": chosen["url"],
                    "w": chosen.get("width") or 0,
                    "h": chosen.get("height") or 0,
                    "id": h.get("id"),
                    "tags": h.get("tags", "")[:70]})
    return out


SEARCH = {"pexels": search_pexels, "pixabay": search_pixabay}


def download(url, dest, referer, tries=4):
    """Download with a browser-ish UA; Pixabay rejects bare urllib."""
    tmp = dest + ".part"
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
               "Referer": referer}
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=240) as r, \
                    open(tmp, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            if os.path.getsize(tmp) < 20000:
                raise IOError("suspiciously small file")
            os.replace(tmp, dest)
            return os.path.getsize(dest)
        except Exception:
            if attempt == tries - 1:
                if os.path.exists(tmp):
                    os.remove(tmp)
                raise
            time.sleep(3 * (attempt + 1))
    return 0


def query_variants(query):
    """The exact query first, then progressively shorter versions."""
    words = query.split()
    variants = [query]
    for n in range(len(words) - 1, 1, -1):
        v = " ".join(words[:n])
        if v not in variants:
            variants.append(v)
    return variants


# ------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=("pexels", "pixabay"),
                    default=os.environ.get("FOOTAGE_PROVIDER", "pixabay"))
    ap.add_argument("--key", help="API key (or set the provider's env var)")
    ap.add_argument("--per-page", type=int, default=20)
    ap.add_argument("--only", type=int, action="append", default=[],
                    help="download only this scene id (repeatable)")
    ap.add_argument("--dry-run", action="store_true",
                    help="show the searches without downloading")
    args = ap.parse_args()

    provider = args.provider
    key = resolve_key(provider, args.key)
    if not key:
        raise SystemExit("ERROR: no %s key.\n"
                         "  pass --key, export %s, or put it in brand/%s"
                         % (provider, ENV_VAR[provider], KEY_FILE[provider]))
    print("provider: %s   key: %s...%s (%d chars)"
          % (provider, key[:6], key[-4:], len(key)))

    with io.open(os.path.join(REPO, "video.json"), encoding="utf-8") as f:
        plan = json.load(f)

    todo = [s for s in plan["scenes"] if not s.get("visuals")]
    if args.only:
        todo = [s for s in todo if s["id"] in args.only]
    os.makedirs(OUT_DIR, exist_ok=True)

    referer = "https://%s.com/" % provider
    ok, skipped, failed = 0, 0, []
    search_fn = SEARCH[provider]

    for i, sc in enumerate(todo, 1):
        sid = sc["id"]
        dest = os.path.join(OUT_DIR, "scene-%02d.mp4" % sid)
        if os.path.exists(dest) and os.path.getsize(dest) > 20000:
            skipped += 1
            print("[%2d/%2d] scene %02d already present" % (i, len(todo), sid))
            continue

        query = sc.get("footage_query", "")
        if not query:
            failed.append((sid, "no footage_query in video.json"))
            continue

        print("[%2d/%2d] scene %02d  %s" % (i, len(todo), sid, query))
        if args.dry_run:
            continue

        results, used = [], None
        for variant in query_variants(query):
            try:
                results = search_fn(variant, key, args.per_page)
            except SystemExit:
                raise
            except Exception as e:
                print("      search error: %s" % e)
                results = []
            if results:
                used = variant
                break
            if variant != query:
                print("      (shortened to %r)" % variant)
            time.sleep(0.7)

        if not results:
            failed.append((sid, "no results for %r" % query))
            print("      !! no results")
            continue

        # prefer the widest clip; ties go to the earlier (more relevant) hit
        best = max(results, key=lambda r: r["w"])
        if used != query:
            print("      matched via %r" % used)
        if best.get("tags"):
            print("      tags: %s" % best["tags"])

        try:
            size = download(best["url"], dest, referer)
        except Exception as e:
            failed.append((sid, "download failed: %s" % e))
            print("      !! download failed: %s" % e)
            continue

        ok += 1
        print("      -> %dx%d  %.1f MB  (id %s)"
              % (best["w"], best["h"], size / 1048576.0, best["id"]))
        time.sleep(0.7)

    print()
    print("=" * 64)
    print("downloaded : %d" % ok)
    print("already had: %d" % skipped)
    print("failed     : %d" % len(failed))
    for sid, why in failed:
        print("   scene %02d: %s" % (sid, why))
    print("=" * 64)
    if failed:
        print("Re-run the same command to retry only what failed.")
        print("Scenes that stay empty can be searched by hand on %s.com"
              % provider)
    else:
        print("All footage present. Build with:")
        print("    python3 build_video.py video.json")


if __name__ == "__main__":
    main()
