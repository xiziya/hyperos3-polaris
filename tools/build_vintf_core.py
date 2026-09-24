#!/usr/bin/env python3
"""Build a limited libvintf host harness from hash-locked AOSP sources."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

from integrate_rom import sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', choices=('8', '9'), required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--hidl-header', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    lock = json.loads((project / 'config/vintf-check-sources.json').read_text())
    spec = lock['libvintf'][args.version]
    if sha(args.archive) != spec['archive_sha256'] or sha(args.hidl_header) != lock['hidl_header']['sha256']:
        raise ValueError('VINTF build input hash mismatch')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = out / 'source'
    source.mkdir()
    with tarfile.open(args.archive) as tar:
        tar.extractall(source, filter='data')
    include = out / 'include/hidl'
    include.mkdir(parents=True)
    shutil.copyfile(args.hidl_header, include / 'metadata.h')
    files = ('parse_string parse_xml CompatibilityMatrix FQName FqInstance HalManifest '
             'HalInterface KernelConfigTypedValue KernelInfo ManifestHal ManifestInstance '
             'MatrixHal MatrixInstance MatrixKernel Regex SystemSdk TransportArch XmlFile utils').split()
    command = ['g++', '-std=c++20', '-include', 'functional', '-include', 'algorithm', '-include', 'memory',
               '-O1', '-ffunction-sections', '-fdata-sections', '-Iinclude', '-Iinclude/vintf', '-I.',
               '-I' + str(include.parent), '-I/usr/include/android', *[f + '.cpp' for f in files],
               str(project / 'tools/vintf_core_check.cpp'), '-L/usr/lib/x86_64-linux-gnu/android',
               '-Wl,-rpath,/usr/lib/x86_64-linux-gnu/android', '-Wl,--gc-sections',
               '-lbase', '-llog', '-lutils', '-ltinyxml2', '-o', str(out / 'vintf-core-check')]
    result = subprocess.run(command, cwd=source, capture_output=True, text=True, timeout=300)
    (out / 'build.txt').write_text(result.stdout + result.stderr)
    if result.returncode:
        raise SystemExit('Build failed; see local build.txt')
    report = {'schema': 1, 'source': spec, 'binary_sha256': sha(out / 'vintf-core-check'),
              'scope': 'Core VINTF XML parser, merger and manifest/matrix checks only; not full checkvintf CLI',
              'metadata_provider_stubbed': False, 'upstream_sources_modified': False}
    (out / 'build-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
