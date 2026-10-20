import json
import os
from pathlib import Path
import subprocess
import time
import pymysql
p=Path(__file__).resolve().parents[1]
name='mariamem-routine-definer-reference'
image='mariadb@sha256:805c8e104bd563d5bfa24fadd3f31cd419ea859cb5277f32b5dbf2db714f9ed1'
# Named container is created by this task only; do not reuse or replace another.
started=False
try:
    creation=subprocess.run(['docker','run','--rm','-d','--name',name,'--tmpfs','/var/lib/mysql',
        '-e','MARIADB_ALLOW_EMPTY_ROOT_PASSWORD=1','-e','MARIADB_DATABASE=test',
        '-e','MARIADB_ROOT_HOST=%','-p','127.0.0.1::3306',image],check=True,capture_output=True,text=True)
    started=True
    address=subprocess.check_output(['docker','port',name,'3306/tcp'],text=True).strip()
    port=int(address.rsplit(':',1)[1])
    deadline=time.monotonic()+50
    while True:
        try:
            connection=pymysql.connect(host='127.0.0.1',port=port,user='root',database='test')
            break
        except pymysql.MySQLError:
            if time.monotonic()>deadline:raise
            time.sleep(.5)
    with connection:
        with connection.cursor() as cursor:
            cursor.execute("SHOW VARIABLES LIKE 'version_source_revision'")
            revision=cursor.fetchall()
            assert revision[0][1]=='83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e',revision
            cursor.execute('SELECT VERSION(),@@skip_grant_tables')
            version=cursor.fetchall()
    (p/'evidence/native-identity.json').write_text(json.dumps({'image':image,'container_id':creation.stdout.strip(),'revision':revision,'version':version},indent=2)+'\n')
    subprocess.run([str(p/'temp/venv/bin/python'),str(p/'temp/definer_probe.py'),'--native-port',str(port),
                    '--output',str(p/'evidence/native-definer.json')],check=True)
finally:
    if started:
        log=subprocess.run(['docker','logs',name],capture_output=True)
        (p/'evidence/native-container.log').write_bytes(log.stdout+log.stderr)
        subprocess.run(['docker','stop',name],check=True)
