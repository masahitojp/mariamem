"""Explicit, bounded MariaDB12.3.3 dump import for preparation databases."""
from array import array
from bisect import bisect_left
from dataclasses import dataclass
from pathlib import Path
import re

MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_STATEMENT_BYTES = 4 * 1024 * 1024
MAX_STATEMENTS = 10000
_MODE = 'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'
_INIT = ("SET time_zone='+00:00', sql_mode='"+_MODE+"', "
         "collation_connection='utf8mb4_unicode_ci', foreign_key_checks=1, "
         "unique_checks=1, sql_notes=1, autocommit=1, note_verbosity=3")


class DumpImportError(RuntimeError):
    """A failed import whose database has been discarded; SQL is never echoed."""
    route = 'library'
    next_action = 'Inspect the original-file location and supported dump profile; start a fresh preparation DB before retrying.'

    def __init__(self, reason, *, stage, path=None, location=None, errno=None, sqlstate=None):
        self.reason, self.stage, self.path = reason, stage, path
        self.location = location
        self.errno, self.sqlstate = errno, sqlstate
        self.closed = False
        self.cleanup_error = None
        super().__init__(reason)

    def __str__(self):
        where = f' in {self.path}' if self.path is not None else ''
        if self.location:
            loc = self.location
            where += f" at statement {loc['ordinal']}, line {loc['line_start']}, bytes {loc['byte_start']}:{loc['byte_end']}"
        return f'Dump import {self.stage}: {self.reason}{where}'

    @property
    def details(self):
        return dict(reason=self.reason, stage=self.stage, location=self.location,
                    errno=self.errno, sqlstate=self.sqlstate)


@dataclass(frozen=True)
class _Statement:
    sql: bytes
    ordinal: int
    byte_start: int
    byte_end: int
    line_start: int
    line_end: int

    def location(self):
        return {k: getattr(self, k) for k in
                ['ordinal', 'byte_start', 'byte_end', 'line_start', 'line_end']}


def _frame(data):
    """Preflight whole input. Byte spans are zero-based, half-open; lines are 1-based."""
    try:
        data.decode('utf8')
    except UnicodeDecodeError as cause:
        raise DumpImportError('invalid_utf8', stage='preflight', location={
            'ordinal': None, 'byte_start': cause.start, 'byte_end': cause.end,
            'line_start': data.count(b'\n', 0, cause.start)+1,
            'line_end': data.count(b'\n', 0, cause.end)+1}) from cause
    newlines = array('I', (i for i, byte in enumerate(data) if byte == 10))
    statements, directives = [], []
    buffer = bytearray()
    delimiter = b';'
    position = start = 0
    meaningful = False
    state = 'normal'
    quote = None
    state_start = 0

    def location(begin, end):
        return dict(ordinal=len(statements)+1, byte_start=begin, byte_end=end,
                    line_start=bisect_left(newlines, begin)+1,
                    line_end=bisect_left(newlines, max(begin, end-1))+1)

    def fail(reason, begin, end):
        raise DumpImportError(reason, stage='preflight', location=location(begin, end))

    while position < len(data):
        if position-start > MAX_STATEMENT_BYTES:
            fail('statement_too_large', start, position)
        char = data[position]
        if state == 'line_comment':
            buffer.append(char)
            position += 1
            if char == 10:
                state = 'normal'
            continue
        if state == 'block_comment':
            if data[position:position+2] == b'*/':
                buffer.extend(b'*/')
                position += 2
                state = 'normal'
            else:
                buffer.append(char)
                position += 1
            continue
        if state == 'quote':
            buffer.append(char)
            position += 1
            if char == 92 and quote == 96:
                fail('unsupported_identifier', state_start, position)
            if char == 92:
                if position == len(data):
                    fail('unterminated_quote', state_start, position)
                buffer.append(data[position])
                position += 1
            elif char == quote:
                if position < len(data) and data[position] == quote:
                    buffer.append(data[position])
                    position += 1
                else:
                    if quote == 96 and not re.fullmatch(br'[A-Za-z0-9_$]{1,64}', data[state_start+1:position-1]):
                        fail('unsupported_identifier', state_start, position)
                    state = 'normal'
            continue
        if position == 0 or data[position-1] == 10:
            end = data.find(b'\n', position)
            end = len(data) if end < 0 else end+1
            line = data[position:end].strip()
            match = re.match(br'(?i)DELIMITER(?:\s|$)', line)
            if match:
                if meaningful:
                    fail('delimiter_inside_statement', position, end)
                parts = line.split()
                if len(parts) != 2 or parts[1] not in [b';', b';;']:
                    fail('unsupported_or_malformed_delimiter', position, end)
                delimiter = parts[1]
                directives.append(dict(kind='DELIMITER', value=delimiter.decode(),
                                       **location(position, end)))
                position = end
                continue
            if re.match(br'(?i)(SOURCE|SYSTEM|CONNECT|CHARSET|PAGER|NOPAGER|TEE|NOTEE|QUIT|EXIT|HELP|STATUS|PROMPT|PRINT|EDIT|GO|EGO|REHASH|RESETCONNECTION)(?:\s|;|$)', line) or line.startswith(b'\\'):
                fail('unsupported_client_command', position, end)
        if data[position:position+2] == b'/*':
            meaningful |= data[position:position+3] == b'/*!' or data[position:position+4] == b'/*M!'
            state, state_start = 'block_comment', position
            buffer.extend(b'/*')
            position += 2
        elif char == 35 or (data[position:position+2] == b'--' and
                            (position+2 == len(data) or data[position+2] <= 32)):
            state = 'line_comment'
            buffer.append(char)
            position += 1
        elif char in [39, 34, 96]:
            state, quote, state_start = 'quote', char, position
            meaningful = True
            buffer.append(char)
            position += 1
        elif data[position:position+len(delimiter)] == delimiter:
            if meaningful:
                loc = location(start, position)
                if len(statements) >= MAX_STATEMENTS:
                    fail('too_many_statements', start, position)
                statements.append(_Statement(sql=bytes(buffer), **loc))
            buffer.clear()
            meaningful = False
            position += len(delimiter)
            start = position
        else:
            meaningful |= char > 32
            buffer.append(char)
            position += 1
    if state in ['quote', 'block_comment']:
        fail('unterminated_'+state, state_start, len(data))
    if meaningful:
        fail('missing_final_delimiter', start, len(data))
    return statements, directives


