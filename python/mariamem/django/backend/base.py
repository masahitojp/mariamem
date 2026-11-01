"""Delegate SQL to Django; refuse accidental connections before DB setup."""
from django.core.exceptions import ImproperlyConfigured
from django.db.backends.mysql.base import DatabaseWrapper as MySQLDatabaseWrapper

from .._database import Configuration, KEY


class DatabaseWrapper(MySQLDatabaseWrapper):
    def get_connection_params(self):
        config = self.settings_dict.get(KEY)
        if not isinstance(config, Configuration) or config.manager is None:
            raise ImproperlyConfigured(
                'Prepared Django database is not active. Use PreparedDiscoverRunner '
                'or mariamem.django.pytest_plugin; settings/check/shell do not start a host.')
        return super().get_connection_params()
