#!/usr/bin/env python3
"""Keep official sync/patch steps, use verified local clones for Fox sources."""
import argparse
import json
from pathlib import Path
import subprocess


def prepare(source, cache, lock_path, output):
    lock = json.loads(lock_path.read_text())
    text = source.read_text()
    for key, branch in (('recovery', 'fox_12.1'), ('vendor', 'main')):
        repo = (cache / key).resolve()
        if any(c.isspace() for c in str(repo)):
            raise ValueError('Upstream clone script requires cache paths without whitespace')
        revision = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
        if revision != lock[key]['commit']:
            raise ValueError('Cached source does not match lock: ' + key)
        branches = subprocess.check_output(
            ['git', '-C', str(repo), 'branch', '--format=%(refname:short)'],
            text=True,
        ).splitlines()
        if branch not in branches:
            subprocess.run(['git', '-C', str(repo), 'branch', branch, revision], check=True)
        elif subprocess.check_output(
            ['git', '-C', str(repo), 'rev-parse', branch], text=True
        ).strip() != revision:
            raise ValueError('Cached branch does not match lock: ' + key)
        original = 'URL="' + lock[key]['url'] + '";'
        if text.count(original) != 1:
            raise ValueError('Locked upstream sync script changed: ' + key)
        text = text.replace(original, 'URL="' + repo.as_uri() + '";')
    output.write_text(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'cache', 'lock', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    prepare(args.source, args.cache, args.lock, args.output)


if __name__ == '__main__':
    main()
