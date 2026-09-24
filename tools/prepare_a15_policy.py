#!/usr/bin/env python3
"""Apply reviewed permission reductions to a locked A15 vendor policy and compile."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def prepare(source, destination, config):
    destination.mkdir(parents=True, exist_ok=False)
    changes = []
    for name, expected in config['sources'].items():
        data = (source / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f'Policy source mismatch: {name}')
        text = data.decode()
        for patch in config['reductions']:
            if patch['file'] != name:
                continue
            old, new = patch['old'], patch['new']
            # Some userdebug macros emit the identical su rule more than once.
            count = text.splitlines().count(old)
            if count != patch['count']:
                raise ValueError(f'Policy rule count changed: {name}: {old}')
            text = text.replace(old + '\n', new + '\n' if new else '')
            changes.append({'file': name, 'count': count, 'reason': patch['reason']})
        (destination / name).write_text(text)
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vendor', type=Path, required=True)
    parser.add_argument('--system', type=Path, required=True)
    parser.add_argument('--system-ext', type=Path, required=True)
    parser.add_argument('--product', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    config = json.loads((project / 'config/a15-policy-reductions.json').read_text())
    changes = prepare(args.vendor, args.output, config)
    inputs = []
    for root, stem in ((args.system, 'plat'), (args.system_ext, 'system_ext'), (args.product, 'product')):
        inputs += [root / f'{stem}_sepolicy.cil', root / 'mapping/202404.cil']
        compat = root / 'mapping/202404.compat.cil'
        if compat.exists():
            inputs.append(compat)
    inputs += [args.output / 'plat_pub_versioned.cil', args.output / 'vendor_sepolicy.cil']
    command = ['secilc', '-m', '-M', 'true', '-G', '-c', '30', '-o', str(args.output / 'policy'),
               '-f', str(args.output / 'compiled-contexts'), *map(str, inputs)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    report = {'schema': 1, 'compile_passed': result.returncode == 0, 'neverallow_checks_enabled': True,
              'policy_version': '202404', 'permission_reductions': changes,
              'runtime_enforcing_verified': False, 'diagnostics': result.stderr,
              'input_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    if result.returncode:
        raise SystemExit(result.stderr)
    print('A15 split policy compiled with neverallow checks; runtime not verified.')


if __name__ == '__main__':
    main()
