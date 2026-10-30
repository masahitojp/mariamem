"""Owned-entry fault controls; controlled Live, real Python exception semantics."""
import contextlib
import threading
import unittest
from unittest.mock import patch

from mariamem.e2e import BrowserEntry, Config, EntryError


class Resource:
    def __init__(self, events, name, fail=False):
        self.events, self.name, self.fail = events, name, fail
        self.count = 0
    def close(self):
        self.count += 1
        self.events.append(self.name)
        if self.fail:
            raise RuntimeError(self.name)


class Live(Resource):
    def __init__(self, events):
        super().__init__(events, "live.close")
        self.generation = 0
        self.reset_error = None
    def connection_info(self):
        return {"host": "127.0.0.1", "port": 42}
    def status(self):
        return {"state": "ready", "generation": self.generation}
    def reset(self, **kwargs):
        self.events.append("reset")
        if self.reset_error:
            raise self.reset_error
        self.generation += 1


class App:
    identity, base_url = "app-1", "http://127.0.0.1:1234"
    def __init__(self, events):
        self.events = events
        self.fail_stop = self.fail_quiesce = False
    def quiesce_and_retire(self, ctx):
        self.events.append("quiesce")
        if self.fail_quiesce:
            raise RuntimeError("busy pool")
    def stop_reap(self, ctx):
        self.events.append("stop")
        if self.fail_stop:
            raise RuntimeError("stop failed")


