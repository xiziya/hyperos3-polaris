import hashlib,json,re,shutil,stat,sys,xml.etree.ElementTree as ET
from pathlib import Path
p=Path(__import__('os').environ['POLARIS_WORKSPACE'])
repo=p/'outputs/hyperos3-polaris'
sys.path.insert(0,str(repo/'tools'))
from integrate_rom import sha,run,debugfs,dump
out=p/'outputs/rom-integration-development/a15-vendor-3'
if (out/'integration-report.json').exists():raise ValueError('Completed output already exists')
out.mkdir(exist_ok=True);scratch=out/'assembly';scratch.mkdir(exist_ok=True)
source=p/'outputs/rom-integration-development/a15-vendor-2/vendor-a15-candidate.img'
reference=p/'work/research/images/vendor.raw.img'
assert sha(source)=='49016f848160f57bb0909abffe8480d827640fbc83aa70b60ffa5e828787d5ba'
assert sha(reference)=='fff1b4d272f1be26a78e1d965645cb543a23eecf4e47a9572edd16491809669d'
image=out/'vendor-a15-candidate.img';shutil.copyfile(source,image)
changes=[]
def install(name,data=None,label='vendor_file',mode=0o644):
    i=len(changes);local=scratch/f'input-{i}'
    if data is None:
        dump(reference,name,local)
        original_attr=scratch/f'original-attr-{i}'
        debugfs(reference,f'ea_get -f {original_attr} {name} security.selinux')
        raw=original_attr.read_bytes().rstrip(b'\0').decode('ascii')
        if not re.fullmatch(r'u:object_r:[A-Za-z0-9_]+:s0',raw):
            raise ValueError('Invalid reference label '+name)
        label=raw.split(':')[2]
    else:local.write_bytes(data)
    debugfs(image,f'rm {name}',True)
    debugfs(image,f'write {local} {name}',True)
    debugfs(image,f'set_inode_field {name} mode 0{stat.S_IFREG | mode:o}',True)
    for field in ('uid','gid','atime','mtime','ctime'):debugfs(image,f'set_inode_field {name} {field} 0',True)
    labelpath=scratch/f'label-{i}';labelpath.write_bytes(f'u:object_r:{label}:s0'.encode()+b'\0')
    debugfs(image,f'ea_set -f {labelpath} {name} security.selinux',True)
    check=scratch/f'check-{i}';dump(image,name,check)
    attr=scratch/f'attr-{i}';debugfs(image,f'ea_get -f {attr} {name} security.selinux')
    if sha(check)!=sha(local) or attr.read_bytes()!=labelpath.read_bytes():raise ValueError('Readback failed '+name)
    meta=debugfs(image,f'stat {name}')
    if 'Type: regular' not in meta or f'Mode:  0{mode:o}' not in meta or not re.search(r'User:\s+0\s+Group:\s+0',meta):
        raise ValueError('Ownership/mode readback failed '+name)
    changes.append({'path':name,'sha256':sha(local),'label':label,'mode':oct(mode)})

for bits,lib in ((32,'lib'),(64,'lib64')):
    for f in sorted((Path('/var/tmp/polaris-media-mix')/str(bits)).glob('*.so')):
        install('/'+lib+'/'+f.name)
    for name in ('android.hardware.graphics.mapper@3.0-impl-qti-display.so','android.hardware.graphics.mapper@4.0-impl-qti-display.so','gralloc.qcom.so','gralloc.default.so'):
        install('/'+lib+'/hw/'+name)
for name in ('vendor.qti.hardware.display.allocator-service','vendor.qti.hardware.display.composer-service','vendor.qti.media.c2@1.0-service'):
    install('/bin/hw/'+name,mode=0o755)
    rcname='/etc/init/'+name+'.rc'
    rc=scratch/('rc-'+name);dump(reference,rcname,rc)
    data=rc.read_text().replace('    writepid /dev/cpuset/foreground/tasks','    task_profiles ProcessCapacityHigh')
    install(rcname,data.encode(),'vendor_configs_file')
    if 'media.c2' in name:
        # Reference path not covered by Lineage's default media-service regex.
        pass

removals=[
 '/etc/init/android.hardware.graphics.composer@2.3-service.rc',
 '/etc/init/vendor.qti.hardware.display.allocator@1.0-service.rc',
 '/etc/init/vendor.display.color@1.0-service.rc',
 '/etc/init/vendor.lineage.livedisplay-service.sdm.rc',
 '/etc/vintf/manifest/vendor.lineage.livedisplay-service.sdm-dm.xml',
 '/etc/vintf/manifest/vendor.lineage.livedisplay-service.sdm-pa.xml',
]
for name in removals:
    if 'File not found' in debugfs(image,f'stat {name}'):raise ValueError('Unexpected missing old provider '+name)
    debugfs(image,f'rm {name}',True)
