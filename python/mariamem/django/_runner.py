import sys

from django.core.exceptions import ImproperlyConfigured
from django.test import TransactionTestCase
from django.test.runner import DiscoverRunner

from ._cases import validate_case
from ._database import Manager, configuration
from ._lifecycle import preserving_cleanup


def _cases(suite):
    for item in suite:
        if hasattr(item, '__iter__'):
            yield from _cases(item)
        else:
            yield item


class PreparedDiscoverRunner(DiscoverRunner):
    """Django owns create/migrate/drop; mariamem owns each physical DB lineage."""
    def run_tests(self, test_labels, **kwargs):
        config = configuration(validate=False)
        if config.manager is not None:
            raise ImproperlyConfigured("A mariamem prepared run is already active")
        self._mariamem_teardown_error = None
        self._mariamem_environment = False
        def close_run():
            errors = []
            error = self._mariamem_teardown_error
            # DiscoverRunner can suppress teardown errors after a run failure.
            if error is not None and error is not sys.exception():
                errors.append(error)
            if self._mariamem_environment:
                try:
                    self.teardown_test_environment()
                except BaseException as failure:
                    errors.append(failure)
            try:
                config.close()
            except BaseException as failure:
                errors.append(failure)
            if errors:
                raise BaseExceptionGroup('mariamem run cleanup failed', errors)
        with preserving_cleanup(close_run):
            configuration()
            if self.parallel not in (0, 1) or self.keepdb:
                raise ImproperlyConfigured('PreparedDiscoverRunner requires serial execution without --keepdb')
            self._mariamem_manager = Manager(config)
            return super().run_tests(test_labels, **kwargs)

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._mariamem_environment = True

    def teardown_test_environment(self, **kwargs):
        try:
            super().teardown_test_environment(**kwargs)
        finally:
            self._mariamem_environment = False

    def build_suite(self, *args, **kwargs):
        suite = super().build_suite(*args, **kwargs)
        for test in _cases(suite):
            if isinstance(test, TransactionTestCase):
                validate_case(type(test))
        return suite

    def setup_databases(self, **kwargs):
        old_config = super().setup_databases(**kwargs)
        if old_config:  # Pure SimpleTestCase suites create no database.
            self._mariamem_manager.prepare()
        return old_config

    def teardown_databases(self, old_config, **kwargs):
        try:
            self._mariamem_manager.finish_databases()
            super().teardown_databases(old_config, **kwargs)
        except BaseException as error:
            self._mariamem_teardown_error = error
            raise
