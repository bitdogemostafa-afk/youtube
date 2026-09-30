#!/usr/bin/env bash
# new_video.sh — يبدأ فيديو جديد: بيعمل فولدر فيه video.json جاهز للتعبئة
#
# الاستخدام:
#   ./scripts/new_video.sh "ليه البحر مالح؟"

set -euo pipefail

TITLE="${1:-}"
if [ -z "$TITLE" ]; then
  echo 'الاستخدام: ./scripts/new_video.sh "عنوان الفيديو"'
  exit 1
fi

DATE="$(date +%Y-%m-%d)"
SLUG="$(printf '%s' "$TITLE" | tr ' ' '-' | tr -d '/\\:*?"<>|'"'"'')"
ID="${DATE}-$(date +%H%M%S)"
DIR="videos/${DATE}-${SLUG}"

mkdir -p "$DIR"

cat > "$DIR/video.json" << EOF
{
  "meta": {
    "id": "$ID",
    "title": "$TITLE",
    "status": "research",
    "current_owner": "researcher",
    "target_publish": "",
    "history": []
  },
  "research": {
    "by": "researcher",
    "questions": [],
    "facts": [],
    "scene_visuals": []
  },
  "hook": {
    "text": "",
    "duration_sec": 25,
    "by": "scriptwriter"
  },
  "intro": {
    "logo": "assets/logo/logo-final-800.png",
    "sound": "assets/voice/intro-sample.mp3",
    "animation": "zoom-in",
    "duration_sec": 5
  },
  "scenes": [],
  "outro": {
    "text": "",
    "interactive_questions": [],
    "end_screen": true,
    "duration_sec": 20
  },
  "audio": {
    "voiceover": {
      "voice_id": "voice-00",
      "files": [],
      "synced": false
    },
    "music": {
      "track": "",
      "source": "youtube_audio_library",
      "url": "",
      "volume": 0.15
    },
    "sfx": [],
    "mixer_notes": ""
  },
  "seo": {
    "title": "",
    "description": "",
    "tags": [],
    "by": "seo-manager"
  },
  "thumbnail": {
    "ideas": [],
    "chosen": "",
    "by": "thumbnail-designer"
  },
  "publish": {
    "scheduled_at": "",
    "checklist": [],
    "by": "publisher"
  },
  "review": {
    "fact_check": { "status": "pending", "by": "fact-checker", "notes": "" },
    "language": { "status": "pending", "by": "language-editor", "notes": "" },
    "user_approval": { "status": "pending", "notes": "" }
  }
}
EOF

echo "✅ تم إنشاء الفيديو: $DIR/video.json"
echo "   الخطوة الجاية: الباحث يكتب قسم research ويسلّم تقريرلك للمراجعة."
echo "   التحقق من القواعد: python3 scripts/validate_video.py $DIR/video.json"
