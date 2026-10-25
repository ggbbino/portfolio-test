# Digital Journal — анимация для закреплённого поста

Концепция «Оживающий журнал»: синяя страница проходит по белому листу, за её
кромкой проявляется монограмма DJ, затем страница складывается в синий сгиб
логотипа, появляется «Digital Journal», и страница закрывает всё обратно в
исходный кадр. Петля бесшовная.

## Файлы

| Файл | Что это |
|---|---|
| `digital_journal_intro.gif` | Для публикации: 720×720, 25 fps, 7,0 с, 175 кадров, бесконечный цикл, ≈0,95 МБ |
| `digital_journal_intro.mp4` | H.264 High, yuv420p, 1080×1080, 25 fps, 7,0 с, без аудио, ≈0,18 МБ |
| `previews/` | Ключевые кадры (`t*.png`) и `contact_sheet.jpg` |
| `src/render.py` | Покадровый рендер (Python, Pillow + numpy) |
| `src/export.sh` | Рендер + экспорт MP4/GIF + превью одной командой |
| `src/digital_journal_logo.png` | Утверждённый логотип (исходник) |
| `src/Inter-Medium.otf` | Шрифт названия (Inter, SIL OFL) |

## Тайминг

| Время | Что происходит |
|---|---|
| 0,0–1,0 с | Узкий синий край страницы слева, лёгкое «дыхание» |
| 1,0–4,2 с | Страница раскрывается и проходит по кадру; где она прошла, проявляется DJ; затем складывается в синий сгиб |
| ≈4,1 с | Последние ~0,1 с вектор незаметно передаёт кадр исходному PNG (финальный знак — пиксели оригинала) |
| 4,2–5,0 с | «Digital Journal»: проявление + смещение на 10 px |
| 5,0–6,0 с | Статичная композиция |
| 6,0–7,0 с | Название гаснет, страница раскрывается обратно и закрывает знак, возвращаясь в первый кадр |

## Повторный экспорт

Нужны `python3` с `Pillow` и `numpy`, `ffmpeg`, ImageMagick (`montage`, только для превью).

```bash
cd telegram-intro
./src/export.sh
```

Скрипт рендерит кадры в `build/frames/` (в git не попадают), затем:

```bash
# MP4
ffmpeg -framerate 25 -i build/frames/frame_%04d.png -c:v libx264 -preset slow -crf 14 \
  -tune animation -pix_fmt yuv420p -profile:v high -movflags +faststart -an digital_journal_intro.mp4
# GIF
ffmpeg -framerate 25 -i build/frames/frame_%04d.png -vf "scale=720:720:flags=lanczos,split[a][b];\
[a]palettegen=max_colors=96:stats_mode=full[p];[b][p]paletteuse=dither=sierra2_4a:diff_mode=rectangle" \
  -loop 0 digital_journal_intro.gif
```

Основные настройки в начале `src/render.py`: `SCALE` (размер знака), `TITLE_SIZE`/`TITLE_GAP`
(название), `T_*` (тайминг), `KEYS` (траектория страницы по ключевым точкам).

## Автозапуск в Telegram

GIF зациклен бесконечно, но будет ли он воспроизводиться сам, зависит от настроек
автозагрузки и автовоспроизведения у читателя. Файл это не контролирует.