def _effective(sql):
    """Inspect comments for the profile; never use this projection for execution."""
    text, out, i = sql.decode('utf8'), [], 0
    while i < len(text):
        if text[i] in "'\"`":
            begin, quote = i, text[i]
            i += 1
            while i < len(text):
                char = text[i]
                i += 1
                if char == '\\' and quote != '`':
                    i += 1
                elif char == quote:
                    if i < len(text) and text[i] == quote:
                        i += 1
                    else:
                        break
            out.append(text[begin:i])
        elif text.startswith('/*', i):
            end = text.index('*/', i+2)
            comment = text[i+2:end]
            executable = re.match(r'(M!|!)(\d{5,6})\s*(.*)', comment, re.S)
            if executable:
                kind, version, body = executable.groups()
                if (kind, version) == ('M!', '999999') and body.strip() == r'\- enable the sandbox mode':
                    pass
                elif (kind == '!' and version in {'40000', '40014', '40101', '40103', '50003'}) or (kind, version) == ('M!', '100616'):
                    out.append(' '+body+' ')
                else:
                    raise ValueError('unsupported_executable_comment')
            elif comment.startswith(('!', 'M!')):
                raise ValueError('unsupported_executable_comment')
            out.append(' ')
            i = end+2
        elif text[i] == '#' or (text.startswith('--', i) and (i+2 == len(text) or text[i+2].isspace())):
            end = text.find('\n', i)
            i = len(text) if end < 0 else end+1
            out.append(' ')
        else:
            out.append(text[i])
            i += 1
    return ''.join(out).strip()


