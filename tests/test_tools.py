import importlib.util
import gzip
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / f'{name}.py')
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


inspect_package = module('inspect_package')
kernel = module('check_kernel_config')
recovery = module('inspect_recovery')
sepolicy = module('audit_sepolicy')
vendor_overlay = module('prepare_vendor_overlay')


class SafetyTests(unittest.TestCase):
    def test_vendor_irq_fix_preserves_perf_init_and_rejects_other_input(self):
        source = '\n'.join((*vendor_overlay.IRQ_WRITES, '# Tell the perf HAL',
                            'setprop vendor.post_boot.parsed 1', ''))
        patched = vendor_overlay.patch_post_boot(source)
        self.assertNotIn('/proc/irq/', patched)
        self.assertIn('setprop vendor.post_boot.parsed 1', patched)
        with self.assertRaises(ValueError):
            vendor_overlay.patch_post_boot(source.replace('/irq/493/', '/irq/494/'))
        with self.assertRaises(ValueError):
            vendor_overlay.patch_post_boot(patched)

    def test_recovery_truncated_archive_rejected(self):
        name = b'etc/recovery.fstab\0'
        fields = [0, 0o100644, 0, 0, 1, 0, 128, 0, 0, 0, 0, len(name), 0]
        archive = b'070701' + b''.join(f'{x:08x}'.encode() for x in fields) + name
        archive += b'\0' * (-len(archive) % 4)
        with self.assertRaisesRegex(ValueError, 'Truncated'):
            list(recovery.cpio_entries(archive))

    def test_recovery_decompression_limit(self):
        data = gzip.compress(b'x' * 1024)
        with self.assertRaisesRegex(ValueError, 'limit'):
            recovery.unpack_gzip(data, 512)

    def test_missing_policy_mapping_cannot_pass(self):
        with tempfile.TemporaryDirectory() as d:
            roots = {name: Path(d) / name for name in ('system', 'system_ext', 'product', 'vendor')}
            for path in roots.values():
                path.mkdir()
            (roots['vendor'] / 'plat_sepolicy_vers.txt').write_text('202504\n')
            report = sepolicy.audit(roots)
            self.assertFalse(report['compile_passed'])
            self.assertFalse(report['precompiled_usable_by_hash'])
            self.assertIn('system/mapping/202504.cil', report['missing'])

    def test_gpt_crc_and_capacity(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'gpt_main0.bin'
            data = bytearray(3 * 4096)
            entry = bytearray(128)
            entry[0] = 1
            struct.pack_into('<QQ', entry, 32, 100, 109)
            entry[56:70] = 'product'.encode('utf-16le')
            data[8192:8320] = entry
            header = bytearray(92)
            header[:8] = b'EFI PART'
            struct.pack_into('<I', header, 12, 92)
            struct.pack_into('<QIII', header, 72, 2, 1, 128, zlib.crc32(entry))
            struct.pack_into('<I', header, 16, zlib.crc32(header))
            data[4096:4188] = header
            p.write_bytes(data)
            self.assertEqual(inspect_package.gpt_info(p)['partitions'][0]['bytes'], 40960)
            data[8192] ^= 1
            p.write_bytes(data)
            with self.assertRaises(ValueError):
                inspect_package.gpt_info(p)

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
