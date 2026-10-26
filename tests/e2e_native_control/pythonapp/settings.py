import os
SECRET_KEY='test-fixture-only'
DEBUG=False
ALLOWED_HOSTS=['127.0.0.1','localhost']
ROOT_URLCONF='urls'
INSTALLED_APPS=['orders']
MIDDLEWARE=['django.middleware.csrf.CsrfViewMiddleware']
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','APP_DIRS':True}]
DATABASES={'default':{'ENGINE':'django.db.backends.mysql','NAME':os.environ['E2E_DB_NAME'],
 'HOST':os.environ['E2E_DB_HOST'],'PORT':int(os.environ['E2E_DB_PORT']),
 'USER':'root','PASSWORD':'','CONN_MAX_AGE':0,
 'OPTIONS':{'charset':'utf8mb4','init_command':"SET sql_mode='STRICT_TRANS_TABLES'"}}}
DEFAULT_AUTO_FIELD='django.db.models.AutoField'
USE_TZ=True
