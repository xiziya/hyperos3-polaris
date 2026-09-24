import json,re,sys,hashlib
from pathlib import Path
p=Path(__import__('os').environ['POLARIS_WORKSPACE'])
sys.path.insert(0,str(p/'outputs/hyperos3-polaris/tools'))
from audit_elf import inspect
codec=Path('/var/tmp/polaris-media-mix/32/libqcodec2.so').read_bytes()
strings=set(x.decode('ascii') for x in re.findall(rb'[A-Za-z_][A-Za-z_0-9]{3,}',codec))
rows=[]
for name in ('libC2D2.so','libadreno_utils.so'):
    ref=Path('/var/tmp/polaris-vendor-audit/lib/lib')/name
    actual=Path('/mnt/e/CodexWork/hyperos3-polaris/research/elf32/vendor/lib')/name
    a,b=inspect(ref),inspect(actual)
    referenced=strings&a['exports'];missing=referenced-b['exports']
    rows.append({'library':name,'reference_sha256':hashlib.sha256(ref.read_bytes()).hexdigest(),'candidate_sha256':hashlib.sha256(actual.read_bytes()).hexdigest(),'reference_export_names_present_as_codec_strings':sorted(referenced),'missing_candidate_export_names':sorted(missing)})
assert not any(r['missing_candidate_export_names'] for r in rows)
# Flat dependency inventory selected the vendor libbase for a platform library.
# Its actual platform provider exports this strong symbol; runtime namespaces
# still need verification on device rather than declaring the inventory a pass.
symbol='_ZN7android4base4JoinINSt3__16vectorINS2_12basic_stringIcNS2_11char_traitsIcEENS2_9allocatorIcEEEENS7_IS9_EEEEcEES9_RKT_T0_'
libbase=Path('/var/tmp/polaris-donor-audit/system-lib64/libbase.so')
assert symbol in inspect(libbase)['exports']
report={'schema':1,'codec_sha256':hashlib.sha256(codec).hexdigest(),'dlopen_export_candidate_checks':rows,'graphicsenv_join_exported_by_platform_libbase':True,'runtime_linker_namespace_verified':False,'scope':'Conservative static dlopen string/export comparison; not execution or proof of all dlsym branches.'}
(p/'work/research/media-dlopen-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
