#!/usr/bin/env python3
"""Package six validated images for the measured polaris static layout.

Produces a local first-boot development ZIP, never a stable release. It does
not contact a phone, flash partitions or redistribute vendor blobs to GitHub.
"""
import argparse,hashlib,json,stat,zipfile
from pathlib import Path

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--images',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();root=Path(__file__).resolve().parents[1]
    folder=args.images.resolve();out=args.output.resolve()
    if out.exists():raise ValueError('Refusing to overwrite an existing ZIP')
    layout={p['name']:p for p in json.loads((root/'reports/live-layout.json').read_text())['partitions']}
    vendor_boot=json.loads((folder/'vendor-boot.report.json').read_text())
    if not all(vendor_boot[k] for k in ('vendor_fsck_passed','boot_roundtrip_passed','boot_vendor_fstab_identical')):
        raise ValueError('Incomplete vendor/boot validation')
    specs={x['name']:x for x in vendor_boot['images']}
    for name in ('system','system_ext','product','mi_ext'):
        r=json.loads((folder/f'{name}.report.json').read_text())
        if not r['fsck_passed'] or not r['all_files_metadata_and_hash_roundtrip'] or r['erofs_incompat'] & ~3:
            raise ValueError('Incomplete EROFS validation: '+name)
        specs[name+'.img']=r
    rows=[];images=[]
    for name in ('system','system_ext','product','mi_ext','vendor','boot'):
        f=folder/(name+'.img');size=f.stat().st_size;digest=sha(f);part=layout[name]
        if not 0<size<=part['bytes'] or size!=specs[f.name]['bytes'] or digest!=specs[f.name]['sha256']:
            raise ValueError('Image differs from validated report: '+name)
        rows.append(f"{name}\t{part['bytes']}\t{part['start_sector_512']}\t{Path(part['block']).name}\t{size}\t{digest}\n")
        images.append({'name':f.name,'bytes':size,'sha256':digest})
    manifest={'schema':1,'device':'polaris','ram_gib':6,'marketed_storage_gb':128,
              'target':'HyperOS 3 China / Android 15','status':'first-boot-development',
              'runtime_verified':False,'stable':False,'kernel_root_frameworks':False,
              'images':images,'installer':'recovery; existing measured static layout; boot last',
              'data_policy':'Explicit user backup and Format Data required; installer never formats. ext4 software FBEv2, runtime/recovery decryption untested.',
              'untouched':['GPT','bootloader','recovery','vbmeta','modem','EFS','persist','userdata'],
              'hardware_tests_required':['display/touch','radio/IMEI/dual SIM/4G/IMS','Wi-Fi/Bluetooth','storage/FBE/reboot','charging/thermal/suspend','video encode/decode','camera/audio','Xiaomi account/cloud','recovery/rollback']}
    out.parent.mkdir(parents=True,exist_ok=True)
    installer=(root/'device/polaris/installer/update-binary').read_bytes()
    with zipfile.ZipFile(out,'x',zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
        info=zipfile.ZipInfo('META-INF/com/google/android/update-binary',(2026,9,25,0,0,0))
        info.create_system=3;info.external_attr=(stat.S_IFREG|0o755)<<16;info.compress_type=zipfile.ZIP_DEFLATED
        z.writestr(info,installer)
        z.writestr('META-INF/com/google/android/updater-script','# Installation is performed by the reviewed recovery shell installer.\n')
        z.writestr('manifest.tsv',''.join(rows))
        z.writestr('build-manifest.json',json.dumps(manifest,indent=2)+'\n')
        z.write(root/'docs/first-device-test.md','README-FIRST-TEST.md')
        for record in images:
            print('Packing',record['name'],flush=True)
            z.write(folder/record['name'],'images/'+record['name'])
    # Decode every ZIP image and compare it to the validated source; CRC and
    # decompression errors also raise here. A ZIP file existing is not success.
    with zipfile.ZipFile(out) as z:
        expected={'META-INF/com/google/android/update-binary','META-INF/com/google/android/updater-script','manifest.tsv','build-manifest.json','README-FIRST-TEST.md',*('images/'+r['name'] for r in images)}
        if len(z.namelist())!=len(expected) or set(z.namelist())!=expected:raise ValueError('Unexpected archive entries')
        for record in images:
            with z.open('images/'+record['name']) as stream:
                if hashlib.file_digest(stream,'sha256').hexdigest()!=record['sha256']:raise ValueError('ZIP roundtrip failed')
        assert z.read('META-INF/com/google/android/update-binary')==installer
    manifest['package']={'file':out.name,'bytes':out.stat().st_size,'sha256':sha(out),'zip_image_roundtrip':True}
    out.with_suffix('.json').write_text(json.dumps(manifest,indent=2)+'\n')
    out.with_suffix('.sha256').write_text(manifest['package']['sha256']+'  '+out.name+'\n')
    print(json.dumps(manifest['package'],indent=2))

if __name__=='__main__':main()
