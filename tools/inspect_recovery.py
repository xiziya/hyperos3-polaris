#!/usr/bin/env python3
"""Audit a legacy Android recovery image without extracting or executing its files."""
import argparse
import gzip
import hashlib
import io
import json
import re
import stat
import struct
from pathlib import Path


def unpack_gzip(data, limit):
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
        result = stream.read(limit + 1)
    if len(result) > limit:
        raise ValueError('Decompressed input exceeds inspection limit')
    return result


def cpio_entries(data):
    """Read newc/crc entries in memory; never follow links or write archive paths."""
    pos = 0
    while pos + 110 <= len(data):
        header = data[pos:pos + 110]
        if header[:6] not in (b'070701', b'070702'):
            raise ValueError('Unsupported or malformed CPIO header')
        fields = [int(header[6 + i * 8:14 + i * 8], 16) for i in range(13)]
        mode, size, namesize, checksum = fields[1], fields[6], fields[11], fields[12]
        end_name = pos + 110 + namesize
        if not 1 <= namesize <= 4096 or end_name > len(data) or data[end_name - 1] != 0:
            raise ValueError('Invalid CPIO name length or terminator')
        name = data[pos + 110:end_name - 1].decode('utf-8')
        start = (end_name + 3) & ~3
        end = start + size
        if end > len(data):
            raise ValueError('Truncated CPIO file')
        payload = data[start:end]
        if header[:6] == b'070702' and sum(payload) & 0xffffffff != checksum:
            raise ValueError('CPIO checksum mismatch')
        if name == 'TRAILER!!!':
            return
        yield name.removeprefix('./'), mode, payload
        pos = (end + 3) & ~3
    raise ValueError('CPIO trailer missing')


def fstab_rows(text):
    rows = []
    for line in text.splitlines():
        parts = line.split('#', 1)[0].split()
        if len(parts) < 3:
            continue
        if parts[0].startswith('/dev/') or not parts[1] in ('ext4', 'erofs', 'f2fs', 'emmc', 'vfat', 'auto'):
            device, mount, fs = parts[:3]
        else:
            mount, fs, device = parts[:3]
        rows.append({'device': device, 'mount': mount, 'fs': fs,
                     'options': ' '.join(parts[3:])})
    return rows


def inspect(path):
    size = path.stat().st_size
    with path.open('rb') as stream:
        header = stream.read(4096)
        if len(header) < 1660 or header[:8] != b'ANDROID!':
            raise ValueError('Not a legacy Android boot image')
        kernel_size = struct.unpack_from('<I', header, 8)[0]
        ramdisk_size = struct.unpack_from('<I', header, 16)[0]
        page, version = struct.unpack_from('<II', header, 36)
        if version > 2 or page not in (2048, 4096, 8192, 16384):
            raise ValueError('Only legacy v0-v2 headers with known page sizes supported')
        ramdisk_offset = page + (kernel_size + page - 1) // page * page
        if not kernel_size or not ramdisk_size or ramdisk_offset + ramdisk_size > size:
            raise ValueError('Image components outside file')
        if kernel_size > 128 * 1024**2 or ramdisk_size > 128 * 1024**2:
            raise ValueError('Compressed component exceeds inspection limit')
        stream.seek(page)
        kernel = stream.read(kernel_size)
        stream.seek(ramdisk_offset)
        ramdisk = stream.read(ramdisk_size)
    compression = 'gzip' if ramdisk.startswith(b'\x1f\x8b') else 'raw-newc'
    if compression == 'gzip':
        ramdisk = unpack_gzip(ramdisk, 512 * 1024**2)
    report = {'schema': 1, 'file': path.name, 'sha256': '', 'bytes': size,
              'boot_header': version, 'page_size': page, 'ramdisk_compression': compression,
              'target_android': 15, 'fstabs': {}, 'properties': {}, 'script_references': [],
              'filesystem_helpers': [],
              'boot_tested': False, 'mount_tested': False, 'decrypt_tested': False,
              'note': 'Offline evidence only. Properties and kernel version strings may be spoofed.'}
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024**2), b''):
            digest.update(block)
    report['sha256'] = digest.hexdigest()
    refs = re.compile(r'recovery-(?:non-)?dynamic\.fstab|twrp-(?:non-)?dynamic\.flags|by-name/(?:cust|product|system_ext)|fileencryption|metadata_encryption')
    for name, mode, payload in cpio_entries(ramdisk):
        if 'erofs' in name.lower() or name.endswith('.ko'):
            report['filesystem_helpers'].append(name)
        if not stat.S_ISREG(mode):
            continue
        if 'fstab' in name or name.endswith('.flags'):
            text = payload.decode('utf-8', 'replace')
            report['fstabs'][name] = {'sha256': hashlib.sha256(payload).hexdigest(), 'rows': fstab_rows(text)}
        if name.endswith(('.prop', 'fox.cfg')):
            report['properties'][name] = dict(line.split('=', 1) for line in payload.decode('utf-8', 'replace').splitlines()
                                               if line.startswith(('ro.', 'orangefox.')) and '=' in line)
        if name.endswith(('.sh', '.rc')):
            for number, line in enumerate(payload.decode('utf-8', 'replace').splitlines(), 1):
                if refs.search(line):
                    report['script_references'].append({'file': name, 'line': number, 'text': line.strip()})
    # A gzip kernel can have appended DTBs: only decompress its first gzip member.
    if kernel.startswith(b'\x1f\x8b'):
        import zlib
        decoder = zlib.decompressobj(31)
        kernel = decoder.decompress(kernel, 128 * 1024**2 + 1)
        if len(kernel) > 128 * 1024**2 or not decoder.eof:
            raise ValueError('Kernel decompression exceeds limit or is truncated')
    start, end = kernel.find(b'IKCFG_ST'), kernel.find(b'IKCFG_ED')
    report['kernel_config_available'] = start >= 0 and end > start
    if report['kernel_config_available']:
        config = unpack_gzip(kernel[start + 8:end], 4 * 1024**2).decode()
        report['kernel_config_sha256'] = hashlib.sha256(config.encode()).hexdigest()
        report['kernel_relevant_options'] = [line for line in config.splitlines()
            if re.match(r'(?:# )?CONFIG_(?:KSU|KERNELSU|SUKISU|SUSFS|KPM|APATCH|EROFS|EXT4|F2FS|FS_ENCRYPTION)', line)]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = inspect(args.image)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'Recovery inspected: {report["sha256"]}. Android 15 compatibility remains untested.')


if __name__ == '__main__':
    main()
