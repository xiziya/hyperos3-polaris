import json,re,struct,zipfile,subprocess
from pathlib import Path
root=Path('/mnt/polaris-rom-assembly/system_ext/priv-app/Settings/Settings.apk')
out=Path('/var/tmp/polaris-settings-identity');out.mkdir(exist_ok=True)
result={}
with zipfile.ZipFile(root) as z:
    for name in z.namelist():
        if not re.fullmatch(r'classes\d*\.dex',name):continue
        data=z.read(name);(out/name).write_bytes(data)
        count,offset=struct.unpack_from('<II',data,56)
        strings=[]
        for i in range(count):
            j=struct.unpack_from('<I',data,offset+i*4)[0]
            while data[j]&128:j+=1
            j+=1;strings.append(data[j:data.index(b'\0',j)].decode('utf-8','replace'))
        props=[s for s in strings if s.startswith(('ro.','persist.')) and any(k in s.lower() for k in ('cpu','soc','product','market','hardware','memory','ram','storage','chip','device'))]
        classes=[s for s in strings if s.startswith('Lcom/android/settings/') and s.endswith(';') and any(k in s for k in ('MiuiDevice','AboutPhone','DeviceInfo','CpuInfo','MiuiMyDevice','HardwareInfo','MyDevice'))]
        result[name]={'properties':props,'classes':classes}
        chosen=[s for s in strings if s.startswith('Lcom/android/settings/device/') and s.endswith(';')]
        if chosen:
            subprocess.run(['java','-jar',str(p/'work/research/port-reference/bin/baksmali.jar'),'disassemble','--classes',','.join(chosen),'-o',str(out/name.replace('.dex','')),str(out/name)],check=True,capture_output=True)
(out/'strings.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
