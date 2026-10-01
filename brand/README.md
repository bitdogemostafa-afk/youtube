# 🎨 مجلد البراند — حطّ ملفاتك هنا

ده الفولدر اللي **انت** هتحط فيه، والبرنامج بيقرأ منه أوتوماتيك وقت التجميع.

## الملفات المقبولة

| الملف | الوصف | إجباري؟ |
|---|---|---|
| `logo.png` | لوجو القناة (PNG شفاف، مربّع، ≥ 1000×1000) | ✅ مطلوب |
| `intro.mp4` | انترو القناة — بيشتغل **أول** الفيديو (طوله زي ما تحب؛ باقي المشاهد 10 ثوانٍ بالظبط) | ✅ مطلوب |
| `outro.mp4` | خاتمة — لو مش هتحطها، البرنامج يعمل End card من اللوجو (10 ثوانٍ) | اختياري |
| `music/*.mp3` | موسيقى خلفية — بيشتغل أول ملف أبجدياً | اختياري* |
| `sfx/*.mp3` | مؤثرات: `whoosh` لكل انتقال + `riser` للتشويق | اختياري* |
| `footage/*.mp4` | فيديوهات حقيقية من pexels/pixabay — كل واحد يتقطع لأول **10 ثوانٍ** لمشهد | اختياري |

\* لو مش هتحط ملفات، البرنامج يولّد موسيقى خليجية ومؤثرات **صناعية مؤقتة** لحد ما تحط الأصلية.

## 📥 موسيقى مجانية اخترتهالك (نزّلها من جهازك → حطها في `music/`)

1. **Mixkit — "Valley Sunset"** (Alejandro Magaña) — Ambient / Mysterious / Atmospheric — https://mixkit.co/free-stock-music/
2. **Mixkit — "Spirit in the Woods"** (Alejandro Magaña) — Ambient / Mysterious / Atmospheric
3. **Pixabay Music** — دور على `cinematic ambient mystery` — https://pixabay.com/music/search/cinematic%20ambient/
4. **YouTube Audio Library** — فلتر: Genre = Ambient، Mood = Dark/Mysterious، Duration = Long — https://studio.youtube.com → Audio Library

## 🔊 مؤثرات صوتية مجانية (نزّلها → حطها في `sfx/`)

1. **Mixkit — "Cinematic whoosh fast transition"** — https://mixkit.co/free-sound-effects/whoosh/
2. **Mixkit — "Cinematic mystery heartbeat transition"**
3. **Mixkit — "Epic orchestra transition"**
4. **Pixabay — "Swoosh 015"** (Universfield) / **"Epic Transition"** (DRAGON-STUDIO) — https://pixabay.com/sound-effects/search/transition/

> سمِّ الملفات بأسماءها (مثلاً `Valley Sunset.mp3`, `Cinematic whoosh fast transition.mp3`) — البرنامج بيلاقي الـ whoosh والـ riser من اسم الملف.
