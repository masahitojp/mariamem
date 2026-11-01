import os
SECRET_KEY = 'd1-disposable-prototype'
INSTALLED_APPS = ['orders']
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:',
                        'TEST': {'NAME': os.path.join(os.environ['D1_SCRATCH'], 'source.sqlite')}}}
TEST_RUNNER = 'entry.Runner'
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
USE_TZ = True
