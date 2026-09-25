import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from fix_deviceid_property_contexts import PREFIXES, duplicates, fix


class PropertyContextTests(unittest.TestCase):
    def fixture(self):
        return {
            'system_ext_property_contexts': '\n'.join(f'{name} u:object_r:{label}:s0' for name, label in PREFIXES.items()),
            'vendor_property_contexts': '\n'.join(f'{name} u:object_r:vendor_deviceid_prop:s0' for name in PREFIXES),
        }

    def test_fatal_duplicates_resolved_and_rild_access_preserved(self):
        files = self.fixture()
        policy = '(allow rild vendor_deviceid_prop (property_service (set)))\n(allow rild vendor_deviceid_prop (file (read getattr map open)))\n'
        vendor, result = fix(files, policy)
        self.assertFalse(duplicates(dict(files, vendor_property_contexts=vendor)))
        self.assertIn('(allow rild deviceid_prop (property_service (set)))', result)
        self.assertIn('(allow rild miui_deviceid_prop (property_service (set)))', result)
        self.assertIn(policy.strip(), result)

    def test_unreviewed_conflict_rejected(self):
        files = self.fixture()
        files['product_property_contexts'] = 'persist.radio.imei u:object_r:unexpected:s0'
        with self.assertRaises(ValueError):
            fix(files, '')

    def test_exact_and_prefix_are_distinct(self):
        self.assertFalse(duplicates({'one': 'foo u:object_r:a:s0 exact string\nfoo u:object_r:b:s0 prefix string'}))
