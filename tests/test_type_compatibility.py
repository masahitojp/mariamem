"""Bounded types/metadata probe; optional native DSN uses identical PyMySQL SQL."""
import datetime
from decimal import Decimal
import json
import os

import mariamem
import pymysql
import pytest


def exercise(connection):
    with connection.cursor() as cur:
        cur.execute("SET time_zone='+00:00'")
        cur.execute("CREATE TABLE type_probe(i INT,b BIGINT UNSIGNED,f FLOAT,d DOUBLE,n DECIMAL(12,3),day DATE,dt DATETIME,ts TIMESTAMP,v VARCHAR(32),txt TEXT,blobval BLOB,bin BINARY(4),bits BIT(8),nullable INT NULL) ENGINE=InnoDB")
        try:
            cur.execute("INSERT INTO type_probe VALUES(-7,18446744073709551615,1.25,2.5,123.450,'2026-10-01','2026-10-01 03:04:05','2026-10-01 03:04:05','日本語','text',X'00FF',X'01020304',b'10100101',NULL)")
            connection.commit()
            cur.execute("SELECT * FROM type_probe")
            row = cur.fetchone()
            assert row == (-7,18446744073709551615,1.25,2.5,Decimal('123.450'),datetime.date(2026,10,1),datetime.datetime(2026,10,1,3,4,5),datetime.datetime(2026,10,1,3,4,5),'日本語','text',b'\x00\xff',b'\x01\x02\x03\x04',b'\xa5',None)
            print(json.dumps({'values':[str(v) for v in row], 'python_types':[type(v).__name__ for v in row], 'description':cur.description}, ensure_ascii=False))
        finally:
            cur.execute("DROP TABLE type_probe")
            connection.commit()


def test_representative_types():
    native = os.environ.get('MARIAMEM_TYPE_PORT')
    if native:
        with pymysql.connect(host='127.0.0.1',port=int(native),user='root',password='probe-only',database='test',charset='utf8mb4') as connection:
            exercise(connection)
    else:
        host = os.environ.get('MARIAMEM_TEST_HOST')
        if not host:
            pytest.skip('requires real host or native comparison server')
        with mariamem.start(host_binary=host) as db:
            with pymysql.connect(**db.connection_info(), charset='utf8mb4') as connection:
                exercise(connection)
