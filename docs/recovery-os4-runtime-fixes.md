# Polaris recovery runtime corrections — 2026-09-30

## Scope and evidence

The owner now tests HyperOS 4 / Android 17 on the same static polaris layout.
This change updates recovery only. Historical A15 ROM reports and release gates
remain historical; this commit does not publish or validate the OS4 ROM. The
owner explicitly requested this recovery CI run before the next system-boot test.

The running September 25 OrangeFox build uses the locked pure 4.19.325 kernel.
Read-only capture found a mounted pstore backend with no saved records, a
non-empty BCB command `boot-recovery`, readable battery capacity/status sysfs
nodes, and a UI fstab without `/misc` or EROFS vendor. Raw captures stay private.
No flash, format, reboot, or live BCB write was performed by this repair task.

These findings identify recovery defects. They do **not** establish the cause of
the OS4 V1 Android bootloop. The earlier 4.9 recovery capture had an empty BCB;
all seven ROM image writes had passed readback, and installed kernel/ramdisk
matched the candidate. Those are separate observations from different boots.

## Implementation and rationale

1. **BCB discovery:** `fstab.android` supplies the five-column Android libfs_mgr
   format as `/etc/recovery.fstab`. Staging installs the UI-specific legacy
   format as `/etc/twrp.fstab`, which the locked OrangeFox selects first. Both
   describe the same static nodes. `/misc` is not a backup, image-flash or wipe
   menu target. This avoids feeding four-column TWRP options into libfs_mgr.
2. **Explicit system reboot:** the source-locked patch adds a guard in the
   `rb_system`/`rb_current` path. It verifies the static misc path is a block
   device, uses AOSP `read_bootloader_message_from`/`write_bootloader_message_to`,
   clears only the 2048-byte BCB if needed and reads it back. Failure cancels
   reboot and logs the reason. No whole-partition erase or guessed physical
   `sda*` number, and no change to intentional Reboot Recovery. The native
   implementation fsyncs its write. No system boot, vendor or GPT is patched.
3. **Battery:** explicitly enable `TW_USE_LEGACY_BATTERY_SERVICES` and set
   `TW_CUSTOM_BATTERY_PATH` to `/sys/class/power_supply/battery`. Both settings
   are necessary: the locked Android.mk evaluates the legacy define before it
   processes the custom path. The known-good polaris capacity/status nodes are
   used instead of relying on a health HAL absent from this staged recovery.
4. **Mounting:** add EROFS vendor and mi_product for the current OS4 image set.
   The kernel already supplies EROFS, PSTORE_CONSOLE/PMSG/RAM and the fixed
   4 MiB ramoops reservation at 0xb0000000. Preserve its console/pmsg split to
   match the system kernel. Empty pstore is reported honestly, not filled with
   recovery dmesg and presented as the failed system log.
5. **Evidence:** at recovery boot copy available pstore files into
   `/tmp/polaris-boot-evidence/pstore`, at most eight files of 2 MiB each. Copy
   the recovery's own dmesg separately. Do not unlink pstore, mount/format Data,
   or write persistent storage. These RAM copies must be pulled before reboot.
6. **Build gates:** retain prior source cache/sync-cwd and image metadata fixes.
   CI compiles the locked pure kernel and OrangeFox; post-build inspection
   requires the actual recovery ELF's reboot-guard marker, both misc mappings,
   the snapshot script and embedded EROFS/pstore config before publishing the
   image artifact. The artifact is still explicitly UNTESTED.

The first CI attempt after this change failed at the final ramdisk rsync because
staging had created `recovery/root/etc` as a real directory. OrangeFox's locked
image step creates that path as a symlink to its system etc tree. The staging
directory is now left untouched; the device fstab is consumed by the normal
OrangeFox image step, so the fix does not change the runtime layout.

## Validation and limits

WSL host tests execute the exact C++ reboot guard with simulated BCB I/O. They
cover success, already empty BCB, missing/non-block device, read failure, write
failure, failed readback and a write that falsely claims success. Bytes outside
the first 2048 remain unchanged. Configuration tests check both fstab mappings
and reject changed/repeated upstream patch anchors. This is not device testing.

The full recovery build runs remotely after the owner-authorized dev push.
UI battery display, successful System/Reboot Recovery selection, actual EROFS
mounts, and previous-boot log retention need hardware validation. Android 17
FBE decryption remains unverified: keymaster/FBE settings were not replaced on
the basis of this reboot/battery fix. Do not Format Data for this diagnostic.

After the owner installs the recovery and reboots **Recovery once**, verify the
new variant `polaris-static-os4-bcb1-test`, battery and nodes. Then the owner can
choose System to reproduce the OS4 failure and return to recovery once. Pull
pstore plus `/tmp/polaris-boot-evidence` immediately; keep originals private.
If the BCB guard refuses reboot, read its error instead of bypassing the guard.
Rollback means owner reinstalling a known recovery image to Recovery only.

## Sources

- Locked OrangeFox recovery source: `config/recovery-sources.json`,
  `twrp.cpp` battery monitor and fstab selection, `twrp-functions.cpp` reboot,
  `bootloader_message/bootloader_message.cpp` bounded BCB I/O.
- AOSP-derived TeamWin libfs_mgr: https://github.com/TeamWin/android_system_core/blob/android-12.1/fs_mgr/fs_mgr_fstab.cpp
- Locked kernel `fs/pstore/ram.c`: existing `ramoops_memreserve` implementation.
- Local read-only evidence and source audit, summarized above without device IDs.
