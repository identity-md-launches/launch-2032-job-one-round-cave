#!/usr/bin/env python3
"""Read-only verification of an exact selected tree against an approved ZIP."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import time
import zipfile
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'zipselect'))
from zipselect import Rejected, local_path, process as select_plan


def verify(archive, tree, selected, *, expected_sha256, seconds=None,
           cancelled=None, **limits):
    """Rebuild the reference from approved bytes, never trust a saved report.

    Every archive payload is validated through ZipSelect/ZipGate/SafeZip before
    traversal. Only selected files and their implicit parents may be present.
    No writes, repairs, execution, network, environment or external paths.
    """
    if seconds is not None:
        try:
            valid = (not isinstance(seconds, bool) and isinstance(seconds, (int, float))
                     and math.isfinite(seconds) and seconds > 0)
        except OverflowError:
            valid = False
        if not valid:
            raise Rejected('seconds must be a finite positive number')
    if cancelled is not None and not callable(cancelled):
        raise Rejected('cancelled must be callable')
    started = time.monotonic()

    def checkpoint():
        if cancelled is not None and cancelled():
            raise Rejected('verification cancelled')
        if seconds is not None and time.monotonic() - started >= seconds:
            raise Rejected('verification time budget exceeded')
        return False

    checkpoint()
    root = local_path(tree)
    if not stat.S_ISDIR(root.lstat().st_mode):
        raise Rejected('verification root must be a directory')
    reference = select_plan(archive, selected, expected_sha256=expected_sha256,
                            cancelled=checkpoint, **limits)
    expected = {}
    for entry in reference['entries']:
        checkpoint()
        parts = entry['path'].split('/')
        for depth in range(1, len(parts)):
            expected['/'.join(parts[:depth])] = {'kind': 'directory'}
        expected[entry['path']] = entry
    seen, pending, checked_bytes = set(), [(root, '')], 0
    while pending:
        checkpoint()
        directory, prefix = pending.pop()
        # Stream children; refuse the first extra node, never list a whole tree.
        with os.scandir(directory) as children:
            for child in children:
                checkpoint()
                name = prefix + child.name
                entry = expected.get(name)
                if entry is None:
                    raise Rejected('unexpected path: ' + repr(name))
                metadata = child.stat(follow_symlinks=False)
                if entry['kind'] == 'directory':
                    if not stat.S_ISDIR(metadata.st_mode):
                        raise Rejected('wrong type or link: ' + repr(name))
                    pending.append((Path(child.path), name + '/'))
                else:
                    if not stat.S_ISREG(metadata.st_mode):
                        raise Rejected('wrong type or link: ' + repr(name))
                    size = entry['bytes']
                    if metadata.st_size != size:
                        raise Rejected('size differs: ' + repr(name))
                    count, digest = 0, hashlib.sha256()
                    with open(child.path, 'rb') as reader:
                        if not stat.S_ISREG(os.fstat(reader.fileno()).st_mode):
                            raise Rejected('file is no longer regular: ' + repr(name))
                        while True:
                            checkpoint()
                            chunk = reader.read(min(65536, size - count + 1))
                            if not chunk:
                                break
                            count += len(chunk)
                            if count > size:
                                raise Rejected('file grew: ' + repr(name))
                            digest.update(chunk)
                    if count != size or digest.hexdigest() != entry['sha256']:
                        raise Rejected('content differs: ' + repr(name))
                    checked_bytes += count
                seen.add(name)
    checkpoint()
    missing = expected.keys() - seen
    if missing:
        raise Rejected('missing path: ' + repr(min(missing)))
    return {'ok': True, 'mode': 'verify-selected',
            'archive_sha256': reference['archive_sha256'],
            'all_archive_payloads_checked': True, 'exact_selected_tree': True,
            'selected_files': reference['selected_files'],
            'nodes_checked': len(seen), 'bytes_checked': checked_bytes,
            'preflight': reference['preflight']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive')
    parser.add_argument('tree')
    parser.add_argument('--file', dest='selected', action='append', required=True)
    parser.add_argument('--sha256', dest='expected_sha256', required=True)
    parser.add_argument('--seconds', type=float)
    for name, default in [('entries', 1000), ('directory-bytes', 2097152),
                          ('archive-bytes', 33554432), ('nodes', 32000),
                          ('file-bytes', 16777216), ('total-bytes', 67108864),
                          ('ratio', 200), ('output-nodes', 32000),
                          ('output-bytes', 67108864)]:
        parser.add_argument('--' + name, type=int, default=default)
    args = vars(parser.parse_args())
    try:
        result = verify(**args)
    except (ValueError, OSError, zipfile.BadZipFile, NotImplementedError,
            RuntimeError, EOFError, zlib.error) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=True))
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
