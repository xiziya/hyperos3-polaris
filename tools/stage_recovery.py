#!/usr/bin/env python3
"""Stage our recovery tree with explicitly selected pinned upstream HAL files."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('android', type=Path)
    parser.add_argument('kernel', type=Path)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    common = args.android / 'device/xiaomi/sdm845-common'
    lock = json.loads((project / 'config/recovery-sources.json').read_text())
    actual = subprocess.check_output(['git', '-C', str(common), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != lock['common']['commit']:
        raise SystemExit('Recovery hardware source does not match lock')
    destination = args.android / 'device/xiaomi/polaris'
    if destination.exists():
        raise SystemExit('Refusing to overwrite an existing polaris tree')
    if not args.kernel.is_file():
        raise SystemExit('Built project kernel required')
    shutil.copytree(project / 'recovery/polaris', destination)
    root = destination / 'recovery/root'
    upstream = common / 'recovery/root'
    shutil.copytree(upstream / 'vendor/lib64', root / 'vendor/lib64')
    # No factory/format/dynamic-conversion scripts from the generic device tree.
    (root / 'system/bin').mkdir(parents=True)
    for name in ('qseecomd', 'android.hardware.keymaster@4.0-service-qti',
                 'android.hardware.gatekeeper@1.0-service-qti'):
        shutil.copy2(upstream / 'system/bin' / name, root / 'system/bin' / name)
    shutil.copy2(common / 'recovery/kernel_419/init.recovery.usb.rc', root / 'init.recovery.usb.rc')
    (destination / 'prebuilt').mkdir()
    shutil.copy2(args.kernel, destination / 'prebuilt/Image.gz-dtb')
    print('Staged static polaris recovery. Hardware and decryption remain untested.')


if __name__ == '__main__':
    main()
