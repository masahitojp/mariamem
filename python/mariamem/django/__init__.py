"""Explicit prepared Django test entry; settings declaration does not start a server."""
from ._database import prepared_database

__all__ = ['prepared_database', 'PreparedTestCase', 'PreparedTransactionTestCase',
           'PreparedDiscoverRunner']


def __getattr__(name):
    # Settings can import prepared_database before Django apps are ready.
    if name in ('PreparedTestCase', 'PreparedTransactionTestCase'):
        from . import _cases
        return getattr(_cases, name)
    if name == 'PreparedDiscoverRunner':
        from ._runner import PreparedDiscoverRunner
        return PreparedDiscoverRunner
    raise AttributeError(name)
