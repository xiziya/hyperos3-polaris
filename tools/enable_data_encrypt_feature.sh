#!/sbin/sh
# Explicit owner opt-in only. Never called by the ROM installer.
# Data must already be unmounted. Does not format, flash ROM or reboot.
set -eu
PATH=/system/bin:/sbin:/bin
export PATH
die() { echo "ERROR: $*" >&2; exit 1; }
[ "${1:-}" = --enable-encrypt ] || die 'Explicit --enable-encrypt required.'
[ "$(id -u)" = 0 ] || die 'Recovery root required.'
[ "$(getprop init.svc.recovery)" = running ] && [ -f /etc/recovery.fstab ] || die 'Recovery required.'
[ "$(getprop ro.product.device)" = polaris ] || die 'Wrong device.'
target=$(readlink -f /dev/block/by-name/userdata)
[ "$target" = /dev/block/sda21 ] && [ -b "$target" ] || die 'Unexpected userdata mapping.'
[ "$(blockdev --getsize64 "$target")" = 116928786432 ] || die 'Unexpected userdata size.'
[ "$(cat /sys/class/block/sda21/start)" = 11927552 ] || die 'Unexpected userdata start.'
mm=$(cat /sys/class/block/sda21/dev)
if awk -v d="$mm" '$3==d {found=1} END{exit !found}' /proc/self/mountinfo; then
    die 'Unmount Data and internal storage before changing filesystem features.'
fi
for holder in /sys/class/block/sda21/holders/*; do
    [ ! -e "$holder" ] || die 'Active userdata mapper.'
done
task_tmp=$(mktemp -d /tmp/polaris-fs-feature.XXXXXX)
dd if="$target" of="$task_tmp/super.before" bs=1024 skip=1 count=1 2>/dev/null
magic=$(od -An -tu2 -j56 -N2 "$task_tmp/super.before" | tr -d ' ')
features=$(od -An -tu4 -j96 -N4 "$task_tmp/super.before" | tr -d ' ')
[ "$magic" = 61267 ] || die 'Not ext4.'
[ "$((features & 4))" = 0 ] || die 'Journal recovery needed; refusing modification.'
[ "$((features & 65536))" = 0 ] || die 'Encrypt feature already enabled.'
e2fsck -fn "$target" || die 'Read-only fsck failed; nothing changed by this tool.'
tune2fs -O encrypt "$target" || die 'Feature update failed; remain in recovery.'
e2fsck -fn "$target" || die 'Post-update fsck failed; remain in recovery.'
dd if="$target" of="$task_tmp/super.after" bs=1024 skip=1 count=1 2>/dev/null
after=$(od -An -tu4 -j96 -N4 "$task_tmp/super.after" | tr -d ' ')
[ "$((after & 65536))" != 0 ] || die 'Encrypt flag not present after update.'
echo "Encrypt feature enabled; superblock snapshots retained at $task_tmp."
echo 'No format, ROM install or reboot performed. Remount Data and run preflight.'
