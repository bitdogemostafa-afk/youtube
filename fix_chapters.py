#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""seo-manager employee: chapter timestamps must match the real timeline.

Scene N starts at (N-1) * (scene_duration - transition_duration) because every
scene crossfades into the next one.  The description below was written by hand
and had drifted by up to ~100s, so recompute every stamp from the plan.
"""
import io
import json
import os

REPO = os.path.dirname(os.path.abspath(__file__))

# chapter label -> first scene id of that section
CHAPTERS = [
    ("اللغز", 1),              # scenes 1-4    hook / the mystery
    ("اسم الريحة", 5),          # scenes 5-8    petrichor named 1964
    ("صانع الريحة", 9),         # scenes 9-13   Streptomyces + geosmin
    ("إزاي توصل لأنفك", 14),    # scenes 14-22  MIT aerosol mechanism
    ("الريحة قبل المطر", 23),   # scenes 23-25  ozone vs petrichor
    ("أنفك ضد القرش", 26),      # scenes 26-31  5 parts per trillion
    ("رسالة للحشرات", 32),      # scenes 32-43  springtails + culture
    ("ليه بنحبها", 44),         # scenes 44-49  memory + relief
    ("الإجابة", 50),            # scenes 50-63  the answer + CTA
]


def stamp(seconds):
    seconds = int(seconds)          # floor: never point past the section start
    return "%02d:%02d" % (seconds // 60, seconds % 60)


def main():
    with io.open(os.path.join(REPO, "video.json"), encoding="utf-8") as f:
        plan = json.load(f)

    meta = plan["meta"]
    sdur = float(meta.get("scene_duration", 10.0))
    xfade = float(meta.get("transition_duration", 0.5))
    step = sdur - xfade
    n_scenes = len(plan["scenes"])
    total = n_scenes * sdur - (n_scenes - 1) * xfade

    lines = []
    for label, sid in CHAPTERS:
        if not (1 <= sid <= n_scenes):
            raise SystemExit("chapter %s points at scene %d which does not exist"
                             % (label, sid))
        lines.append("%s %s" % (stamp((sid - 1) * step), label))

    chapters = "\n".join(lines)

    import re

    md = plan["metadata"]
    lines = md["description"].split("\n")
    # the chapter block is the run of lines that start with a mm:ss stamp
    chap = [i for i, l in enumerate(lines) if re.match(r"^\d{2}:\d{2}\s", l)]
    if not chap:
        raise SystemExit("no chapter lines found in the description")
    first, last = chap[0], chap[-1]
    intro = "\n".join(lines[:first]).rstrip()
    rest = "\n".join(lines[last + 1:]).strip()
    md["description"] = intro + "\n\n" + chapters + ("\n\n" + rest if rest else "")

    plan["history"].append({
        "stage": "seo-manager",
        "note": ("recomputed the 9 chapter timestamps from the real timeline "
                 "(scene N starts at (N-1)*(%.1f-%.1f)s; total %.1fs). The hand-written "
                 "stamps had drifted up to ~100s. Added the missing «ليه بنحبها» "
                 "chapter (scenes 44-49)." % (sdur, xfade, total)),
    })

    with io.open(os.path.join(REPO, "video.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=1)

    print("total runtime: %.1fs (%.1f min)" % (total, total / 60.0))
    print(chapters)


if __name__ == "__main__":
    main()
