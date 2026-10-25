"""Product format, execution, diagnostics and source-discard boundaries."""
from pathlib import Path
import sys
import subprocess

import pytest

import mariamem
from mariamem import DumpImportError, import_dump
from mariamem import dump

CORPUS = Path(__file__).parent/'dump_import_acceptance/input/application.sql'


def test_real_dump_bytes_and_routines_preserved():
    data = CORPUS.read_bytes()
    statements, schema = dump._preflight(data)
    assert schema == 'app' and len(statements) == 90
    assert sum(b'CREATE DEFINER=' in s.sql for s in statements) == 2
    assert b'/*M!999999\\- enable the sandbox mode */' in statements[0].sql
    assert any(b'0x00273B5CFF' in s.sql for s in statements)
    assert any(b'path; newline' in s.sql for s in statements)


@pytest.mark.parametrize('before,after,reason', [
    (b'12.3.3-MariaDB', b'12.3.4-MariaDB', 'unsupported_dump_profile'),
    (b'-- MariaDB dump', b'-- MySQL dump', 'unsupported_dump_profile'),
    (b"'NO_AUTO_VALUE_ON_ZERO'", b"'NO_BACKSLASH_ESCAPES'", 'unsupported_sql_mode'),
    (b"'NO_AUTO_VALUE_ON_ZERO'", b"'ANSI_QUOTES'", 'unsupported_sql_mode'),
    (b'ENGINE=InnoDB', b'ENGINE=MyISAM', 'unsupported_table_options'),
    (b'DELIMITER ;;', b'DELIMITER //', 'unsupported_or_malformed_delimiter'),
    (b'/*!40101', b'/*!77777', 'unsupported_executable_comment'),
    (b'`users`', b'`user space`', 'unsupported_identifier'),
    (b'COLLATE=utf8mb4_unicode_ci', b'COLLATE=latin1_swedish_ci', 'unsupported_table_options'),
])
def test_profile_mutations_rejected(before, after, reason):
    with pytest.raises(DumpImportError) as e:
        dump._preflight(CORPUS.read_bytes().replace(before, after))
    assert e.value.stage == 'preflight' and e.value.reason == reason


@pytest.mark.parametrize('suffix,reason', [
    (b'\nSOURCE absent.sql\n', 'unsupported_client_command'),
    (b'\n\\. absent.sql\n', 'unsupported_client_command'),
    (b"\nSELECT 'unterminated", 'unterminated_quote'),
    (b'\nCREATE VIEW unsupported AS SELECT 1;', 'unsupported_statement'),
    (b'\nUSE other;', 'unsupported_statement'),
    (b'\nCREATE DATABASE other;', 'unsupported_statement'),
    (b'\nSET SQL_MODE=CONCAT(@@SQL_MODE,\',ANSI_QUOTES\');', 'unsupported_sql_mode'),
])
def test_rejection_has_original_file_location(suffix, reason):
    data = CORPUS.read_bytes()+suffix
    with pytest.raises(DumpImportError) as e:
        dump._preflight(data)
    assert e.value.reason == reason
    loc = e.value.location
    assert loc['ordinal'] >= 91 and loc['byte_start'] < len(data)
    assert loc['byte_end'] <= len(data)
    assert loc['line_start'] == data.count(b'\n', 0, loc['byte_start'])+1
    assert loc['line_end'] >= loc['line_start']


def test_not_a_single_fixture_hash():
    original = CORPUS.read_bytes()
    changed = original.replace(b"'legacy'", "'別の; data'".encode()).replace(b'12345678901234.123456', b'999.123456')
    assert changed != original
    assert len(dump._preflight(changed)[0]) == 90


@pytest.mark.parametrize('key,limit,reason', [
    ('MAX_FILE_BYTES', 100, 'file_too_large'),
    ('MAX_STATEMENT_BYTES', 100, 'statement_too_large'),
    ('MAX_STATEMENTS', 10, 'too_many_statements'),
])
def test_product_resource_limits(monkeypatch, key, limit, reason):
    monkeypatch.setattr(dump, key, limit)
    with pytest.raises(DumpImportError) as e:
        dump._preflight(CORPUS.read_bytes())
    assert e.value.reason == reason and e.value.stage == 'preflight'


class Target(mariamem.Database):
    def __init__(self):
        self._is_closed = False

    @property
    def closed(self):
        return self._is_closed

    def close(self):
        self._is_closed = True

    def connection_info(self):
        return dict(host='127.0.0.1', port=12345, user='root', password='', database='test')


class Cursor:
    def __init__(self, fail=None, occupied=0):
        self.executed, self.fail, self.occupied = [], fail, occupied

    def __enter__(self): return self
    def __exit__(self, *args): pass

    def execute(self, sql, parameters=None):
        self.executed.append(sql)
        if self.fail is not None and isinstance(sql, bytes):
            raise self.fail

    def fetchone(self):
        if self.executed[-1] == 'SELECT VERSION()': return ('12.3.3-MariaDB',)
        if self.executed[-1].startswith('SELECT DEFAULT_CHARACTER'): return ('utf8mb4', 'utf8mb4_unicode_ci')
        return (self.occupied,)

    def nextset(self): return False


