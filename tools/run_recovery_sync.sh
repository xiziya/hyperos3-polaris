#!/usr/bin/env bash
# The locked upstream script uses BASE_DIR="$PWD", not dirname "$0".
set -euo pipefail
sync_checkout=$(realpath "${1:?Pass the locked OrangeFox sync checkout}")
android_destination=$(realpath -m "${2:?Pass the dedicated Android destination}")
test -f "$sync_checkout/orangefox_sync.sh"
test -f "$sync_checkout/patches/patch-manifest-fox_12.1.diff"
cd -- "$sync_checkout"
exec bash ./orangefox_sync.sh --branch 12.1 --path "$android_destination"
