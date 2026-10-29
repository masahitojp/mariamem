"""Controlled partial-app prototype, not the mariamem SDK."""
import os
import tempfile
import unittest

class App:
    def __init__(self, events, fail=False):
        self.fd, self.path = tempfile.mkstemp(prefix="e2e-partial-")
        self.events, self.fail, self.stops = events, fail, 0
    def stop(self):
        self.stops += 1
        self.events.append("stop")
        os.close(self.fd)
        os.unlink(self.path)
        if self.fail:
            raise RuntimeError("stop failed after physical disposal")

class Registry:
    def __init__(self):
        self.apps, self.events, self.errors = [], [], []
    def register(self, app):
        if any(app is a for a in self.apps):
            raise ValueError("duplicate registration")
        self.apps.append(app)
        self.events.append("register")
    def close(self):
        apps, self.apps = self.apps, []
        for app in reversed(apps):
            try: app.stop()
            except BaseException as error: self.errors.append(error)
        self.events.extend(["live-close", "baseline-close"])

class Probe(unittest.TestCase):
    def test_partial_readiness_and_combined_failure(self):
        r=Registry();a=App(r.events,fail=True)
        original=RuntimeError("readiness failed")
        try:
            r.register(a)
            raise original
        except RuntimeError as caught:
            self.assertIs(caught,original)
            r.close()
        self.assertEqual(a.stops,1)
        self.assertEqual(r.events,["register","stop","live-close","baseline-close"])
        self.assertEqual(str(r.errors[0]),"stop failed after physical disposal")
        self.assertFalse(os.path.exists(a.path))
        with self.assertRaises(OSError): os.fstat(a.fd)
    def test_duplicate_does_not_double_stop(self):
        r=Registry();a=App(r.events);r.register(a)
        try:
            with self.assertRaises(ValueError):r.register(a)
        finally:r.close()
        self.assertEqual(a.stops,1)
    def test_interrupt_identity(self):
        r=Registry();a=App(r.events,fail=True);interrupt=KeyboardInterrupt()
        try:
            r.register(a)
            raise interrupt
        except BaseException as caught:
            r.close()
            self.assertIs(caught,interrupt)
        self.assertEqual(len(r.errors),1)
        self.assertEqual(a.stops,1)
    def test_all_partial_handles_attempted(self):
        r=Registry();a=App(r.events);b=App(r.events,fail=True)
        r.register(a);r.register(b);r.close()
        self.assertEqual((a.stops,b.stops),(1,1))
        self.assertFalse(os.path.exists(a.path));self.assertFalse(os.path.exists(b.path))
    def test_late_registration_control(self):
        r=Registry();a=App(r.events)
        try:
            r.close()
            self.assertEqual(a.stops,0) # detector must reject this missing ownership
        finally:a.stop() # probe itself must not leak its negative-control FD

if __name__=="__main__":unittest.main()
