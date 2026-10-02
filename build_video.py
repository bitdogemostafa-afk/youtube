#!/usr/bin/env python3
"""
build_video.py — professional assembler for the science channel.

Usage:
    python3 build_video.py [path/to/video.json]

Reads the production plan (default: ./video.json) and writes final.mp4.

Enforced rules:
  * every scene is EXACTLY meta.scene_duration seconds (default 10.0)
  * every scene is VIDEO footage (brand/footage/ from pexels/pixabay/unsplash)
    EXCEPT at most STILL_SCENE_LIMIT scenes that use still images
    (at most 2 stills per still scene: 5.25s each + 0.5s mini crossfade)
  * real transitions between scenes (xfade crossfade, default 0.5s)
  * per-scene voiceover fitted (edge-silence trim + atempo <= max_voice_tempo)
  * music bed with sidechain ducking under the voice (looped to full length)
  * whoosh SFX at every transition + riser under the hook
  * mild colour grade + subtle Ken Burns on stills
  * final loudness normalised (default -14 LUFS)
"""

import glob
import json
import os
import re
import shutil
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(REPO, ".build")
SEG_DIR = os.path.join(BUILD, "segments")

GRADE = "eq=contrast=1.06:saturation=1.12"
MINI_XFADE = 0.5
MAX_STILLS_PER_SCENE = 2
STILL_SCENE_LIMIT = 2

XFADE_MAP = {
    "crossfade": "fade", "fade": "fade", "fadeblack": "fadeblack",
    "fadewhite": "fadewhite", "wipeleft": "wipeleft", "wiperight": "wiperight",
    "slideleft": "slideleft", "slideright": "slideright",
    "circlecrop": "circlecrop", "rectcrop": "rectcrop", "distance": "distance",
}


def get_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        sys.exit("ERROR: ffmpeg not found. Run: pip3 install --break-system-packages imageio-ffmpeg")


def run(cmd, what=""):
    print(f"  [ffmpeg] {what}")
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        sys.stderr.write(p.stderr[-4000:])
        sys.exit(f"ERROR: ffmpeg failed on: {what}")
    return p


def probe_duration(ffmpeg, path):
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        p = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True)
        try:
            return float(p.stdout.strip())
        except ValueError:
            pass
    p = subprocess.run([ffmpeg, "-i", path, "-f", "null", "-"],
                       capture_output=True, text=True)
    times = re.findall(r"time=(\d+):(\d+):(\d+\.\d+)", p.stderr)
    if times:
        h, m, s = times[-1]
        return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


def has_audio_stream(path):
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return False
    p = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", path],
        capture_output=True, text=True)
    return bool(p.stdout.strip())


def first_file(directory, exts=("mp3", "wav", "m4a", "mp4", "mov")):
    if not directory or not os.path.isdir(directory):
        return None
    for ext in exts:
        hits = sorted(glob.glob(os.path.join(directory, f"*.{ext}")))
        if hits:
            return hits[0]
    return None


def find_sfx(sfx_dir, *keywords):
    if not sfx_dir or not os.path.isdir(sfx_dir):
        return None
    files = [f for f in sorted(glob.glob(os.path.join(sfx_dir, "*")))
             if os.path.isfile(f)]
    for kw in keywords:
        for f in files:
            if kw in os.path.basename(f).lower():
                return f
    return None


