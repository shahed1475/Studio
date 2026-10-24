#!/usr/bin/env bash
# Render the same template twice and print real numbers: seconds, peak memory (cgroup), CPU seconds. The clips stay inside the container.
set -euo pipefail
cpu() { awk '/^usage_usec/ {printf "%.1f", $2/1000000}' /sys/fs/cgroup/cpu.stat 2>/dev/null || echo 0; }
for f in vertical wide; do
  c0=$(cpu); t0=$(date +%s.%N)
  npx remotion render src/index.ts Timeline "/tmp/$f.mp4" --props="examples/$f.json" --concurrency=2 --log=error >"/tmp/$f.log" 2>&1 || { tail -20 "/tmp/$f.log"; exit 1; }
  t1=$(date +%s.%N); c1=$(cpu)
  echo "$f: $(echo "$t1 - $t0" | bc -l | cut -c1-6) s wall; $(echo "$c1 - $c0" | bc -l | cut -c1-6) cpu-s; $(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,nb_frames,duration -of csv=p=0 "/tmp/$f.mp4")"
done
echo "peak memory (cgroup memory.peak): $(( $(cat /sys/fs/cgroup/memory.peak) / 1048576 )) MiB"
