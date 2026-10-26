#!/usr/bin/env bash
# Full rebuild of the Plates film.
#   ./src/export.sh <screen-recording.mov> <logo.png> <music-29s.mp3>
# Needs: python3 (Pillow, numpy), node + playwright (Chromium), ffmpeg, ImageMagick.
set -euo pipefail
cd "$(dirname "$0")/.."
APP=${1:?screen recording}; LOGO=${2:?logo png}; MUSIC=${3:?music (BerryDeep 29 s cut)}

python3 src/prep_assets.py --app "$APP" --logo "$LOGO"      # clean UI material (privacy pass)
python3 -c "
from PIL import Image
im=Image.open('assets/training_page.png').convert('RGBA').crop((0,0,512,1108))
im.alpha_composite(Image.open('assets/training_overlay.png'),(0,870)); im.convert('RGB').save('build/final_screen.png')"
rm -rf build/frames
node src/render.js build/frames 30 29                        # 870 frames, 1080x1920
python3 src/merge.py build/frames                            # motion-blur sub-frames
python3 src/sfx.py                                           # secondary sound design
python3 src/mix.py "$MUSIC"                                  # music + SFX -> build/mix.wav, -14 LUFS

mkdir -p out preview
# final master with music (mix already at -14 LUFS / -1 dBTP, so no loudnorm here)
ffmpeg -y -loglevel error -framerate 30 -i build/frames/f_%04d.png -i build/mix.wav \
  -c:v libx264 -preset slow -crf 15 -pix_fmt yuv420p -profile:v high -level 4.2 -movflags +faststart \
  -c:a aac -b:a 256k -ar 48000 -shortest out/plates_promo_final_master_1080x1920.mp4
# picture only
ffmpeg -y -loglevel error -framerate 30 -i build/frames/f_%04d.png \
  -c:v libx264 -preset slow -crf 15 -pix_fmt yuv420p -profile:v high -level 4.2 -movflags +faststart -an \
  out/plates_promo_final_master_silent.mp4
ffmpeg -y -loglevel error -i out/plates_promo_final_master_1080x1920.mp4 -vf scale=720:1280:flags=lanczos \
  -c:v libx264 -preset slow -crf 22 -pix_fmt yuv420p -movflags +faststart -c:a aac -b:a 128k preview/plates_promo_final_preview_720.mp4
cp build/sfx.wav out/plates_sfx_stem.wav
cp build/mix.wav out/plates_final_mix.wav

# previews: key frames + a 2 fps sheet of every moment (used for the privacy review)
for t in 2.6 4.6 7.5 10.3 11.5 12.5 13.6 15.2 16.9 18.6 19.6 20.6 23.6 27.8; do
  f=$(python3 -c "print(f'{round($t*30):04d}')"); cp build/frames/f_$f.png preview/key_${t}s.png
done
montage build/frames/f_0{000..869..15}.png -tile 8x -geometry 216x384+3+3 -background '#222' \
  preview/privacy_sheet_2fps.jpg
echo done
