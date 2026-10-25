"""Test-only framing for the observed 12.3.3 dump; no product API/dependency."""
from dataclasses import dataclass
import re


@dataclass
class Statement:
    ordinal: int
    sql: bytes
    byte_start: int
    byte_end: int
    line_start: int
    line_end: int

    def location(self):
        return {k: getattr(self, k) for k in
                ['ordinal', 'byte_start', 'byte_end', 'line_start', 'line_end']}


class ImportFailure(RuntimeError):
    def __init__(self, reason, *, stage, location, errno=None, sqlstate=None):
        self.details = dict(reason=reason, stage=stage, location=location,
                            errno=errno, sqlstate=sqlstate)
        super().__init__(f'{stage}: {reason}; original file location {location}')


def frame(data):
    """Preflight whole input. Byte spans are zero-based, half-open; lines are 1-based."""
    data.decode('utf8')
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
                    line_start=data.count(b'\n', 0, begin)+1,
                    line_end=data.count(b'\n', 0, max(begin, end-1))+1)

    def fail(reason, begin, end):
        raise ImportFailure(reason, stage='preflight', location=location(begin, end))

    while position < len(data):
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
                statements.append(Statement(sql=bytes(buffer), **loc))
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


def execute(connection, data):
    statements, directives = frame(data)
    with connection.cursor() as cursor:
        for statement in statements:
            try:
                cursor.execute(statement.sql)
                while cursor.nextset():
                    pass
            except Exception as cause:
                raise ImportFailure('sql_error', stage='execute', location=statement.location(),
                    errno=cause.args[0] if cause.args and isinstance(cause.args[0], int) else None,
                    sqlstate=getattr(cause, 'sqlstate', None)) from cause
    return dict(statement_count=len(statements), directives=directives)
