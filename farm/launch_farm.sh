#!/bin/bash
# $1=letter(A/B/C)  $2=display-num  $3=ctl-port
L=$1; D=$2; P=$3
export DISPLAY=:$D
export RC_MAC_CTL_PORT=$P
MB=~/mac-farm/src/macemu/BasiliskII/src/Unix/BasiliskII
exec "$MB" --config ~/mac-farm/farm$L.prefs < /dev/null > /tmp/farm$L.log 2>&1
