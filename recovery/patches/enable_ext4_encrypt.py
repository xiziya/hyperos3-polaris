#!/usr/bin/env python3
"""Add the polaris A15 ext4 encrypt feature to recovery's Format Data path."""
from pathlib import Path
import sys


needle = '''\tif (Needs_Metadata_Csum) {
\t\tCommand += " -O metadata_csum,64bit,extent";
\t}
\tCommand += " " + Actual_Block_Device + " " + size_str;'''
replacement = '''\tif (Needs_Metadata_Csum) {
\t\tCommand += " -O metadata_csum,64bit,extent";
\t}
\t// Polaris A15 software FBEv2 requires the ext4 encrypt feature.
\tif (Mount_Point == "/data" && File_System == "ext4") {
\t\tCommand += " -O encrypt";
\t}
\tCommand += " " + Actual_Block_Device + " " + size_str;'''


def main():
    if len(sys.argv) != 2:
        raise SystemExit('usage: enable_ext4_encrypt.py partition.cpp')
    path = Path(sys.argv[1])
    text = path.read_text()
    if 'Command += " -O encrypt"' in text:
        raise SystemExit('encrypt feature patch already present')
    if text.count(needle) != 1:
        raise SystemExit('unexpected recovery Format Data source; refusing patch')
    path.write_text(text.replace(needle, replacement))


if __name__ == '__main__':
    main()
