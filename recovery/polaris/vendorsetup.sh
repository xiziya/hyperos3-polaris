#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
if [[ "${FOX_BUILD_DEVICE:-}" == polaris ]]; then
    export FOX_BUILD_TYPE=Unofficial
    export FOX_VARIANT=polaris-static-a15-test
    export FOX_KERNEL=4.19
    export FOX_VANILLA_BUILD=1
    export FOX_DELETE_MAGISK_ADDON=1
    export FOX_DELETE_AROMAFM=1
    export FOX_RECOVERY_SYSTEM_PARTITION=/dev/block/bootdevice/by-name/system
    export FOX_RECOVERY_VENDOR_PARTITION=/dev/block/bootdevice/by-name/vendor
    export FOX_USE_LZ4_BINARY=1
    export FOX_USE_ZSTD_BINARY=1
    export FOX_USE_TAR_BINARY=1
    export FOX_USE_NANO_EDITOR=1
fi
