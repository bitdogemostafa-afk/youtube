#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
assemble_video.py
=================
يبني الفيديو فعلياً من ملف video.json + الصور + المقاطع الصوتية.

- كل مشهد: صورة ثابتة + حركة كاميرا (zoom/pan/tilt) حسب الانتقال المحدد
- كل مشهد: مقطعه الصوتي مربوط بيه (قص السكون + تسريع خفيف لو أطول)
- النتيجة: MP4 1280×720 مع تعليق صوتي ممزوج

الاستخدام:
    python3 scripts/assemble_video.py videos/<folder>/video.json
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
ROOT = Path(__file__).resolve().parent.parent
FPS = 25
W, H = 1280, 720
SILENCE_DB = "-45dB"


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr[-2000:])
        raise SystemExit(f"ffmpeg failed: {' '.join(map(str, cmd))}")


def mp3_duration(path: Path) -> float:
    data = path.read_bytes()
    if data[:3] == b"ID3":
        size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]
        pos = 10 + size
    else:
        pos = 0
    br_v1 = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320]
    br_v2 = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]
    total = 0.0
    while pos + 4 <= len(data):
        if data[pos] != 0xFF or (data[pos + 1] & 0xE0) != 0xE0:
            pos += 1
            continue
        hdr = int.from_bytes(data[pos:pos + 4], "big")
        version = (hdr >> 19) & 3
        layer = (hdr >> 17) & 3
        br_idx = (hdr >> 12) & 0xF
        sr_idx = (hdr >> 10) & 3
        if layer != 1 or br_idx in (0, 15) or sr_idx == 3:
            pos += 1
            continue
        if version == 3:
            sr, samples, br = [44100, 48000, 32000][sr_idx], 1152, br_v1[br_idx] * 1000
        elif version == 2:
            sr, samples, br = [22050, 24000, 16000][sr_idx], 576, br_v2[br_idx] * 1000
        else:
            pos += 1
            continue
        total += samples / sr
        pos += int(samples / 8 * br / sr)
    return total


def zoompan(move: str, frames: int) -> str:
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    if move == "zoom-in":
        z = "min(zoom+0.0012,1.35)"
        x, y = cx, cy
    elif move == "zoom-out":
        z = "if(eq(on,1),1.35,max(zoom-0.0012,1.0))"
        x, y = cx, cy
    elif move == "pan-right":
        z, x, y = "1.2", f"(iw-iw/zoom)*on/{max(frames - 1, 1)}", cy
    elif move == "pan-left":
        z, x, y = "1.2", f"(iw-iw/zoom)*(1-on/{max(frames - 1, 1)})", cy
    elif move == "tilt-up":
        z, x, y = "1.2", cx, f"(ih-ih/zoom)*(1-on/{max(frames - 1, 1)})"
    else:
        z, x, y = "1.0", cx, cy
    return (
        f"scale=2560:1440:force_original_aspect_ratio=increase,"
        f"crop=2560:1440,"
        f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={W}x{H}:fps={FPS}"
    )


def build_segment(image: Path, duration: float, move: str, out: Path):
    frames = int(round(duration * FPS))
    vf = zoompan(move, frames)
    run([
        FFMPEG, "-y", "-loop", "1", "-i", str(image),
        "-vf", vf, "-t", f"{duration:.2f}",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", str(FPS),
        str(out),
    ])


def build_audio(audio: Path, duration: float, out: Path):
    measured = mp3_duration(audio)
    # قصّ السكون الطرفي + تسريع خفيف لو المقطع أطول من مدة المشهد
    trim = (
        f"silenceremove=start_periods=1:start_threshold={SILENCE_DB},"
        f"areverse,silenceremove=start_periods=1:start_threshold={SILENCE_DB},areverse"
    )
    filters = [trim]
    if measured > duration * 1.02:
        tempo = min(measured * 0.95 / duration, 1.3)
        filters.append(f"atempo={tempo:.3f}")
    filters.append("apad")
    run([
        FFMPEG, "-y", "-i", str(audio),
        "-af", ",".join(filters),
        "-t", f"{duration:.2f}",
        "-c:a", "aac", "-b:a", "128k", str(out),
    ])


