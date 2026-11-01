"""Fixed authored orders app, using the public prepared entry."""
import json
import os
from pathlib import Path

from mariamem.django import prepared_database

SECRET_KEY = 'prepared-entry-test-only'
INSTALLED_APPS = ['orders']
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
USE_TZ = True
DATABASES = {'default': prepared_database(options={'host_binary': os.environ['MARIAMEM_PREPARED_HOST']})}
TEST_RUNNER = 'mariamem.django.PreparedDiscoverRunner'
MARIAMEM_DJANGO_PREPARE = 'prepared_settings.prepare'
if os.environ.get('MARIAMEM_PREPARED_MODE') == 'migration-failure':
    MIGRATION_MODULES = {'orders': 'failure_migrations'}


def event(name, **data):
    with Path(os.environ['MARIAMEM_PREPARED_EVENTS']).open('a') as stream:
        stream.write(json.dumps(dict(event=name, **data)) + '\n')


def prepare(connection):
    event('prepare')
    event('host', pid=DATABASES['default']['MARIAMEM_PREPARED'].source.diagnostics['host_pid'])
    if os.environ.get('MARIAMEM_PREPARED_MODE') == 'prepare-failure':
        raise RuntimeError('PREPARED_SEED_FAILURE')
    if os.environ.get('MARIAMEM_PREPARED_MODE') == 'busy-source':
        import MySQLdb
        global _retained_observer
        cfg = connection.settings_dict
        _retained_observer = MySQLdb.connect(host=cfg['HOST'], port=int(cfg['PORT']),
                                            user=cfg['USER'], passwd=cfg['PASSWORD'], db=cfg['NAME'])
    with connection.cursor() as cursor:
        cursor.execute('CREATE TABLE prepared_sentinel (n INT PRIMARY KEY)')
        cursor.execute('INSERT INTO prepared_sentinel VALUES (17)')


_source = DATABASES['default']['MARIAMEM_PREPARED'].source
event('host', pid=_source.diagnostics['host_pid'])
