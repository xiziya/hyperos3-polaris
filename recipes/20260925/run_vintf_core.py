import hashlib,json,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
p=Path(__import__('os').environ['POLARIS_WORKSPACE'])
out=Path('/var/tmp/polaris-vintf-build/inputs')
out.mkdir(exist_ok=True)
image=Path('/mnt/e/CodexWork/hyperos3-polaris/assembled/vendor.img')
vendor=out/'vendor-final'
vendor.mkdir(exist_ok=True)
subprocess.run(['debugfs','-R',f'rdump /etc/vintf {vendor}',str(image)],check=True,capture_output=True)
base=vendor/'vintf/manifest.xml'
root=ET.parse(base).getroot()
assert root.find('kernel') is None
k=ET.SubElement(root,'kernel',{'version':'4.19.325','target-level':'5'})
for line in (p/'outputs/kernel-development/kernel.config').read_text().splitlines():
    if line.startswith('CONFIG_') and '=' in line:
        key,value=line.split('=',1)
    elif line.startswith('# CONFIG_') and line.endswith(' is not set'):
        key,value=line[2:-11],'n'
    else:continue
    c=ET.SubElement(k,'config')
    ET.SubElement(c,'key').text=key
    ET.SubElement(c,'value').text=value
testmanifest=out/'device-with-real-kernel.xml'
ET.ElementTree(root).write(testmanifest,encoding='unicode')
cmd=['/var/tmp/polaris-vintf-build/vintf-core-check','--device',str(testmanifest)]
for f in sorted((vendor/'vintf/manifest').glob('*.xml')):
    cmd+=['--device',str(f)]
cmd+=['--device-matrix',str(vendor/'vintf/compatibility_matrix.xml')]
for role in ('system','system_ext','product'):
    d=p/f'work/research/donor-{role}-etc/vintf'
    manifest=d/'manifest.xml'
    if manifest.exists():cmd+=['--framework',str(manifest)]
    for f in sorted((d/'manifest').glob('*.xml')):
        cmd+=['--framework',str(f)]
    for f in sorted(d.glob('compatibility_matrix*.xml')):
        cmd+=['--framework-matrix',str(f)]
result=subprocess.run(cmd,capture_output=True,text=True)
negative=out/'negative-required-hal.xml'
negative.write_text('<compatibility-matrix version="8.0" type="framework"><hal format="hidl" optional="false"><name>vendor.polaris.test.missing</name><version>1.0</version><interface><name>IMissing</name><instance>default</instance></interface></hal></compatibility-matrix>')
negative_result=subprocess.run([*cmd,'--framework-matrix',str(negative)],capture_output=True,text=True)
assert negative_result.returncode==1 and 'vendor.polaris.test.missing' in negative_result.stdout
report={'schema':1,'scope':'Actual AOSP libvintf core parser/merger and bidirectional checkCompatibility; not full checkvintf CLI',
    'libvintf_commit':'0748000fca71d7ecea7184883fed4c23997f91b6',
    'vendor_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),
    'real_kernel':'4.19.325','kernel_level_assumption':5,'returncode':result.returncode,
    'actual_vendor_xml_extracted':True,'complete_checkvintf':False,
    'negative_missing_required_hal_rejected':True,
    'output':result.stdout,'diagnostics':result.stderr,
    'inputs':[{'option':cmd[i],'file':str(Path(cmd[i+1]).relative_to(p)) if Path(cmd[i+1]).is_relative_to(p) else str(Path(cmd[i+1]).relative_to(out)), 'sha256':hashlib.sha256(Path(cmd[i+1]).read_bytes()).hexdigest()} for i in range(1,len(cmd),2)],
    'runtime_verified':False}
(p/'work/research/vintf-core-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(result.stdout,result.stderr)
raise SystemExit(result.returncode)