def main():
    if len(sys.argv) < 2:
        print("الاستخدام: python3 scripts/assemble_video.py videos/<folder>/video.json")
        sys.exit(1)

    json_path = Path(sys.argv[1]).resolve()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    video_id = data["meta"]["id"]
    # مسار الصوت/الصور: جرّب الـ id كامل، وبعدين الـ id من غير التاريخ
    images_dir = ROOT / "assets" / "video" / video_id
    if not images_dir.is_dir():
        fallback = ROOT / "assets" / "video" / video_id.split("-", 3)[-1]
        if fallback.is_dir():
            images_dir = fallback
    audio_dir = ROOT / "assets" / "voice" / "videos" / video_id
    if not audio_dir.is_dir():
        fallback = ROOT / "assets" / "voice" / "videos" / video_id.split("-", 3)[-1]
        if fallback.is_dir():
            audio_dir = fallback
    out_file = json_path.parent / "final.mp4"

    # قائمة المقاطع: (صورة، مدة، حركة كاميرا، ملف صوتي)
    timeline = []

    hook = data.get("hook", {})
    if hook.get("text"):
        timeline.append((
            images_dir / "scene-01.jpg",
            float(hook.get("duration_sec", 25)),
            "zoom-in",
            audio_dir / "hook.mp3",
        ))

    intro = data.get("intro", {})
    if intro.get("logo"):
        timeline.append((
            images_dir / "intro.jpg",
            float(intro.get("duration_sec", 5)),
            "zoom-in",
            Path(intro["sound"]) if Path(intro["sound"]).is_absolute() else ROOT / intro["sound"],
        ))

    for scene in data.get("scenes", []):
        image = images_dir / f"scene-{scene['id']:02d}.jpg"
        if not image.exists():
            image = images_dir / "scene-01.jpg"
        timeline.append((
            image,
            float(scene.get("duration_sec", 8)),
            scene.get("visual", {}).get("camera_move", "zoom-in"),
            audio_dir / f"scene-{scene['id']:02d}.mp3",
        ))

    outro = data.get("outro", {})
    if outro.get("text"):
        timeline.append((
            images_dir / "outro.jpg",
            float(outro.get("duration_sec", 20)),
            "zoom-out",
            audio_dir / "outro.mp3",
        ))

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        segments, clips = [], []
        for i, (image, duration, move, audio) in enumerate(timeline):
            seg = tmp / f"seg{i:02d}.mp4"
            build_segment(image, duration, move, seg)
            segments.append(seg)
            clip = tmp / f"clip{i:02d}.m4a"
            if audio.exists():
                build_audio(audio, duration, clip)
            else:
                run([FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                     "-t", f"{duration:.2f}", "-c:a", "aac", str(clip)])
            clips.append(clip)

        # دمج المقاطع المرئية
        concat_list = tmp / "concat.txt"
        concat_list.write_text(
            "".join(f"file '{s}'\n" for s in segments), encoding="utf-8"
        )
        video_only = tmp / "video_only.mp4"
        run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
             "-c", "copy", str(video_only)])

        # مزج الصوت مع التأخير الزمني لكل مقطع
        offsets, total = [], 0.0
        for _, duration, _, _ in timeline:
            offsets.append(int(total * 1000))
            total += duration

        inputs = ["-i", str(video_only)]
        for clip in clips:
            inputs += ["-i", str(clip)]
        filters = []
        for i, offset in enumerate(offsets):
            filters.append(f"[{i + 1}:a]adelay={offset}:all=1[a{i}]")
        mix_inputs = "".join(f"[a{i}]" for i in range(len(clips)))
        filters.append(
            f"{mix_inputs}amix=inputs={len(clips)}:normalize=0:dropout_transition=0[mix]"
        )
        run([
            FFMPEG, "-y", *inputs,
            "-filter_complex", ";".join(filters),
            "-map", "0:v", "-map", "[mix]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", "-shortest", str(out_file),
        ])

    print(f"🎬 تم بناء الفيديو: {out_file}")
    print(f"   المدة: {total:.0f} ثانية ({total / 60:.1f} دقيقة)")


if __name__ == "__main__":
    main()