class TestEntry(unittest.TestCase):
    def harness(self, **overrides):
        events = []
        live = Live(events)
        source = Resource(events, "source.close")
        baseline = Resource(events, "baseline.close")
        source.wait_disconnected = lambda **kw: events.append("disconnect")
        source.snapshot = lambda **kw: baseline
        baseline.live = lambda: live
        app = App(events)
        def start(ctx, target, register):
            register(app)
            events.append("start")
            return app
        cfg = dict(prepare=lambda db: events.append("prepare"), start_ready=start, sole_work_source=True)
        cfg.update(overrides)
        owner = BrowserEntry(Config(**cfg))
        self.addCleanup(lambda: owner.close() if not owner._started else None)
        return owner, source, baseline, live, app, events

    @contextlib.contextmanager
    def opened(self, **overrides):
        values = self.harness(**overrides)
        with patch("mariamem.start", return_value=values[1]):
            with values[0]:
                yield values

    def browser(self, events, fail_context=False, fail_page=False):
        context = Resource(events, "context.close", fail_context)
        def new_page():
            events.append("page")
            if fail_page:
                raise RuntimeError("page failed")
            return object()
        context.new_page = new_page
        browser = type("Browser", (), {"new_context": lambda _: context})()
        return browser, context

    def test_first_and_next_case_order(self):
        with self.opened() as (o, source, baseline, live, app, events):
            browser, context = self.browser(events)
            with o.case(browser=browser) as c:
                self.assertIs(c.app, app)
                events.append("body")
            with o.case(browser=browser):
                pass
            self.assertEqual(live.generation, 2)
            self.assertEqual(events[:7], ["prepare", "disconnect", "start", "quiesce", "reset", "page", "body"])
        self.assertEqual(events[-4:], ["stop", "live.close", "baseline.close", "source.close"])

    def test_close_waits_for_active_case_before_disposal(self):
        with self.opened() as (o, source, baseline, live, _, events):
            waiting = threading.Event()
            errors = []
            original_wait = o._condition.wait
            def observed_wait(timeout=None):
                waiting.set()
                return original_wait(timeout)
            def close():
                try:
                    o.close()
                except BaseException as error:
                    errors.append(error)
            browser, _ = self.browser(events)
            with patch.object(o._condition, "wait", side_effect=observed_wait):
                worker = threading.Thread(target=close)
                with o.case(browser=browser):
                    worker.start()
                    self.assertTrue(waiting.wait(2), "close never waited for case")
                    self.assertNotIn("stop", events)
                    self.assertEqual((source.count, baseline.count, live.count), (0, 0, 0))
                worker.join(2)
                self.assertFalse(worker.is_alive(), "close did not join after case exit")
            self.assertEqual(errors, [])
            self.assertEqual(events[-4:], ["stop", "live.close", "baseline.close", "source.close"])
            self.assertEqual((source.count, baseline.count, live.count), (1, 1, 1))

    def test_close_timeout_preserves_active_case_until_explicit_cleanup(self):
        with self.opened(cleanup_timeout=.01) as (o, source, baseline, live, _, events):
            errors = []
            def close():
                try:
                    o.close()
                except BaseException as error:
                    errors.append(error)
            browser, _ = self.browser(events)
            with o.case(browser=browser):
                worker = threading.Thread(target=close)
                worker.start()
                worker.join(2)
                self.assertFalse(worker.is_alive())
                self.assertEqual(len(errors), 1)
                self.assertIsInstance(errors[0], EntryError)
                self.assertEqual(errors[0].stage, "close_wait")
                self.assertNotIn("stop", events)
                self.assertEqual(live.count, 0)
            with self.assertRaises(EntryError):
                with o.case(browser=browser):
                    self.fail("admitted after close timeout")
            o.close()
            self.assertEqual((source.count, baseline.count, live.count), (1, 1, 1))

    def test_ordinary_assertion_allows_next(self):
        with self.opened() as (o, _, _, live, _, events):
            b, _ = self.browser(events)
            with self.assertRaisesRegex(AssertionError, "original"):
                with o.case(browser=b):
                    raise AssertionError("original")
            with o.case(browser=b):
                pass
            self.assertEqual(live.generation, 2)

    def test_setup_failure_stops_future(self):
        for stage in ("quiesce", "reset", "page"):
            with self.subTest(stage=stage), self.opened() as (o, _, _, live, app, events):
                app.fail_quiesce = stage == "quiesce"
                if stage == "reset":
                    live.reset_error = RuntimeError("replacement failed")
                b, context = self.browser(events, fail_page=stage == "page")
                with self.assertRaises(EntryError):
                    with o.case(browser=b):
                        self.fail("body admitted")
                count = live.generation
                with self.assertRaises(EntryError):
                    with o.case(browser=b):
                        self.fail("later body admitted")
                self.assertEqual(live.generation, count)
                if stage == "page":
                    self.assertEqual(context.count, 1)

    def test_cleanup_debt_and_interrupt_identity(self):
        with self.opened() as (o, _, _, _, _, events):
            b, _ = self.browser(events, fail_context=True)
            interrupt = KeyboardInterrupt()
            with self.assertRaises(KeyboardInterrupt) as caught:
                with o.case(browser=b):
                    raise interrupt
            self.assertIs(caught.exception, interrupt)
            self.assertIsNotNone(interrupt.__cause__)
            with self.assertRaises(EntryError):
                with o.case(browser=b):
                    pass

    def test_overlap_no_reset_and_no_close_under_case(self):
        with self.opened() as (o, _, _, live, _, events):
            b, _ = self.browser(events)
            with o.case(browser=b):
                with self.assertRaises(EntryError):
                    with o.case(browser=b):
                        pass
                with self.assertRaises(EntryError):
                    o.close()
                self.assertEqual(live.generation, 1)
            with o.case(browser=b):
                pass

    def test_partial_start_and_all_cleanup_attempts(self):
        o, source, baseline, live, app, events = self.harness()
        original = RuntimeError("readiness")
        def broken(ctx, target, register):
            register(app)
            raise original
        o.config = Config(prepare=lambda db: None, start_ready=broken, sole_work_source=True)
        app.fail_stop = live.fail = baseline.fail = source.fail = True
        with patch("mariamem.start", return_value=source):
            with self.assertRaises(BaseExceptionGroup) as caught:
                with o:
                    self.fail("owner admitted")
        self.assertIs(caught.exception.exceptions[0], original)
        cleanup = caught.exception.exceptions[1]
        self.assertEqual([str(e) for e in cleanup.exceptions],
                         ["stop failed", "live.close", "baseline.close", "source.close"])
        self.assertEqual(events[-4:], ["stop", "live.close", "baseline.close", "source.close"])
        with self.assertRaises(BaseExceptionGroup):
            o.close()
        self.assertEqual(live.count, 1)
        self.assertEqual((baseline.count, source.count), (1, 1))

    def test_live_creation_error_keeps_baseline_cleanup_failures(self):
        o, source, baseline, live, _, events = self.harness()
        original = RuntimeError("Live creation failed after its own cleanup")
        def failed_live():
            raise original
        baseline.live = failed_live
        baseline.fail = source.fail = True
        with patch("mariamem.start", return_value=source):
            with self.assertRaises(BaseExceptionGroup) as caught:
                with o:
                    self.fail("owner admitted")
        self.assertIs(caught.exception.exceptions[0], original)
        self.assertEqual([str(e) for e in caught.exception.exceptions[1].exceptions],
                         ["baseline.close", "source.close"])
        self.assertNotIn("start", events)
        self.assertEqual(events[-2:], ["baseline.close", "source.close"])
        self.assertEqual((live.count, baseline.count, source.count), (0, 1, 1))

    def test_quiesce_deadline_stops_reset_and_cleanup_has_fresh_context(self):
        with self.opened() as (o, _, _, live, app, events):
            contexts = []
            def expired(ctx):
                contexts.append(ctx)
                ctx.deadline = 0
            def stop(ctx):
                ctx.check()
                self.assertIsNot(ctx, contexts[0])
                events.append("stop")
            app.quiesce_and_retire, app.stop_reap = expired, stop
            browser, _ = self.browser(events)
            with self.assertRaises(EntryError) as caught:
                with o.case(browser=browser):
                    self.fail("expired hook admitted body")
            self.assertIsInstance(caught.exception.__cause__, TimeoutError)
            with self.assertRaises(EntryError):
                with o.case(browser=browser):
                    self.fail("expired hook admitted later body")
            self.assertEqual(live.generation, 0)
        self.assertEqual(events[-4:], ["stop", "live.close", "baseline.close", "source.close"])

    def test_partial_source_and_prepare_failure(self):
        o, source, _, _, _, events = self.harness(prepare=lambda db: (_ for _ in ()).throw(ValueError("migration")))
        with patch("mariamem.start", return_value=source):
            with self.assertRaisesRegex(ValueError, "migration"):
                with o:
                    self.fail("admitted")
        self.assertEqual(events, ["source.close"])

    def test_external_resource_on_failure(self):
        events = []
        r = Resource(events, "external.close")
        def external(ctx, app, register):
            register(r)
            raise RuntimeError("external failed")
        with self.opened(external_state=external) as (o, _, _, _, _, e):
            b, _ = self.browser(e)
            with self.assertRaises(EntryError):
                with o.case(browser=b):
                    pass
            self.assertEqual(events, ["external.close"])

    def test_identity_mismatch_latches(self):
        with self.opened() as (o, _, _, live, app, events):
            b, _ = self.browser(events)
            app.identity = "different-app"
            with self.assertRaises(EntryError):
                with o.case(browser=b):
                    self.fail("admitted wrong app")
            self.assertTrue(o._failed)

    def test_owner_cleanup_interrupt_preserves_primary(self):
        o, source, baseline, live, app, events = self.harness()
        interrupt = KeyboardInterrupt()
        app.fail_stop = True
        with patch("mariamem.start", return_value=source):
            with self.assertRaises(KeyboardInterrupt) as caught:
                with o:
                    raise interrupt
        self.assertIs(caught.exception, interrupt)
        self.assertEqual(events[-4:], ["stop", "live.close", "baseline.close", "source.close"])

    def test_late_registration_rejected(self):
        with self.opened() as (o, _, _, _, app, _):
            with self.assertRaises(EntryError):
                o._register_app(app)

    def test_resume_failure_stops_before_browser(self):
        def resume(ctx, app):
            raise RuntimeError("resume failed")
        with self.opened(resume=resume) as (o, _, _, _, _, events):
            b, _ = self.browser(events)
            with self.assertRaises(EntryError) as caught:
                with o.case(browser=b):
                    self.fail("admitted")
            self.assertEqual(caught.exception.stage, "resume")
            self.assertNotIn("page", events)

    def test_config_invalid_before_allocation(self):
        for override in ({"prepare": None}, {"setup_timeout": float("nan")}, {"resume": None, "sole_work_source": False}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                Config(**dict(dict(prepare=lambda db: None, start_ready=lambda *a: None, sole_work_source=True), **override))


if __name__ == "__main__":
    unittest.main()
