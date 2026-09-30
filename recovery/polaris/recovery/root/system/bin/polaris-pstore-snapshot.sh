#!/system/bin/sh
# Private early-boot evidence, bounded to RAM. Pull before leaving recovery.
umask 077
out=/tmp/polaris-boot-evidence
mkdir -p "$out/pstore" || exit 1
{
    uname -a
    cat /proc/mounts
    cat /sys/class/power_supply/battery/capacity
    cat /sys/class/power_supply/battery/status
} > "$out/recovery-state.txt" 2>&1
count=0
for source in /sys/fs/pstore/*; do
    [ -f "$source" ] || continue
    [ "$count" -lt 8 ] || break
    name=${source##*/}
    dd if="$source" of="$out/pstore/$name" bs=4096 count=512 2>> "$out/copy-errors.txt"
    count=$((count + 1))
done
printf 'pstore_files=%s\n' "$count" > "$out/status.txt"
dmesg > "$out/recovery-dmesg.txt" 2>&1
# This dmesg belongs to RECOVERY, not to the failed Android boot.
exit 0
