import gzip,hashlib,json,re,shutil,stat,struct,sys,tarfile
from pathlib import Path
p=Path(__import__('os').environ['POLARIS_WORKSPACE'])
repo=p/'outputs/hyperos3-polaris';sys.path.insert(0,str(repo/'tools'))
from integrate_rom import sha,run,debugfs,dump,make_cpio
from inspect_recovery import cpio_entries
out=Path('/mnt/e/CodexWork/hyperos3-polaris/assembled');scratch=out/'vendor-final-assembly';scratch.mkdir(exist_ok=False)
source=p/'outputs/rom-integration-development/a15-vendor-3/vendor-a15-candidate.img'
assert sha(source)=='ccb31ff55e63ad4871c8eb0eae482beb65f67e2834fcd0f205bb82916a28ebd5'
image=out/'vendor.img';assert not image.exists();shutil.copyfile(source,image)
changes=[]
def get(name):
    local=scratch/('original-'+name.replace('/','_'));dump(image,name,local);return local.read_text()
def put(name,text):
    i=len(changes);local=scratch/f'file-{i}';local.write_text(text)
    attr=scratch/f'attr-{i}';debugfs(image,f'ea_get -f {attr} {name} security.selinux')
    expected_attr=attr.read_bytes();meta=debugfs(image,f'stat {name}')
    mode=int(re.search(r'Mode:\s+(\d+)',meta)[1],8)
    uid,gid=map(int,re.search(r'User:\s+(\d+)\s+Group:\s+(\d+)',meta).groups())
    debugfs(image,f'rm {name}',True);debugfs(image,f'write {local} {name}',True)
    for field,value in [('mode','0'+format(stat.S_IFREG|mode,'o')),('uid',uid),('gid',gid)]:
        debugfs(image,f'set_inode_field {name} {field} {value}',True)
    debugfs(image,f'ea_set -f {attr} {name} security.selinux',True)
    verify=scratch/f'verify-{i}';dump(image,name,verify)
    assert sha(verify)==sha(local)
    debugfs(image,f'ea_get -f {attr} {name} security.selinux');assert attr.read_bytes()==expected_attr
    newmeta=debugfs(image,f'stat {name}')
    assert 'Type: regular' in newmeta and f'Mode:  0{mode:o}' in newmeta
    assert re.search(r'User:\s+(\d+)\s+Group:\s+(\d+)',newmeta).groups()==(str(uid),str(gid))
    changes.append({'path':name,'sha256':sha(local),'selinux':expected_attr.rstrip(b'\0').decode(),'mode':oct(mode),'uid':uid,'gid':gid})

fstab=get('/etc/fstab.qcom');rows=[]
for line in fstab.splitlines():
    f=line.split()
    if f and not line.lstrip().startswith('#') and f[1]=='/data':
        if f[2]=='f2fs':continue
        assert f[2]=='ext4'
        f[3]='noatime,nosuid,nodev,barrier=1,noauto_da_alloc'
        f[4]='latemount,wait,check,fileencryption=aes-256-xts:aes-256-cts:v2,quota,reservedsize=128M'
        line='\t'.join(f)
    rows.append(line)
fstab='\n'.join(rows)+'\n';put('/etc/fstab.qcom',fstab)
(out/'fstab.qcom').write_text(fstab)
props=get('/build.prop');updates={'ro.boot.dynamic_partitions':'false','ro.product.vendor.name':'polaris','ro.product.vendor.model':'MIX 2S','ro.vendor.radio.5g':'0','persist.radio.multisim.config':'dsds','tombstoned.max_tombstone_count':'10'}
put('/build.prop','\n'.join(s for s in props.splitlines() if s.partition('=')[0] not in updates)+'\n'+''.join(k+'='+v+'\n' for k,v in updates.items()))
rc=get('/etc/init/hw/init.qcom.rc')
rc,count=re.subn(r'^service ppd .*?(?=^\S|\Z)','',rc,flags=re.M|re.S);assert count==1
rc=re.sub(r'^\s+(?:start|stop) ppd\s*\n','',rc,flags=re.M)
put('/etc/init/hw/init.qcom.rc',rc)
rc=get('/etc/init/hw/init.qcom.power.rc')
assert 'start vendor.thermal-engine' in rc
rc=rc.replace('start vendor.thermal-engine','start thermal-engine')
rc=re.sub(r'^\s*write /sys/module/msm_thermal/parameters/enabled "N"\s*\n','',rc,flags=re.M)
put('/etc/init/hw/init.qcom.power.rc',rc)
(out/'vendor-fsck.txt').write_text(run(['e2fsck','-fn',image]))