def footage_gate(scenes):
    """Every scene must be footage, except at most STILL_SCENE_LIMIT scenes."""
    no_footage = [sc for sc in scenes
                  if not (sc.get("footage") and os.path.exists(sc["footage"]))]
    if len(no_footage) > STILL_SCENE_LIMIT:
        print("!! footage shopping list — download these clips into brand/footage/:")
        # scenes that carry `visuals` are the intentional still scenes, so they
        # are never part of the shopping list
        for sc in no_footage:
            if sc.get("visuals"):
                continue
            default = os.path.join("brand", "footage",
                                   f"scene-{sc.get('id', 0):02d}.mp4")
            print(f"   scene {sc.get('id')}: {sc.get('footage', default)}"
                  f"  | search ({sc.get('footage_source', 'pexels')}): "
                  f"{sc.get('footage_query', '(no query in video.json)')}")
        sys.exit(f"ERROR: {len(no_footage)} scenes have no footage — "
                 f"only {STILL_SCENE_LIMIT} scenes may use still images.")
    if no_footage:
        ids = ", ".join(str(sc.get("id")) for sc in no_footage)
        print(f"== still scenes ({len(no_footage)}/{STILL_SCENE_LIMIT}): {ids}")


def header_duration(ffmpeg, path):
    """Duration from the container header - no decoding, so it is cheap.

    ffprobe is not installed on the runner, and the null-decode fallback in
    probe_duration would read every 4K frame just to check a cache hit.
    """
    try:
        p = subprocess.run([ffmpeg, "-hide_banner", "-i", path],
                           capture_output=True, text=True, timeout=30)
    except Exception:
        return None
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", p.stderr)
    if not m:
        return None
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def build_segment(ffmpeg, label, visual, dur, w, h, fps, move="zoom-in"):
    """Normalise one visual into a silent segment of exactly `dur` seconds."""
    out = os.path.join(SEG_DIR, f"seg-{label}.mp4")
    # reuse an already-built segment: a 4K encode of the same footage and the
    # same duration is deterministic, and the runner has only ~4 GB and 2 CPUs
    if os.path.exists(out):
        have = header_duration(ffmpeg, out)
        if have and abs(have - dur) < 0.06:
            return out
    ext = os.path.splitext(visual)[1].lower()
    if ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
        frames = max(1, int(round(dur * fps)))
        if move == "zoom-out":
            z, x, y = f"1.12-0.12*on/{frames}", None, None
        elif move == "pan-right":
            z, x, y = "1.10", f"(iw-iw/zoom)*on/{frames}", "ih/2-(ih/zoom/2)"
        elif move == "pan-left":
            z, x, y = "1.10", f"(iw-iw/zoom)*(1-on/{frames})", "ih/2-(ih/zoom/2)"
        elif move == "static":
            z, x, y = "1.04", None, None
        else:  # zoom-in (default)
            z, x, y = f"1+0.12*on/{frames}", None, None
        if x is None:
            x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
        # pre-scale with headroom for the camera move
        # (2x up to 1440p, 1.25x at 4K to keep it manageable)
        pre_w = w * 2 if w <= 1440 else int(w * 1.25)
        pre_h = h * 2 if h <= 1440 else int(h * 1.25)
        vf = (f"scale={pre_w}:{pre_h}:force_original_aspect_ratio=increase,crop={pre_w}:{pre_h},"
              f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={w}x{h}:fps={fps},"
              f"{GRADE},format=yuv420p")
        cmd = [ffmpeg, "-y", "-loop", "1", "-framerate", str(fps),
               "-t", f"{dur:.3f}", "-i", visual,
               "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast",
               "-pix_fmt", "yuv420p", "-r", str(fps), out]
    else:
        d = probe_duration(ffmpeg, visual)
        pre = ["-stream_loop", "-1"] if d < dur else []
        vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
              f"fps={fps},{GRADE},format=yuv420p")
        cmd = [ffmpeg, "-y"] + pre + ["-i", visual, "-vf", vf,
               "-t", f"{dur:.3f}", "-an", "-c:v", "libx264",
               "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", str(fps), out]
    run(cmd, f"segment {label}: {os.path.basename(visual)} -> {dur:.2f}s")
    return out