_ID = r'(?:`[A-Za-z0-9_$]{1,64}`|[A-Za-z_][A-Za-z0-9_$]{0,63})'
_SAVED = {
    '@old_character_set_client': '@@character_set_client',
    '@old_character_set_results': '@@character_set_results',
    '@old_collation_connection': '@@collation_connection',
    '@old_time_zone': '@@time_zone', '@old_unique_checks': '@@unique_checks',
    '@old_foreign_key_checks': '@@foreign_key_checks', '@old_sql_notes': '@@sql_notes',
    '@old_sql_mode': '@@sql_mode', '@old_note_verbosity': '@@note_verbosity',
    '@old_autocommit': '@@autocommit', '@saved_sql_mode': '@@sql_mode',
    '@saved_cs_client': '@@character_set_client', '@saved_cs_results': '@@character_set_results',
    '@saved_col_connection': '@@collation_connection',
}
_RESTORES = {
    'character_set_client': {'@old_character_set_client', '@saved_cs_client', 'utf8mb4'},
    'character_set_results': {'@old_character_set_results', '@saved_cs_results', 'utf8mb4'},
    'collation_connection': {'@old_collation_connection', '@saved_col_connection',
                             'utf8mb4_unicode_ci', 'utf8mb4_uca1400_ai_ci'},
    'time_zone': {'@old_time_zone', "'+00:00'"},
    'foreign_key_checks': {'@old_foreign_key_checks', '0'},
    'unique_checks': {'@old_unique_checks', '0'}, 'sql_notes': {'@old_sql_notes', '0'},
    'note_verbosity': {'@old_note_verbosity', '0'}, 'autocommit': {'@old_autocommit', '0'},
    '@@autocommit': {'0'},
}


def _check_set(body):
    if re.fullmatch(r'SET\s+NAMES\s+utf8mb4', body, re.I):
        return
    if len(body) > 1024:
        raise ValueError('unsupported_session_statement')
    for item in re.split(r",(?=(?:[^']*'[^']*')*[^']*$)", body[3:]):
        match = re.fullmatch(r'\s*(@{0,2}[a-z_]+)\s*=\s*(.*?)\s*', item, re.I | re.S)
        if not match:
            raise ValueError('unsupported_session_statement')
        key, value = (v.lower() for v in match.groups())
        if key in _SAVED and value == _SAVED[key]:
            continue
        if key == 'sql_mode':
            if value in {'@old_sql_mode', '@saved_sql_mode'}:
                continue
            if value.startswith("'") and value.endswith("'"):
                flags = value[1:-1].upper().split(',')
                if len(flags) == len(set(flags)) and set(flags) in [{'NO_AUTO_VALUE_ON_ZERO'}, set(_MODE.split(','))]:
                    continue
            raise ValueError('unsupported_sql_mode')
        if key not in _RESTORES or value not in _RESTORES[key]:
            raise ValueError('unsupported_session_statement')


def _check_statement(statement):
    body = _effective(statement.sql)
    if re.match(r'SET\b', body, re.I):
        _check_set(body)
    elif re.fullmatch(r'COMMIT', body, re.I):
        pass
    elif re.fullmatch(r'DROP\s+(?:TABLE|FUNCTION|PROCEDURE)\s+IF\s+EXISTS\s+'+_ID, body, re.I):
        pass
    elif re.fullmatch(r'ALTER\s+TABLE\s+'+_ID+r'\s+(?:ENABLE|DISABLE)\s+KEYS', body, re.I):
        pass
    elif re.match(r'INSERT\s+INTO\s+'+_ID+r'\s*(?:\([^)]*\)\s*)?VALUES\s*\(', body, re.I):
        pass
    elif re.match(r'CREATE\s+TABLE\s+'+_ID+r'\s*\(', body, re.I):
        if not re.search(r'\)\s*ENGINE\s*=\s*InnoDB(?:\s+AUTO_INCREMENT\s*=\s*\d+)?(?:\s+DEFAULT\s+CHARSET\s*=\s*utf8mb4(?:\s+COLLATE\s*=\s*utf8mb4_unicode_ci)?)?\s*$', body, re.I):
            raise ValueError('unsupported_table_options')
    elif re.match(r'CREATE\s+DEFINER\s*=\s*`root`@`localhost`\s+(?:FUNCTION|PROCEDURE)\s+'+_ID+r'\s*\(', body, re.I):
        pass
    else:
        raise ValueError('unsupported_statement')