# Build only from source-locked generic init, compiled kernel, and reviewed boot
# geometry. The very same fstab bytes are installed in vendor and first stage.
inputs={k:Path(v) for k,v in json.loads((p/'work/research/integration-local-inputs.json').read_text()).items()}
lock=json.loads((repo/'config/integration-sources.json').read_text())
for key in ('reference_boot','first_stage_init','mkbootimg_archive','kernel'):
    assert sha(inputs[key])==lock['files'][key]['sha256']
dirs=['debug_ramdisk','dev','metadata','mnt','proc','second_stage_resources','sys','system','system/etc','vendor','product','system_ext','mi_ext']
entries=[(d,stat.S_IFDIR|0o755,b'') for d in dirs]
entries += [('init',stat.S_IFREG|0o750,inputs['first_stage_init'].read_bytes()),('system/etc/fstab.qcom',stat.S_IFREG|0o644,fstab.encode())]
ramdisk=scratch/'ramdisk.gz';ramdisk.write_bytes(gzip.compress(make_cpio(entries),mtime=0))
mkboot=scratch/'mkbootimg';mkboot.mkdir()
with tarfile.open(inputs['mkbootimg_archive']) as tar:tar.extractall(mkboot,filter='data')
ref=inputs['reference_boot'].read_bytes();page,version=struct.unpack_from('<II',ref,36)
assert ref[:8]==b'ANDROID!' and page==4096 and version==1
cmdline=(ref[64:576]+ref[608:1632]).split(b'\0')[0].decode()
assert not any(s in cmdline for s in ('permissive','androidboot.verifiedbootstate=','androidboot.flash.locked='))
boot=out/'boot.img'
run(['python3',mkboot/'mkbootimg.py','--kernel',inputs['kernel'],'--ramdisk',ramdisk,'--header_version','1','--pagesize',str(page),'--base','0','--kernel_offset',hex(struct.unpack_from('<I',ref,12)[0]),'--ramdisk_offset',hex(struct.unpack_from('<I',ref,20)[0]),'--tags_offset',hex(struct.unpack_from('<I',ref,32)[0]),'--cmdline',cmdline,'--os_version','15.0.0','--os_patch_level','2026-08','-o',boot])
b=boot.read_bytes();ksize=struct.unpack_from('<I',b,8)[0];rsize=struct.unpack_from('<I',b,16)[0];rstart=page+((ksize+page-1)//page)*page
assert hashlib.sha256(b[page:page+ksize]).hexdigest()==sha(inputs['kernel'])
unpacked={n:d for n,m,d in cpio_entries(gzip.decompress(b[rstart:rstart+rsize]))}
assert unpacked['init']==inputs['first_stage_init'].read_bytes() and unpacked['system/etc/fstab.qcom']==fstab.encode()
assert boot.stat().st_size<=67108864
report={'schema':1,'source_vendor_sha256':sha(source),'changes':changes,'vendor_fsck_passed':True,'boot_roundtrip_passed':True,'boot_vendor_fstab_identical':True,'userdata':'Clean ext4 required for first Android17 to Android15 downgrade. Software AES-XTS/CTS FBEv2; no autoformat, no ICE claim. Recovery decryption and keymaster3 runtime remain untested.','images':[{'name':f.name,'bytes':f.stat().st_size,'sha256':sha(f)} for f in (image,boot)],'runtime_verified':False}
(out/'vendor-boot.report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report['images'],indent=2))