def build_scene_segment(ffmpeg, label, sc, dur, w, h, fps):
    """Build ONE scene segment of exactly `dur` seconds.

    Source priority:
      1. real footage clip (brand/footage/)   -> trimmed to dur
      2. up to TWO still images               -> dur/2 each + mini crossfade
      3. a single still image                 -> Ken Burns for dur
    """
    out = os.path.join(SEG_DIR, f"seg-{label}.mp4")
    sid = sc.get("id", label)

    footage = sc.get("footage")
    if footage and os.path.exists(footage):
        return build_segment(ffmpeg, label, footage, dur, w, h, fps, "static")

    visuals = list(sc.get("visuals") or [])
    if not visuals and sc.get("visual"):
        visuals = [sc["visual"]]
    visuals = [v for v in visuals if v and os.path.exists(v)]
    if not visuals:
        sys.exit(f"ERROR: scene {sid}: no footage and no visuals.\n"
                 "  -> drop a clip in brand/footage/ or generate at most 2 "
                 "stills (English prompts) with the video-editor employee.")
    if len(visuals) > MAX_STILLS_PER_SCENE:
        sys.exit(f"ERROR: scene {sid}: {len(visuals)} stills — "
                 f"the maximum is {MAX_STILLS_PER_SCENE} per scene.")

    if len(visuals) == 1:
        return build_segment(ffmpeg, label, visuals[0], dur, w, h, fps,
                             sc.get("move", "zoom-in"))

    # two stills: each plays (dur + MINI_XFADE)/2 so the pair totals exactly dur
    half = (dur + MINI_XFADE) / 2.0
    a = build_segment(ffmpeg, f"{label}a", visuals[0], half, w, h, fps,
                      sc.get("move", "zoom-in"))
    b = build_segment(ffmpeg, f"{label}b", visuals[1], half, w, h, fps,
                      sc.get("move_b", "zoom-out"))
    tr = XFADE_MAP.get(str(sc.get("intra_transition", "fade")).lower(), "fade")
    fc = (f"[0:v][1:v]xfade=transition={tr}:duration={MINI_XFADE}:"
          f"offset={half - MINI_XFADE:.3f}[v]")
    cmd = [ffmpeg, "-y", "-i", a, "-i", b, "-filter_complex", fc, "-map", "[v]",
           "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
           "-r", str(fps), out]
    run(cmd, f"scene {sid}: 2 stills -> {dur:.2f}s")
    return out


def voice_filter(idx, start_ms, dur, max_tempo, measured):
    tempo = 1.0
    if measured > dur:
        tempo = min(max_tempo, measured / dur)
    return (
        f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,"
        f"silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
        f"areverse,"
        f"silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
        f"areverse,"
        f"atempo={tempo:.4f},"
        f"apad=whole_dur={dur:.3f},atrim=0:{dur:.3f},"
        f"adelay={start_ms}|{start_ms}[v{idx}]"
    )


