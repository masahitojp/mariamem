"""Observe a real stalled child's stderr, not mocked faulthandler calls."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class ChildDiagnostics(unittest.TestCase):
    def test_stalled_child_emits_stack_and_exits_normally(self):
        directory=Path(__file__).parent/'live_acceptance/diagnostics'
        env=dict(os.environ,PYTHONPATH=str(directory),E2E_CHILD_DIAGNOSTICS='1',PYTHONUNBUFFERED='1')
        result=subprocess.run([sys.executable,'-c','import time; time.sleep(11); print("child finished")'],
                              env=env,capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0)
        self.assertEqual(result.stdout,'child finished\n')
        self.assertIn('E2E_CHILD_DIAGNOSTICS pid=',result.stderr)
        self.assertIn('Timeout (0:00:10)!',result.stderr)
        self.assertIn('File "<string>", line 1 in <module>',result.stderr)
        env['E2E_CHILD_DIAGNOSTICS']='0'
        result=subprocess.run([sys.executable,'-c','print("normal")'],env=env,capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0)
        self.assertEqual(result.stderr,'')


if __name__=='__main__':unittest.main()
