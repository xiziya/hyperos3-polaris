#!/usr/bin/env python3
"""Reject a resolved kernel configuration with root frameworks or missing hardware."""
import argparse
import re
from pathlib import Path

REQUIRED = ('MACH_XIAOMI_D5X', 'MACH_XIAOMI_SDM845', 'QCA_CLD_WLAN',
            'THERMAL', 'THERMAL_TSENS', 'PSTORE', 'PSTORE_RAM', 'PSTORE_CONSOLE',
            'PSTORE_PMSG', 'ANDROID_BINDER_IPC', 'EXT4_FS', 'F2FS_FS', 'EROFS_FS',
            'BPF', 'BPF_SYSCALL', 'BPF_JIT', 'CGROUP_BPF', 'NET_CLS_BPF', 'NET_ACT_BPF')
ROOT_OPTION = re.compile(r'^CONFIG_(?:KSU(?:_|$)|KERNELSU(?:_|$)|SUKISU(?:_|$)|SUSFS(?:_|$)|KPM(?:_|$)|APATCH(?:_|$))')


def validate(text):
    options = dict(line.split('=', 1) for line in text.splitlines()
                   if line.startswith('CONFIG_') and '=' in line)
    failures = [f'{key}={value}: root framework must be absent or disabled'
                for key, value in options.items() if ROOT_OPTION.match(key) and value != 'n']
    failures += [f'CONFIG_{key}=y is required' for key in REQUIRED if options.get(f'CONFIG_{key}') != 'y']
    return failures


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('config', type=Path)
    a = p.parse_args()
    errors = validate(a.config.read_text())
    if errors:
        raise SystemExit('\n'.join(errors))
    print('Pure polaris configuration passed; build/boot and HAL compatibility remain separate checks.')


if __name__ == '__main__':
    main()
