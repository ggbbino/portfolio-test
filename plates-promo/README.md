# Plates — product film (final)

Вертикальный ролик 1080×1920, 30 fps, 29,0 с, рендер сцены напрямую в 1080×1920.
Музыка: BerryDeep — Minimal Techno (фрагмент ≈1:01–1:30, 29 с), микс −14 LUFS, true peak −1 dBTP. Монтаж на сетке **120 BPM** (доля 0,5 с, такт 2 с).

| Файл | Что это |
|---|---|
| `out/plates_promo_final_master_1080x1920.mp4` | Master: H.264 High, yuv420p, 1080×1920, 30 fps + AAC (sound design, −18 LUFS) |
| `out/plates_promo_final_master_silent.mp4` | Master без звука — для наложения трека |
| `preview/plates_promo_final_preview_720.mp4` | Лёгкое превью 720×1280 для пересылки |
| `out/plates_final_mix.wav` | Финальный микс (музыка + SFX), 48 kHz |
| `out/plates_sfx_stem.wav` | Дорожка эффектов отдельно |
| `preview/key_*.png` | Ключевые кадры |
| `preview/privacy_sheet_2fps.jpg` | Все моменты ролика с шагом 0,5 с — проверка личных данных |

## Синхронизация с треком (≈105 BPM, доля 0,571 с)

2,1 «Система.» · 2,5–3,0 брейк трека → 3,015 reveal на первом ударе · 5,87 вход в интерфейс ·
9,87 / 11,015 / 12,155 — 60 / 55 / 50 кг · 14,445 экран «Прогресс» · 16,16 точка прогресса ·
21,88 остановка на финальном кадре · 26,445 логотип · 26,6–29,0 затухание музыки.

## Пересборка

```bash
cd plates-promo
./src/export.sh <запись-экрана.mov> <логотип.png> <музыка-29с.mp3>
```

1. `src/prep_assets.py` — кадры записи, склейка прокрутки в длинные страницы, удаление статус-бара,
   веса тела и карточки «Вес тела»; экран настроек не используется вовсе.
2. `src/scene.html` — весь ролик как один детерминированный таймлайн (`render(t)`).
3. `src/render.js` — покадровый рендер в Chromium; `src/merge.py` — motion blur из подкадров.
4. `src/sfx.py` — вторичные звуковые акценты (синтез); `src/mix.py` — сведение с музыкой, −14 LUFS.

Нужны: Python 3 + Pillow + numpy, Node.js + Playwright (Chromium), ffmpeg, ImageMagick.
Шрифт Inter Display (SIL OFL) лежит в `src/fonts/`.
