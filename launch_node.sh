#!/bin/bash
# $1 = node number (display :8N, port 656N)
N=${1:-1}
export DISPLAY=:8$N
export RC_MAC_CTL_PORT=$((6560 + N - 1))
MB=~/mac-farm/src/macemu/BasiliskII/src/Unix/BasiliskII
exec "$MB" --config ~/mac-farm/node$N.prefs < /dev/null > /tmp/basilisk_node$N.log 2>&1
