#!/usr/bin/env python3
"""Install hash-checked normalized VINTF files into an isolated vendor copy."""
import argparse
import json
from pathlib import Path
import shutil

from integrate_rom import debugfs, dump, run, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source-image', 'normalized', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    source, normalized, out = args.source_image.resolve(), args.normalized.resolve(), args.output.resolve()
    if not source.is_file():
        raise ValueError('Only an ordinary image file is accepted')
    report = json.loads((normalized / 'report.json').read_text())
    if not report['files'] or not all(r['semantic_roundtrip_equal'] for r in report['files']):
        raise ValueError('Missing semantic roundtrip evidence')
    out.mkdir(parents=True, exist_ok=False)
    scratch = out / 'assembly'
    scratch.mkdir()
    image = out / 'vendor-a15-candidate.img'
    shutil.copyfile(source, image)
    for i, row in enumerate(report['files']):
        relative = Path(row['file'])
        if relative.is_absolute() or '..' in relative.parts or relative.suffix != '.xml':
            raise ValueError('Unsafe VINTF path')
        name = '/etc/vintf/' + relative.as_posix()
        old = scratch / f'old-{i}'
        dump(image, name, old)
        new = normalized / relative
        if sha(old) != row['source_sha256'] or sha(new) != row['normalized_sha256']:
            raise ValueError(f'Source drift: {relative}')
        local = scratch / f'new-{i}'
        shutil.copyfile(new, local)
        debugfs(image, f'rm {name}', True)
        debugfs(image, f'write {local} {name}', True)
        debugfs(image, f'set_inode_field {name} mode 0100644', True)
        for field in ('uid', 'gid', 'atime', 'mtime', 'ctime'):
            debugfs(image, f'set_inode_field {name} {field} 0', True)
        label = scratch / f'label-{i}'
        label.write_bytes(b'u:object_r:vendor_configs_file:s0\0')
        debugfs(image, f'ea_set -f {label} {name} security.selinux', True)
        check = scratch / f'check-{i}'
        dump(image, name, check)
        attr = scratch / f'attr-{i}'
        debugfs(image, f'ea_get -f {attr} {name} security.selinux')
        metadata = debugfs(image, f'stat {name}')
        if sha(check) != sha(new) or attr.read_bytes() != label.read_bytes() or 'Mode:  0644' not in metadata:
            raise ValueError(f'Image verification failed: {relative}')
    (out / 'fsck.txt').write_text(run(['e2fsck', '-fn', image]))
    result = {'schema': 1, 'source_image_sha256': sha(source), 'image_sha256': sha(image),
              'bytes': image.stat().st_size, 'vintf_normalization': report,
              'flashable': False, 'runtime_verified': False, 'fsck_clean': True}
    (out / 'integration-report.json').write_text(json.dumps(result, indent=2) + '\n')
    (out / 'NOT-FLASHABLE.txt').write_text('Intermediate vendor only; complete ROM integration and preflight remain.\n')
    print(json.dumps({'sha256': result['image_sha256'], 'flashable': False}))


if __name__ == '__main__':
    main()
