"""Test-only collection permutations/exception observations; no DB fixture override."""
import os
import random
import pytest
from observation import error_details, record


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_collection_modifyitems(items):
    yield
    order = os.environ.get('W3_ORDER', 'normal')
    # Keep unittest classes contiguous so their class-level atomic owners are
    # never interleaved. Function parameter groups are kept together as well.
    groups = {}
    for item in items:
        key = (item.path, item.cls or item.originalname)
        groups.setdefault(key, []).append(item)
    grouped = list(groups.values())
    if order.startswith('shuffle'):
        seed = int(order.split('-')[1])
        rng = random.Random(seed)
        rng.shuffle(grouped)
        for group in grouped:
            rng.shuffle(group)
    if order.endswith('reverse'):
        grouped.reverse()
        for group in grouped:
            group.reverse()
    if order != 'normal':
        items[:] = [item for group in grouped for item in group]
    record('collected_order', names=[item.nodeid for item in items], order=order)


def pytest_runtest_logstart(nodeid):
    record('test_started', name=nodeid)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == 'setup' and call.excinfo is not None:
        record('setup_failed', name=item.nodeid, errors=error_details(call.excinfo.value))
