"""Apply reviewed bring-up changes to metadata-preserving local extracts."""
import hashlib,json,os,stat,xml.etree.ElementTree as ET
from pathlib import Path
p=Path(__import__('os').environ['POLARIS_WORKSPACE'])
repo=p/'outputs/hyperos3-polaris'
base=Path('/mnt/polaris-rom-assembly')
report=[]
def sha(b):return hashlib.sha256(b).hexdigest()
def write(path,data,like=None,mode=None):
    path=Path(path)
    assert str(path).startswith(str(base)+'/') and not path.is_symlink()
    old=path.read_bytes() if path.exists() else None
    ref=path if path.exists() else Path(like)
    info=ref.stat();attrs={k:os.getxattr(ref,k) for k in os.listxattr(ref)}
    path.write_bytes(data.encode() if isinstance(data,str) else data)
    os.chown(path,info.st_uid,info.st_gid);os.chmod(path,mode or stat.S_IMODE(info.st_mode))
    for key,value in attrs.items():os.setxattr(path,key,value)
    assert os.getxattr(path,'security.selinux')==attrs['security.selinux']
    report.append({'path':str(path.relative_to(base)),'before_sha256':sha(old) if old is not None else None,'sha256':sha(path.read_bytes()),'uid':info.st_uid,'gid':info.st_gid,'mode':oct(stat.S_IMODE(path.stat().st_mode)),'selinux':attrs['security.selinux'].rstrip(b'\0').decode()})
def props(path,updates,remove=()):
    lines=path.read_text().splitlines()
    lines=[s for s in lines if s.partition('=')[0] not in {*updates,*remove}]
    write(path,'\n'.join(lines)+'\n# polaris development adaptation\n'+''.join(k+'='+v+'\n' for k,v in updates.items()))

system=base/'system/system';ext=base/'system_ext';product=base/'product'
write(system/'bin/logcatlog.sh',(repo/'device/polaris/diagnostics/system/bin/logcatlog.sh').read_text().replace('# Staged replacement for ziyi\'s existing logcatlog service, not installed yet.','# Bounded crash log for the polaris development image.'))
# Eliminate donor-only charger mounts (logfs/rescue) and unbounded boot/kernel
# log services; preserve its already-reviewed kernellog domain and file labels.
write(system/'etc/init/init.offline.log.rc','''on post-fs-data
    mkdir /data/local/log 0770 system system
    restorecon_recursive /data/local/log

service logcatlog /system/bin/sh /system/bin/logcatlog.sh
    class late_start
    user system
    group system log
    disabled
    seclabel u:r:kernellog:s0
    task_profiles ServiceCapacityLow

on property:sys.boot_completed=1 && property:persist.sys.polaris.diag=1
    start logcatlog

on property:persist.sys.polaris.diag=0
    stop logcatlog
''')
contexts=system/'etc/selinux/plat_property_contexts'
assert 'persist.sys.polaris.diag' not in contexts.read_text()
write(contexts,contexts.read_text()+'\npersist.sys.polaris.diag u:object_r:system_prop:s0 exact int\n')
props(system/'build.prop',{'ro.build.product':'polaris','persist.sys.polaris.diag':'1',
    'ro.product.device':'polaris','ro.product.name':'polaris',
    'ro.product.model':'MIX 2S','ro.product.marketname':'MIX 2S',
    'ro.product.manufacturer':'Xiaomi','ro.product.brand':'Xiaomi'})
props(base/'mi_ext/etc/build.prop',{'ro.product.mod_device':'polaris'})
# Keep the actual polaris vendor power HAL and thermal engine as the owners.
# These donor controllers have not been ported to 845; explicit runtime starts
# of miuibooster still require follow-up validation (disabled stops class_start).
rc=ext/'etc/init/miuibooster.rc'
write(rc,rc.read_text().replace('  class main\n','  class main\n  disabled\n',1))
rc=ext/'etc/init/perfservice.rc'
text=rc.read_text().replace('    class main\n','    class main\n    disabled\n',1)
text=text.split('on property:ro.vendor.qti.per_boot_created=1')[0]
write(rc,text+'\n# zram is owned by the polaris vendor init, not donor fstab.default.\n')

