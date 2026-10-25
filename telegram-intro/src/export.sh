#!/usr/bin/env bash
# Re-render and re-export the Digital Journal intro.
# Requirements: python3 with Pillow + numpy, ffmpeg, ImageMagick (previews only).
set -euo pipefail
cd "$(dirname "$0")/.."

FRAMES=build/frames
rm -rf "$FRAMES"
python3 src/render.py --out "$FRAMES"

# MP4: 1080x1080, 25 fps, H.264 High, yuv420p, no audio, web-optimised.
ffmpeg -y -loglevel error -framerate 25 -i "$FRAMES/frame_%04d.png" \
  -c:v libx264 -preset slow -crf 14 -tune animation -pix_fmt yuv420p \
  -profile:v high -movflags +faststart -an digital_journal_intro.mp4

# GIF: 720x720, 25 fps (4 cs per frame), infinite loop, palette from all frames.
ffmpeg -y -loglevel error -framerate 25 -i "$FRAMES/frame_%04d.png" \
  -vf "scale=720:720:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=full:reserve_transparent=0[p];[b][p]paletteuse=dither=sierra2_4a:diff_mode=rectangle" \
  -loop 0 digital_journal_intro.gif

# Key-frame previews (time in seconds -> frame index at 25 fps).
mkdir -p previews
for f in 0 25 45 60 75 90 105 125 155 165; do
  t=$(printf '%.1f' "$(echo "$f/25" | bc -l)")
  cp "$FRAMES/frame_$(printf '%04d' "$f").png" "previews/t${t}s.png"
done
montage previews/t*.png -tile 5x2 -geometry 360x360+6+6 -background '#e5e5e5' \
  previews/contact_sheet.jpg
echo "done: digital_journal_intro.mp4, digital_journal_intro.gif, previews/"
