#!/bin/sh
# Rebuilds the synthetic demo clips and the demo transition (no footage needed).
set -e
cd "$(dirname "$0")"
ffmpeg -v error -y -f lavfi -i "testsrc2=s=1280x720:d=2:r=30" -pix_fmt yuv420p a.mp4
ffmpeg -v error -y -f lavfi -i "gradients=s=1280x720:d=2:r=30:c0=0x00c9a7:c1=0x2d1b4e:c2=0xff6b35:nb_colors=3,hue=h=t*60" -pix_fmt yuv420p b.mp4
python3 ../scripts/wipe.py a.mp4 b.mp4 out.mp4 --no-sfx
