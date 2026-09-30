#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_video.py
=================
يتأكد إن ملف video.json ماشي على قواعد قناة «طب ليه؟» قبل أي تسليم.

الاستخدام:
    python3 scripts/validate_video.py videos/<folder>/video.json
"""

import json
import sys
from pathlib import Path

ALLOWED_SOURCES = {
    "pexels", "pixabay", "unsplash",   # بنوك الفيديو المجانية
    "google", "wikipedia",             # صور (بشرط حركة كاميرا)
    "generated", "logo",               # مخرجاتنا
}
STATIC_SOURCES = {"google", "wikipedia"}  # صور ثابتة → لازم حركة كاميرا
CAMERA_MOVES = {"zoom-in", "zoom-out", "pan-right", "pan-left", "tilt-up", "tilt-down"}


def validate(data: dict):
    errors, warnings = [], []

    meta = data.get("meta", {})
    for key in ("id", "title", "status", "current_owner"):
        if not meta.get(key):
            errors.append(f"meta.{key} مطلوب")

    # الهوك
    hook = data.get("hook", {})
    if not hook.get("text"):
        errors.append("hook.text مطلوب")
    if hook.get("duration_sec", 0) > 30:
        errors.append(f"الهوك {hook['duration_sec']} ثانية — القاعدة: أقصى مدة 30 ثانية")

    # الانترو
    intro = data.get("intro", {})
    if not intro.get("logo"):
        errors.append("intro.logo مطلوب (لوجو القناة)")
    if not intro.get("sound"):
        errors.append("intro.sound مطلوب (الصوت المميز)")

    # المشاهد
    scenes = data.get("scenes", [])
    if len(scenes) < 3:
        errors.append("مطلوب 3 مشاهد على الأقل")

    used_visuals = set()
    for i, scene in enumerate(scenes):
        sid = scene.get("id", i + 1)
        tag = f"مشهد {sid}"

        if not scene.get("narration"):
            errors.append(f"{tag}: narration مطلوب (تعليق صوتي)")

        duration = scene.get("duration_sec", 0)
        if duration <= 0:
            errors.append(f"{tag}: duration_sec مطلوب")
        elif duration > 10:
            errors.append(f"{tag}: {duration} ثانية — القاعدة: المشهد ما يزيدش عن 10 ثوانٍ")

        visual = scene.get("visual", {})
        source = visual.get("source", "")
        if source not in ALLOWED_SOURCES:
            errors.append(f"{tag}: مصدر غير مسموح ({source or 'فاضي'})")
        if not (visual.get("url") or visual.get("local_file")):
            errors.append(f"{tag}: visual محتاج url أو local_file")
        if not visual.get("rights"):
            errors.append(f"{tag}: rights مطلوب (التأكد من حقوق الاستخدام)")

        key = visual.get("url") or visual.get("local_file") or ""
        if key and key in used_visuals:
            errors.append(f"{tag}: نفس المرئي متكرر ({key}) — ممنوع تكرار نفس الصورة/الفيديو")
        used_visuals.add(key)

        if source in STATIC_SOURCES and visual.get("camera_move") not in CAMERA_MOVES:
            errors.append(f"{tag}: صورة ثابتة من {source} → لازم حركة كاميرا (zoom-in مثلاً)")

        if not scene.get("transition_in"):
            errors.append(f"{tag}: transition_in مطلوب (انتقال بين المشاهد)")

    # الخاتمة
    outro = data.get("outro", {})
    if not outro.get("interactive_questions"):
        errors.append("outro.interactive_questions مطلوب (أسئلة تفاعلية)")

    # الصوت
    audio = data.get("audio", {})
    music = audio.get("music", {})
    if music.get("source") != "youtube_audio_library":
        errors.append("audio.music.source لازم youtube_audio_library")
    voiceover = audio.get("voiceover", {})
    if not voiceover.get("voice_id"):
        errors.append("audio.voiceover.voice_id مطلوب")

    # بوابات ما قبل النشر
    status = meta.get("status")
    if status in ("ready", "published"):
        if not voiceover.get("synced"):
            errors.append("voiceover.synced لازم true قبل النشر (ارتباط كامل بالفيديو)")
        if data.get("review", {}).get("user_approval", {}).get("status") != "approved":
            errors.append("موافقة المستخدم مطلوبة قبل النشر")
        if data.get("review", {}).get("fact_check", {}).get("status") != "approved":
            errors.append("موافقة مدقق الحقائق مطلوبة قبل النشر")

    return errors, warnings


def main() -> None:
    if len(sys.argv) < 2:
        print("الاستخدام: python3 scripts/validate_video.py videos/<folder>/video.json")
        sys.exit(1)

    path = Path(sys.argv[1])
    data = json.loads(path.read_text(encoding="utf-8"))
    errors, warnings = validate(data)

    for warning in warnings:
        print(f"⚠️  {warning}")
    for error in errors:
        print(f"❌ {error}")

    if errors:
        print(f"\n🚫 فشل التحقق: {len(errors)} خطأ في {path}")
        sys.exit(1)
    print(f"✅ {path} ماشي على كل القواعد")


if __name__ == "__main__":
    main()
