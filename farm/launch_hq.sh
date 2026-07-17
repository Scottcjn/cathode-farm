#!/bin/bash
N=$1; D=$2; P=$3
export DISPLAY=:$D
export RC_MAC_CTL_PORT=$P
exec ~/mac-farm/src/macemu/BasiliskII/src/Unix/BasiliskII --config ~/mac-farm/hq$N.prefs </dev/null >/tmp/hq$N.log 2>&1
