#!/usr/bin/env python3
"""Check split SELinux inputs before attempting an Android platform/vendor mix."""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path


def audit(roots, compiler=None):
    vendor = roots['vendor']
    version = (vendor / 'plat_sepolicy_vers.txt').read_text().strip()
    if not re.fullmatch(r'\d+(?:\.\d+)?', version):
        raise ValueError('Invalid vendor policy version')
    report = {'schema': 1, 'vendor_policy_version': version, 'inputs': [],
              'missing': [], 'precompiled_hash_matches': {}, 'compile_passed': False,
              'runtime_enforcing_verified': False}
    inputs = []
    for name in ('system', 'system_ext', 'product'):
        stem = 'plat' if name == 'system' else name
        directory = roots[name]
        required = [directory / f'{stem}_sepolicy.cil', directory / 'mapping' / f'{version}.cil']
        compat = directory / 'mapping' / f'{version}.compat.cil'
        if compat.is_file():
            required.append(compat)
        inputs += required
        current = directory / f'{stem}_sepolicy_and_mapping.sha256'
        previous = vendor / f'precompiled_sepolicy.{stem}_sepolicy_and_mapping.sha256'
        report['precompiled_hash_matches'][name] = (current.is_file() and previous.is_file()
            and current.read_text().strip() == previous.read_text().strip())
    inputs += [vendor / 'plat_pub_versioned.cil', vendor / 'vendor_sepolicy.cil']
    for path in inputs:
        role = next(name for name, directory in roots.items() if path.is_relative_to(directory))
        label = f'{role}/{path.relative_to(roots[role]).as_posix()}'
        if not path.is_file():
            report['missing'].append(label)
            continue
        data = path.read_bytes()
        report['inputs'].append({'file': label, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    report['precompiled_usable_by_hash'] = ((vendor / 'precompiled_sepolicy').is_file()
        and all(report['precompiled_hash_matches'].values()))
    if report['missing']:
        report['compile_status'] = 'blocked-missing-inputs'
    elif compiler:
        # Preserve neverallow checks; never use -N or a permissive fallback.
        with tempfile.TemporaryDirectory(prefix='polaris-sepolicy-') as tmp:
            command = [compiler, '-m', '-M', 'true', '-G', '-c', '30',
                       '-o', str(Path(tmp) / 'policy'), '-f', str(Path(tmp) / 'contexts'),
                       *map(str, inputs)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=120)
            report['compile_passed'] = result.returncode == 0
            report['compile_status'] = 'passed' if result.returncode == 0 else 'failed'
            diagnostics = result.stderr[-16000:]
            for name, directory in roots.items():
                diagnostics = diagnostics.replace(str(directory), name)
            report['compiler_diagnostics'] = diagnostics
    else:
        report['compile_status'] = 'not-run'
    report['note'] = 'Preflight/host compilation does not prove runtime permissions. Do not rename policy versions or bypass enforcing.'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('system', 'system_ext', 'product', 'vendor'):
        parser.add_argument('--' + name.replace('_', '-'), type=Path, required=True,
                            help='Extracted etc/selinux directory')
    parser.add_argument('--secilc', help='Optional compiler executable; runs only with complete inputs')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit({name: getattr(args, name).resolve() for name in ('system', 'system_ext', 'product', 'vendor')}, args.secilc)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(report['compile_status'])
    if not report['compile_passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
