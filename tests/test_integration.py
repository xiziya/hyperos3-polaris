import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from integrate_rom import adapt_fstab


class MountIntegrationTests(unittest.TestCase):
    def reference(self):
        lines = [f'/dev/block/by-name/{p} /{p} ext4 ro,barrier=1 wait,first_stage_mount'
                 for p in ('system', 'system_ext', 'product', 'mi_ext', 'mi_product', 'vendor')]
        lines += ['/dev/block/by-name/userdata /data ext4 noatime,barrier=0 latemount,wait,check,formattable',
                  '/dev/block/by-name/logdump /metadata ext4 noatime wait,check,formattable,first_stage_mount',
                  '/dev/block/by-name/modem /vendor/firmware_mnt vfat ro wait']
        return '\n'.join(lines) + '\n'

    def test_readonly_mounts_change_without_formatting_or_firmware_redirect(self):
        rows = [row.split() for row in adapt_fstab(self.reference()).splitlines()]
        mounts = {r[1]: r for r in rows}
        for name in ('/system', '/system_ext', '/product', '/mi_ext'):
            self.assertEqual(mounts[name][2:4], ['erofs', 'ro'])
        self.assertEqual(mounts['/data'][2:4], ['ext4', 'noatime,barrier=0'])
        self.assertEqual(mounts['/vendor/firmware_mnt'],
                         ['/dev/block/by-name/modem', '/vendor/firmware_mnt', 'vfat', 'ro', 'wait'])
        self.assertEqual(mounts['/metadata'][0], '/dev/block/by-name/logdump')
        self.assertNotIn('/mi_product', mounts)
        self.assertFalse(any('formattable' in r[4].split(',') for r in rows))

    def test_unknown_layout_and_duplicate_mounts_are_rejected(self):
        with self.assertRaises(ValueError):
            adapt_fstab(self.reference().replace('/dev/block/by-name/system ', 'system '))
        with self.assertRaises(ValueError):
            adapt_fstab(self.reference() + '/dev/block/by-name/system /system ext4 ro wait\n')


if __name__ == '__main__':
    unittest.main()
