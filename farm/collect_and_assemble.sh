#!/bin/bash
# Collect rendered PPM frames from the three farm disks (after clean shutdown has
# flushed them) and assemble the robot-laser animation. Run AFTER all nodes are down.
set -e
OUT=/tmp/farmout
rm -rf "$OUT"; mkdir -p "$OUT"
rm -f ~/.hcwd

for D in A B C; do
  disk="$HOME/mac-farm/farm$D.dsk"
  humount 2>/dev/null || true
  hmount "$disk" >/dev/null
  for p in $(hls | grep -oE 'frame[0-9]{2}\.ppm'); do
    hcopy -r ":$p" "$OUT/$p" && echo "  farm$D -> $p"
  done
  humount >/dev/null
done

echo "collected $(ls "$OUT"/*.ppm 2>/dev/null | wc -l)/18 frames"
# PPM -> PNG, then scale up 3x (nearest, keep the crisp retro pixels) and assemble
cd "$OUT"
for f in frame*.ppm; do convert "$f" "${f%.ppm}.png"; done
convert frame*.png -filter point -resize 480x360 -set delay 12 -loop 0 /tmp/robot_laser.gif
convert frame*.png -filter point -resize 480x360 -set delay 12 /tmp/robot_laser_seq.gif
echo "made /tmp/robot_laser.gif"
montage frame*.png -tile 6x3 -geometry 160x120+2+2 -background black /tmp/robot_farm_contact.png
echo "made contact sheet"
