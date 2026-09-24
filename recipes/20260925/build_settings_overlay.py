import hashlib,json,os,subprocess
from pathlib import Path
p=Path(__import__('os').environ['POLARIS_WORKSPACE'])
source=p/'outputs/hyperos3-polaris/device/polaris/settings-overlay'
tool=p/'work/research/port-reference/bin/linux/x86_64/aapt2'
out=Path('/var/tmp/polaris-settings-overlay');out.mkdir(exist_ok=True)
base=Path('/mnt/polaris-rom-assembly')
key=p/'private/overlay-signing'
subprocess.run([str(tool),'compile','--dir',str(source/'res'),'-o',str(out/'resources.zip')],check=True)
subprocess.run([str(tool),'link','-I',str(base/'system/system/framework/framework-res.apk'),'--manifest',str(source/'AndroidManifest.xml'),'--auto-add-overlay','-o',str(out/'unsigned.apk'),str(out/'resources.zip')],check=True)
subprocess.run(['apksigner','sign','--ks',str(key/'overlay.jks'),'--ks-pass','file:'+str(key/'password'),'--out',str(out/'PolarisSettingsOverlay.apk'),str(out/'unsigned.apk')],check=True)
verification=subprocess.check_output(['apksigner','verify','--verbose',str(out/'PolarisSettingsOverlay.apk')],text=True)
target=base/'product/overlay/PolarisSettingsOverlay.apk'
ref=base/'product/overlay/PolarisFrameworkOverlay.apk'
info=ref.stat();target.write_bytes((out/'PolarisSettingsOverlay.apk').read_bytes())
os.chown(target,info.st_uid,info.st_gid);os.chmod(target,0o644)
for attr in os.listxattr(ref):os.setxattr(target,attr,os.getxattr(ref,attr))
report_path=p/'work/research/hardware-overlay-report.json';report=json.loads(report_path.read_text())
for name in ('SettingsRroDeviceHideStatusBarOverlay.apk','SettingsRroDeviceTypeOverlay.apk','SettingsRroDeviceSystemUiOverlay.apk'):
    path=base/'product/overlay'/name
    report['removed_donor_hardware_overlays'].append({'file':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    path.unlink()
report['settings_overlay']={'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'signature_verification':verification}
report_path.write_text(json.dumps(report,indent=2)+'\n');print(verification)
