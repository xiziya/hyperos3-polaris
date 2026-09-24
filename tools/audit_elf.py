#!/usr/bin/env python3
"""Inventory ELF dependencies without running binaries (requires pyelftools)."""
import argparse
import hashlib
import io
import json
from collections import defaultdict
from pathlib import Path
from elftools.elf.elffile import ELFFile


def inspect(path):
    # pyelftools performs many small seeks. A memory buffer avoids minutes of
    # per-read overhead when input files reside on a Windows/WSL mount.
    with io.BytesIO(path.read_bytes()) as stream:
        if stream.read(4) != b'\x7fELF':
            return None
        stream.seek(0)
        elf = ELFFile(stream)
        dynamic = elf.get_section_by_name('.dynamic')
        needed = [tag.needed for tag in dynamic.iter_tags() if tag.entry.d_tag == 'DT_NEEDED'] if dynamic else []
        exports, imports = set(), set()
        version_needs, version_defs = {}, {}
        section = elf.get_section_by_name('.gnu.version_r')
        if section:
            for version, auxiliaries in section.iter_versions():
                for aux in auxiliaries:
                    version_needs[aux['vna_other'] & 0x7fff] = (version.name, aux.name)
        section = elf.get_section_by_name('.gnu.version_d')
        if section:
            for version, auxiliaries in section.iter_versions():
                version_defs[version['vd_ndx'] & 0x7fff] = next(auxiliaries).name
        versions = elf.get_section_by_name('.gnu.version')
        required_versions, exported_versions, global_exports = [], set(), set()
        symbols = elf.get_section_by_name('.dynsym')
        if symbols:
            for index, symbol in enumerate(symbols.iter_symbols()):
                if not symbol.name:
                    continue
                vid = versions.get_symbol(index)['ndx'] if versions else None
                vid = vid & 0x7fff if isinstance(vid, int) else None
                if symbol['st_shndx'] == 'SHN_UNDEF':
                    if symbol['st_info']['bind'] != 'STB_WEAK':
                        imports.add(symbol.name)
                        if vid in version_needs:
                            library, version = version_needs[vid]
                            required_versions.append((library, symbol.name, version))
                elif symbol['st_info']['bind'] in ('STB_GLOBAL', 'STB_WEAK', 'STB_GNU_UNIQUE'):
                    if symbol['st_other']['visibility'] in ('STV_DEFAULT', 'STV_PROTECTED'):
                        exports.add(symbol.name)
                        if vid in version_defs:
                            exported_versions.add((symbol.name, version_defs[vid]))
                        elif not versions or versions.get_symbol(index)['ndx'] == 'VER_NDX_GLOBAL':
                            global_exports.add(symbol.name)
        return {'path': path, 'class': elf.elfclass, 'machine': elf['e_machine'],
                'needed': needed, 'exports': exports, 'imports': imports,
                'required_versions': required_versions, 'exported_versions': exported_versions,
                'global_exports': global_exports, 'defined_versions': set(version_defs.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--search', action='append', required=True, help='label=library-directory; earlier labels have precedence')
    parser.add_argument('--binary', action='append', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    providers = defaultdict(list)
    counts = {}
    for spec in args.search:
        label, directory = spec.split('=', 1)
        directory = Path(directory)
        counts[label] = 0
        # Explicit search directories only: do not accidentally select hwasan,
        # bootstrap, hw, or unrelated namespace variants by recursive basename.
        for path in sorted(directory.glob('*')):
            # Never follow Android absolute symlinks into the build host.
            if path.is_symlink() or not path.is_file():
                continue
            entry = inspect(path)
            if entry:
                entry['label'] = f'{label}/{path.relative_to(directory).as_posix()}'
                providers[(path.name, entry['class'], entry['machine'])].append(entry)
                counts[label] += 1
    rows = []
    for binary in args.binary:
        root = inspect(binary)
        if not root:
            raise ValueError(f'{binary.name} is not ELF')
        visited = {str(binary): root}
        missing, candidates = set(), {}
        pending = [root]
        while pending:
            current = pending.pop()
            for name in current['needed']:
                matches = providers.get((name, current['class'], current['machine']), [])
                if not matches:
                    missing.add(name)
                    continue
                selected = matches[0]
                candidates[name] = [entry['label'] for entry in matches]
                key = str(selected['path'])
                if key not in visited:
                    visited[key] = selected
                    pending.append(selected)
        visible = set().union(*(entry['exports'] for entry in visited.values()))
        undefined = sorted(root['imports'] - visible)
        dependent_undefined = {entry.get('label', binary.name): sorted(entry['imports'] - visible)
                               for entry in visited.values() if entry['imports'] - visible}
        version_issues, global_fallbacks = [], []
        for library, symbol, version in root['required_versions']:
            matches = providers.get((library, root['class'], root['machine']), [])
            if matches and (symbol, version) in matches[0]['exported_versions']:
                continue
            # Android 15 linker_soinfo.cpp check_symbol_version accepts a
            # global definition when the requested version is absent in DSO.
            # Record the fallback distinctly from an exact version match.
            if (matches and version not in matches[0]['defined_versions']
                    and symbol in matches[0]['global_exports']):
                global_fallbacks.append({'library': library, 'symbol': symbol, 'requested_version': version})
            else:
                version_issues.append({'library': library, 'symbol': symbol, 'version': version})
        rows.append({'binary': binary.name, 'sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
                     'elf_class': root['class'], 'machine': root['machine'],
                     'direct_needed': root['needed'], 'candidate_dependency_count': len(visited) - 1,
                     'missing_in_inventory': sorted(missing),
                     'root_undefined_in_inventory': undefined,
                     'dependent_undefined_in_inventory': dependent_undefined,
                     'root_named_version_requirements_checked': len(root['required_versions']),
                     'root_named_version_issues': version_issues,
                     'root_android_global_version_fallbacks': global_fallbacks,
                     'multiple_candidates': {name: values for name, values in candidates.items() if len(values) > 1},
                     'linker_namespace_verified': False, 'symbol_versions_verified': False,
                     'runtime_verified': False})
    report = {'schema': 1, 'library_counts': counts, 'binaries': rows,
              'note': 'Candidate paths only, not a linker verdict. APEX/VNDK namespaces, dlopen dependencies, symbol versions, CPU instructions and HAL registration still need validation.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps([{'binary': row['binary'], 'missing': row['missing_in_inventory'],
                       'undefined_count': len(row['root_undefined_in_inventory'])} for row in rows], indent=2))


if __name__ == '__main__':
    main()
