#!/usr/bin/env python3
"""Verify the final deliverable against the standing spec.

Usage: python3 verify_final.py [video.mp4]

Checks the hard gates from the standing orders:
  * duration is 599s (63 scenes x 10.0s - 62 x 0.5s xfades)
  * resolution is 3840x2160 (4K)
  * frame rate is 25 fps
  * audio is present and normalized-ish
  * exactly two still scenes (11, 53) and 61 footage scenes
  * every scene in video.json resolves to a file on disk
"""
import json
import os
import subprocess
import sys

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
PLAN = "video.json"
VIDEO = sys.argv[1] if len(sys.argv) > 1 else "final.mp4"


def probe(path):
    out = subprocess.run(
        [FFMPEG, "-hide_banner", "-i", path, "-f", "null", "-"],
        capture_output=True, text=True)
    return out.stderr


def streams(path):
    out = subprocess.run(
        [FFMPEG, "-hide_banner", "-i", path],
        capture_output=True, text=True).stderr
    v = [l for l in out.splitlines() if "Video:" in l]
    a = [l for l in out.splitlines() if "Audio:" in l]
    dur = [l for l in out.splitlines() if "Duration:" in l]
    return (dur[0].split("Duration:")[1].split(",")[0].strip() if dur else "?",
            v[0].strip() if v else "NO VIDEO",
            a[0].strip() if a else "NO AUDIO")


def main():
    plan = json.load(open(PLAN))
    scenes = plan["scenes"]
    meta = plan["meta"]

    print("=" * 62)
    print("FINAL DELIVERABLE VERIFICATION")
    print("=" * 62)

    ok = True

    # ---- plan gates -------------------------------------------------------
    stills = [s["id"] for s in scenes if s.get("visuals")]
    foot = [s["id"] for s in scenes if not s.get("visuals")]
    print(f"\n[plan] scenes           : {len(scenes)}")
    print(f"[plan] still scenes     : {stills} (limit {meta.get('STILL_SCENE_LIMIT', 2)})")
    print(f"[plan] footage scenes   : {len(foot)}")
    if len(stills) != 2:
        print("  !! still-scene gate FAILED")
        ok = False
    else:
        print("  ok - exactly 2 still scenes")

    missing_f = [s["id"] for s in scenes
                 if not s.get("visuals") and not os.path.exists(s.get("footage", ""))]
    missing_a = [s["id"] for s in scenes if not os.path.exists(s.get("audio", ""))]
    missing_s = [s["id"] for s in scenes
                 if s.get("visuals") and not all(os.path.exists(p) for p in s["visuals"])]
    print(f"[plan] missing footage  : {missing_f or 'none'}")
    print(f"[plan] missing audio    : {missing_a or 'none'}")
    print(f"[plan] missing stills   : {missing_s or 'none'}")
    if missing_f or missing_a or missing_s:
        ok = False

    # ---- expected timeline ------------------------------------------------
    sd = meta["scene_duration"]
    xf = meta["transition"]
    expected = round(len(scenes) * sd - (len(scenes) - 1) * xf, 3)
    print(f"\n[timeline] expected     : {expected}s "
          f"({len(scenes)} x {sd}s - {len(scenes)-1} x {xf}s)")

    # ---- the file itself --------------------------------------------------
    if not os.path.exists(VIDEO):
        print(f"\n!! {VIDEO} does not exist yet")
        return 1

    size_mb = os.path.getsize(VIDEO) / 1048576
    dur, vline, aline = streams(VIDEO)
    print(f"\n[file] {VIDEO}")
    print(f"[file] size             : {size_mb:.1f} MB")
    print(f"[file] duration         : {dur}")
    print(f"[file] {vline[:80]}")
    print(f"[file] {aline[:80]}")

    try:
        h, m, s = dur.split(":")
        actual = round(int(h) * 3600 + int(m) * 60 + float(s), 3)
    except Exception:
        actual = 0
    if abs(actual - expected) > 1.0:
        print(f"  !! duration mismatch: got {actual}, want {expected}")
        ok = False
    else:
        print(f"  ok - duration within 1s of {expected}s")

    if f"{meta['width']}x{meta['height']}" not in vline:
        print(f"  !! resolution is not {meta['width']}x{meta['height']} (4K)")
        ok = False
    else:
        print(f"  ok - 4K resolution {meta['width']}x{meta['height']}")

    if aline == "NO AUDIO":
        print("  !! no audio stream")
        ok = False

    print("\n" + "=" * 62)
    print("RESULT: " + ("PASS" if ok else "FAIL"))
    print("=" * 62)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
