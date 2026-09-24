#!/usr/bin/env python3
"""Assemble offline boot/vendor candidates; known blockers prevent installer export."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import tarfile

from inspect_recovery import cpio_entries
from prepare_vendor_overlay import patch_post_boot


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def adapt_fstab(text):
    """Change only audited mounts; never add logical/slotselect or autoformat."""
    changed, removed, rows = [], [], []
    for line in text.splitlines():
        fields = line.split()
        if not fields or line.lstrip().startswith('#'):
            rows.append(line)
            continue
        if len(fields) != 5:
            raise ValueError('Unexpected fstab row; manual review required')
        device, mount, fs, options, flags = fields
        if mount == '/mi_product':
            # This donor contains no mi_product partition. Do not mount or write
            # the reference's 2MiB image into its declared 256KiB partition.
            removed.append(mount)
            continue
        if mount in ('/system', '/system_ext', '/product', '/mi_ext'):
            if fs != 'ext4' or device != '/dev/block/by-name/' + mount[1:]:
                raise ValueError(f'Unexpected reference mount: {mount}')
            fs, options = 'erofs', 'ro'
            changed.append(mount)
        # Formatting must be an explicit user operation, never a mount fallback.
        flags = ','.join(f for f in flags.split(',') if f and f != 'formattable')
        rows.append('\t'.join((device, mount, fs, options, flags)))
    if sorted(changed) != ['/mi_ext', '/product', '/system', '/system_ext'] or removed != ['/mi_product']:
        raise ValueError('Missing or duplicate reference mount entries')
    return '\n'.join(rows) + '\n'


def make_cpio(entries):
    data = bytearray()
    names = set()
    for index, (name, mode, payload) in enumerate([*entries, ('TRAILER!!!', 0, b'')], 1):
        if name in names or name.startswith('/') or '..' in Path(name).parts:
            raise ValueError('Unsafe or duplicate ramdisk path')
        names.add(name)
        encoded = name.encode() + b'\0'
        fields = [index, mode, 0, 0, 2 if stat.S_ISDIR(mode) else 1,
                  0, len(payload), 0, 0, 0, 0, len(encoded), 0]
        data += b'070701' + b''.join(f'{f:08x}'.encode() for f in fields) + encoded
        data += b'\0' * (-len(data) % 4)
        data += payload
        data += b'\0' * (-len(data) % 4)
    data += b'\0' * (-len(data) % 512)
    return bytes(data)


def run(command, allowed=(0,)):
    result = subprocess.run(list(map(str, command)), capture_output=True, text=True, timeout=240)
    if result.returncode not in allowed:
        raise RuntimeError(f'{command[0]} failed ({result.returncode}): {result.stderr[-3000:]} {result.stdout[-3000:]}')
    return result.stdout + result.stderr


def debugfs(image, command, write=False):
    return run(['debugfs', *(['-w'] if write else []), '-R', command, image])


def dump(image, name, target):
    # Commands run without a shell; keep debugfs paths unambiguous as well.
    for value in (name, str(target)):
        if not re.fullmatch(r'[/A-Za-z0-9_.+@:-]+', value):
            raise ValueError('Use paths without whitespace or debugfs metacharacters')
    debugfs(image, f'dump {name} {target}')
    if not target.is_file():
        raise ValueError(f'Cannot extract {name}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New Linux path, no spaces')
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    lock = json.loads((project / 'config/integration-sources.json').read_text())
    inputs = {k: Path(v).resolve() for k, v in json.loads(args.inputs.read_text()).items()}
    out = args.output.resolve()
    if out.exists():
        raise SystemExit('Use a new output directory; never mutate source images')
    for key, expected in lock['files'].items():
        if sha(inputs[key]) != expected['sha256']:
            raise ValueError(f'Locked source mismatch: {key}')
    out.mkdir(parents=True)
    scratch = out / 'assembly'
    scratch.mkdir()
    vendor = out / 'vendor-candidate.img'
    shutil.copyfile(inputs['vendor_raw'], vendor)
    # Repair only this isolated copy. Original image has an inode-bitmap padding
    # error. Preserve repair output and require a clean read-only check below.
    (out / 'vendor-fsck-repair.txt').write_text(run(['e2fsck', '-fy', vendor], allowed=(0, 1)))
    fstab_source = scratch / 'fstab.source'
    dump(vendor, '/etc/fstab.qcom', fstab_source)
    fstab = scratch / 'fstab.qcom'
    fstab.write_text(adapt_fstab(fstab_source.read_text()))
    postboot = scratch / 'postboot.source'
    dump(vendor, '/bin/init.qcom.post_boot.sh', postboot)
    node_lock = json.loads((project / 'config/node-contracts.json').read_text())
    if sha(postboot) != node_lock['post_boot_source_sha256']:
        raise ValueError('post-boot source differs from audited input')
    patched_postboot = scratch / 'init.qcom.post_boot.sh'
    patched_postboot.write_text(patch_post_boot(postboot.read_text()))
    contexts = scratch / 'vendor_file_contexts'
    dump(vendor, '/etc/selinux/vendor_file_contexts', contexts)
    contexts.write_text(contexts.read_text().rstrip() + '\n' +
                        (project / 'device/polaris/lights/file_contexts').read_text())
    policy = scratch / 'vendor_sepolicy.cil'
    dump(vendor, '/etc/selinux/vendor_sepolicy.cil', policy)
    policy_text = policy.read_text()
    permissive_domains = re.findall(r'^\(typepermissive ([^ )]+)\)$', policy_text, re.M)
    policy.write_text(re.sub(r'^\(typepermissive [^ )]+\)\n?', '', policy_text, flags=re.M))

    replacements = [
        ('/etc/fstab.qcom', fstab, 0o644, 'vendor_configs_file'),
        ('/bin/init.qcom.post_boot.sh', patched_postboot, 0o755, 'vendor_qti_init_shell_exec'),
        ('/etc/selinux/vendor_file_contexts', contexts, 0o644, 'vendor_configs_file'),
        ('/etc/selinux/vendor_sepolicy.cil', policy, 0o644, 'vendor_configs_file'),
        ('/etc/init/init.polaris.nodes.rc', project / 'device/polaris/vendor-overlay/etc/init/init.polaris.nodes.rc', 0o644, 'vendor_configs_file'),
        ('/bin/hw/android.hardware.light-service.polaris', inputs['lights'], 0o755, 'hal_light_default_exec'),
        ('/etc/init/android.hardware.light-service.polaris.rc', project / 'device/polaris/lights/android.hardware.light-service.polaris.rc', 0o644, 'vendor_configs_file'),
        ('/etc/vintf/manifest/android.hardware.light-service.polaris.xml', project / 'device/polaris/lights/android.hardware.light-service.polaris.xml', 0o644, 'vendor_configs_file')]
    removals = ['/apex/com.qualcomm.hardware.lights.rust.apex',
                '/etc/vintf/manifest/vendor.qti.hardware.lights.service.rust.xml']
    # Refuse silently changing a different vendor layout.
    for i, name in enumerate(removals):
        dumped = scratch / f'removed-{i}'
        dump(vendor, name, dumped)
        debugfs(vendor, f'rm {name}', write=True)
    changed = []
    for index, (name, source, mode, label) in enumerate(replacements):
        local = scratch / f'input-{index}'
        shutil.copyfile(source, local)
        context = scratch / f'context-{index}'
        expected_context = f'u:object_r:{label}:s0'.encode() + b'\0'
        context.write_bytes(expected_context)
        debugfs(vendor, f'rm {name}', write=True)  # may not exist for new files
        debugfs(vendor, f'write {local} {name}', write=True)
        debugfs(vendor, f'set_inode_field {name} mode 0{stat.S_IFREG | mode:o}', write=True)
        for field in ('uid', 'gid', 'mtime', 'atime', 'ctime'):
            debugfs(vendor, f'set_inode_field {name} {field} 0', write=True)
        debugfs(vendor, f'ea_set -f {context} {name} security.selinux', write=True)
        verify = scratch / f'verify-{index}'
        dump(vendor, name, verify)
        if sha(verify) != sha(local):
            raise ValueError(f'Image write verification failed: {name}')
        meta = debugfs(vendor, f'stat {name}')
        if f'Mode:  0{mode:o}' not in meta or not re.search(r'User:\s+0\s+Group:\s+0', meta):
            raise ValueError(f'Image ownership/mode verification failed: {name}')
        attr = scratch / f'attr-{index}'
        debugfs(vendor, f'ea_get -f {attr} {name} security.selinux')
        if attr.read_bytes() != expected_context:
            raise ValueError(f'Image SELinux xattr verification failed: {name}')
        changed.append({'path': name, 'sha256': sha(local), 'mode': oct(mode), 'selinux': expected_context[:-1].decode()})
    for name in removals:
        if 'File not found' not in debugfs(vendor, f'stat {name}'):
            raise ValueError(f'Obsolete provider remains: {name}')
    (out / 'vendor-fsck-final.txt').write_text(run(['e2fsck', '-fn', vendor]))

    # Build a minimal ramdisk with generic A15 init only; no donor driver/DTB,
    # ziyi properties, root framework or old SDK36 init is copied.
    dirs = ['debug_ramdisk', 'dev', 'metadata', 'mnt', 'proc', 'second_stage_resources',
            'sys', 'system', 'system/etc', 'vendor', 'product', 'system_ext', 'mi_ext']
    entries = [(d, stat.S_IFDIR | 0o755, b'') for d in dirs]
    entries += [('init', stat.S_IFREG | 0o750, inputs['first_stage_init'].read_bytes()),
                ('system/etc/fstab.qcom', stat.S_IFREG | 0o644, fstab.read_bytes())]
    ramdisk = scratch / 'ramdisk.cpio.gz'
    ramdisk.write_bytes(gzip.compress(make_cpio(entries), mtime=0))
    mkboot = scratch / 'mkbootimg'
    mkboot.mkdir()
    with tarfile.open(inputs['mkbootimg_archive']) as tar:
        tar.extractall(mkboot, members=[m for m in tar.getmembers() if m.isfile() or m.isdir()], filter='data')
    ref = inputs['reference_boot'].read_bytes()
    kernel_addr, ramdisk_addr = struct.unpack_from('<I', ref, 12)[0], struct.unpack_from('<I', ref, 20)[0]
    page, version = struct.unpack_from('<II', ref, 36)
    if ref[:8] != b'ANDROID!' or version != 1 or page != 4096 or struct.unpack_from('<I', ref, 24)[0]:
        raise ValueError('Unexpected reference boot header')
    cmdline = (ref[64:576] + ref[608:1632]).split(b'\0')[0].decode()
    # Keep audited boot parameters for now. The kernel also embeds
    # cgroup_disable=pressure; global PSI remains enabled. Changing only this
    # header cannot override the built-in command line or establish a power win.
    if any(x in cmdline for x in ('permissive', 'androidboot.verifiedbootstate=', 'androidboot.flash.locked=')):
        raise ValueError('Unreviewed security override in reference cmdline')
    boot = out / 'boot-candidate.img'
    command = ['python3', mkboot / 'mkbootimg.py', '--kernel', inputs['kernel'], '--ramdisk', ramdisk,
               '--header_version', '1', '--pagesize', str(page), '--base', '0',
               '--kernel_offset', hex(kernel_addr), '--ramdisk_offset', hex(ramdisk_addr),
               '--tags_offset', hex(struct.unpack_from('<I', ref, 32)[0]),
               '--cmdline', cmdline, '--os_version', '15.0.0', '--os_patch_level', '2026-08', '-o', boot]
    run(command)
    built = boot.read_bytes()
    ksize, rsize = struct.unpack_from('<I', built, 8)[0], struct.unpack_from('<I', built, 16)[0]
    ramstart = page + (ksize + page - 1) // page * page
    if hashlib.sha256(built[page:page + ksize]).hexdigest() != sha(inputs['kernel']):
        raise ValueError('Boot kernel round-trip failed')
    unpacked = {name: data for name, mode, data in cpio_entries(gzip.decompress(built[ramstart:ramstart + rsize]))}
    if unpacked['init'] != inputs['first_stage_init'].read_bytes() or unpacked['system/etc/fstab.qcom'] != fstab.read_bytes():
        raise ValueError('Boot ramdisk round-trip failed')
    if len(built) > 64 * 1024**2:
        raise ValueError('Candidate exceeds reference boot size')
    artifacts = [{'name': x.name, 'bytes': x.stat().st_size, 'sha256': sha(x)} for x in (boot, vendor)]
    report = {'schema': 1, 'phase': 'offline-image-assembly', 'flashable': False,
              'source_lock_sha256': sha(project / 'config/integration-sources.json'),
              'images': artifacts, 'vendor_replacements_verified': changed, 'vendor_removed': removals,
              'removed_permissive_domains': permissive_domains, 'vendor_fsck_clean': True,
              'boot_component_roundtrip_passed': True, 'ramdisk_vendor_fstab_identical': True,
              'boot_cmdline': cmdline, 'tested_on_device': False,
              'blockers': ['vendor SDK36 APEX services remaining', 'vendor/platform SELinux compatibility',
                           'Wi-Fi/Keystore Binder ABI', 'actual partition sizes and boot-chain validation',
                           'data encryption and recovery rollback'],
              'note': 'No installer, EDL rawprogram or device write is produced. System donor images remain source inputs pending full integration.'}
    (out / 'integration-report.json').write_text(json.dumps(report, indent=2) + '\n')
    (out / 'NOT-FLASHABLE.txt').write_text('工程中间镜像，已知有启动阻断，禁止作为测试刷机包使用。\n见 integration-report.json。\n', encoding='utf-8')
    print(json.dumps({'output': str(out), 'images': artifacts, 'flashable': False}, indent=2))


if __name__ == '__main__':
    main()
