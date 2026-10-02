#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Last resort: hunt for real stock footage hosted on GitHub itself.

github.com is the only reachable host from this sandbox, so before asking the
user to download 61 clips by hand, sweep GitHub for repositories that actually
carry .mp4 footage and report which ones look usable.
"""
import json
import urllib.parse
import urllib.request

QUERIES = [
    "stock footage", "broll", "b-roll", "free footage", "stock video",
    "video clips collection", "nature footage", "rain video", "footage pack",
    "cinematic footage", "video library", "stock-video", "video assets",
]


def get(url):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "footage-hunt"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def tree_mp4s(full_name, limit=400):
    try:
        d = get("https://api.github.com/repos/%s/git/trees/HEAD?recursive=1"
                % full_name)
    except Exception:
        return []
    out = []
    for t in d.get("tree", []):
        p = t.get("path", "")
        if p.lower().endswith((".mp4", ".mov", ".m4v", ".webm")):
            out.append(p)
        if len(out) >= limit:
            break
    return out


def main():
    seen = {}
    for q in QUERIES:
        url = ("https://api.github.com/search/repositories?q=%s"
               "&sort=stars&per_page=20" % urllib.parse.quote(q))
        try:
            d = get(url)
        except Exception as e:
            print("search %r failed: %s" % (q, e))
            continue
        for r in d.get("items", []):
            fn = r["full_name"]
            if fn in seen:
                continue
            seen[fn] = {"stars": r["stargazers_count"],
                        "size_mb": r["size"] / 1024.0,
                        "desc": (r.get("description") or "")[:70]}
    print("candidate repos: %d" % len(seen))
    print("scanning trees for real video files...\n")

    hits = []
    for fn, meta in sorted(seen.items(), key=lambda kv: -kv[1]["size_mb"]):
        if meta["size_mb"] < 3:
            continue
        vids = tree_mp4s(fn)
        if len(vids) >= 3:
            hits.append((fn, meta, vids))
            print("== %s  (%.0fMB, %d videos)" % (fn, meta["size_mb"], len(vids)))
            for v in vids[:6]:
                print("     ", v)
    print("\nrepos with >=3 video files: %d" % len(hits))


if __name__ == "__main__":
    main()