main=scratch/'main.xml';dump(image,'/etc/vintf/manifest.xml',main)
tree=ET.parse(main);root=tree.getroot()
oldnames={'android.hardware.graphics.allocator','android.hardware.graphics.composer','android.hardware.graphics.mapper','vendor.display.color','vendor.display.config','vendor.display.postproc'}
removed=[]
for hal in list(root.findall('hal')):
    if hal.findtext('name') in oldnames:removed.append(hal.findtext('name'));root.remove(hal)
assert set(removed)==oldnames
install('/etc/vintf/manifest.xml',ET.tostring(root,encoding='utf-8'),'vendor_configs_file')
providers=[('android.hardware.graphics.allocator','hwbinder',['@3.0::IAllocator/default','@4.0::IAllocator/default']),
('vendor.qti.hardware.display.allocator','hwbinder',['@3.0::IQtiAllocator/default','@4.0::IQtiAllocator/default']),
('android.hardware.graphics.mapper','passthrough',['@3.0::IMapper/default','@4.0::IMapper/default']),
('android.hardware.graphics.composer','hwbinder',['@2.4::IComposer/default']),
('vendor.qti.hardware.display.composer','hwbinder',['@3.0::IQtiComposer/default']),
('vendor.display.config','hwbinder',['@2.0::IDisplayConfig/default']),
('vendor.display.color','hwbinder',['@1.5::IDisplayColor/default']),
('vendor.display.postproc','hwbinder',['@1.0::IDisplayPostproc/default']),
('android.hardware.media.c2','hwbinder',['@1.0::IComponentStore/default'])]
manifest=ET.Element('manifest',version='8.0',type='device')
for name,transport,instances in providers:
    hal=ET.SubElement(manifest,'hal',format='hidl');ET.SubElement(hal,'name').text=name
    t=ET.SubElement(hal,'transport');t.text=transport
    if transport=='passthrough':t.set('arch','32+64')
    for fq in instances:ET.SubElement(hal,'fqname').text=fq
install('/etc/vintf/manifest/polaris-media-display.xml',ET.tostring(manifest,encoding='utf-8'),'vendor_configs_file')
for name in ('media_codecs_c2.xml','media_codecs_performance_c2.xml'):
    install('/etc/'+name)
# Replace the 4.9 OMX video catalog with the 4.19 Codec2 catalog. Keep the
# existing OMX audio catalog; do not advertise uninstalled Dolby components.
for name,c2 in (('media_codecs.xml','media_codecs_c2.xml'),('media_codecs_performance.xml','media_codecs_performance_c2.xml')):
    local=scratch/name;dump(image,'/etc/'+name,local)
    catalog=ET.fromstring(local.read_bytes())
    for parent in catalog.iter():
        for child in list(parent):
            if child.tag=='MediaCodec' and ('video.' in child.get('name','') or child.get('type','').startswith('video/')):
                parent.remove(child)
    ET.SubElement(catalog,'Include',href=c2)
    install('/etc/'+name,ET.tostring(catalog,encoding='utf-8'),'vendor_configs_file')
for name in ('codec2.vendor.base.policy','codec2.vendor.ext.policy'):
    install('/etc/seccomp_policy/'+name)
contexts=scratch/'contexts';dump(image,'/etc/selinux/vendor_file_contexts',contexts)
text=contexts.read_text()+'\n/(vendor|system/vendor)/bin/hw/vendor\\.qti\\.media\\.c2@1\\.0-service u:object_r:mediacodec_exec:s0\n'
install('/etc/selinux/vendor_file_contexts',text.encode(),'vendor_configs_file')
props=scratch/'props';dump(image,'/build.prop',props)
updates={'ro.hardware.gralloc':'qcom','debug.stagefright.ccodec':'4','debug.stagefright.omx_default_rank':'0'}
lines=[s for s in props.read_text().splitlines() if s.partition('=')[0] not in updates]
install('/build.prop',('\n'.join(lines)+'\n'+''.join(k+'='+v+'\n' for k,v in updates.items())).encode(),'vendor_file')
(out/'fsck.txt').write_text(run(['e2fsck','-fn',image]))
report={'schema':1,'source_image_sha256':sha(source),'reference_vendor_sha256':sha(reference),'image_sha256':sha(image),'bytes':image.stat().st_size,'changes':changes,'removed_init_and_vintf':removals,'flashable':False,'runtime_verified':False,'note':'Coherent display/Codec2 candidate replaces 4.9-origin hardware path; complete ROM, policy/runtime and dlopen checks remain.'}
(out/'integration-report.json').write_text(json.dumps(report,indent=2)+'\n')
(out/'NOT-FLASHABLE.txt').write_text('Intermediate vendor only; not a complete flashable ROM.\n')
print(report['image_sha256'])
