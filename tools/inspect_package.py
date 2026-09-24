#!/usr/bin/env python3
"""Read-only inspection of a polaris fastboot/EDL directory. Never flashes."""
import argparse
import hashlib
import json
import struct
import xml.etree.ElementTree as ET
from pathlib import Path


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def image_info(path):
    size = path.stat().st_size
    with path.open('rb') as f:
        head = f.read(4096)
    result = {'file': path.name, 'stored_bytes': size}
    if len(head) >= 28 and struct.unpack_from('<I', head)[0] == 0xED26FF3A:
        _, major, minor, fh, ch, block, total, chunks, crc = struct.unpack_from('<I4H4I', head)
        if major != 1 or fh < 28 or ch < 12 or not block or block % 4:
            raise ValueError(f'{path.name}: invalid sparse header')
        result.update(format='android-sparse', expanded_bytes=block * total,
                      block_size=block, chunks=chunks)
    elif head.startswith(b'ANDROID!'):
        version = struct.unpack_from('<I', head, 40)[0]
        result.update(format='android-boot', header_version=version)
        if version <= 2:
            result.update(kernel_bytes=struct.unpack_from('<I', head, 8)[0],
                          ramdisk_bytes=struct.unpack_from('<I', head, 16)[0],
                          page_size=struct.unpack_from('<I', head, 36)[0],
                          cmdline=(head[64:576].split(b'\0')[0] + b' ' +
                                   head[608:1632].split(b'\0')[0]).decode('utf-8', 'replace').strip())
    else:
        result.update(format='raw-or-unknown', expanded_bytes=size)
    return result


def inspect(folder):
    images = folder / 'images' if (folder / 'images').is_dir() else folder
    result = {'schema': 1, 'evidence': 'package-only-not-device', 'partitions': [],
              'images': [], 'missing_program_files': [], 'protected_program_entries': []}
    protected = {'modemst1', 'modemst2', 'fsg', 'fsc', 'persist', 'persistbak',
                 'frp', 'devinfo', 'sec', 'PrimaryGPT', 'BackupGPT'}
    for xml in sorted(images.glob('rawprogram*.xml')):
        for e in ET.parse(xml).getroot().iter('program'):
            a = e.attrib
            row = {'label': a['label'], 'lun': int(a['physical_partition_number']),
                   'start_sector': a['start_sector'],
                   'sectors': int(a['num_partition_sectors']),
                   'sector_bytes': int(a['SECTOR_SIZE_IN_BYTES']),
                   'file': a.get('filename', '')}
            row['bytes'] = row['sectors'] * row['sector_bytes']
            result['partitions'].append(row)
            if row['file'] and not (images / row['file']).is_file():
                result['missing_program_files'].append(row['file'])
            if row['file'] and row['label'] in protected:
                result['protected_program_entries'].append(row['label'])
    for path in sorted(images.glob('*.img')):
        info = image_info(path)
        part = next((p for p in result['partitions'] if p['label'] == path.stem), None)
        if part and part['bytes']:
            info['partition_bytes'] = part['bytes']
            info['fits_package_partition'] = info.get('expanded_bytes', info['stored_bytes']) <= part['bytes']
        if path.stem in {'boot', 'vendor', 'modem'}:
            info['sha256'] = sha256(path)
        result['images'].append(info)
    result['xml_sha256'] = {p.name: sha256(p) for p in sorted(images.glob('*.xml'))}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    report = inspect(args.package)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f"Inspected {len(report['images'])} images; no device writes. Report: {args.output}")


if __name__ == '__main__':
    main()