def main():
    plan_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "video.json")
    if not os.path.exists(plan_path):
        sys.exit(f"ERROR: plan not found: {plan_path}")
    with open(plan_path, encoding="utf-8") as f:
        plan = json.load(f)

    ffmpeg = get_ffmpeg()
    meta = plan.get("meta", {})
    scenes = plan.get("scenes") or []
    if not scenes:
        sys.exit("ERROR: video.json has no scenes.")

    sdur = float(meta.get("scene_duration", 10.0))
    xfade = float(meta.get("transition_duration", 0.5))
    fps = int(meta.get("fps", 25))
    w = int(meta.get("width", 1280))
    h = int(meta.get("height", 720))
    out_path = os.path.join(REPO, meta.get("output", "final.mp4"))

    brand = plan.get("brand", {})
    music_dir = brand.get("music_dir") or os.path.join(REPO, "brand", "music")
    sfx_dir = brand.get("sfx_dir") or os.path.join(REPO, "brand", "sfx")
    audio_cfg = plan.get("audio", {})
    music_vol = float(audio_cfg.get("music_volume", 0.16))
    lufs = float(audio_cfg.get("target_lufs", -14))
    max_tempo = float(audio_cfg.get("max_voice_tempo", 1.15))

    os.makedirs(SEG_DIR, exist_ok=True)

    # ---------------- footage gate (military order) ----------------
    footage_gate(scenes)

    # ---------------- collect segments ----------------
    entries = []
    intro = brand.get("intro")
    if intro and os.path.exists(intro):
        entries.append({"kind": "intro", "visual": intro,
                        "dur": probe_duration(ffmpeg, intro), "move": "static"})
    for i, sc in enumerate(scenes, 1):
        a = sc.get("audio")
        if not a or not os.path.exists(a):
            sys.exit(f"ERROR: scene {i} has no audio file: {a}\n"
                     "-> run the voiceover-artist employee first.")
        entries.append({"kind": "scene", "n": i, "dur": sdur,
                        "audio": a, "move": sc.get("move", "zoom-in"),
                        "transition": sc.get("transition", "fade")})
    outro = brand.get("outro")
    if outro and os.path.exists(outro):
        entries.append({"kind": "outro", "visual": outro,
                        "dur": probe_duration(ffmpeg, outro), "move": "static"})
    else:
        logo = brand.get("logo")
        if logo and os.path.exists(logo):
            entries.append({"kind": "outro", "visual": logo, "dur": sdur,
                            "move": "static"})

    # ---------------- build video segments + timeline ----------------
    print("== building segments ==")
    segs = []
    for i, e in enumerate(entries):
        if e["kind"] == "scene":
            e["seg"] = build_scene_segment(ffmpeg, f"{i:03d}", scenes[e["n"] - 1],
                                           e["dur"], w, h, fps)
        else:
            e["seg"] = build_segment(ffmpeg, f"{i:03d}", e["visual"], e["dur"],
                                     w, h, fps, e.get("move", "static"))
        segs.append(e["seg"])
    for i, e in enumerate(entries):
        e["start"] = 0.0 if i == 0 else entries[i - 1]["start"] + entries[i - 1]["dur"] - xfade
    total = entries[-1]["start"] + entries[-1]["dur"]

    # ---------------- crossfaded timeline (video only) ----------------
    # A single 63-input xfade graph at 3840x2160 keeps every decoder resident
    # at once and is OOM-killed on a ~4 GB runner (7 inputs already die). So
    # the timeline is assembled the cheap way instead: each segment keeps its
    # clean middle, every 0.5s overlap becomes its own tiny two-input xfade,
    # and the 125 pieces are joined with a stream copy - one encode per piece
    # rather than three nested re-encodes.
    print("== crossfade timeline ==")
    if len(entries) > 1:
        chain = os.path.join(BUILD, "chain.mp4")
        # 0.5s at 25fps is 12.5 frames, so a transition is either 12 or 13
        # frames. Alternating them keeps the running total exactly on the
        # nominal 14975-frame timeline (599.0s); a fixed 12 or 13 would drift
        # by up to 31 frames and desync the picture from the narration.
        n = len(entries)
        pieces = []
        for i in range(n):
            if i == 0:
                cframes = int(round((entries[i]["dur"] - xfade) * fps))
            elif i == n - 1:
                cframes = int(round((entries[i]["dur"] - xfade) * fps)) - 1
            else:
                cframes = int(round((entries[i]["dur"] - 2 * xfade) * fps))
            cp = os.path.join(BUILD, f"clean-{i:03d}.mp4")
            ss = 0.0 if i == 0 else xfade
            run([ffmpeg, "-y", "-ss", f"{ss:.3f}", "-i", segs[i],
                 "-frames:v", str(cframes),
                 "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                 "-r", str(fps), "-g", "25",
                 "-video_track_timescale", "12800", cp],
                f"clean {i:03d} ({cframes}f)")
            pieces.append(cp)
            if i < n - 1:
                # 13, 12, 13, 12 ... averaging exactly 12.5
                tframes = 13 if (i + 1) % 2 == 1 else 12
                tr = XFADE_MAP.get(
                    str(entries[i + 1].get("transition", "fade")).lower(), "fade")
                tp = os.path.join(BUILD, f"trans-{i + 1:03d}.mp4")
                run([ffmpeg, "-y",
                     "-ss", f"{entries[i]['dur'] - xfade:.3f}", "-i", segs[i],
                     "-ss", "0", "-i", segs[i + 1],
                     "-filter_complex",
                     f"[0:v][1:v]xfade=transition={tr}"
                     f":duration={xfade:.3f}:offset=0[v]",
                     "-map", "[v]", "-frames:v", str(tframes),
                     "-c:v", "libx264", "-preset", "veryfast",
                     "-pix_fmt", "yuv420p", "-r", str(fps), "-g", "25",
                     "-video_track_timescale", "12800", tp],
                    f"transition {i + 1:03d} ({tframes}f)")
                pieces.append(tp)

        lst = os.path.join(BUILD, "pieces.txt")
        with open(lst, "w") as fh:
            for p in pieces:
                fh.write("file '%s'\n" % os.path.abspath(p))
        run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", lst,
             "-c", "copy", "-movflags", "+faststart", chain],
            "join %d pieces" % len(pieces))
    else:
        chain = segs[0]

    # ---------------- audio mix ----------------
    print("== audio mix ==")
    a_inputs = []
    fc = []
    ai = 0
    vlabels = []
    for e in entries:
        if e["kind"] != "scene":
            continue
        measured = probe_duration(ffmpeg, e["audio"])
        a_inputs += ["-i", e["audio"]]
        fc.append(voice_filter(ai, int(round(e["start"] * 1000)), e["dur"],
                               max_tempo, measured))
        vlabels.append(f"[v{ai}]")
        if measured > e["dur"] * max_tempo:
            print(f"  ! WARNING scene {e['n']}: voice {measured:.2f}s exceeds "
                  f"slot {e['dur']:.1f}s even at {max_tempo}x — tail will be cut")
        ai += 1
    fc.append("".join(vlabels) +
              f"amix=inputs={len(vlabels)}:normalize=0:duration=longest,volume=0.9[voice]")

    mix_inputs = []

    # intro / outro original audio (if present)
    for e in entries:
        if e["kind"] not in ("intro", "outro"):
            continue
        if not has_audio_stream(e["visual"]):
            continue
        a_inputs += ["-i", e["visual"]]
        ms = int(round(e["start"] * 1000))
        fc.append(f"[{ai}:a]aresample=48000,aformat=channel_layouts=stereo,"
                  f"atrim=0:{e['dur']:.3f},volume=0.8,"
                  f"adelay={ms}|{ms}[seg{ai}]")
        mix_inputs.append(f"[seg{ai}]")
        ai += 1

    music = first_file(music_dir)
    if not music:
        # no real track supplied -> synthesise a temporary cinematic bed + SFX
        try:
            import make_music
            make_music.main()
            music = first_file(music_dir)
        except Exception as exc:
            print(f"  ! could not synthesise placeholder music: {exc}")

    if music:
        a_inputs += ["-i", music]
        fc.append(f"[{ai}:a]aresample=48000,aformat=channel_layouts=stereo,"
                  f"aloop=loop=-1:size=2147483647,"
                  f"atrim=0:{total:.3f},volume={music_vol},"
                  f"afade=t=in:st=0:d=1.5,afade=t=out:st={max(0.0, total - 2):.3f}:d=2[mus]")
        # duck the music under the voice; the sidechain is padded to the full
        # length, otherwise the ducked music stops when the voice stops
        fc.append("[voice]asplit=2[voiceA][voiceSC]")
        fc.append(f"[voiceSC]apad=whole_dur={total:.3f}[voiceSCp]")
        fc.append("[mus][voiceSCp]sidechaincompress=threshold=0.03:ratio=6:attack=25:release=500[musd]")
        mix_inputs.append("[voiceA]")
        mix_inputs.append("[musd]")
        ai += 1
        print(f"  music: {os.path.basename(music)} @ volume {music_vol}")
    else:
        print("  ! no music available — shipping without a music bed")
        mix_inputs.append("[voice]")

    whoosh = find_sfx(sfx_dir, "whoosh", "swoosh", "transition")
    riser = find_sfx(sfx_dir, "riser", "rise", "build")
    sfx_labels = []
    if whoosh:
        for e in entries[1:]:
            a_inputs += ["-i", whoosh]
            t = max(0.0, e["start"] - xfade / 2)
            ms = int(round(t * 1000))
            fc.append(f"[{ai}:a]aresample=48000,aformat=channel_layouts=stereo,"
                      f"atrim=0:1.5,volume=0.45,adelay={ms}|{ms}[s{ai}]")
            sfx_labels.append(f"[s{ai}]")
            ai += 1
        print(f"  whoosh: {os.path.basename(whoosh)} on {len(entries) - 1} transitions")
    if riser:
        first_scene = next((e for e in entries if e["kind"] == "scene"), entries[0])
        t = max(0.0, first_scene["start"] - 1.0)
        ms = int(round(t * 1000))
        a_inputs += ["-i", riser]
        fc.append(f"[{ai}:a]aresample=48000,aformat=channel_layouts=stereo,"
                  f"atrim=0:3,volume=0.35,adelay={ms}|{ms}[s{ai}]")
        sfx_labels.append(f"[s{ai}]")
        ai += 1
        print(f"  riser: {os.path.basename(riser)} at {t:.1f}s")

    mix_inputs += sfx_labels
    if len(mix_inputs) > 1:
        fc.append("".join(mix_inputs) +
                  f"amix=inputs={len(mix_inputs)}:normalize=0:duration=longest[premix]")
    else:
        fc.append(f"{mix_inputs[0]}anull[premix]")
    fc.append(f"[premix]loudnorm=I={lufs}:TP=-1.5:LRA=11,"
              f"atrim=0:{total:.3f},"
              # loudnorm can land a few frames short of the slot; without the
              # pad, -shortest below would trim the video to match and the
              # deliverable would come out at 598.90s instead of 599.00s
              f"apad=whole_dur={total:.3f},"
              f"asetpts=N/SR/TB,aresample=48000[aout]")

    cmd = [ffmpeg, "-y"] + a_inputs + ["-i", chain] + [
        "-filter_complex", ";".join(fc),
        "-map", f"{ai}:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", "-shortest", out_path]
    run(cmd, "final mux")

    # ---------------- report ----------------
    n_scenes = len([e for e in entries if e["kind"] == "scene"])
    n_still = len([sc for sc in scenes
                   if not (sc.get("footage") and os.path.exists(sc["footage"]))])
    print("\n== done ==")
    print(f"output   : {out_path}")
    print(f"duration : {total:.2f}s  ({n_scenes} scenes x {sdur}s, "
          f"{n_still} still scene(s) of max {STILL_SCENE_LIMIT})")
    for e in entries:
        if e["kind"] == "scene":
            sc = scenes[e["n"] - 1]
            tag = f"scene-{e['n']:02d}"
            if sc.get("footage") and os.path.exists(sc["footage"]):
                src = f"footage: {os.path.basename(sc['footage'])}"
            else:
                vs = [os.path.basename(v) for v in
                      (sc.get("visuals") or ([sc["visual"]] if sc.get("visual") else []))]
                src = "stills: " + " + ".join(vs)
        else:
            tag = e["kind"].upper()
            src = os.path.basename(e["visual"])
        print(f"  {e['start']:7.2f}s  {tag:10s} {src}")


if __name__ == "__main__":
    main()
