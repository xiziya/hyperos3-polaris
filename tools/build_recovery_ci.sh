#!/usr/bin/env bash
# Build a test recovery image only; never flash or promote stable.
set -euo pipefail
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$project/tools/retry_git_fetch.sh"
: "${RECOVERY_WORK:?Set RECOVERY_WORK to a new dedicated Linux build directory}"
mkdir -p "$RECOVERY_WORK"
RECOVERY_WORK=$(realpath "$RECOVERY_WORK")
read_lock() {
    python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]][sys.argv[3]])' "$1" "$2" "$3"
}
checkout_locked() {
    local lock=$1 key=$2 destination=$3 url revision
    url=$(read_lock "$lock" "$key" url)
    revision=$(read_lock "$lock" "$key" commit)
    if [[ ! -d "$destination/.git" ]]; then git init "$destination"; fi
    if [[ $(git -C "$destination" rev-parse HEAD 2>/dev/null || true) == "$revision" ]]; then
        return 0
    fi
    if [[ -d "$RECOVERY_WORK/source-cache/$key/.git" && "$destination" != "$RECOVERY_WORK/source-cache/$key" ]]; then
        url="$RECOVERY_WORK/source-cache/$key"
    fi
    retry_git_fetch -C "$destination" fetch --depth=1 "$url" "$revision"
    git -C "$destination" checkout --detach FETCH_HEAD
    [[ $(git -C "$destination" rev-parse HEAD) == "$revision" ]]
}
checkout_locked "$project/config/recovery-sources.json" sync "$RECOVERY_WORK/sync"
test -f "$RECOVERY_WORK/sync/patches/patch-manifest-fox_12.1.diff"
mkdir -p "$project/build/recovery-evidence"
# Fetch locked GitLab sources before the expensive kernel/base Android build.
# The official sync script later clones these exact local commits, so a late
# GitLab 503 cannot discard two hours of successful base synchronization.
for key in recovery vendor common; do
    checkout_locked "$project/config/recovery-sources.json" "$key" "$RECOVERY_WORK/source-cache/$key"
done
checkout_locked "$project/config/sources.json" kernel "$RECOVERY_WORK/kernel"
checkout_locked "$project/config/sources.json" toolchain "$RECOVERY_WORK/clang"
KERNEL_SOURCE="$RECOVERY_WORK/kernel" KERNEL_OUT="$RECOVERY_WORK/kernel-out" CLANG_BIN="$RECOVERY_WORK/clang/bin" JOBS=4 \
    bash "$project/tools/build_kernel.sh"
cp "$RECOVERY_WORK/kernel-out/provenance.txt" "$project/build/recovery-evidence/kernel-provenance.txt"
cp "$RECOVERY_WORK/kernel-out/.config" "$project/build/recovery-evidence/kernel.config"
# Reviewed official sync script; runs only inside this dedicated checkout.
bash "$project/tools/run_recovery_sync.sh" "$RECOVERY_WORK/sync" "$RECOVERY_WORK/android" "$RECOVERY_WORK/source-cache"
checkout_locked "$project/config/recovery-sources.json" recovery "$RECOVERY_WORK/android/bootable/recovery"
checkout_locked "$project/config/recovery-sources.json" vendor "$RECOVERY_WORK/android/vendor/recovery"
checkout_locked "$project/config/recovery-sources.json" common "$RECOVERY_WORK/android/device/xiaomi/sdm845-common"
checkout_locked "$project/config/recovery-sources.json" qcom_common "$RECOVERY_WORK/android/device/qcom/common"
checkout_locked "$project/config/recovery-sources.json" qcom_twrp_common "$RECOVERY_WORK/android/device/qcom/twrp-common"
python3 "$project/tools/stage_recovery.py" "$RECOVERY_WORK/android" "$RECOVERY_WORK/kernel-out/arch/arm64/boot/Image.gz-dtb"
# Enable ext4 encrypt in the recovery's explicit Format Data path.
python3 "$project/recovery/patches/enable_ext4_encrypt.py" \
    "$RECOVERY_WORK/android/bootable/recovery/partition.cpp"
git -C "$RECOVERY_WORK/android/bootable/recovery" diff > "$project/build/recovery-evidence/recovery-source-changes.patch"
cd "$RECOVERY_WORK/android"
repo manifest -r -o "$project/build/recovery-evidence/android-manifest.xml"
repo diff > "$project/build/recovery-evidence/android-source-changes.patch"
export FOX_BUILD_DEVICE=polaris
export ALLOW_MISSING_DEPENDENCIES=true
export LC_ALL=C
export USE_CCACHE=0
# AOSP envsetup depends on unset variables and non-zero probes.
set +eu
source build/envsetup.sh
lunch twrp_polaris-eng
lunch_result=$?
set -eu
[[ $lunch_result == 0 ]]
make -j4 recoveryimage
image="$RECOVERY_WORK/android/out/target/product/polaris/recovery.img"
test -s "$image"
[[ $(stat -c %s "$image") -le 67108864 ]]
python3 "$project/tools/inspect_recovery.py" "$image" --output "$project/build/recovery-evidence/recovery-inspection.json"
cp "$image" "$project/build/recovery-evidence/recovery-UNTESTED-polaris-static-a15.img"
sha256sum "$image" > "$project/build/recovery-evidence/SHA256SUMS.txt"
echo 'UNTESTED development recovery. No stable release or installation is authorized by build success.' > "$project/build/recovery-evidence/STATUS.txt"
