#!/usr/bin/env python3
"""Create a new installer revision without recompressing unchanged images."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'report', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    root = Path(__file__).resolve().parents[1]
    if output.exists():
        raise ValueError('Output must be a new file')
    report = json.loads(args.report.read_text())
    if source.stat().st_size != report['package']['bytes'] or sha(source) != report['package']['sha256']:
        raise ValueError('Source differs from verified package')
    print('Source package hash verified', flush=True)
    installer_name = 'META-INF/com/google/android/update-binary'
    installer = (root / 'device/polaris/installer/update-binary').read_bytes()
    with zipfile.ZipFile(source) as archive:
        names = archive.namelist()
        manifest = json.loads(archive.read('build-manifest.json'))
    if manifest['images'] != report['images']:
        raise ValueError('Source image manifest mismatch')
    manifest['installer_revision'] = 'r3-active-recovery-check'
    manifest['installer_sha256'] = hashlib.sha256(installer).hexdigest()
    replacements = {
        installer_name: installer,
        'build-manifest.json': (json.dumps(manifest, indent=2) + '\n').encode(),
        'README-FIRST-TEST.md': (root / 'docs/first-device-test.md').read_bytes(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='polaris-revision-') as folder:
        stage = Path(folder)
        for name, data in replacements.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (stage / installer_name).chmod(0o755)
        # Explicit scratch location: source drive may not fit another 5.6GB ZIP.
        subprocess.run(['zip', '-q', '-b', str(output.parent), str(source),
                        '--out', str(output), *replacements], cwd=stage, check=True)
    with zipfile.ZipFile(output) as archive:
        if len(archive.namelist()) != len(set(names)) or set(archive.namelist()) != set(names):
            raise ValueError('Duplicate or unexpected ZIP members')
        for name, data in replacements.items():
            if archive.read(name) != data:
                raise ValueError('Replacement mismatch: ' + name)
        for item in manifest['images']:
            name = 'images/' + item['name']
            if archive.getinfo(name).file_size != item['bytes']:
                raise ValueError('Image size mismatch: ' + name)
            with archive.open(name) as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != item['sha256']:
                    raise ValueError('Image hash mismatch: ' + name)
            print('Verified', name, flush=True)
    manifest['supersedes_package_sha256'] = report['package']['sha256']
    manifest['package'] = dict(file=output.name, bytes=output.stat().st_size,
                               sha256=sha(output), zip_image_roundtrip=True)
    output.with_suffix('.json').write_text(json.dumps(manifest, indent=2) + '\n')
    output.with_suffix('.sha256').write_text(manifest['package']['sha256'] + '  ' + output.name + '\n')
    print(json.dumps(manifest['package']), flush=True)


if __name__ == '__main__':
    main()
