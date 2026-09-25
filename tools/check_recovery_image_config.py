#!/usr/bin/env python3
"""Run the real AOSP partition-image Make checks and missing-type controls.

This isolates the relevant board_config.mk checks, not the complete lunch or
Soong build. CI must still run both after this focused regression check.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile


def check(aosp, board, product):
    upstream = aosp.read_text()
    macro = 'define check_image_config\n' + upstream.split('define check_image_config\n', 1)[1].split('endef', 1)[0] + 'endef\n'
    sections = []
    for part, end in (('VENDOR', '# Now we can substitute with the real value of TARGET_COPY_OUT_PRODUCT'),
                      ('PRODUCT', '# TODO(b/135957588)'),
                      ('SYSTEM_EXT', '# Now we can substitute with the real value of TARGET_COPY_OUT_VENDOR_DLKM')):
        start = '# Now we can substitute with the real value of TARGET_COPY_OUT_' + part + '\n'
        sections.append(upstream.split(start, 1)[1].split(end, 1)[0])
    product_flags = '\n'.join(line for line in product.read_text().splitlines() if line.startswith('PRODUCT_BUILD_'))
    helpers = "to-upper = $(shell echo '$(1)' | tr a-z A-Z)\nto-lower = $(shell echo '$(1)' | tr A-Z a-z)\n"
    tail = '\n.PHONY: verify\nverify:\n\t@test -z "$(BUILDING_VENDOR_IMAGE)$(BUILDING_PRODUCT_IMAGE)$(BUILDING_SYSTEM_EXT_IMAGE)"\n'
    with tempfile.TemporaryDirectory(prefix='polaris-image-check-') as folder:
        path = Path(folder) / 'Makefile'
        def run(config):
            path.write_text(helpers + config + '\n' + product_flags + '\n' + macro + '\n'.join(sections) + tail)
            return subprocess.run(['make', '--no-print-directory', '-f', str(path), 'verify'], text=True, capture_output=True)
        config = board.read_text()
        positive = run(config)
        if positive.returncode:
            raise ValueError(positive.stdout + positive.stderr)
        controls = {}
        for part in ('PRODUCT', 'SYSTEM_EXT'):
            key = 'BOARD_' + part + 'IMAGE_FILE_SYSTEM_TYPE'
            missing = '\n'.join(line for line in config.splitlines() if not line.startswith(key + ' '))
            result = run(missing)
            controls[part] = result.returncode != 0 and key in result.stderr
            if not controls[part]:
                raise ValueError('Missing-type negative control did not fail: ' + part)
    return {'image_config_passed': True, 'unrequested_system_image_builds': False,
            'negative_controls': controls, 'full_lunch_verified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('aosp_board_config', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(check(args.aosp_board_config, root / 'recovery/polaris/BoardConfig.mk',
                           root / 'recovery/polaris/twrp_polaris.mk'), indent=2))


if __name__ == '__main__':
    main()
