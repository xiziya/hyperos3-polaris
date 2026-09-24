#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
download_dir=${1:-"$repo_root/work/downloads"}
mkdir -p -- "$download_dir"
name=ziyi-ota_full-OS3.0.6.0.VLLCNXM-user-15.0-f6ef5f9254.zip
# Original Xiaomi CDN, same path/content as bigota; keep TLS validation enabled.
aria2c --continue=true --max-connection-per-server=16 --split=16 --min-split-size=4M \
    --max-tries=5 --retry-wait=5 --connect-timeout=15 --timeout=30 \
    --file-allocation=none --auto-file-renaming=false --allow-overwrite=false \
    --show-console-readout=false --summary-interval=60 \
    --dir="$download_dir" --out="$name" \
    "https://cdnorg.d.miui.com/OS3.0.6.0.VLLCNXM/$name"
python3 "$repo_root/tools/verify_donor.py" "$download_dir/$name"
