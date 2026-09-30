"""Compile the exact reboot guard with fake BCB I/O; never touch devices."""
import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('reboot_patch', ROOT/'recovery/patches/fix_polaris_system_reboot.py')
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)

class RecoveryRuntimeTests(unittest.TestCase):
    def test_fstab_formats_agree_without_exposing_misc_to_wipe(self):
        ui = [l.split(maxsplit=3) for l in (ROOT/'recovery/polaris/recovery.fstab').read_text().splitlines() if l and not l.startswith('#')]
        android = [l.split() for l in (ROOT/'recovery/polaris/fstab.android').read_text().splitlines() if l and not l.startswith('#')]
        self.assertTrue(all(len(row) == 5 for row in android))
        self.assertTrue(all((row[1],row[2],row[0]) in {(u[0],u[1],u[2]) for u in ui} for row in android))
        misc = [row for row in ui if row[0] == '/misc']
        self.assertEqual(len(misc), 1)
        for flag in ('backup=0', 'flashimg=0', 'wipeingui=0'): self.assertIn(flag, misc[0][3])
        for mount in ('/vendor','/system_root','/system_ext','/product','/mi_ext','/mi_product'):
            self.assertIn((mount,'erofs'), {(u[0],u[1]) for u in ui})

    def test_battery_enables_legacy_before_custom_path(self):
        cfg = (ROOT/'recovery/polaris/BoardConfig.mk').read_text()
        self.assertIn('TW_USE_LEGACY_BATTERY_SERVICES := true', cfg)
        self.assertIn('TW_CUSTOM_BATTERY_PATH := "/sys/class/power_supply/battery"', cfg)

    def test_patch_refuses_changed_or_already_patched_source(self):
        source = '// reboot: Reboot the system. Return -1 on error, no return on success\n\t\t\tcheck_and_run_script("/system/bin/rebootsystem.sh", "reboot system");'
        result = patch.apply(source)
        self.assertIn('if (!Polaris_Prepare_System_Reboot()) return -1;', result)
        for bad in (result, source + source, ''):
            with self.assertRaises(ValueError): patch.apply(bad)

    @unittest.skipUnless(shutil.which('g++'), 'g++ required for executable BCB negative tests')
    def test_compiled_guard_success_and_io_failures(self):
        preamble = r'''
#include <cassert>
#include <cstring>
#include <string>
#include <sys/stat.h>
#define LOGERR(...) ((void)0)
#define LOGINFO(...) ((void)0)
struct bootloader_message { unsigned char bytes[2048]; };
static unsigned char storage[65536];
static int mode, writes, reads;
int stat(const char*, struct stat* st) noexcept {
    if (mode == 1) return -1;
    st->st_mode = mode == 2 ? S_IFREG : S_IFBLK; return 0;
}
bool read_bootloader_message_from(bootloader_message* b, const std::string& p, std::string*) {
    assert(p == "/dev/block/bootdevice/by-name/misc");
    ++reads;
    if (mode == 3 || (mode == 5 && reads == 2)) return false;
    memcpy(b, storage, sizeof(*b)); return true;
}
bool write_bootloader_message_to(const bootloader_message& b, const std::string&, std::string*) {
    ++writes; if (mode == 4) return false;
    if (mode != 6) memcpy(storage, &b, sizeof(b));
    return true;
}
'''
        main = r'''
int main() {
    for (mode = 0; mode <= 6; ++mode) {
        memset(storage, 0xa5, sizeof(storage)); reads = writes = 0;
        bool ok = Polaris_Prepare_System_Reboot();
        assert(ok == (mode == 0));
        for (int i=2048; i<65536; ++i) assert(storage[i] == 0xa5);
        if (mode <= 3 && mode != 0) assert(writes == 0);
        if (ok) for (int i=0; i<2048; ++i) assert(storage[i] == 0);
    }
    mode=0; reads=writes=0; memset(storage,0,2048);
    assert(Polaris_Prepare_System_Reboot()); assert(writes==0);
}
'''
        with tempfile.TemporaryDirectory() as temp:
            src=Path(temp)/'guard.cpp'; exe=Path(temp)/'guard'
            src.write_text(preamble+patch.HELPER+main)
            subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror',str(src),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)

if __name__ == '__main__': unittest.main()
