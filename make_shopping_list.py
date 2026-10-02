#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""video-editor employee: build the footage shopping list.

The build refuses to run unless every scene has real footage (or one of the
two allowed still scenes).  pexels/pixabay/unsplash are not reachable from
the build sandbox, so the clips must be downloaded by a human into
brand/footage/.  This writes brand/footage/SHOPPING_LIST.md with, for every
scene that needs a clip: the English search query, the source, the exact
filename to save it as, and the narration the clip must match.
"""
import io
import json
import os

REPO = os.path.dirname(os.path.abspath(__file__))


def main():
    with io.open(os.path.join(REPO, "video.json"), encoding="utf-8") as f:
        plan = json.load(f)

    scenes = plan["scenes"]
    need = [s for s in scenes if not s.get("visuals")]
    still = [s for s in scenes if s.get("visuals")]

    lines = []
    lines.append("# قائمة تحميل الفيديوهات — فيديو «ريحة المطر»")
    lines.append("")
    lines.append("المطلوب: **%d مقطع فيديو** (كل مشهد 10 ثواني على الأقل)." % len(need))
    lines.append("")
    lines.append("## إزاي تنزّلهم (مهم)")
    lines.append("")
    lines.append("1. افتح الموقع المكتوب جنب كل مشهد (pexels.com أو pixabay.com).")
    lines.append("2. اكتب **كلمة البحث الإنجليزية** بالظبط في مربع البحث.")
    lines.append("3. نزّل المقطع (يفضّل 4K أو أعلى جودة متاحة).")
    lines.append("4. سمّه بالاسم المكتوب في العمود الأخير بالظبط،")
    lines.append("   وحُطّ الملفات كلها في فولدر `brand/footage/` جوه المشروع.")
    lines.append("")
    lines.append("> ملاحظة: المقطع بيتقصّ على أول 10 ثواني، فأي مقطع أطول من 10 ثواني تمام.")
    lines.append("> لو الموقع عرض جودات، نزّل الأعلى (الهدف 4K).")
    lines.append("")
    lines.append("## المشاهد اللي محتاجة فيديو (%d)" % len(need))
    lines.append("")
    lines.append("| # | احفظ الملف باسم | ابحث عن (إنجليزي) | المصدر | التعليق اللي لازم المقطع يوصفه |")
    lines.append("|---|---|---|---|---|")
    for s in need:
        q = s.get("footage_query", "")
        src = s.get("footage_source", "pexels")
        path = s.get("footage", "")
        name = os.path.basename(path)
        nar = s["narration"].replace("|", "/")
        lines.append("| %d | `%s` | %s | %s | %s |" % (s["id"], name, q, src, nar))

    lines.append("")
    lines.append("## المشاهد اللي مش محتاجة تحميل (صور ثابتة — جاهزة)")
    lines.append("")
    for s in still:
        lines.append("- مشهد %d: صورتين جاهزين في `.build/scenes/` (%s)"
                     % (s["id"], ", ".join(os.path.basename(v) for v in s["visuals"])))
    lines.append("")
    lines.append("## بعد ما تخلّص التحميل")
    lines.append("")
    lines.append("قول «خلّصت التحميل» وأنا هشغّل البناء 4K تلقائي.")
    lines.append("")

    out = os.path.join(REPO, "brand", "footage", "SHOPPING_LIST.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with io.open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("wrote %s (%d clips needed)" % (out, len(need)))
    srcs = {}
    for s in need:
        srcs[s.get("footage_source", "pexels")] = srcs.get(s.get("footage_source", "pexels"), 0) + 1
    print("by source:", srcs)


if __name__ == "__main__":
    main()
