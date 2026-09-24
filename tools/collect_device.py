#!/usr/bin/env python3
"""Collect a bounded local ADB report. Does not reboot, root, flash or upload."""
import argparse
import datetime
import json
import subprocess
from pathlib import Path

PROPS = ['ro.product.device', 'ro.product.vendor.device', 'ro.board.platform',
         'ro.build.version.release', 'ro.build.version.sdk', 'ro.build.version.incremental',
         'ro.vendor.build.version.sdk', 'ro.vndk.version', 'ro.boot.slot_suffix',
         'ro.boot.dynamic_partitions', 'ro.boot.super_partition', 'ro.boot.verifiedbootstate',
         'ro.boot.flash.locked', 'gsm.version.baseband', 'gsm.sim.state',
         'persist.radio.multisim.config', 'ro.boot.bootreason']
COMMANDS = {
    'kernel.txt': 'uname -a; cat /proc/version; cat /proc/meminfo; getconf PAGE_SIZE',
    'partitions.txt': 'cat /proc/partitions; ls -l /dev/block/by-name /dev/block/bootdevice/by-name; cat /proc/mounts',
    'partition-sizes.txt': 'for p in /sys/class/block/sd* /sys/class/block/dm-*; do echo "$p"; cat "$p/size" "$p/uevent" 2>/dev/null; done',
    'fstab.txt': 'cat /vendor/etc/fstab* /odm/etc/fstab* /system/etc/fstab* 2>/dev/null',
    'vintf.txt': 'cat /vendor/etc/vintf/manifest.xml /vendor/etc/vintf/compatibility_matrix.xml 2>/dev/null; lshal',
    'services.txt': 'getprop | grep -E "init.svc.*(ril|qcril|ims|rmt|netmgr|wifi|wpa|thermal|power|perfd)"; service list',
    'power.txt': 'dumpsys battery; dumpsys thermalservice; cat /sys/power/mem_sleep 2>/dev/null; for p in /sys/devices/system/cpu/cpufreq/policy*; do echo "$p"; cat "$p/scaling_governor" "$p/scaling_min_freq" "$p/scaling_max_freq"; done',
    'selinux.txt': 'getenforce',
}


def run(adb, args, timeout=45):
    try:
        r = subprocess.run([*adb, *args], capture_output=True, timeout=timeout)
        return {'returncode': r.returncode, 'stdout': r.stdout.decode('utf-8', 'replace'),
                'stderr': r.stderr.decode('utf-8', 'replace')}
    except subprocess.TimeoutExpired:
        return {'returncode': 124, 'stdout': '', 'stderr': 'Timed out'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--adb', default='adb')
    p.add_argument('--serial', help='Required if more than one device is connected')
    p.add_argument('--output', type=Path, default=Path('private/device'))
    p.add_argument('--include-logs', action='store_true', help='Local crash/radio logs may contain personal identifiers. Never upload automatically.')
    a = p.parse_args()
    adb = [a.adb]
    devices = run(adb, ['devices'])
    connected = [line.split()[0] for line in devices['stdout'].splitlines()[1:]
                 if len(line.split()) == 2 and line.split()[1] == 'device']
    if (a.serial and a.serial not in connected) or (not a.serial and len(connected) != 1):
        raise SystemExit('Connect and authorize exactly one device, or select --serial. No data collected.')
    adb += ['-s', a.serial or connected[0]]
    board = run(adb, ['shell', 'getprop ro.board.platform'])['stdout'].strip()
    if board != 'sdm845':
        raise SystemExit(f'Unexpected platform {board!r}; refusing to collect from another device.')
    folder = a.output / datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    folder.mkdir(parents=True, exist_ok=False)
    statuses = {}
    commands = dict(COMMANDS)
    commands['properties.txt'] = '; '.join(f'echo {x}; getprop {x}' for x in PROPS)
    if a.include_logs:
        commands.update({'crash.txt': 'logcat -b crash -d -t 2000',
                         'radio.txt': 'logcat -b radio -d -t 2000',
                         'kernel-log.txt': 'dmesg',
                         'pstore.txt': 'ls -l /sys/fs/pstore; cat /sys/fs/pstore/* 2>/dev/null',
                         'dropbox-index.txt': 'dumpsys dropbox'})
    for name, command in commands.items():
        result = run(adb, ['shell', command])
        statuses[name] = result['returncode']
        (folder / name).write_text(result['stdout'] + '\nSTDERR:\n' + result['stderr'], encoding='utf-8')
    (folder / 'collection.json').write_text(json.dumps({'schema': 1, 'statuses': statuses,
        'hardware_pass': False, 'note': 'Collection success is not hardware acceptance; missing root privileges are not bypassed.'}, indent=2), encoding='utf-8')
    print(f'Local report: {folder}. No flash, reboot, IMEI query or upload performed.')


if __name__ == '__main__':
    main()
