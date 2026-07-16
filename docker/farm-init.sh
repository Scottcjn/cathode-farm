#!/bin/bash
# Give each farm node its own writable copy of the base System 7.5 disk.
# Usage: ./farm-init.sh alpha bravo charlie ...   (defaults to the 3 compose nodes)
set -e
cd "$(dirname "$0")"
BASE=assets/os_base.img
[ -f "$BASE" ] || { echo "missing $BASE"; exit 1; }
mkdir -p os
NODES=("$@"); [ ${#NODES[@]} -eq 0 ] && NODES=(alpha bravo charlie)
for n in "${NODES[@]}"; do
  if [ ! -f "os/$n.img" ]; then
    echo "creating os/$n.img (copy of base)…"; cp "$BASE" "os/$n.img"
  else
    echo "os/$n.img exists, keeping"
  fi
done
echo "done: $(ls os/)"
