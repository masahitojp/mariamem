from boot import source
SECRET_KEY = 'd1-disposable-real-prototype'
INSTALLED_APPS = ['orders']
info = source.connection_info()
DATABASES = {'default': {'ENGINE': 'django.db.backends.mysql', 'NAME': info['database'],
                        'HOST': info['host'], 'PORT': info['port'], 'USER': info['user'],
                        'PASSWORD': info['password'], 'TEST': {'NAME': 'test_d1'},
                        'OPTIONS': {'charset': 'utf8mb4'}}}
TEST_RUNNER = 'entry.Runner'
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
USE_TZ = True
