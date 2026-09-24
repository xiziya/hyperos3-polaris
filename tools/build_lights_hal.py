#!/usr/bin/env python3
"""Build the API35 Lights candidate from hash-locked local inputs (Linux)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile
import zipfile


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def check_inputs(inputs, lock):
    for key, spec in lock['files'].items():
        if digest(inputs[key]) != spec['sha256']:
            raise ValueError(f'Input hash mismatch: {key}')
    for key, spec in lock['trees'].items():
        root = Path(inputs[key])
        for name, expected in spec['files'].items():
            if digest(root / name) != expected:
                raise ValueError(f'Source hash mismatch: {key}/{name}')


def check_toolchain(archive, root):
    """Verify extracted toolchain bytes against the already checked official ZIP."""
    prefix = 'android-ndk-r27c/toolchains/llvm/prebuilt/linux-x86_64/'
    count = 0
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            if not info.filename.startswith(prefix) or info.is_dir():
                continue
            relative = info.filename[len(prefix):]
            if '..' in Path(relative).parts:
                raise ValueError('Unexpected toolchain archive path')
            path = root / relative
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                if not path.is_symlink() or os.readlink(path).encode() != z.read(info):
                    raise ValueError(f'Toolchain symlink mismatch: {relative}')
            else:
                if path.is_symlink():
                    raise ValueError(f'Unexpected toolchain symlink: {relative}')
                with z.open(info) as stream:
                    expected = hashlib.file_digest(stream, 'sha256').hexdigest()
                if digest(path) != expected:
                    raise ValueError(f'Toolchain hash mismatch: {relative}')
            count += 1
    if count < 100:
        raise ValueError('Incomplete NDK toolchain archive')
    return count


def unpack(archive, target):
    target.mkdir()
    with tarfile.open(archive) as tar:
        # AOSP's .clang-format points outside libbase into build/soong.
        # This standalone compile needs regular files/directories only.
        members = [m for m in tar.getmembers() if m.isfile() or m.isdir()]
        tar.extractall(target, members=members, filter='data')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True, help='Local path map; see docs/lights-hal.md')
    parser.add_argument('--output', type=Path, required=True, help='New directory on a disk with build space')
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    lock_path = project / 'config/lights-build-sources.json'
    lock = json.loads(lock_path.read_text())
    inputs = json.loads(args.inputs.read_text())
    out = args.output.resolve()
    if out.exists():
        raise SystemExit('Output must not exist; source inputs are never modified')
    check_inputs(inputs, lock)
    toolchain = Path(inputs['toolchain']).resolve()
    print('Verifying extracted NDK against locked official archive', flush=True)
    checked = check_toolchain(inputs['ndk_archive'], toolchain)
    out.mkdir(parents=True)
    build = out / 'build'
    build.mkdir()
    base = build / 'libbase'
    headers = build / 'include'
    unpack(inputs['libbase_archive'], base)
    unpack(inputs['binder_headers_archive'], headers)
    shutil.copyfile(inputs['llndk_header'], headers / 'android/llndk-versioning.h')
    host = build / 'host'
    host.mkdir()
    shutil.copyfile(inputs['aidl'], host / 'aidl')
    (host / 'aidl').chmod(0o755)
    shutil.copyfile(inputs['aidl_libcxx'], host / 'libc++.so')
    gen = build / 'generated'
    gen.mkdir()
    # Copy only locked source files; extra files in a checkout cannot enter a build.
    for key in ('light', 'light_api'):
        for name in lock['trees'][key]['files']:
            dst = build / key / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(inputs[key]) / name, dst)
    light, api = build / 'light', build / 'light_api'
    env = dict(os.environ, LD_LIBRARY_PATH=str(host), SOURCE_DATE_EPOCH='1735689600', LC_ALL='C')
    interface_hash = (api / '.hash').read_text().splitlines()[-1]
    commands = []

    def run(command):
        commands.append(list(map(str, command)))
        subprocess.run(commands[-1], check=True, env=env)

    run([host / 'aidl', '--lang=ndk', '--structured', '--stability=vintf', '--version=2',
         '--hash=' + interface_hash, '--min_sdk_version=35', '--out=' + str(gen),
         '--header_out=' + str(headers), '-I' + str(api),
         *sorted((api / 'android/hardware/light').glob('*.aidl'))])
    sources = [*sorted(light.glob('*.cpp')), *sorted(gen.rglob('*.cpp')),
               *[base / f for f in ('logging.cpp', 'strings.cpp', 'stringprintf.cpp',
                                   'threads.cpp', 'file.cpp', 'posix_strerror_r.cpp')]]
    binary = out / 'android.hardware.light-service.polaris'
    clang = toolchain / 'bin/aarch64-linux-android35-clang++'
    run([clang, '-std=c++20', '-O2', '-fPIE', '-pie', '-fvisibility=hidden',
         '-ffunction-sections', '-fdata-sections', '-fstack-protector-strong',
         '-D_FORTIFY_SOURCE=2', '-D_FILE_OFFSET_BITS=64', '-DBINDER_STABILITY_SUPPORT',
         '-D__ANDROID_VENDOR__', '-D__ANDROID_VENDOR_API__=202404', '-static-libstdc++',
         '-ffile-prefix-map=' + str(build) + '=/polaris-lights',
         '-I' + str(headers), '-I' + str(base / 'include'), '-I' + str(light),
         *sources, inputs['binder_library'], '-llog', '-Wl,--gc-sections',
         '-Wl,-z,relro,-z,now', '-Wl,--build-id=sha1', '-o', binary])
    # Exercise the actual upstream conversion implementation, not a Python copy.
    run(['c++', '-std=c++17', '-O2', '-I' + str(light), light / 'Utils.cpp',
         project / 'tests/lights_brightness.cpp', '-o', build / 'brightness-test'])
    run([build / 'brightness-test'])
    readelf = toolchain / 'bin/llvm-readelf'
    elf = subprocess.check_output([readelf, '--notes', '--dynamic', '--version-info', binary], text=True)
    (out / 'elf-details.txt').write_text(elf)
    licenses = out / 'licenses'
    licenses.mkdir()
    shutil.copyfile(base / 'NOTICE', licenses / 'Apache-2.0.txt')
    shutil.copyfile(toolchain / 'NOTICE', licenses / 'NDK-NOTICE.txt')
    (licenses / 'sources.txt').write_text(
        'LineageOS Lights: Apache-2.0; upstream copyright notices preserved in build/light.\n'
        'AOSP light AIDL, libbase and Binder headers: Apache-2.0.\n'
        'NDK libc++ is statically linked; see NDK-NOTICE.txt for LLVM and other notices.\n')
    report = {'schema': 1, 'target': 'polaris Android 15 / SDK35',
              'source_lock_sha256': digest(lock_path), 'binary_sha256': digest(binary),
              'api': 35, 'aidl_version': 2, 'aidl_hash': interface_hash,
              'ndk_files_verified': checked, 'commands': commands,
              'brightness_test_passed': True, 'vintf_stability_enabled': True,
              'integrated_into_vendor': False, 'runtime_verified': False}
    (out / 'build-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Built {binary}; candidate only, not installed or runtime validated')


if __name__ == '__main__':
    main()
