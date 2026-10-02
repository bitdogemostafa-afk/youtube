#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""video-editor employee: build a REVIEWABLE PREVIEW when real footage is absent.

Real stock footage cannot be downloaded from this sandbox (every footage host is
network-blocked; only github.com is reachable and it carries no matching clips).
So this generates, for every scene that needs footage, a 10s placeholder clip
with the scene number and the English search query burned into the picture.
The preview then shows the full edit — narration, pacing, xfades, audio mix —
with labelled placeholders, and swapping in the real clips is a one-command
rebuild.
"""
import io
import json
import os
import subprocess

from imageio_ffmpeg import get_ffmpeg_exe

REPO = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(REPO, ".build", "preview-footage")

# loosely evocative palette so the preview still reads as a sequence
PALETTE = ["1b2a3a", "24333f", "2e3b2e", "3a2f24", "2b2b3a", "33404d",
           "3d3327", "26333a", "2f3a2c", "3a3040"]


def write_ass(path, sid, query):
    body = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 640\nPlayResY: 360\n"
            "WrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Ph,Amiri-Bold,30,&H00FFFFFF,&H000000FF,&H00101010,&H80000000,"
            "-1,0,0,0,100,100,1,0,1,3,1,7,20,20,24,1\n"
            "Style: Q,Amiri-Bold,20,&H00FFD27F,&H000000FF,&H00101010,&H80000000,"
            "-1,0,0,0,100,100,1,0,1,3,1,2,20,20,20,1\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:00.00,0:00:10.00,Ph,,0,0,0,,scene %02d\n"
            "Dialogue: 1,0:00:00.00,0:00:10.00,Q,,0,0,0,,%s\n"
            % (sid, query.replace("\n", " ")))
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(body)


def main():
    ff = get_ffmpeg_exe()
    fonts = os.path.join(REPO, "brand", "fonts")
    os.makedirs(OUT_DIR, exist_ok=True)

    with io.open(os.path.join(REPO, "video.json"), encoding="utf-8") as f:
        plan = json.load(f)

    scenes = plan["scenes"]
    made = 0
    for i, sc in enumerate(scenes):
        if sc.get("visuals"):
            continue
        out = os.path.join(OUT_DIR, "scene-%02d.mp4" % sc["id"])
        if os.path.exists(out):
            continue
        query = sc.get("footage_query", "")
        ass = os.path.join(OUT_DIR, "scene-%02d.ass" % sc["id"])
        write_ass(ass, sc["id"], query)
        colour = PALETTE[i % len(PALETTE)]
        cmd = [ff, "-y",
               "-f", "lavfi", "-i", "color=c=0x%s:s=640x360:r=25:d=10" % colour,
               "-vf", "subtitles=%s:fontsdir=%s" % (ass, fonts),
               "-t", "10", "-pix_fmt", "yuv420p",
               "-c:v", "libx264", "-preset", "ultrafast", "-g", "50", out]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            raise SystemExit("failed on scene %d:\n%s" % (sc["id"], r.stderr[-800:]))
        made += 1

    # preview plan: same 63 scenes, same audio/stills, low resolution
    preview = {
        "meta": {"width": 640, "height": 360, "fps": 25,
                 "scene_duration": 10.0, "transition_duration": 0.5,
                 "output": ".build/preview.mp4"},
        "brand": {}, "audio": plan["audio"], "scenes": [],
    }
    for sc in scenes:
        c = dict(sc)
        if not c.get("visuals"):
            c["footage"] = os.path.join(".build", "preview-footage",
                                        "scene-%02d.mp4" % c["id"])
        preview["scenes"].append(c)
    with io.open(os.path.join(REPO, ".build", "preview_plan.json"), "w",
                 encoding="utf-8") as f:
        json.dump(preview, f, ensure_ascii=False, indent=1)

    print("placeholder clips: %d (total on disk: %d)"
          % (made, len([s for s in scenes if not s.get("visuals")])))
    print("preview plan -> .build/preview_plan.json")


if __name__ == "__main__":
    main()
