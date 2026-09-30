#!/usr/bin/env python3
"""Patch the locked OrangeFox system-reboot path; no device I/O on host."""
from pathlib import Path
import argparse

HELPER = r'''// Polaris: explicit static misc node; do not depend on donor/default fstab.
// libbootloader_message reads/writes only the 2048-byte BCB, not all of misc.
static bool Polaris_Prepare_System_Reboot() {
    const std::string misc = "/dev/block/bootdevice/by-name/misc";
    struct stat st {};
    if (stat(misc.c_str(), &st) != 0 || !S_ISBLK(st.st_mode)) {
        LOGERR("Polaris: misc block device unavailable; cancelling system reboot.\n");
        return false;
    }
    bootloader_message before {}, empty {}, after {};
    std::string err;
    if (!read_bootloader_message_from(&before, misc, &err)) {
        LOGERR("Polaris: cannot read BCB: %s\n", err.c_str());
        return false;
    }
    if (memcmp(&before, &empty, sizeof(empty)) != 0 &&
        !write_bootloader_message_to(empty, misc, &err)) {
        LOGERR("Polaris: cannot clear BCB: %s\n", err.c_str());
        return false;
    }
    if (!read_bootloader_message_from(&after, misc, &err) ||
        memcmp(&after, &empty, sizeof(empty)) != 0) {
        LOGERR("Polaris: BCB readback failed; cancelling system reboot: %s\n", err.c_str());
        return false;
    }
    LOGINFO("Polaris: BCB cleared and verified before system reboot.\n");
    return true;
}

'''

def apply(text):
    anchor = '// reboot: Reboot the system. Return -1 on error, no return on success'
    reboot = '\t\t\tcheck_and_run_script("/system/bin/rebootsystem.sh", "reboot system");'
    if 'Polaris_Prepare_System_Reboot' in text:
        raise ValueError('System reboot patch already applied')
    if text.count(anchor) != 1 or text.count(reboot) != 1:
        raise ValueError('Unexpected upstream reboot source; refusing patch')
    text = text.replace(anchor, HELPER + anchor)
    return text.replace(reboot, reboot + '\n\t\t\tif (!Polaris_Prepare_System_Reboot()) return -1;')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    args.source.write_text(apply(args.source.read_text(encoding='utf-8')), encoding='utf-8')
