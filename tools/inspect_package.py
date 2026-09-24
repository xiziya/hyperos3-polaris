#!/usr/bin/env python3
"""Read-only inspection of a polaris fastboot/EDL directory. Never flashes."""
import argparse
import hashlib
import json
import struct
import xml.etree.ElementTree as ET
import zlib
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


def gpt_info(path, sector=4096):
    """Read package GPT geometry without exporting disk or partition GUIDs."""
    data = path.read_bytes()
    header = data[sector:sector + 512]
    if header[:8] != b'EFI PART':
        raise ValueError(f'{path.name}: GPT signature missing')
    length, checksum = struct.unpack_from('<II', header, 12)
    if not 92 <= length <= len(header):
        raise ValueError('Invalid GPT header size')
    checked = bytearray(header[:length])
    checked[16:20] = b'\0' * 4
    if zlib.crc32(checked) != checksum:
        raise ValueError(f'{path.name}: GPT header checksum mismatch')
    lba, count, entry_size, crc = struct.unpack_from('<QIII', header, 72)
    if entry_size < 128 or count > 4096:
        raise ValueError('Invalid GPT entry layout')
    entries = data[lba * sector:lba * sector + count * entry_size]
    if len(entries) != count * entry_size or zlib.crc32(entries) != crc:
        raise ValueError(f'{path.name}: GPT entry checksum mismatch')
    result = []
    for i in range(count):
        e = entries[i * entry_size:(i + 1) * entry_size]
        if e[:16] == b'\0' * 16:
            continue
        first, last = struct.unpack_from('<QQ', e, 32)
        result.append({'label': e[56:128].decode('utf-16le').split('\0')[0],
                       'first_lba': first, 'last_lba': last,
                       'bytes': (last - first + 1) * sector if last >= first else None,
                       'extent_valid_without_edl_patching': last >= first})
    return {'file': path.name, 'crc_valid': True, 'partitions': result}


def inspect(folder):
    images = folder / 'images' if (folder / 'images').is_dir() else folder
    result = {'schema': 1, 'evidence': 'package-only-not-device', 'partitions': [],
              'images': [], 'missing_program_files': [], 'protected_program_entries': []}
    result['gpt'] = [gpt_info(path) for path in sorted(images.glob('gpt_main*.bin'))]
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
