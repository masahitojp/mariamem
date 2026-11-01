import os


def pytest_collection_modifyitems(items):
    if os.environ.get('MARIAMEM_PREPARED_MODE') == 'reverse':
        items.reverse()
