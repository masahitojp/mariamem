"""Actual independent browser owners; selected only by owned runtime CI."""
import contextlib
import os

import pytest

if os.environ.get("E2E_OWNED_RUNTIME") != "1":
    pytest.skip("explicit owned runtime only", allow_module_level=True)

import test_orders as example
from playwright.sync_api import expect
from mariamem.e2e import BrowserEntry, Config

browser = example.browser


def test_independent_owners_reverse_order_and_assertion(browser):
    apps = []
    with contextlib.ExitStack() as stack:
        owners = [stack.enter_context(BrowserEntry(Config(
            prepare=example.prepare, start_ready=example.start_ready,
            sole_work_source=True,
            options={"host_binary": os.environ["MARIAMEM_TEST_HOST"]}))) for _ in range(2)]
        apps = [o.app for o in owners]
        identities = [a.identity for a in apps]
        endpoints = [o._live.connection_info() for o in owners]
        assert identities[0] != identities[1]
        assert endpoints[0] != endpoints[1]

        def seed(case):
            case.page.set_default_timeout(10000)
            case.page.goto(case.app.base_url + "/orders")
            expect(case.page.get_by_test_id("order")).to_have_text(["SEED:2:ready"])

        for left, right in ((0, 1), (1, 0)):
            with pytest.raises(AssertionError, match="intentional application assertion"):
                with owners[left].case(browser=browser) as first:
                    seed(first)
                    first.page.get_by_label("SKU", exact=True).fill("NEW")
                    first.page.get_by_label("Quantity", exact=True).fill("3")
                    first.page.get_by_role("button", name="Save", exact=True).click()
                    expect(first.page.get_by_test_id("order")).to_have_text(["SEED:2:ready", "NEW:3:ready"])
                    with owners[right].case(browser=browser) as second:
                        seed(second)
                    # The second owner's Reset must not reset the active first.
                    first.page.reload()
                    expect(first.page.get_by_test_id("order")).to_have_text(["SEED:2:ready", "NEW:3:ready"])
                    raise AssertionError("intentional application assertion")
            with owners[left].case(browser=browser) as recovered:
                seed(recovered)
        assert [a.identity for a in apps] == identities
        assert [o._live.connection_info() for o in owners] == endpoints
    assert all(a.process.poll() is not None for a in apps)
