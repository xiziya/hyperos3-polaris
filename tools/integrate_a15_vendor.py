#!/usr/bin/env python3
"""Create an A15 vendor candidate for the measured static polaris layout."""
import argparse
import json
from pathlib import Path
import re
import shutil
import stat

from integrate_rom import debugfs, dump, run, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    lock = json.loads((project / 'config/a15-vendor-sources.json').read_text())
    inputs = {k: Path(v).resolve() for k, v in json.loads(args.inputs.read_text()).items()}
    for key, spec in lock['files'].items():
        if sha(inputs[key]) != spec['sha256']:
            raise ValueError(f'Source mismatch: {key}')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    scratch = out / 'assembly'
    scratch.mkdir()
    image = out / 'vendor-a15-candidate.img'
    shutil.copyfile(inputs['vendor'], image)
    (out / 'fsck-source.txt').write_text(run(['e2fsck', '-fn', image]))
    # Give ODM and development additions room without altering device geometry.
    with image.open('r+b') as stream:
        stream.truncate(768 * 1024**2)
    (out / 'resize.txt').write_text(run(['resize2fs', image]))
    changed = []
    index = 0

    def install(name, source, mode=0o644, label='vendor_configs_file'):
        nonlocal index
        index += 1
        local = scratch / f'file-{index}'
        shutil.copyfile(source, local)
        debugfs(image, f'rm {name}', True)
        debugfs(image, f'write {local} {name}', True)
        debugfs(image, f'set_inode_field {name} mode 0{stat.S_IFREG | mode:o}', True)
        for field in ('uid', 'gid', 'atime', 'ctime', 'mtime'):
            debugfs(image, f'set_inode_field {name} {field} 0', True)
        context = scratch / f'label-{index}'
        context.write_bytes(f'u:object_r:{label}:s0'.encode() + b'\0')
        debugfs(image, f'ea_set -f {context} {name} security.selinux', True)
        readback = scratch / f'readback-{index}'
        dump(image, name, readback)
        metadata = debugfs(image, f'stat {name}')
        if sha(readback) != sha(local) or f'Mode:  0{mode:o}' not in metadata:
            raise ValueError(f'Failed readback: {name}')
        if not re.search(r'User:\s+0\s+Group:\s+0', metadata):
            raise ValueError(f'Wrong owner: {name}')
        attr = scratch / f'attr-{index}'
        debugfs(image, f'ea_get -f {attr} {name} security.selinux')
        if attr.read_bytes() != context.read_bytes():
            raise ValueError(f'Wrong xattr: {name}')
        changed.append({'path': name, 'sha256': sha(local), 'mode': oct(mode), 'label': label})

    def directory(name, label):
        debugfs(image, f'mkdir {name}', True)
        debugfs(image, f'set_inode_field {name} mode 040755', True)
        for field in ('uid', 'gid'):
            debugfs(image, f'set_inode_field {name} {field} 0', True)
        context = scratch / 'dir-label'
        context.write_bytes(f'u:object_r:{label}:s0'.encode() + b'\0')
        debugfs(image, f'ea_set -f {context} {name} security.selinux', True)

    # Donor /odm/etc is a symlink to /vendor/odm/etc. Replace Lineage's
    # /vendor/odm -> /odm symlink with a directory, avoiding a mount/loop.
    debugfs(image, 'rm /odm', True)
    directory('/odm', 'vendor_file')
    directory('/odm/etc', 'vendor_configs_file')
    directory('/odm/etc/selinux', 'vendor_configs_file')
    odm_names = ('build.prop', 'fs_config_files', 'fs_config_dirs', 'group', 'passwd', 'NOTICE.xml.gz')
    odm_policy = ('odm_sepolicy.cil', 'odm_file_contexts', 'odm_hwservice_contexts',
                  'odm_service_contexts', 'odm_property_contexts', 'odm_mac_permissions.xml', 'odm_seapp_contexts')
    for name in (*odm_names, *('selinux/' + n for n in odm_policy)):
        source = scratch / ('odm-' + name.replace('/', '_'))
        dump(inputs['odm'], '/etc/' + name, source)
        if name == 'selinux/odm_sepolicy.cil' and source.read_text().strip():
            raise ValueError('Nonempty ODM policy requires separate compilation')
        install('/odm/etc/' + name, source)
    # Do not retain Lineage's precompiled policy or source hashes after mixing
    # platforms. Android init will compile the checked split inputs at boot.
    for name in ('plat_pub_versioned.cil', 'vendor_sepolicy.cil'):
        install('/etc/selinux/' + name, inputs[name])
    install('/etc/fstab.qcom', inputs['fstab'])
    install('/etc/init/init.polaris.nodes.rc', project / 'device/polaris/vendor-overlay/etc/init/init.polaris.nodes.rc')
    for name in ('/bin/hw/android.hardware.light-service.lineage',
                 '/etc/init/android.hardware.light-service.lineage.rc',
                 '/etc/vintf/manifest/android.hardware.light-service.lineage.xml'):
        original = scratch / ('old-' + name.rsplit('/', 1)[-1])
        dump(image, name, original)
        debugfs(image, f'rm {name}', True)
        if 'File not found' not in debugfs(image, f'stat {name}'):
            raise ValueError('Duplicate lights provider remains')
    install('/bin/hw/android.hardware.light-service.polaris', inputs['lights'], 0o755, 'hal_light_default_exec')
    install('/etc/init/android.hardware.light-service.polaris.rc', project / 'device/polaris/lights/android.hardware.light-service.polaris.rc')
    install('/etc/vintf/manifest/android.hardware.light-service.polaris.xml', project / 'device/polaris/lights/android.hardware.light-service.polaris.xml')
    contexts = scratch / 'vendor_file_contexts'
    dump(image, '/etc/selinux/vendor_file_contexts', contexts)
    contexts.write_text(contexts.read_text().rstrip() + '\n' + (project / 'device/polaris/lights/file_contexts').read_text())
    install('/etc/selinux/vendor_file_contexts', contexts)
    (out / 'fsck-final.txt').write_text(run(['e2fsck', '-fn', image]))
    report = {'schema': 1, 'flashable': False, 'base': lock['source'],
              'image': {'bytes': image.stat().st_size, 'sha256': sha(image)},
              'replacements': changed, 'fsck_clean': True, 'odm_folded_into_vendor': True,
              'no_sdk36_vendor_apex': True, 'tested_on_device': False,
              'blockers': ['4.9-origin HALs vs selected 4.19 kernel ABI',
                           'full VINTF and linker namespaces', 'data encryption migration',
                           'system/product device overlays and power control', 'boot and rollback trial']}
    (out / 'integration-report.json').write_text(json.dumps(report, indent=2) + '\n')
    (out / 'NOT-FLASHABLE.txt').write_text('Android 15 vendor 工程候选，尚未形成完整可刷 ROM。\n', encoding='utf-8')
    print(json.dumps({'image': str(image), 'sha256': sha(image), 'flashable': False}, indent=2))


if __name__ == '__main__':
    main()
