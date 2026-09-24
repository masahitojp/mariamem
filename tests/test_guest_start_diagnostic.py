"""Only inert child processes; no Wasmer or MariaDB is used here."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from diagnose_guest_start import capture, launch_spec, ready_frame


class StartupDiagnostic(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def child(self, code, timeout=2):
        return capture([sys.executable, '-c', code], dict(os.environ), self.root, self.root, timeout)

    def test_fresh_launch_matches_guest_arguments(self):
        native, runtime, transfer = [self.root/n for n in ('native','runtime','transfer')]
        inherited = {'PATH':'original','WASMER_DIR':'old','CUSTOM':'preserved'}
        argv, env = launch_spec(native, runtime, transfer, inherited)
        self.assertEqual(argv, [str(native/'wasmer-headless'),'run',str(native/'mariamem.wasmu'),
                                '--no-tty','--volume',str(transfer)+':/snapshot-out'])
        self.assertEqual(env, dict(inherited, WASMER_DIR=str(runtime)))
        self.assertEqual(inherited['WASMER_DIR'], 'old')

    def test_eof_does_not_hide_natural_exit_or_stderr(self):
        r = self.child("import os,sys,time; os.close(1); time.sleep(.1); sys.stderr.write('x'*20000); sys.exit(23)")
        self.assertEqual(r['exit_code'],23)
        self.assertTrue(r['natural_exit'])
        self.assertEqual(r['diagnostic_signals'],[])
        self.assertEqual((self.root/'stderr.log').read_bytes(),b'x'*20000)
        self.assertEqual((self.root/'stdout.bin').read_bytes(),b'')

    def test_ready_stop_is_not_a_natural_failure(self):
        frame={'request_id':0,'result':{'ready':True,'api_version':2,'max_sessions':16}}
        code="import sys,struct; b="+repr(json.dumps(frame).encode())+"; sys.stdout.buffer.write(struct.pack('<I',len(b))+b); sys.stdout.buffer.flush(); sys.stdin.read()"
        r=self.child(code)
        self.assertEqual(r['ready_frame'],frame)
        self.assertEqual(r['stop_reason'],'ready_observed')
        self.assertFalse(r['natural_exit'])
        self.assertIn('SIGTERM',r['diagnostic_signals'])
        self.assertEqual(r['signal'],'SIGTERM')

    def test_timeout_is_identified(self):
        r=self.child('import time; time.sleep(20)',timeout=.05)
        self.assertEqual(r['stop_reason'],'timeout')
        self.assertFalse(r['natural_exit'])

    def test_launch_error_still_creates_capture_files(self):
        r=capture([str(self.root/'missing')],dict(os.environ),self.root,self.root,1)
        self.assertIn('diagnostic_error',r)
        self.assertIsNone(r['returncode'])
        self.assertTrue((self.root/'stdout.bin').exists())
        self.assertTrue((self.root/'stderr.log').exists())

    def test_nonframe_is_retained_without_abort(self):
        r=self.child("import sys; sys.stdout.write('not a frame'); sys.exit(7)")
        self.assertEqual(r['exit_code'],7)
        self.assertEqual((self.root/'stdout.bin').read_text(),'not a frame')
        self.assertIsNone(ready_frame(b'bad'))


if __name__ == '__main__':
    unittest.main()
