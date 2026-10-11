import json
from pathlib import Path
import sys
import mariamem
import pymysql

with mariamem.start(host_binary=Path(sys.argv[1])) as db:
    with pymysql.connect(**db.connection_info()) as connection:
        with connection.cursor() as cursor:
            cursor.execute('SELECT CONNECTION_ID(), VERSION()')
            connection_id, version = cursor.fetchone()
        assert version == '12.3.3-MariaDB-embedded'
        assert connection.get_server_info() == version
        assert connection.thread_id() == connection_id
        print(json.dumps({'result':'PASS', 'sql_version':version,
            'handshake_version':connection.get_server_info(), 'connection_id':connection_id,
            'thread_id':connection.thread_id()}, indent=2))
    db.wait_disconnected()
