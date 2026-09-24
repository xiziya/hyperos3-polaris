#!/usr/bin/env bash
# Build only an unflashable Image.gz-dtb + provenance. Never packages old boot.img.
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
: "${KERNEL_SOURCE:?Set KERNEL_SOURCE to a Linux checkout of the locked kernel}"
: "${KERNEL_OUT:?Set KERNEL_OUT to a new or dedicated build directory}"
: "${CLANG_BIN:?Set CLANG_BIN to a compatible Android clang toolchain bin directory}"
export PATH="$CLANG_BIN:$PATH"
expected_toolchain=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["toolchain"]["commit"])' "$repo_root/config/sources.json")
actual_toolchain=$(git -C "$CLANG_BIN" rev-parse HEAD)
[[ "$actual_toolchain" == "$expected_toolchain" ]] || { echo 'Toolchain commit does not match lock'; exit 1; }
[[ -z "$(git -C "$CLANG_BIN" status --porcelain)" ]] || { echo 'Toolchain checkout must be clean'; exit 1; }
expected=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["kernel"]["commit"])' "$repo_root/config/sources.json")
actual=$(git -C "$KERNEL_SOURCE" rev-parse HEAD)
[[ "$actual" == "$expected" ]] || { echo 'Kernel commit does not match lock'; exit 1; }
[[ -z "$(git -C "$KERNEL_SOURCE" status --porcelain)" ]] || { echo 'Kernel checkout must be clean'; exit 1; }
patches=("$repo_root"/kernel/patches/*.patch)
if [[ -f "${patches[0]}" ]]; then
    git -C "$KERNEL_SOURCE" apply --check "${patches[@]}"
    git -C "$KERNEL_SOURCE" apply "${patches[@]}"
    # Source is a clean dedicated checkout; reverse only this exact patch set.
    trap 'git -C "$KERNEL_SOURCE" apply --reverse "${patches[@]}"' EXIT
fi
for executable in clang ld.lld llvm-ar llvm-nm llvm-objcopy llvm-objdump llvm-strip make python3; do
    command -v "$executable" >/dev/null || { echo "Missing $executable"; exit 1; }
done
mkdir -p -- "$KERNEL_OUT"
KERNEL_SOURCE=$(realpath "$KERNEL_SOURCE")
KERNEL_OUT=$(realpath "$KERNEL_OUT")
[[ "$KERNEL_OUT" != "$KERNEL_SOURCE" ]] || { echo 'Use an out-of-tree build'; exit 1; }
export ARCH=arm64
export KBUILD_BUILD_USER=polaris
export KBUILD_BUILD_HOST=hyperos3
export SOURCE_DATE_EPOCH=$(git -C "$KERNEL_SOURCE" show -s --format=%ct HEAD)
export KBUILD_BUILD_TIMESTAMP=$(date -u -d "@$SOURCE_DATE_EPOCH")
export KBUILD_BUILD_VERSION=1
args=(-C "$KERNEL_SOURCE" O="$KERNEL_OUT" ARCH=arm64 LLVM=1 LLVM_IAS=1
      CC=clang LD=ld.lld AR=llvm-ar NM=llvm-nm OBJCOPY=llvm-objcopy
      OBJDUMP=llvm-objdump STRIP=llvm-strip
      CROSS_COMPILE=aarch64-linux-gnu- CROSS_COMPILE_ARM32=arm-linux-gnueabi-)
make "${args[@]}" vendor/sdm845-perf_defconfig
# Merge explicitly: the reference Lineage device tree points to an absent mi845_defconfig.
(cd "$KERNEL_SOURCE" && scripts/kconfig/merge_config.sh -m -O "$KERNEL_OUT" \
    "$KERNEL_OUT/.config" arch/arm64/configs/vendor/xiaomi/sdm845-common.config \
    arch/arm64/configs/vendor/xiaomi/polaris.config "$repo_root/kernel/polaris-pure.config")
make "${args[@]}" olddefconfig
python3 "$repo_root/tools/check_kernel_config.py" "$KERNEL_OUT/.config"
if [[ "${CONFIG_ONLY:-0}" != 1 ]]; then
    make "${args[@]}" -j"${JOBS:-4}" Image.gz-dtb
    test -s "$KERNEL_OUT/arch/arm64/boot/Image.gz-dtb"
fi
{
    echo "kernel_commit=$actual"
    echo "project_commit=$(git -C "$repo_root" rev-parse HEAD)"
    echo "project_worktree_dirty=$(git -C "$repo_root" status --porcelain | wc -l)"
    echo "toolchain_commit=$actual_toolchain"
    sha256sum "$repo_root/tools/build_kernel.sh" "$repo_root/kernel/polaris-pure.config" "$repo_root/config/sources.json"
    if [[ -f "${patches[0]}" ]]; then sha256sum "${patches[@]}"; fi
    clang --version
    ld.lld --version
    sha256sum "$KERNEL_OUT/.config"
    if [[ "${CONFIG_ONLY:-0}" != 1 ]]; then sha256sum "$KERNEL_OUT/arch/arm64/boot/Image.gz-dtb"; fi
} > "$KERNEL_OUT/provenance.txt"
echo 'No boot image, installer or stable release produced. Device integration is separate.'
