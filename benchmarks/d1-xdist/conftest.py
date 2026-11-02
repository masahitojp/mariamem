import os


def pytest_collection_modifyitems(items):
    if os.environ.get('D1_XDIST_MODE') == 'reverse':
        items.reverse()
