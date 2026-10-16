#!/usr/bin/env python3
"""Behavioral tests using only disposable paths in the workspace."""
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from zipverify import Rejected, local_path, select_plan, verify


class VerificationTests(unittest.TestCase):
    def setUp(self):
        scratch = local_path('test/scratch')
        scratch.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch, prefix='zipverify-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.archive, self.tree = self.root / 'in.zip', self.root / 'tree'
        self.selected = ['docs/a', 'docs/b', 'empty']
        self.make_archive()
        select_plan(self.archive, self.selected, self.tree, **self.options)

    def make_archive(self, extra=None):
        with zipfile.ZipFile(self.archive, 'w') as archive:
            for name, data in [('docs/a', b'alpha'), ('docs/b', b'beta'),
                               ('empty', b''), ('omitted', b'not extracted'),
                               ('omitted-dir/', b'')]:
                archive.writestr(name, data)
            if extra is not None:
                archive.writestr(*extra)
        self.options = dict(expected_sha256=hashlib.sha256(self.archive.read_bytes()).hexdigest())

    def check(self, **options):
        return verify(self.archive, self.tree, self.selected, **(self.options | options))

    def test_exact_shared_parent_and_empty_file(self):
        result = self.check(output_nodes=4, output_bytes=9)
        self.assertEqual((result['nodes_checked'], result['bytes_checked']), (4, 9))
        self.assertTrue(result['all_archive_payloads_checked'])
        self.assertTrue(result['exact_selected_tree'])

    def test_same_size_changed_content(self):
        (self.tree / 'docs/a').write_bytes(b'ALPHA')
        with self.assertRaisesRegex(Rejected, 'content differs'):
            self.check()
        self.assertEqual((self.tree / 'docs/a').read_bytes(), b'ALPHA')

    def test_shorter_content(self):
        (self.tree / 'docs/a').write_bytes(b'a')
        with self.assertRaisesRegex(Rejected, 'size differs'):
            self.check()

    def test_longer_content(self):
        (self.tree / 'docs/a').write_bytes(b'alpha!')
        with self.assertRaisesRegex(Rejected, 'size differs'):
            self.check()

    def test_missing_file(self):
        (self.tree / 'empty').unlink()
        with self.assertRaisesRegex(Rejected, 'missing path'):
            self.check()

    def test_unexpected_file(self):
        (self.tree / 'extra').write_bytes(b'')
        with self.assertRaisesRegex(Rejected, 'unexpected path'):
            self.check()

    def test_unselected_archive_file_is_extra(self):
        (self.tree / 'omitted').write_bytes(b'not extracted')
        with self.assertRaisesRegex(Rejected, 'unexpected path'):
            self.check()

    def test_extra_empty_directory(self):
        (self.tree / 'extra').mkdir()
        with self.assertRaisesRegex(Rejected, 'unexpected path'):
            self.check()

    def test_file_replaced_by_directory(self):
        (self.tree / 'empty').unlink()
        (self.tree / 'empty').mkdir()
        with self.assertRaisesRegex(Rejected, 'wrong type'):
            self.check()

    def test_parent_replaced_by_file(self):
        for child in (self.tree / 'docs').iterdir():
            child.unlink()
        (self.tree / 'docs').rmdir()
        (self.tree / 'docs').write_bytes(b'')
        with self.assertRaisesRegex(Rejected, 'wrong type'):
            self.check()

    def test_file_symlink(self):
        (self.tree / 'empty').unlink()
        (self.tree / 'empty').symlink_to(self.tree / 'docs/a')
        with self.assertRaisesRegex(Rejected, 'wrong type'):
            self.check()

    def test_root_symlink(self):
        link = self.root / 'link'
        link.symlink_to(self.tree, target_is_directory=True)
        with self.assertRaisesRegex(Rejected, 'symlink'):
            verify(self.archive, link, self.selected, **self.options)

    def test_root_regular_file(self):
        with self.assertRaisesRegex(Rejected, 'root must be a directory'):
            verify(self.archive, self.archive, self.selected, **self.options)

    def test_wrong_digest(self):
        with self.assertRaisesRegex(Rejected, 'SHA-256 differs'):
            self.check(expected_sha256=hashlib.sha256(b'other approved bytes').hexdigest())

    def test_missing_approval(self):
        with self.assertRaisesRegex(Rejected, 'approved'):
            self.check(expected_sha256=None)

    def test_output_node_budget(self):
        with self.assertRaisesRegex(Rejected, 'output node limit'):
            self.check(output_nodes=3)

    def test_output_byte_budget(self):
        with self.assertRaisesRegex(Rejected, 'output byte limit'):
            self.check(output_bytes=8)

    def test_archive_budget(self):
        with self.assertRaisesRegex(Rejected, 'archive byte limit'):
            self.check(archive_bytes=20)

    def test_directory_gate_before_parser(self):
        with patch('zipfile.ZipFile', side_effect=AssertionError('parser entered')):
            with self.assertRaisesRegex(Rejected, 'entry limit'):
                self.check(entries=1)

    def test_omitted_unsafe_path(self):
        self.make_archive(('../bad', b'bad'))
        with self.assertRaisesRegex(Rejected, 'unsafe member path'):
            self.check()

    def test_omitted_symlink(self):
        info = zipfile.ZipInfo('link')
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.make_archive((info, b'docs/a'))
        with self.assertRaisesRegex(Rejected, 'link or special'):
            self.check()

    def test_omitted_corrupt_payload(self):
        raw = self.archive.read_bytes().replace(b'not extracted', b'NOT extracted', 1)
        self.archive.write_bytes(raw)
        self.options['expected_sha256'] = hashlib.sha256(raw).hexdigest()
        with self.assertRaises(zipfile.BadZipFile):
            self.check()

    def test_cancelled_without_writes(self):
        before = (self.tree / 'docs/a').read_bytes()
        with self.assertRaisesRegex(Rejected, 'cancelled'):
            self.check(cancelled=lambda: True)
        self.assertEqual((self.tree / 'docs/a').read_bytes(), before)

    def test_deadline_during_tree_verification(self):
        def fake_plan(*args, **kwargs):
            return {'entries': [], 'archive_sha256': self.options['expected_sha256']}
        with patch('zipverify.select_plan', side_effect=fake_plan), patch(
                'zipverify.time.monotonic', side_effect=[0, 0, 2]):
            with self.assertRaisesRegex(Rejected, 'time budget'):
                self.check(seconds=1)

    def test_bad_deadlines_and_callback(self):
        for value in [True, 0, -1, float('inf'), float('nan'), '1', 10**1000]:
            with self.subTest(value=repr(value)[:40]), self.assertRaises(Rejected):
                self.check(seconds=value)
        with self.assertRaises(Rejected):
            self.check(cancelled=1)

    def test_bad_selection(self):
        for selected in [[], ['unknown'], ['docs'], ['empty', 'empty'], 'empty']:
            with self.subTest(selected=selected), self.assertRaises(Rejected):
                verify(self.archive, self.tree, selected, **self.options)

    def test_workspace_confinement_without_external_read(self):
        with self.assertRaisesRegex(Rejected, 'inside the current workspace'):
            verify(self.archive, Path.cwd().parent / 'outside', self.selected, **self.options)

    def test_cli_success_and_refusal(self):
        command = [sys.executable, '-B', str(Path(__file__).with_name('zipverify.py')),
                   str(self.archive), str(self.tree), '--sha256', self.options['expected_sha256']]
        for name in self.selected:
            command += ['--file', name]
        good = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertTrue(json.loads(good.stdout)['exact_selected_tree'])
        (self.tree / 'empty').unlink()
        bad = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2)
        self.assertFalse(json.loads(bad.stdout)['ok'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
