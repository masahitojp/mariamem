import os


def pytest_collection_modifyitems(items):
    if not os.environ.get("D1_XDIST_OUTPUT"):
        return
    mode = os.environ.get('D1_XDIST_MODE')
    if mode in ('no-db','collect-only','refuse-auto','refuse-remote'):
        items[:] = [item for item in items if item.cls.__name__ == 'TestWithoutDatabase']
    elif mode != 'idle':
        items[:] = [item for item in items if item.cls.__name__ != 'TestWithoutDatabase']
    if os.environ.get('D1_XDIST_MODE') == 'reverse':
        items.reverse()
