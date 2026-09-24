#!/usr/bin/env python3
"""Produce a separate vendor overlay with two evidence-based node fixes. No flashing."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

IRQ_WRITES = ('echo 2 > /proc/irq/7/smp_affinity_list # msm_drm',
              'echo 1 > /proc/irq/493/smp_affinity_list # kgsl-3d0')


def patch_post_boot(text):
    for line in IRQ_WRITES:
        if text.splitlines().count(line) != 1:
            raise ValueError('Expected legacy IRQ assignment not found exactly once')
        text = text.replace(line + '\n', '')
    if 'setprop vendor.post_boot.parsed 1' not in text:
        raise ValueError('Required perf initialization signal is missing')
    marker = '# Tell the perf HAL'
    text = text.replace(marker, '# Preserve kernel IRQ affinity defaults; IRQ numbers vary between builds.\n\n' + marker, 1)
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--post-boot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    expected = json.loads((project / 'config/node-contracts.json').read_text())['post_boot_source_sha256']
    source = args.post_boot.read_bytes()
    source_hash = hashlib.sha256(source).hexdigest()
    if source_hash != expected:
        raise SystemExit('post-boot source hash differs from audited input; re-audit before patching')
    patched = patch_post_boot(source.decode()).encode()
    if args.output.exists():
        raise SystemExit('Use a new output directory; never overwrite the input vendor')
    shutil.copytree(project / 'device/polaris/vendor-overlay', args.output, ignore=shutil.ignore_patterns('README.md'))
    (args.output / 'bin').mkdir()
    (args.output / 'bin/init.qcom.post_boot.sh').write_bytes(patched)
    report = {'input_sha256': source_hash, 'output_sha256': hashlib.sha256(patched).hexdigest(),
              'removed_irq_numbers': [7, 493], 'perf_ready_signal_preserved': True,
              'applied_to_image': False, 'tested_on_device': False}
    (args.output / 'overlay-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Vendor overlay prepared separately; no source image or device changed.')


if __name__ == '__main__':
    main()
