"""Regression coverage for unofficial recovery without brand properties."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class RecoveryEnvironmentTest(unittest.TestCase):
    def run_detection(self, service='running', executable='/system/bin/recovery', fstab=True, pids='123'):
        source = (Path(__file__).resolve().parents[1] / 'device/polaris/installer/update-binary').read_text()
        block = source.split('# BEGIN recovery detection\n', 1)[1].split('# END recovery detection', 1)[0]
        with tempfile.TemporaryDirectory() as folder:
            fixture = Path(folder) / 'recovery.fstab'
            if fstab:
                fixture.write_text('/data ext4 /dev/block/by-name/userdata\n')
            block = block.replace('/etc/recovery.fstab', '"$TEST_FSTAB"')
            mocks = '''
getprop() { if [ "$1" = init.svc.recovery ]; then printf '%s' "$TEST_SERVICE"; fi; }
pidof() { printf '%s' "$TEST_PIDS"; }
readlink() { printf '%s' "$TEST_EXE"; }
'''
            env = dict(os.environ, TEST_FSTAB=str(fixture), TEST_SERVICE=service,
                       TEST_EXE=executable, TEST_PIDS=pids)
            return subprocess.run(['bash', '-c', mocks + block + '\nrecovery_environment_valid'], env=env).returncode

    def test_unbranded_system_bin_recovery(self):
        self.assertEqual(self.run_detection(), 0)

    def test_legacy_sbin_recovery(self):
        self.assertEqual(self.run_detection(executable='/sbin/recovery'), 0)

    def test_android_system_rejected(self):
        self.assertNotEqual(self.run_detection(service='stopped'), 0)

    def test_unrelated_process_rejected(self):
        self.assertNotEqual(self.run_detection(executable='/system/bin/sh'), 0)

    def test_missing_fstab_rejected(self):
        self.assertNotEqual(self.run_detection(fstab=False), 0)

    def test_missing_process_rejected(self):
        self.assertNotEqual(self.run_detection(pids=''), 0)
