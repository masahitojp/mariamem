"""Actual generated guest only: independently asserted prepared results."""
import datetime
import decimal
import os
import mariamem
import mysql.connector


def test_prepared_real_guest_values_reuse_and_sql_error():
    host = os.environ['MARIAMEM_TEST_HOST']  # Missing candidate must fail, never skip.
    with mariamem.start(host_binary=host) as db:
        with mysql.connector.connect(**db.connection_info()) as c:
            q = c.cursor(prepared=True)
            sql = 'SELECT CAST(? AS SIGNED), CAST(? AS CHAR), CAST(? AS DATETIME), CAST(? AS DECIMAL(8,2))'
            for n in (42, -19, 0):
                q.execute(sql, (n, 'raw行', '2026-01-02 03:04:05', '12.34'))
                assert q.fetchall() == [(n, 'raw行', datetime.datetime(2026, 1, 2, 3, 4, 5), decimal.Decimal('12.34'))]
            q.execute('SELECT ? IS NULL, CAST(? AS BINARY)', (None, b'x' * 65536))
            row = q.fetchone()
            assert row[0] == 1 and bytes(row[1]) == b'x' * 65536
            q.execute('SELECT 1 WHERE 1=?', (0,))
            assert q.fetchall() == []
            q.close()
            with c.cursor() as setup:
                setup.execute('CREATE TABLE raw_retry(id INT PRIMARY KEY) ENGINE=InnoDB')
            q = c.cursor(prepared=True)
            insert = 'INSERT INTO raw_retry VALUES(?)'
            q.execute(insert, (1,))
            try:
                q.execute(insert, (1,))
            except mysql.connector.Error as error:
                assert error.errno == 1062
            else:
                raise AssertionError('duplicate key accepted')
            q.execute(insert, (2,))
            c.commit()
            q.execute('SELECT id FROM raw_retry ORDER BY id')
            assert q.fetchall() == [(1,), (2,)]
            q.close()
            q = c.cursor(prepared=True)
            query = 'SELECT * FROM raw_retry ORDER BY id'
            q.execute(query)
            assert q.fetchall() == [(1,), (2,)]
            with c.cursor() as ddl:
                ddl.execute('ALTER TABLE raw_retry ADD COLUMN extra INT DEFAULT 9')
            q.execute(query)
            assert q.fetchall() == [(1, 9), (2, 9)]
            q.close()
