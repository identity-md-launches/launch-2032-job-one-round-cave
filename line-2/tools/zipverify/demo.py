#!/usr/bin/env python3
"""Offline public-data extraction, verification and tamper detection."""
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile
from zipverify import Rejected, local_path, select_plan, verify


def main():
    source = local_path(Path(__file__).resolve().parents[1] / 'safezip/imd-openapi.json')
    payload = source.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == 'be142840c010710cb2a5b9e5c73e71d8e79ec4054c15661699d60bfa627be96a'
    scratch = local_path('test/scratch')
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch, prefix='zipverify-demo-') as temporary:
        root = Path(temporary)
        archive, tree = root / 'public.zip', root / 'selected'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as writer:
            writer.writestr('docs/imd/openapi.json', payload)
            writer.writestr('unselected.txt', 'Inert demonstration note.\n')
            writer.writestr('unselected-directory/', b'')
        options = dict(expected_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                       output_nodes=3, output_bytes=len(payload), seconds=10)
        selected = ['docs/imd/openapi.json']
        select_plan(archive, selected, tree, **options)
        report = verify(archive, tree, selected, **options)
        document = tree / selected[0]
        document.write_bytes(b'!' + payload[1:])
        try:
            verify(archive, tree, selected, **options)
        except Rejected as error:
            refusal = str(error)
            assert 'content differs' in refusal
        else:
            raise AssertionError('same-length content tampering was accepted')
        assert document.read_bytes() == b'!' + payload[1:]  # never repairs
        print(json.dumps({'ok': True, 'network_used': False,
                          'historical_public_capture': 'https://api.imd.fun/openapi.json',
                          'capture_bytes': len(payload), 'verification': report,
                          'same_length_tampering_refused': refusal,
                          'tampered_content_left_untouched': True}, indent=2))


if __name__ == '__main__':
    main()
