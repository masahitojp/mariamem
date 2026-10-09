"""Focused ownership/control-host tests without starting the MariaDB guest."""
from concurrent.futures import ThreadPoolExecutor
import errno
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))
import mariamem
import mariamem.snapshot as implementation

BUILD = 'a' * 64


class OwnedSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'saved'
        (self.source / 'data/empty-dir').mkdir(parents=True)
        (self.source / 'data/table').write_bytes(b'fixture')
        self.manifest = {'format': 'mariamem-cold-snapshot', 'version': 1,
                         'source_storage': 'memory', 'wasm_sha256': BUILD,
                         'entries': {'.': {'kind': 'directory'}, 'empty-dir': {'kind': 'directory'},
                                     'table': {'kind': 'file', 'bytes': 7,
                                               'sha256': hashlib.sha256(b'fixture').hexdigest()}}}
        self.write_manifest()
        self.host = self.root / 'control-host'
        self.host.write_text(f'''#!{sys.executable}
import json, os, sys
if '--snapshot-info' in sys.argv:
    print(json.dumps({{'wasm_sha256': '{BUILD}', 'snapshot_version': 1}})); sys.exit()
print(json.dumps(dict(event='ready', protocol=1, id='test', host='127.0.0.1', port=1,
                      user='root', password='', database='test', capabilities=[],
                      pid=os.getpid(), runtime_pid=os.getpid())), flush=True)
for line in sys.stdin:
    request=json.loads(line)
    print(json.dumps(dict(id=request['id'], ok=True)), flush=True)
    if request['op']=='close': break
''')
        self.host.chmod(0o700)

    def write_manifest(self):
        (self.source / 'manifest.json').write_text(json.dumps(self.manifest))

    def load(self):
        snapshot = mariamem.load_snapshot(self.source, host_binary=self.host)
        self.addCleanup(snapshot.close)
        return snapshot

    def test_capture_api_separates_temporary_and_persisted_modes(self):
        db = object.__new__(mariamem.Database)
        baseline = object()
        with patch.object(db, '_snapshot', return_value=baseline) as capture:
            self.assertIs(db.snapshot(), baseline)
            capture.assert_called_once_with(None, rollback=False, timeout=120)
            capture.reset_mock()
            self.assertIs(db.snapshot_to(self.source, rollback=True, timeout=9), baseline)
            capture.assert_called_once_with(self.source, rollback=True, timeout=9)
            capture.reset_mock()
            for operation in (lambda: db.snapshot(self.source),
                              lambda: db.snapshot(destination=self.source),
                              lambda: db.snapshot_to(), lambda: db.snapshot_to(None)):
                with self.assertRaises(TypeError): operation()
            capture.assert_not_called()

    def test_exact_verified_descriptors_survive_external_delete(self):
        saved = self.load()
        self.assertFalse(hasattr(saved, 'path'))
        self.assertFalse(hasattr(saved, 'manifest'))
        self.assertFalse(hasattr(saved, 'validate'))
        name, fd, size = saved._files[0]
        self.assertEqual(os.fstat(fd).st_nlink, 0)
        self.assertNotEqual(os.fstat(fd).st_ino, (self.source / 'data/table').stat().st_ino)
        with self.assertRaises(OSError) as error:
            os.pwrite(fd, b'x', 0)
        self.assertEqual(error.exception.errno, errno.EBADF)
        shutil.rmtree(self.source)
        command = [sys.executable, '-c', '''import json,os,sys
info=json.load(os.fdopen(int(sys.argv[-1])))
print(os.pread(info['files'][0]['fd'],7,0).decode())''']
        with patch.object(implementation.hashlib, 'sha256', side_effect=AssertionError('rehash')):
            child = saved._spawn(command, stdout=subprocess.PIPE, text=True)
            self.assertEqual(child.communicate(timeout=5)[0].strip(), 'fixture')
        saved.close()
        saved.close()
        with self.assertRaises(OSError):
            os.fstat(fd)
        with self.assertRaisesRegex(ValueError, 'closed'):
            saved._spawn(command)

    def test_created_adopts_without_copy_and_removes_temporary(self):
        temporary = tempfile.TemporaryDirectory(dir=self.root)
        root = Path(temporary.name) / 'snapshot'
        shutil.copytree(self.source, root)
        inode = (root / 'data/table').stat().st_ino
        saved = mariamem.Snapshot._created(root, {'host_binary': str(self.host)}, temporary)
        self.addCleanup(saved.close)
        self.assertEqual(os.fstat(saved._files[0][1]).st_ino, inode)
        self.assertFalse(root.exists())
        saved.close()
        self.assertFalse(Path(temporary.name).exists())

    def test_created_failure_removes_temporary(self):
        temporary = tempfile.TemporaryDirectory(dir=self.root)
        root = Path(temporary.name) / 'snapshot'
        shutil.copytree(self.source, root)
        (root / 'data/table').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'manifest mismatch'):
            mariamem.Snapshot._created(root, {'host_binary': str(self.host)}, temporary)
        self.assertFalse(Path(temporary.name).exists())

    def test_import_refuses_mismatch_and_bad_inventory(self):
        for field, value in [('wasm_sha256', 'b' * 64), ('version', True), ('version', 1.0)]:
            with self.subTest(field=field, value=value):
                original = self.manifest[field]
                self.manifest[field] = value
                self.write_manifest()
                with self.assertRaises(ValueError): self.load()
                self.manifest[field] = original
        self.write_manifest()
        (self.source / 'data/table').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'manifest mismatch'): self.load()
        (self.source / 'data/table').unlink()
        with self.assertRaisesRegex(ValueError, 'manifest mismatch'): self.load()

    def test_partial_adoption_closes_all_opened_fds(self):
        descriptors = []
        def fail(fd, *args):
            descriptors.append(fd)
            raise OSError(errno.EIO, 'read failure')
        with patch.object(implementation.os, 'pread', side_effect=fail):
            with self.assertRaisesRegex(OSError, 'read failure'): self.load()
        self.assertTrue(descriptors)
        for fd in descriptors:
            with self.assertRaises(OSError): os.fstat(fd)

    def test_partial_metadata_initialization_closes_backing(self):
        descriptors = []
        original = os.open
        def record(*args, **kwargs):
            fd = original(*args, **kwargs)
            descriptors.append(fd)
            return fd
        with patch.object(implementation.os, 'open', side_effect=record), patch.object(
                implementation.threading, 'Condition', side_effect=MemoryError('metadata failure')):
            # Avoid patching subprocess's own threading initialization.
            with patch.object(implementation, '_host_identity', return_value=(str(self.host), BUILD)):
                with self.assertRaisesRegex(MemoryError, 'metadata failure'): self.load()
        self.assertTrue(descriptors)
        for fd in set(descriptors):
            with self.assertRaises(OSError): os.fstat(fd)

    def test_host_format_and_identity_rejected_at_acquisition(self):
        invalid = [{'snapshot_version': True, 'wasm_sha256': BUILD},
                   {'snapshot_version': 2, 'wasm_sha256': BUILD},
                   {'snapshot_version': 1, 'wasm_sha256': 'invalid'}]
        for info in invalid:
            with self.subTest(info=info), patch.object(implementation.subprocess, 'run') as run:
                run.return_value.stdout = json.dumps(info)
                with self.assertRaises(ValueError): self.load()

    def test_close_waits_until_real_fd_handoff(self):
        saved = self.load()
        entered, proceed = threading.Event(), threading.Event()
        original = subprocess.Popen
        def pause(*args, **kwargs):
            entered.set()
            if not proceed.wait(5): raise AssertionError('handoff timeout')
            return original(*args, **kwargs)
        with ThreadPoolExecutor(max_workers=3) as workers:
            with patch.object(implementation.subprocess, 'Popen', side_effect=pause):
                future = workers.submit(saved._spawn, [sys.executable, '-c', ''], stdout=subprocess.PIPE)
                self.assertTrue(entered.wait(5))
                closing = workers.submit(saved.close)
                double = workers.submit(saved.close)
                self.assertFalse(closing.done())
                proceed.set()
                child = future.result(5)
                child.communicate(timeout=5)
                closing.result(5)
                double.result(5)
        self.assertEqual(saved._files, ())

    def test_path_import_cleanup_before_process_launch(self):
        imported = []
        original = mariamem.Snapshot.open
        def record(*args, **kwargs):
            saved = original(*args, **kwargs)
            imported.append(saved)
            return saved
        # An existing log file must not be overwritten; imported FDs still close.
        log = self.root / 'existing.log'
        log.write_text('keep')
        with patch.object(mariamem.Snapshot, 'open', side_effect=record):
            with self.assertRaises(mariamem.HostError):
                mariamem.start(host_binary=self.host, snapshot=self.source, log_path=log)
        self.assertEqual(log.read_text(), 'keep')
        self.assertEqual(len(imported), 1)
        self.assertTrue(imported[0]._released)
        self.assertEqual(imported[0]._files, ())

    def test_handle_and_subclass_are_not_reimported(self):
        class Specialized(mariamem.Snapshot): pass
        with Specialized.open(self.source, host_binary=self.host) as saved:
            with patch.object(mariamem.Snapshot, 'open', side_effect=AssertionError('reimport')):
                with mariamem.start(host_binary=self.host, snapshot=saved): pass
                with saved.fork(): pass
            self.assertFalse(saved._closed)

    def test_reader_start_failure_reaps_launched_process(self):
        process = []
        original = subprocess.Popen
        def capture(*args, **kwargs):
            child = original(*args, **kwargs)
            process.append(child)
            return child
        with patch.object(mariamem.subprocess, 'Popen', side_effect=capture), patch.object(
                mariamem.threading.Thread, 'start', side_effect=RuntimeError('thread start')):
            with self.assertRaises(mariamem.HostError): mariamem.start(host_binary=self.host)
        self.assertEqual(len(process), 1)
        self.assertIsNotNone(process[0].poll())
        self.assertTrue(process[0].stdin.closed and process[0].stdout.closed)


if __name__ == '__main__':
    unittest.main()
