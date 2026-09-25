#!/usr/bin/env python3
"""Resolve the five audited donor/vendor duplicate property prefixes.

Preserve donor property labels and grant only the existing vendor rild reader/
writer access to those labels. Never read or write any device ID values.
"""
from collections import defaultdict

PREFIXES = {
    'persist.radio.imei': 'deviceid_prop',
    'persist.radio.meid': 'deviceid_prop',
    'ro.ril.oem.imei': 'deviceid_prop',
    'ro.ril.oem.meid': 'deviceid_prop',
    'ro.ril.miui.imei': 'miui_deviceid_prop',
}


def duplicates(files):
    entries = defaultdict(list)
    for name, text in files.items():
        for number, line in enumerate(text.splitlines(), 1):
            fields = line.split('#', 1)[0].split()
            if len(fields) < 2:
                continue
            match = fields[2] if len(fields) > 2 else 'prefix'
            if match not in ('prefix', 'exact'):
                raise ValueError('Invalid property match: ' + name)
            entries[(fields[0], match)].append((name, number, fields[1]))
    return {key: value for key, value in entries.items() if len(value) > 1}


def fix(files, policy):
    clashes = duplicates(files)
    if set(clashes) != {(name, 'prefix') for name in PREFIXES}:
        raise ValueError('Property conflicts differ from the reviewed five prefixes')
    for name, label in PREFIXES.items():
        owners = [(owner, context) for owner, _, context in clashes[(name, 'prefix')]]
        expected = [('system_ext_property_contexts', f'u:object_r:{label}:s0'),
                    ('vendor_property_contexts', 'u:object_r:vendor_deviceid_prop:s0')]
        if sorted(owners) != sorted(expected):
            raise ValueError('Unexpected property owner: ' + name)
    old_rules = ['(allow rild vendor_deviceid_prop (property_service (set)))',
                 '(allow rild vendor_deviceid_prop (file (read getattr map open)))']
    if any(rule not in policy.splitlines() for rule in old_rules):
        raise ValueError('Expected vendor rild access missing')
    vendor = '\n'.join(line for line in files['vendor_property_contexts'].splitlines()
                       if not line.split() or line.split()[0] not in PREFIXES) + '\n'
    updated = dict(files, vendor_property_contexts=vendor)
    if duplicates(updated):
        raise ValueError('Duplicate property rules remain')
    rules = [rule.replace('vendor_deviceid_prop', label)
             for label in sorted(set(PREFIXES.values())) for rule in old_rules]
    if any(rule in policy.splitlines() for rule in rules):
        raise ValueError('Access bridge already exists')
    return vendor, policy.rstrip() + '\n; Polaris donor device-ID property ownership bridge\n' + '\n'.join(rules) + '\n'
