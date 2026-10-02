#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""thumbnail-designer employee.

Composes the YouTube thumbnail: AI background + big Arabic title rendered
through libass (ffmpeg's `subtitles` filter) so the Arabic is properly
shaped and right-to-left.  drawtext is NOT compiled into the bundled ffmpeg,
and libass is, so we burn the text with a generated .ass file instead.

Usage:  python3 make_thumbnail.py [background.jpg]
Reads the concept/text/font from video.json -> writes thumbnail.jpg
"""
import io
import json
import os
import subprocess
import sys

from imageio_ffmpeg import get_ffmpeg_exe

REPO = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(REPO, "brand", "fonts")
W, H = 1280, 720

# &HAABBGGRR
WHITE = "&H00FFFFFF"
DARK = "&H00141414"
BOX = "&H9E000000"      # ~62% opaque black plate behind the text
GOLD = "&H0000D7FF"     # accent for the small kicker line


def ass_colour(hex_rgb, alpha=0):
    return "&H%02X%02X%02X%02X" % (alpha, int(hex_rgb[4:6], 16),
                                   int(hex_rgb[2:4], 16), int(hex_rgb[0:2], 16))


def write_ass(path, text, kicker=None):
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: %d" % W,
        "PlayResY: %d" % H,
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: None",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        # main title: heavy Arabic display face on an opaque dark plate
        "Style: Title,Amiri-Bold,132,%s,%s,%s,%s,-1,0,0,0,100,100,2,0,3,16,0,5,70,70,64,1"
        % (WHITE, WHITE, DARK, BOX),
        # optional kicker above the title
        "Style: Kicker,Amiri-Bold,54,%s,%s,%s,%s,-1,0,0,0,100,100,6,0,3,10,0,8,70,70,40,1"
        % (GOLD, GOLD, DARK, BOX),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text",
    ]
    if kicker:
        lines.append("Dialogue: 0,0:00:00.00,0:00:02.00,Kicker,,0,0,0,,%s" % kicker)
    lines.append("Dialogue: 1,0:00:00.00,0:00:02.00,Title,,0,0,0,,%s" % text)
    with io.open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    bg = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, ".build", "thumbnail-bg.jpg")
    if not os.path.exists(bg):
        sys.exit("ERROR: background not found: %s\n"
                 "-> generate the AI background first (generate_image)." % bg)

    with io.open(os.path.join(REPO, "video.json"), encoding="utf-8") as f:
        plan = json.load(f)
    th = plan.get("thumbnail", {})
    text = th.get("text_ar", "")
    if not text:
        sys.exit("ERROR: video.json has no thumbnail.text_ar")

    # the title itself carries the hook question; reuse its second half as the
    # kicker so the thumbnail states the mystery, not just the topic
    title = plan.get("metadata", {}).get("title", "")
    kicker = None
    if "—" in title:
        kicker = title.split("—", 1)[1].strip()

    font = os.path.join(FONTS, "Amiri-Bold.ttf")
    if not os.path.exists(font):
        sys.exit("ERROR: Arabic font missing: %s" % font)

    ass_path = os.path.join(REPO, ".build", "thumbnail.ass")
    os.makedirs(os.path.dirname(ass_path), exist_ok=True)
    write_ass(ass_path, text, kicker)

    out = os.path.join(REPO, th.get("file", "thumbnail.jpg"))
    ff = get_ffmpeg_exe()
    cmd = [ff, "-y", "-i", bg,
           "-vf", "subtitles=%s:fontsdir=%s" % (ass_path, FONTS),
           "-frames:v", "1", "-q:v", "2", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit("ERROR: thumbnail render failed:\n" + r.stderr[-1500:])
    print("thumbnail -> %s (%dx%d)" % (out, W, H))
    if kicker:
        print("  kicker: %s" % kicker)


if __name__ == "__main__":
    main()
