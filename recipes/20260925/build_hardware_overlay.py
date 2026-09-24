import hashlib,json,os,subprocess
from pathlib import Path
p=Path(__import__('os').environ['POLARIS_WORKSPACE'])
source=p/'outputs/hyperos3-polaris/device/polaris/framework-overlay'
aapt=p/'work/research/port-reference/bin/linux/x86_64/aapt2'
out=Path('/var/tmp/polaris-hardware-overlay');out.mkdir(exist_ok=True)
base=Path('/mnt/polaris-rom-assembly')
key=p/'private/overlay-signing';key.mkdir(parents=True,exist_ok=True)
if not (key/'overlay.jks').exists():
    (key/'password').write_text(os.urandom(32).hex());os.chmod(key/'password',0o600)
    subprocess.run(['keytool','-genkeypair','-keystore',str(key/'overlay.jks'),'-storepass:file',str(key/'password'),'-keypass:file',str(key/'password'),'-alias','polaris-overlay','-keyalg','RSA','-keysize','3072','-validity','10000','-dname','CN=Polaris development overlay'],check=True,capture_output=True)
subprocess.run([str(aapt),'compile','--dir',str(source/'res'),'-o',str(out/'resources.zip')],check=True)
subprocess.run([str(aapt),'link','-I',str(base/'system/system/framework/framework-res.apk'),'--manifest',str(source/'AndroidManifest.xml'),'--auto-add-overlay','-o',str(out/'unsigned.apk'),str(out/'resources.zip')],check=True)
subprocess.run(['apksigner','sign','--ks',str(key/'overlay.jks'),'--ks-pass','file:'+str(key/'password'),'--out',str(out/'PolarisFrameworkOverlay.apk'),str(out/'unsigned.apk')],check=True)
verified=subprocess.check_output(['apksigner','verify','--verbose',str(out/'PolarisFrameworkOverlay.apk')],text=True)
target=base/'product/overlay/PolarisFrameworkOverlay.apk'
ref=base/'product/overlay/DevicesAndroidOverlay.apk'
info=ref.stat();target.write_bytes((out/'PolarisFrameworkOverlay.apk').read_bytes())
os.chown(target,info.st_uid,info.st_gid);os.chmod(target,0o644)
for attr in os.listxattr(ref):os.setxattr(target,attr,os.getxattr(ref,attr))
removed=[]
for name in ('DevicesAndroidOverlay.apk','DevicesOverlay.apk'):
    path=base/'product/overlay'/name
    removed.append({'file':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    path.unlink()  # only donor hardware-specific RRO files in the local extract
report={'schema':1,'removed_donor_hardware_overlays':removed,'new_apk_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'signature_verification':verified,'runtime_idmap_and_settings_verified':False,'note':'No Settings/SystemUI APK code or signature modified; hardware-specific resources override donor defaults.'}
(p/'work/research/hardware-overlay-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(verified)
