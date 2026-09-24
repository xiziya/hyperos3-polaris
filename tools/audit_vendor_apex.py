#!/usr/bin/env python3
"""Read APEX APK metadata using aapt; never changes manifests, signatures or payloads."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


def inspect(path, target_sdk, aapt):
    result = subprocess.run([aapt, 'dump', 'badging', str(path)], capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ValueError(f'{path.name}: aapt failed: {result.stderr[:1000]}')
    sdk = re.search(r"^sdkVersion:'(\d+)'", result.stdout, re.M)
    package = re.search(r"^package: name='([^']+)'", result.stdout, re.M)
    target = re.search(r"^targetSdkVersion:'(\d+)'", result.stdout, re.M)
    minimum = int(sdk[1]) if sdk else None
    return {'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'package': package[1] if package else None, 'min_sdk': minimum,
            'target_sdk': int(target[1]) if target else None,
            'target_rom_sdk': target_sdk,
            'sdk_gate': 'unknown' if minimum is None else ('blocked' if minimum > target_sdk else 'passed'),
            'native_abi_verified': False, 'signature_verified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--target-sdk', type=int, default=35)
    parser.add_argument('--aapt', default='aapt')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows = [inspect(path, args.target_sdk, args.aapt) for path in sorted(args.directory.glob('*.apex'))]
    if not rows:
        raise SystemExit('No APEX packages found')
    report = {'schema': 1, 'target_android': 15, 'target_sdk': args.target_sdk, 'packages': rows,
              'note': 'A passing SDK gate alone does not prove apexd/native ABI/SELinux compatibility. Do not lower minSdk or strip signatures to bypass this gate.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    blocked = sum(row['sdk_gate'] != 'passed' for row in rows)
    print(f'{len(rows)} vendor APEX packages inspected; {blocked} blocked or unknown for SDK {args.target_sdk}.')
    if blocked:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