def _preflight(data, database=None):
    if len(data) > MAX_FILE_BYTES:
        raise DumpImportError('file_too_large', stage='preflight')
    statements, _ = _frame(data)
    header = data[:4096]
    if not (data.startswith(b'/*M!999999\\- enable the sandbox mode */')
            and re.search(br'^-- MariaDB dump [^\r\n]*12\.3\.3-MariaDB,', header, re.M)
            and re.search(br'^-- Server version\s+12\.3\.3-MariaDB', header, re.M)
            and re.search(br'^-- Dump completed\s*$', data, re.M)):
        raise DumpImportError('unsupported_dump_profile', stage='preflight')
    schema = re.search(br'^-- Host: [^\r\n]*    Database: ([A-Za-z_][A-Za-z0-9_$]{0,63})\r?$', header, re.M)
    if schema is None:
        raise DumpImportError('unsupported_database_name', stage='preflight')
    schema = schema[1].decode('ascii')
    if database is not None and database != schema:
        raise DumpImportError('database_mismatch', stage='preflight')
    if not statements:
        raise DumpImportError('empty_dump', stage='preflight')
    for statement in statements:
        try:
            _check_statement(statement)
        except ValueError as cause:
            raise DumpImportError(str(cause), stage='preflight', location=statement.location()) from cause
    return statements, schema


def import_dump(db, path, *, database=None):
    """Import a supported dump into an empty preparation schema; discard DB on error.

    Requires the ``dump`` extra. Returns the number of SQL statements executed.
    The default schema is the dump header's Database. ``database`` asserts it;
    this function never remaps SQL. Limits:16MiB/file,4MiB/statement,10000 statements.
    """
    from . import Database
    if not isinstance(db, Database):
        raise TypeError('db must be a mariamem Database')
    stage, location = 'read', None
    try:
        path = Path(path)
        if not path.is_file():
            raise DumpImportError('not_a_regular_file', stage=stage)
        with path.open('rb') as source:
            data = source.read(MAX_FILE_BYTES+1)
        statements, schema = _preflight(data, database)
        stage = 'connect'
        try:
            import pymysql
        except ImportError as cause:
            raise DumpImportError('missing_dump_dependency', stage=stage) from cause
        info = db.connection_info()
        with pymysql.connect(host=info['host'], port=info['port'], user=info['user'],
                password=info['password'], database=info['database'], charset='utf8mb4',
                autocommit=True, init_command=_INIT, connect_timeout=10,
                read_timeout=60, write_timeout=60) as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT VERSION()')
                if not cursor.fetchone()[0].startswith('12.3.3-MariaDB'):
                    raise DumpImportError('unsupported_server_version', stage=stage)
                stage = 'target'
                cursor.execute('SELECT (SELECT COUNT(*) FROM information_schema.tables WHERE TABLE_SCHEMA=%s) + '
                    '(SELECT COUNT(*) FROM information_schema.routines WHERE ROUTINE_SCHEMA=%s)', (schema, schema))
                if cursor.fetchone()[0]:
                    raise DumpImportError('target_not_empty', stage=stage)
                cursor.execute('CREATE DATABASE IF NOT EXISTS `'+schema+'` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
                cursor.execute('SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME '
                    'FROM information_schema.schemata WHERE SCHEMA_NAME=%s', (schema,))
                if cursor.fetchone() != ('utf8mb4', 'utf8mb4_unicode_ci'):
                    raise DumpImportError('unsupported_target_collation', stage=stage)
                connection.select_db(schema)
                stage = 'execute'
                for statement in statements:
                    location = statement.location()
                    cursor.execute(statement.sql)
                    while cursor.nextset():
                        pass
            stage, location = 'disconnect', None
        return len(statements)
    except BaseException as cause:
        if isinstance(cause, DumpImportError):
            failure = cause
        elif isinstance(cause, Exception):
            failure = DumpImportError('sql_error' if stage == 'execute' else 'import_failed', stage=stage,
                location=location, errno=cause.args[0] if cause.args and isinstance(cause.args[0], int) else None,
                sqlstate=getattr(cause, 'sqlstate', None))
        else:
            failure = None
        try:
            db.close()
        except BaseException as cleanup:
            if failure is not None:
                failure.cleanup_error = cleanup
        if failure is None:
            raise
        failure.path = str(path)
        try:
            failure.closed = db.closed
        except BaseException:
            failure.closed = False
        if failure is cause:
            raise
        raise failure from cause
