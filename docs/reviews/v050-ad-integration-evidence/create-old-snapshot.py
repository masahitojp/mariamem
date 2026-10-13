import json
import os
from pathlib import Path
import sys
import mariamem
import pymysql

out = Path(sys.argv[1])
host = Path(sys.argv[2])
with mariamem.start(host_binary=host) as db:
    with pymysql.connect(**db.connection_info(), autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute('SELECT VERSION()')
            version = cursor.fetchone()[0]
            cursor.execute('CREATE TABLE old_guest_marker (id INT PRIMARY KEY)')
            cursor.execute('INSERT INTO old_guest_marker VALUES (47)')
    db.wait_disconnected()
    snapshot = db.snapshot_to(out)
    snapshot.close()
print(json.dumps({'sql_version': version, 'manifest': json.loads((out / 'manifest.json').read_text())}, indent=2))
