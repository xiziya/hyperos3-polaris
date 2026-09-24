#!/usr/bin/env python3
"""Verify the TAS2557 unsigned-magic fix preserves ARM32/ARM64 ioctl constants."""
import argparse
import json
import struct
import subprocess
import tempfile
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kernel', type=Path, required=True)
    p.add_argument('--clang-bin', type=Path, required=True)
    a = p.parse_args()
    relative = 'techpack/audio/asoc/codecs/tas2557/tas2557-misc.h'
    original = subprocess.check_output(['git', '-C', str(a.kernel), 'show', f'HEAD:{relative}']).decode()
    fixed = original.replace('0x32353537\t', '0x32353537U\t')
    if original == fixed:
        raise SystemExit('Expected original header not found')
    names = ['SMARTPA_SPK_DAC_VOLUME', 'SMARTPA_SPK_POWER_ON', 'SMARTPA_SPK_POWER_OFF',
             'SMARTPA_SPK_SWITCH_PROGRAM', 'SMARTPA_SPK_SWITCH_CONFIGURATION',
             'SMARTPA_SPK_SWITCH_CALIBRATION', 'SMARTPA_SPK_SET_SAMPLERATE', 'SMARTPA_SPK_SET_BITRATE']
    report = {}
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        for arch in ('aarch64-linux-gnu', 'arm-linux-gnueabi'):
            blobs = []
            for label, header in [('original', original), ('fixed', fixed)]:
                (root / 'header.h').write_text(header)
                (root / 'test.c').write_text('#include <asm-generic/ioctl.h>\nstruct tas2557_priv;\n#include "header.h"\nconst unsigned int commands[] = {' + ','.join(names) + '};\n')
                flags = ['-Werror'] if label == 'fixed' else ['-Wno-shift-overflow']
                subprocess.run([str(a.clang_bin / 'clang'), f'--target={arch}', *flags,
                                '-I', str(a.kernel / 'include/uapi'), '-c', str(root / 'test.c'),
                                '-o', str(root / 'test.o')], check=True, capture_output=True)
                subprocess.run([str(a.clang_bin / 'llvm-objcopy'), '-O', 'binary', '--only-section=.rodata',
                                str(root / 'test.o'), str(root / 'test.bin')], check=True)
                blobs.append((root / 'test.bin').read_bytes())
            if len(blobs[0]) != 32 or blobs[0] != blobs[1]:
                raise SystemExit(f'{arch}: ioctl ABI changed')
            report[arch] = [f'0x{x:08x}' for x in struct.unpack('<8I', blobs[0])]
    print(json.dumps({'result': 'pass', 'commands': report}, indent=2))


if __name__ == '__main__':
    main()
