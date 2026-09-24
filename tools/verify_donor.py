#!/usr/bin/env python3
"""Verify download integrity; a filename MD5 prefix is not a signature check."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('file', type=Path)
    a = p.parse_args()
    config = json.loads((Path(__file__).resolve().parents[1] / 'config/sources.json').read_text())['donor_candidate']
    if Path(str(a.file) + '.aria2').exists():
        raise SystemExit('Incomplete aria2 download; refusing verification.')
    if a.file.stat().st_size != config['bytes']:
        raise SystemExit('Unexpected length')
    md5, sha = hashlib.md5(), hashlib.sha256()
    with a.file.open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
            md5.update(chunk)
            sha.update(chunk)
    if not md5.hexdigest().startswith('f6ef5f9254'):
        raise SystemExit('Filename MD5 prefix mismatch')
    if config['sha256'] and sha.hexdigest() != config['sha256']:
        raise SystemExit('Locked SHA256 mismatch')
    with zipfile.ZipFile(a.file) as z:
        bad = z.testzip()
        if bad:
            raise SystemExit(f'ZIP CRC failure: {bad}')
        metadata = z.read('META-INF/com/android/metadata').decode()
        if 'pre-device=ziyi' not in metadata or 'OS3.0.6.0.VLLCNXM' not in metadata:
            raise SystemExit('OTA metadata does not match the selected China donor')
    report = {'file': a.file.name, 'bytes': a.file.stat().st_size,
              'md5': md5.hexdigest(), 'sha256': sha.hexdigest(),
              'zip_crc': 'pass', 'metadata': metadata, 'ota_signature_verified': False}
    a.file.with_suffix('.verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
