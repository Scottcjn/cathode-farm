#!/bin/bash
# Collect the 30 HQ frames from the 6 farm disks (after clean shutdown flushes them)
# and assemble the final robot-laser movie. Run AFTER all nodes are shut down.
set -e
OUT=/tmp/hqfinal; rm -rf "$OUT"; mkdir -p "$OUT"; rm -f ~/.hcwd
for N in 1 2 3 4 5 6; do
  disk="$HOME/mac-farm/hq$N.dsk"; humount 2>/dev/null || true
  hmount "$disk" >/dev/null
  for p in $(hls | grep -oE 'frame[0-9]{2}\.ppm'); do hcopy -r ":$p" "$OUT/$p" && echo "  hq$N -> $p"; done
  humount >/dev/null
done
echo "collected $(ls "$OUT"/*.ppm 2>/dev/null | wc -l)/30 frames"
cd "$OUT"; for f in frame*.ppm; do convert "$f" "${f%.ppm}.png"; done
convert frame*.png -set delay 8 -loop 0 /tmp/robot_laser_hq_final.gif
ffmpeg -y -framerate 12 -pattern_type glob -i 'frame*.png' -pix_fmt yuv420p -vf "scale=640:480:flags=lanczos" /tmp/robot_laser_hq_final.mp4 2>/dev/null
montage frame*.png -tile 6x5 -geometry 160x120+2+2 -background black /tmp/robot_hq_contact.png
echo "assembled /tmp/robot_laser_hq_final.{gif,mp4}"
