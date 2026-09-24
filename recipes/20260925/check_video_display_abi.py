import json,re,shutil,struct,subprocess
from pathlib import Path
from elftools.elf.elffile import ELFFile
p=Path(__import__('os').environ['POLARIS_WORKSPACE'])
k=Path('/var/tmp/hyperos3-polaris/work/kernel/include/uapi')
ndk=Path('/var/tmp/polaris-hal-build/android-ndk-r27c/toolchains/llvm/prebuilt/linux-x86_64')
out=Path('/var/tmp/polaris-video-display-abi');out.mkdir(exist_ok=True)
paths=['linux/videodev2.h','linux/v4l2-controls.h','media/msm_vidc.h','drm/msm_drm.h','drm/drm.h','drm/drm_mode.h','drm/sde_drm.h']
trees={}
for version in ('4.9','4.19'):
    inc=out/version;inc.mkdir(exist_ok=True)
    text=''
    for path in paths:
        source=(p/'work/research/kernel49-uapi'/('include_uapi_'+path.replace('/','_'))) if version=='4.9' else k/path
        dest=inc/path;dest.parent.mkdir(exist_ok=True)
        shutil.copyfile(source,dest);text+=source.read_text()+'\n'
    names=set(re.findall(r'^#define\s+((?:DRM_IOCTL_MSM_|VIDIOC_|V4L2_CID_MPEG_VIDC_|V4L2_PIX_FMT_)[A-Za-z0-9_]+)\s',text,re.M))
    trees[version]=(inc,names)
names=sorted(trees['4.9'][1]&trees['4.19'][1])
structs=['v4l2_buffer','v4l2_plane','v4l2_format','v4l2_requestbuffers','v4l2_ext_control','v4l2_ext_controls','drm_msm_gem_new','drm_msm_gem_info','drm_msm_gem_cpu_prep','drm_msm_gem_submit']
exprs=names+['sizeof(struct '+s+')' for s in structs]
rows=[]
for arch,target in [('arm64','aarch64-linux-android35'),('arm32','armv7a-linux-androideabi35')]:
    results={}
    for version,(inc,_) in trees.items():
        source=out/f'{version}-{arch}.c';obj=source.with_suffix('.o')
        source.write_text('#include <sys/time.h>\n#include <stddef.h>\n#include <linux/videodev2.h>\n#include <drm/msm_drm.h>\nconst unsigned int values[]={'+','.join(exprs)+'};\n')
        r=subprocess.run([ndk/'bin/clang','--target='+target,'--sysroot='+str(ndk/'sysroot'),'-I'+str(inc),'-c',source,'-o',obj],capture_output=True,text=True)
        if r.returncode:raise SystemExit(r.stderr)
        with obj.open('rb') as f:data=ELFFile(f).get_section_by_name('.rodata').data()
        results[version]=list(struct.unpack('<'+str(len(exprs))+'I',data))
    differences=[{'expression':name,'reference':a,'selected':b} for name,a,b in zip(exprs,results['4.9'],results['4.19']) if a!=b]
    rows.append({'arch':arch,'common_constant_count':len(names),'struct_size_count':len(structs),'differences':differences})
report={'schema':1,'reference_kernel_commit':'aa8adfe9bf212c6e93238a86980b4024da4f819a','selected_kernel_commit':'1f326a9202472e8228c2a08ebfd4fdb83da52675','checks':rows,'reference_macros_absent_in_selected':sorted(trees['4.9'][1]-trees['4.19'][1]),'checked_expressions':exprs,'scope':'Common UAPI ioctl/control/pixel constants and selected struct sizes; not control semantics, offsets, firmware or full driver compatibility','runtime_verified':False}
(p/'work/research/video-display-abi.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='checked_expressions'},indent=2))