# Product is extracted independently; do not run this stage until extraction
# completed. Preserve Xiaomi applications and their original signatures.
source=product/'etc/device_features/ziyi.xml'
tree=ET.parse(source);root=tree.getroot()
updates={
 'support_smart_fps':False,'smart_fps_value':60,'defaultFps':60,
 'support_aod':False,'aod_support_keycode_goto_dismiss':False,
 'support_ir':False,'support_dual_gps':False,'support_high_resolution':False,
 'support_round_corner':False,'support_led_light':True,'support_led_color':False,
 'front_fingerprint_sensor':False,'support_low_brightness_fod':False,'fod_solution':0,
 'support_heartbeat_rate':False,'support_front_flash':False,
 'support_touchfeature_gamemode':False,'support_displayfeature_gamemode':False,
 'support_display_expert_mode':False,'support_true_color':False,
 'support_screen_enhance_engine':False,'support_videobox_display_effect':False,
 'support_dolby_version_brighten':False,'support_lhdc_offload':False,
 'support_12bit_backlight':True,'display_width':1080,'battery_capacity_typ':'3400',
 'is_18x9_ratio_screen':True,'cpu_max_freq':280,'btdebug_enabled':False,
 'support_wifi_low_latency_mode':False,'support_network_rps_mode':False,
 'support_broadcom_wapi':False,'gallery_cpu_series':'845',
}
arrays={'fpsList':['60'],'camera_exposable_role_id':[],
 'dynamic_partition_list':[],'log_partition_list':[],
 'knock_support_display_version':[],'display_version_18_knock_area':[]}
seen=set()
for el in list(root):
    name=el.get('name')
    if name in {'finger_alipay_ifaa_model','device_head_sar','device_body_sar','release_time'}:
        root.remove(el);continue
    if name in seen:root.remove(el);continue
    seen.add(name)
    if name in updates:
        value=updates[name];el.text=str(value).lower() if isinstance(value,bool) else str(value)
    if name in arrays:
        for child in list(el):el.remove(child)
        for item in arrays[name]:ET.SubElement(el,'item').text=item
assert set(updates)<=seen and set(arrays)<=seen
ET.indent(root)
write(product/'etc/device_features/polaris.xml',ET.tostring(root,encoding='utf-8',xml_declaration=True),like=source)
# Identity is per-partition; retain original build fingerprints as provenance.
# No device IDs/certificates are fabricated, and DRM/payment is not asserted.
product_updates={
 'ro.product.product.device':'polaris','ro.product.product.name':'polaris',
 'ro.product.product.model':'MIX 2S','ro.product.product.marketname':'MIX 2S',
 'ro.product.product.manufacturer':'Xiaomi','ro.miui.notch':'0',
 'persist.sys.offlinelog.bootlog':'false','persist.sys.scout_binder_gki':'false',
 'persist.sys.device_config_gki':'false','persist.sys.screen_anti_burn_enabled':'false',
 'persist.miui.extm.enable':'0','persist.sys.miui_animator_sched.bigcores':'4-7',
 'debug.config.media.video.dolby_vision_suports':'false',
 'ro.telephony.default_network':'22,22','persist.radio.multisim.config':'dsds',
 'ro.surface_flinger.enable_frame_rate_override':'false',
 'ro.surface_flinger.max_frame_buffer_acquired_buffers':'2',
 'ro.surface_flinger.max_virtual_display_dimension':'4096',
 'media.settings.xml':'/vendor/etc/media_profiles_vendor.xml',
 'ro.hardware.fp.fod':'false','ro.hardware.fp.sideCap':'false',
}
# Hardware-owned vendor properties come from the polaris vendor. Product was
# setting ziyi modem, audio and display values after vendor was loaded.
remove=[s.split('=',1)[0] for s in (product/'etc/build.prop').read_text().splitlines() if s.startswith(('ro.vendor.','persist.vendor.','vendor.')) and '=' in s]
remove+=['ro.product.ab_ota_partitions','ro.display.screen_type']
props(product/'etc/build.prop',product_updates,remove)
(p/'work/research/system-adaptation-report.json').write_text(json.dumps({'schema':1,'changes':report,'device_runtime_verified':False,'notes':['Per-app Xiaomi donor camera resources remain unvalidated; base HAL must be tested first.','No signing bypass, IMEI changes, root, autoformat or thermal disable.']},indent=2)+'\n')
print('Applied',len(report),'metadata-preserving file changes')
