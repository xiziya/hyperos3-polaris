import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / f'{name}.py')
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


inspect_package = module('inspect_package')
kernel = module('check_kernel_config')


class SafetyTests(unittest.TestCase):
    def test_sparse_size_uses_expansion_not_compressed_length(self):
        with tempfile.TemporaryDirectory() as d:
            image = Path(d) / 'system.img'
            image.write_bytes(struct.pack('<I4H4I', 0xED26FF3A, 1, 0, 28, 12, 4096, 2048, 0, 0))
            self.assertEqual(inspect_package.image_info(image)['expanded_bytes'], 8388608)

    def test_sparse_malformed_header_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            image = Path(d) / 'system.img'
            image.write_bytes(struct.pack('<I4H4I', 0xED26FF3A, 2, 0, 28, 12, 4096, 1, 0, 0))
            with self.assertRaises(ValueError):
                inspect_package.image_info(image)

    def test_disabled_ksu_does_not_hide_enabled_susfs(self):
        valid = '\n'.join(f'CONFIG_{name}=y' for name in kernel.REQUIRED)
        self.assertEqual(kernel.validate(valid + '\n# CONFIG_KSU is not set'), [])
        self.assertTrue(kernel.validate(valid + '\nCONFIG_KSU_SUSFS=y'))
        self.assertTrue(kernel.validate(valid + '\nCONFIG_KPM=m'))

    def test_missing_radio_wifi_prerequisite_rejected(self):
        valid = '\n'.join(f'CONFIG_{name}=y' for name in kernel.REQUIRED if name != 'QCA_CLD_WLAN')
        self.assertTrue(kernel.validate(valid))

    def test_protected_edl_entries_and_missing_files_reported(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / 'rawprogram0.xml').write_text('<data><program label="persist" physical_partition_number="0" start_sector="1" num_partition_sectors="4" SECTOR_SIZE_IN_BYTES="4096" filename="persist.img"/></data>')
            result = inspect_package.inspect(p)
            self.assertEqual(result['protected_program_entries'], ['persist'])
            self.assertEqual(result['missing_program_files'], ['persist.img'])


if __name__ == '__main__':
    unittest.main()
