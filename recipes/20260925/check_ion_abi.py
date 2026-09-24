import hashlib,json,struct,subprocess
from pathlib import Path
from elftools.elf.elffile import ELFFile
p=Path(__import__('os').environ['POLARIS_WORKSPACE'])
k=Path('/var/tmp/hyperos3-polaris/work/kernel')
ndk=Path('/var/tmp/polaris-hal-build/android-ndk-r27c/toolchains/llvm/prebuilt/linux-x86_64')
out=Path('/var/tmp/polaris-ion-abi');out.mkdir(exist_ok=True)
old=p/'work/research/kernel49-uapi/drivers_staging_android_uapi_ion.h'
new=k/'drivers/staging/android/ion/ion_legacy.h'
names=['ALLOC','FREE','MAP','SHARE','IMPORT']
results=[]
for arch,target in [('arm64','aarch64-linux-android35'),('arm32','armv7a-linux-androideabi35')]:
    values={}
    for name,header in [('4.9',old),('4.19',new)]:
        source=out/f'{name}-{arch}.c';obj=source.with_suffix('.o')
        alloc='ION_IOC_ALLOC' if name=='4.9' else 'ION_OLD_IOC_ALLOC'
        exprs=[alloc,'ION_IOC_FREE','ION_IOC_MAP','ION_IOC_SHARE','ION_IOC_IMPORT',f'sizeof(struct ion_{"old_" if name=="4.19" else ""}allocation_data)','sizeof(struct ion_fd_data)','sizeof(struct ion_handle_data)']
        source.write_text('#include <stddef.h>\n#define CONFIG_ION_LEGACY 1\n#include "'+str(header)+'"\nconst unsigned int values[]={'+','.join(exprs)+'};\n')
        subprocess.run([ndk/'bin/clang','--target='+target,'--sysroot='+str(ndk/'sysroot'),'-c',source,'-o',obj],check=True,capture_output=True)
        with obj.open('rb') as f:
            data=ELFFile(f).get_section_by_name('.rodata').data()
        values[name]=list(struct.unpack('<8I',data))
    results.append({'arch':arch,'ioctl_names':names,'old':values['4.9'],'new_legacy':values['4.19'],'equal':values['4.9']==values['4.19']})
report={'schema':1,'reference_kernel_commit':'aa8adfe9bf212c6e93238a86980b4024da4f819a','selected_kernel_commit':'1f326a9202472e8228c2a08ebfd4fdb83da52675','checks':results,'scope':'Legacy ION ioctl numbers and struct sizes only; not runtime buffer lifetime/cache or complete video/display ABI','runtime_verified':False}
(p/'work/research/ion-abi.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
