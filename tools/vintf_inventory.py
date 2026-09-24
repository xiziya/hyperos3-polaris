#!/usr/bin/env python3
"""Inventory VINTF names only; NOT a replacement for checkvintf."""
import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vendor', type=Path, required=True, help='Extracted vendor/etc/vintf')
    p.add_argument('--system', type=Path, required=True, help='Extracted system/etc/vintf')
    p.add_argument('--product', type=Path, required=True, help='Extracted product/etc/vintf')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    level = ET.parse(a.vendor / 'manifest.xml').getroot().get('target-level')
    providers = set()
    for f in a.vendor.rglob('*.xml'):
        root = ET.parse(f).getroot()
        if root.tag == 'manifest' and root.get('type') == 'device':
            providers.update(h.findtext('name') for h in root.findall('hal'))
    matrices = [a.system / f'compatibility_matrix.{level}.xml',
                a.system / 'compatibility_matrix.device.xml',
                *sorted(a.product.glob('compatibility_matrix*.xml'))]
    required, optional, kernels = [], [], []
    for f in matrices:
        if not f.exists():
            raise SystemExit(f'Missing matrix: {f}')
        root = ET.parse(f).getroot()
        for h in root.findall('hal'):
            row = {'matrix': f.name, 'name': h.findtext('name'), 'format': h.get('format'),
                   'versions': [v.text for v in h.findall('version')],
                   'provider_name_present': h.findtext('name') in providers}
            (optional if h.get('optional') == 'true' else required).append(row)
        kernels += [{'matrix': f.name, 'version': x.get('version'), 'level': x.get('level')}
                    for x in root.findall('kernel')]
    result = {'validation': 'inventory-only', 'checkvintf_pass': False, 'target_level': level,
              'required': required, 'optional': optional, 'kernel_entries': kernels,
              'note': 'Name presence does not verify version, transport, instance, framework-to-vendor matrix, SEPolicy or runtime registration.'}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'required_provider_names_absent': [r for r in required if not r['provider_name_present']],
                      'kernel_entries': kernels}, indent=2))


if __name__ == '__main__':
    main()
