#!/usr/bin/env python3
"""Read the polaris layout through an already authorized su; never changes a device."""
import argparse
import datetime
import json
from pathlib import Path
import shlex
import subprocess

PARTITIONS = ('boot', 'recovery', 'vendor', 'system', 'system_ext', 'product',
              'mi_ext', 'mi_product', 'logdump', 'userdata', 'vbmeta')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    adb = [args.adb]
    devices = subprocess.check_output([*adb, 'devices'], text=True)
    connected = [line.split()[0] for line in devices.splitlines()[1:]
                 if len(line.split()) == 2 and line.split()[1] == 'device']
    if len(connected) != 1:
        raise SystemExit('Exactly one authorized device required')
    adb += ['-s', connected[0]]

    def shell(command, root=False):
        if root:
            command = 'su -c ' + shlex.quote(command)
        return subprocess.run([*adb, 'shell', command], capture_output=True, text=True, timeout=45)

    if shell('getprop ro.product.device').stdout.strip() != 'polaris':
        raise SystemExit('Unexpected device')
    if not shell('id', True).stdout.startswith('uid=0('):
        raise SystemExit('Existing su authorization required; no elevation attempted')
    folder = args.output / datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    folder.mkdir(parents=True, exist_ok=False)
    rows = []
    for name in PARTITIONS:
        command = (f'p=/dev/block/by-name/{name}; b=$(readlink -f "$p"); '
                   'echo "$b"; blockdev --getsize64 "$p"; '
                   'cat "/sys/class/block/${b##*/}/start"')
        r = shell(command, True)
        lines = r.stdout.splitlines()
        if r.returncode or len(lines) != 3:
            raise SystemExit(f'Cannot read complete geometry for {name}: {r.stderr}')
        rows.append({'name': name, 'block': lines[0], 'bytes': int(lines[1]),
                     'start_sector_512': int(lines[2])})
    report = {'schema': 1, 'device': 'polaris', 'evidence': 'live-authorized-root-readonly',
              'partitions': rows, 'hardware_acceptance': False}
    (folder / 'layout.json').write_text(json.dumps(report, indent=2) + '\n')
    commands = {
        'nodes.txt': 'for p in /sys/class/backlight/panel0-backlight /sys/class/leds/white; do readlink -f "$p"; ls -ldZ "$p" "$p/"; ls -lZ "$p/brightness" "$p/max_brightness" "$p/blink" 2>/dev/null; cat "$p/max_brightness"; done; ls -lZ /sys/module/wlan/parameters/fwpath /dev/wlan /dev/kgsl-3d0 /dev/dri/card0; cat /sys/module/wlan/parameters/fwpath',
        'fstab.txt': 'cat /vendor/etc/fstab.qcom',
        'mounts.txt': 'cat /proc/mounts',
        'cmdline-private.txt': 'cat /proc/cmdline',
        'boot-state.txt': 'getprop ro.boot.verifiedbootstate; getprop ro.boot.vbmeta.device_state; getprop ro.boot.flash.locked; getprop ro.crypto.state; getprop ro.crypto.type; getenforce',
        'suspend.txt': 'cat /sys/module/lpm_levels/parameters/sleep_disabled; cat /sys/power/mem_sleep; cat /sys/kernel/debug/suspend_stats 2>/dev/null',
    }
    for name, command in commands.items():
        r = shell(command, True)
        (folder / name).write_text(r.stdout + '\nSTDERR:\n' + r.stderr)
    print(f'Layout and nodes collected locally: {folder}. No device writes or reboot.')


if __name__ == '__main__':
    main()
