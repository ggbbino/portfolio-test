#!/usr/bin/env bash
# Full rebuild of the Plates film.
#   ./src/export.sh <screen-recording.mov> <logo.png>
# Needs: python3 (Pillow, numpy), node + playwright (Chromium), ffmpeg, ImageMagick.
set -euo pipefail
cd "$(dirname "$0")/.."
APP=${1:?screen recording}; LOGO=${2:?logo png}

python3 src/prep_assets.py --app "$APP" --logo "$LOGO"      # clean UI material (privacy pass)
python3 -c "
from PIL import Image
im=Image.open('assets/training_page.png').convert('RGBA').crop((0,0,512,1108))
im.alpha_composite(Image.open('assets/training_overlay.png'),(0,870)); im.convert('RGB').save('build/final_screen.png')"
rm -rf build/frames
node src/render.js build/frames 30 28                        # 840 frames, 1080x1920
python3 src/merge.py build/frames                            # motion-blur sub-frames
python3 src/sfx.py                                           # sound design + 120 BPM guide

mkdir -p out preview
# film with sound design (SFX only, -18 LUFS so a music bed fits on top)
ffmpeg -y -loglevel error -framerate 30 -i build/frames/f_%04d.png -i build/sfx.wav \
  -c:v libx264 -preset slow -crf 16 -pix_fmt yuv420p -profile:v high -movflags +faststart \
  -af "loudnorm=I=-18:TP=-1.5:LRA=11" -c:a aac -b:a 192k -ar 48000 -shortest out/plates_promo_v1.mp4
# picture only (for laying a 120 BPM track in any editor)
ffmpeg -y -loglevel error -framerate 30 -i build/frames/f_%04d.png \
  -c:v libx264 -preset slow -crf 16 -pix_fmt yuv420p -profile:v high -movflags +faststart -an \
  out/plates_promo_v1_silent.mp4
cp build/sfx.wav out/plates_sfx_stem.wav
cp build/click_120bpm.wav out/beat_guide_120bpm.wav

# previews: key frames + a 2 fps sheet of every moment (used for the privacy review)
for t in 2.4 4.6 7.5 10.3 11.5 12.5 13.6 15.9 17.9 19.7 20.9 23.3 26.8; do
  f=$(python3 -c "print(f'{round($t*30):04d}')"); cp build/frames/f_$f.png preview/key_${t}s.png
done
montage build/frames/f_0{000..839..15}.png -tile 8x -geometry 216x384+3+3 -background '#222' \
  preview/privacy_sheet_2fps.jpg
echo done
