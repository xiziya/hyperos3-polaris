#!/usr/bin/env bash
# The locked upstream script uses BASE_DIR="$PWD", not dirname "$0".
set -euo pipefail
sync_checkout=$(realpath "${1:?Pass the locked OrangeFox sync checkout}")
android_destination=$(realpath -m "${2:?Pass the dedicated Android destination}")
test -f "$sync_checkout/orangefox_sync.sh"
test -f "$sync_checkout/patches/patch-manifest-fox_12.1.diff"
cd -- "$sync_checkout"
if [[ -n ${3:-} ]]; then
    project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
    generated=$(mktemp "$sync_checkout/polaris-sync.XXXXXX.sh")
    trap 'rm -f -- "$generated"' EXIT
    python3 "$project/tools/prepare_cached_recovery_sync.py" \
        --source "$sync_checkout/orangefox_sync.sh" --cache "$3" \
        --lock "$project/config/recovery-sources.json" --output "$generated"
    bash "$generated" --branch 12.1 --path "$android_destination"
else
    exec bash ./orangefox_sync.sh --branch 12.1 --path "$android_destination"
fi