class Connection:
    def __init__(self, cursor): self.c, self.closed = cursor, False
    def __enter__(self): return self
    def __exit__(self, *args): self.closed = True
    def cursor(self): return self.c
    def select_db(self, schema): assert schema == 'app'


def test_public_import_executes_original_sql_and_closes_connection(monkeypatch):
    import pymysql
    c = Cursor(); connection = Connection(c); target = Target()
    monkeypatch.setattr(pymysql, 'connect', lambda **kwargs: connection)
    assert import_dump(target, CORPUS) == 90
    assert [sql for sql in c.executed if isinstance(sql, bytes)] == [s.sql for s in dump._preflight(CORPUS.read_bytes())[0]]
    assert connection.closed and not target.closed


def test_sql_failure_preserves_cause_errno_sqlstate_span_and_discards(monkeypatch):
    import pymysql
    cause = pymysql.ProgrammingError(1146, 'sensitive dump value')
    cause.sqlstate = '42S02'
    connection = Connection(Cursor(cause)); target = Target()
    monkeypatch.setattr(pymysql, 'connect', lambda **kwargs: connection)
    with pytest.raises(DumpImportError) as e:
        import_dump(target, CORPUS)
    failure = e.value
    assert failure.__cause__ is cause and failure.errno == 1146 and failure.sqlstate == '42S02'
    assert failure.stage == 'execute' and failure.location['ordinal'] == 1
    assert failure.path == str(CORPUS) and failure.route == 'library'
    assert failure.closed and target.closed and connection.closed
    assert 'sensitive dump value' not in str(failure)


@pytest.mark.parametrize('failure', ['framing', 'mismatch', 'file', 'dependency', 'connect', 'occupied'])
def test_failure_cannot_leave_a_usable_baseline(monkeypatch, tmp_path, failure):
    import pymysql
    target = Target()
    path, options = CORPUS, {}
    opened = []
    def connect(**kwargs):
        opened.append(True)
        if failure == 'connect': raise OSError('offline')
        return Connection(Cursor(occupied=1 if failure == 'occupied' else 0))
    monkeypatch.setattr(pymysql, 'connect', connect)
    if failure == 'framing':
        path = tmp_path/'bad.sql'; path.write_bytes(CORPUS.read_bytes()+b"\nSELECT 'missing")
    if failure == 'mismatch': options['database'] = 'other'
    if failure == 'file': path = tmp_path/'absent.sql'
    if failure == 'dependency': monkeypatch.setitem(sys.modules, 'pymysql', None)
    with pytest.raises(DumpImportError) as e:
        import_dump(target, path, **options)
    assert target.closed and e.value.closed
    if failure in {'framing', 'mismatch', 'file', 'dependency'}: assert not opened


def test_utf8_byte_location():
    data = CORPUS.read_bytes()+b'\xff'
    with pytest.raises(DumpImportError) as e: dump._preflight(data)
    assert e.value.reason == 'invalid_utf8' and e.value.location['byte_start'] == len(data)-1


def test_base_package_does_not_import_optional_driver():
    subprocess.run([sys.executable, '-c',
        "import sys; sys.modules['pymysql']=None; import mariamem; assert callable(mariamem.import_dump)"], check=True)


def test_error_sqlstate_comes_from_driver_packet(monkeypatch):
    import pymysql
    # Exercise the pinned driver's actual error packet decoder, not a fabricated attribute.
    try:
        pymysql.err.raise_mysql_exception(b'\xff\x7a\x04#42S02missing table')
    except pymysql.ProgrammingError as error:
        cause = error
    connection = Connection(Cursor(cause))
    monkeypatch.setattr(pymysql, 'connect', lambda **kwargs: connection)
    with pytest.raises(DumpImportError) as e:
        import_dump(Target(), CORPUS)
    assert (e.value.errno, e.value.sqlstate) == (1146, '42S02')


def test_wrong_target_collation_discards_without_import(monkeypatch):
    import pymysql
    cursor = Cursor()
    fetch = cursor.fetchone
    cursor.fetchone = lambda: ('latin1', 'latin1_swedish_ci') if cursor.executed[-1].startswith('SELECT DEFAULT_CHARACTER') else fetch()
    connection = Connection(cursor)
    monkeypatch.setattr(pymysql, 'connect', lambda **kwargs: connection)
    target = Target()
    with pytest.raises(DumpImportError, match='unsupported_target_collation'):
        import_dump(target, CORPUS)
    assert target.closed and connection.closed
    assert not any(isinstance(sql, bytes) for sql in cursor.executed)


def test_cleanup_failure_retains_original_import_failure(monkeypatch):
    import pymysql
    cause = pymysql.ProgrammingError(1146, 'missing', sqlstate='42S02')
    connection = Connection(Cursor(cause))
    monkeypatch.setattr(pymysql, 'connect', lambda **kwargs: connection)
    target = Target()
    cleanup = OSError('cannot close')
    def close(): raise cleanup
    target.close = close
    with pytest.raises(DumpImportError) as e:
        import_dump(target, CORPUS)
    assert e.value.__cause__ is cause and e.value.cleanup_error is cleanup
    assert not e.value.closed and connection.closed
