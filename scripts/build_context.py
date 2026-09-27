#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_context.py
================
يجمع كل ملفات شركة "طب ليه؟" في ملف سياق واحد (context/team-context.md)
عشان أي AI agent يفتح الملف ده يكون عارف كل الموظفين وقواعد القناة.

الاستخدام:
    python3 scripts/build_context.py
"""

from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "context" / "team-context.md"

SECTIONS = [
    ("📁 هوية القناة", ROOT / "channel"),
    ("📁 فريق العمل", ROOT / "employees"),
]


def main() -> None:
    parts = []
    parts.append('# 🧠 ذاكرة فريق قناة "طب ليه؟"\n')
    parts.append(
        f"> اتولدت تلقائياً بواسطة scripts/build_context.py — "
        f"{datetime.now():%Y-%m-%d %H:%M}\n"
    )
    parts.append(
        '> افتح الملف ده مع أي AI agent وقوله: '
        '"إنت فريق إدارة قناة طب ليه؟، اشتغل بالمحتوى ده."\n'
    )
    parts.append("---\n")

    count = 0
    for title, folder in SECTIONS:
        if not folder.is_dir():
            continue
        parts.append(f"\n## {title}\n")
        for f in sorted(folder.glob("*.md")):
            count += 1
            parts.append(f"\n### 📄 {f.stem}\n")
            parts.append(f.read_text(encoding="utf-8").strip())
            parts.append("\n")

    workflow = ROOT / "workflow.md"
    if workflow.exists():
        count += 1
        parts.append("\n## 🔁 سير العمل\n")
        parts.append(workflow.read_text(encoding="utf-8").strip())

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"✅ تم تجميع {count} ملف في: {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
