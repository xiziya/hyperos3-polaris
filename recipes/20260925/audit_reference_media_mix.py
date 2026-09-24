import json,shutil,subprocess,sys
from pathlib import Path
p=Path(__import__('os').environ['POLARIS_WORKSPACE'])
sys.path.insert(0,str(p/'outputs/hyperos3-polaris/tools'))
from audit_elf import inspect
stage=Path('/var/tmp/polaris-media-mix')
prefixes=('libsdm','libgralloc','libqdMetaData','libdisplayconfig','libdrmutils','libdrm.so','libqservice','libqdutils','libdisplaydebug','libgpu_tonemapper','libhistogram','vendor.display.','vendor.qti.hardware.display.','android.hardware.graphics.')
for bits in (32,64):
    old=Path('/var/tmp/polaris-vendor-audit')/('lib' if bits==32 else 'lib64')/('lib' if bits==32 else 'lib64')
    dest=stage/str(bits);dest.mkdir(parents=True,exist_ok=True)
    for f in old.glob('*.so'):
        if f.name.startswith(prefixes) and '-ndk.so' not in f.name:
            shutil.copyfile(f,dest/f.name)
    if bits==32:
        for name in ('libqcodec2.so','libcodec2.so','libcodec2_hal_common.so','libcodec2_hidl@1.0.so','libcodec2_vndk.so','libcodec2_hidl_plugin.so'):
            shutil.copyfile(old/name,dest/name)
    vendor=Path('/mnt/e/CodexWork/hyperos3-polaris/research/elf32/vendor/lib') if bits==32 else Path('/var/tmp/polaris-lineage-a15/lib64/lib64')
    system=Path('/mnt/e/CodexWork/hyperos3-polaris/research/elf32/system') if bits==32 else Path('/var/tmp/polaris-donor-audit/system-lib64')
    ext=Path('/mnt/e/CodexWork/hyperos3-polaris/research/elf32/system_ext') if bits==32 else Path('/var/tmp/polaris-donor-audit/system-ext-lib64')
    roots=[old/'hw/android.hardware.graphics.mapper@3.0-impl-qti-display.so',old/'hw/android.hardware.graphics.mapper@4.0-impl-qti-display.so']
    if bits==32:roots += [Path('/var/tmp/polaris-vendor-audit/bin/bin/hw/vendor.qti.media.c2@1.0-service')]
    else:roots += [Path('/var/tmp/polaris-vendor-audit/bin/bin/hw')/x for x in ('vendor.qti.hardware.display.allocator-service','vendor.qti.hardware.display.composer-service')]
    cmd=['python3',str(p/'outputs/hyperos3-polaris/tools/audit_elf.py')]
    for label,d in [('media-mix',dest),('vendor',vendor),('system',system),('system_ext',ext),('bionic',system/'bootstrap')]:cmd+=['--search',label+'='+str(d)]
    for root in roots:cmd+=['--binary',str(root)]
    cmd+=['--output',str(p/f'work/research/reference-media-mix-{bits}.json')]
    subprocess.run(cmd,check=True)
