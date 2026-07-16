#!/bin/bash
# macctl.sh — RELIABLE Classic Mac OS control via patched Basilisk II control server.
# Injects input at the ADB layer (perfect timing), NOT via xdotool/X11. The real
# "control classic Mac OS like we SSH OS X" solution. Serves the 1994 AppleTalk farm
# AND Scott's real-G4 OS9 POSIX/shim project.
#
# Patched emulator: ~/mac-farm/src/macemu/BasiliskII/src/Unix/BasiliskII
# Launch node N: ~/mac-farm/launch_node.sh N  (display :8N, control port 656(N-1))
#
# Usage: macctl.sh <node#> <cmd> ...
#   move X Y | click X Y | dclick X Y | down | up
#   key CODE | keydown CODE | keyup CODE | cmd CODE | type "text"
#   shot [file]
# Mac keycodes: Return=36 Cmd=55 Shift=56 O=31 W=13 Q=12 . =47 etc.
N="${1:-1}"; CMD="$2"; PORT=$((6560 + N - 1)); DISP=":8$N"
send(){ printf '%s\n' "$1" | timeout 5 nc -q1 127.0.0.1 "$PORT"; }
case "$CMD" in
  move)   send "m $3 $4" ;;
  click)  send "c $3 $4" ;;
  dclick) send "dc $3 $4" ;;
  down)   send "d" ;;
  up)     send "u" ;;
  key)    send "k $3" ;;
  keydown)send "kd $3" ;;
  keyup)  send "ku $3" ;;
  cmd)    send "cmd $3" ;;
  type)   send "t $3" ;;
  shot)   f="${3:-/tmp/node${N}_shot.png}"; DISPLAY=$DISP xwd -root -silent 2>/dev/null | convert xwd:- "$f"; echo "$f" ;;
  *) grep '^#' "$0" | sed 's/^# \?//' ;;
esac
