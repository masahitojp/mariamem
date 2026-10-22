"""Tripwires for the current prepared/text integration oracle."""
from collections import deque
import json
from pathlib import Path
import struct

import pymysql
from pymysql.protocol import MysqlPacket
import pytest
from support.wire_acceptance import exercise_prepared_lifecycle


SID = 23
OK = b'\x00\x00\x00\x02\x00\x00\x00'
EOF = b'\xfe\x00\x00\x02\x00'


def error_packet(errno):
    return b'\xff' + struct.pack('<H', errno) + b'#HY000oracle error'


def replies():
    reference = json.loads((Path(__file__).parent / 'fixtures/prepared-p1-native.json').read_text())
    fields = reference['metadata']['placeholder']
    return [b'\x00' + struct.pack('<IHHBH', SID, 1, 1, 0, 0),
            bytes.fromhex(fields['parameters'][0]), EOF,
            bytes.fromhex(fields['columns'][0]), EOF,
            OK, OK, error_packet(1243)]


class Connection:
    def __init__(self, packets):
        self.packets = deque(packets)
        self.commands = []

    def _execute_command(self, command, payload):
        self.commands.append((command, payload))

    def _read_packet(self, packet_type=MysqlPacket):
        packet = packet_type(self.packets.popleft(), 'utf8mb4')
        if packet.is_error_packet():
            packet.raise_for_error()
        return packet


def test_prepare_oracle_drains_metadata_resets_closes_without_ack_and_reuses():
    connection = Connection(replies())
    exercise_prepared_lifecycle(connection)
    assert not connection.packets
    sid = struct.pack('<I', SID)
    assert connection.commands == [(22, b'SELECT ?'), (26, sid),
                                   (25, sid), (14, b''), (26, sid)]


@pytest.mark.parametrize('mutation', ['old-rejection', 'metadata', 'count', 'missing-eof',
                                      'reset-error', 'invented-close-ack', 'closed-id-error'])
def test_prepare_oracle_rejects_contract_mutations(mutation):
    packets = replies()
    if mutation == 'old-rejection':
        packets[0] = error_packet(1235)
    elif mutation == 'metadata':
        packets[1] = packets[1][:-1] + bytes([packets[1][-1] ^ 1])
    elif mutation == 'count':
        packets[0] = b'\x00' + struct.pack('<IHHBH', SID, 1, 2, 0, 0)
    elif mutation == 'missing-eof':
        packets[2] = OK
    elif mutation == 'reset-error':
        packets[5] = error_packet(1235)
    elif mutation == 'invented-close-ack':
        packets.insert(6, OK)
    elif mutation == 'closed-id-error':
        packets[7] = error_packet(1235)
    with pytest.raises((AssertionError, pymysql.MySQLError)):
        exercise_prepared_lifecycle(Connection(packets))
