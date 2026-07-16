#!/bin/bash
# One emulated Macintosh render-farm node.
#   NODE_ID     numeric id (1..N)
#   NODE_NAME   AppleTalk / Chooser name  (default: RenderNode-<ID>)
#   UDP_PORT    shared virtual-ethernet port (SAME on every node = one AppleTalk segment)
set -e
NODE_ID="${NODE_ID:-1}"
NODE_NAME="${NODE_NAME:-RenderNode-${NODE_ID}}"
UDP_PORT="${UDP_PORT:-6066}"
export DISPLAY=:99
CTL_PORT=6560

echo "[node ${NODE_ID}] name='${NODE_NAME}'  udp-ether=${UDP_PORT}  ctl=${CTL_PORT}"

# headless framebuffer
Xvfb :99 -screen 0 800x600x16 >/shared/xvfb_node${NODE_ID}.log 2>&1 &
for i in $(seq 1 20); do xdpyinfo >/dev/null 2>&1 && break; sleep 0.5; done

# per-node writable OS image (mounted at /os/os.img by compose; must already be a copy)
if [ ! -f /os/os.img ]; then echo "FATAL: /os/os.img missing (run farm-init.sh)"; exit 1; fi

cat > /work_node.prefs <<PREFS
disk /os/os.img
disk /opt/mac/stuffit.img
extfs /shared
screen win/800/600
rom /opt/mac/mac.rom
bootdrive 0
bootdriver 0
ramsize 134217728
frameskip 0
modelid 14
cpu 4
fpu true
nocdrom false
nosound true
nogui true
ignoresegv true
idlewait true
ether slirp
udptunnel true
udpport ${UDP_PORT}
PREFS

# start the emulator with the ADB control server reachable from the host
export RC_MAC_CTL_PORT=${CTL_PORT} RC_MAC_CTL_BIND=any
/opt/mac/BasiliskII --config /work_node.prefs >/shared/basilisk_node${NODE_ID}.log 2>&1 &
BPID=$!

# wait for the control server, then dismiss any startup dialog
for i in $(seq 1 40); do nc -z 127.0.0.1 ${CTL_PORT} 2>/dev/null && break; sleep 1; done
sleep 6
printf 'k 36\n' | nc -q1 127.0.0.1 ${CTL_PORT} >/dev/null 2>&1 || true
echo "[node ${NODE_ID}] '${NODE_NAME}' up — control on container :${CTL_PORT}"

# keep the container tied to the emulator
wait ${BPID}
