#!/usr/bin/env python3
"""Re-serialize VINTF 9 inputs for an 8 reader after two real AOSP parsers agree."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


def semantic(element):
    return (element.tag, tuple(sorted(element.attrib.items())),
            (element.text or '').strip(), tuple(semantic(x) for x in element))


def normalize(source, output, schema9, schema8):
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for path in sorted(source.rglob('*.xml')):
        root = ET.parse(path).getroot()
        if root.tag not in ('manifest', 'compatibility-matrix'):
            raise ValueError(f'Unexpected VINTF document: {path}')
        flag = '--roundtrip-manifest' if root.tag == 'manifest' else '--roundtrip-matrix'
        relative = path.relative_to(source)
        target = output / relative
        target.parent.mkdir(exist_ok=True, parents=True)
        canonical9 = target.with_suffix('.9.canonical')
        subprocess.run([schema9, flag, path, canonical9], check=True, timeout=60)
        nine = ET.parse(canonical9)
        if nine.getroot().get('version') != '9.0':
            raise ValueError('Unexpected source serializer version')
        nine.getroot().set('version', '8.0')
        lowered = target.with_suffix('.8.input')
        nine.write(lowered, encoding='unicode')
        subprocess.run([schema8, flag, lowered, target], check=True, timeout=60)
        if semantic(nine.getroot()) != semantic(ET.parse(target).getroot()):
            raise ValueError(f'8/9 semantic roundtrip differs: {relative}')
        rows.append({'file': str(relative), 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                     'normalized_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                     'semantic_roundtrip_equal': True})
    if not rows:
        raise ValueError('No VINTF inputs')
    report = {'schema': 1, 'files': rows,
              'checks': ['QPR2 schema9 parser', 'A15 schema8 parser',
                         'canonical XML semantics equal except root meta version'],
              'runtime_verified': False,
              'scope': 'Standard VINTF semantics understood by the pinned parsers; no HAL API/FCM versions are lowered.'}
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'output', 'schema9', 'schema8'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    result = normalize(args.source.resolve(), args.output.resolve(), args.schema9.resolve(), args.schema8.resolve())
    print(f"Verified {len(result['files'])} VINTF documents; runtime not tested.")


if __name__ == '__main__':
    main()
