"""Raw P2 type-vector reference; a native-only run is not guest acceptance."""

import argparse
import json
from pathlib import Path
import struct

import pymysql

from v06_prepared_p1_probe import RawErrorPacket, close_ping, prepare


def execute(c, payload):
    c._execute_command(23, payload)
    first = c._read_packet(RawErrorPacket)
    raw = first.get_all_data()
    if raw[0] == 255:
        assert len(raw) >= 9 and raw[3:4] == b"#", raw.hex()
        return {"errno": int.from_bytes(raw[1:3], "little"),
                "sqlstate": raw[4:9].decode(), "error_hex": raw[9:].hex()}
    assert not first.is_ok_packet(), "SELECT unexpectedly returned OK"
    count = first.read_length_encoded_integer()
    columns = [c._read_packet().get_all_data().hex() for _ in range(count)]
    metadata_end = c._read_packet()
    assert metadata_end.is_eof_packet()
    rows = []
    while True:
        packet = c._read_packet()
        if packet.is_eof_packet():
            terminal = packet.get_all_data()
            break
        row = packet.get_all_data()
        assert row[0] == 0, row.hex()
        rows.append(row.hex())
    return {"columns": columns, "rows": rows, "terminal": terminal.hex()}


def exercise(info):
    result = {"scope": "P2 exact raw type vectors, not complete P2-P6 acceptance",
              "cases": {}}
    vectors = json.loads((Path(__file__).parent / "fixtures/prepared-p2-values.json").read_text())
    with pymysql.connect(**info, autocommit=True, charset="utf8mb4",
                         read_timeout=10, write_timeout=10) as c:
        with c.cursor() as q:
            q.execute("SELECT VERSION()")
            result["version"] = q.fetchone()[0]
            assert result["version"].startswith("12.3.3"), result["version"]
            q.execute("SET NAMES utf8mb4 COLLATE utf8mb4_general_ci")
            q.execute("SET sql_mode = '', time_zone = '+00:00'")
        for vector in vectors:
            sid, _ = prepare(c, "SELECT ? AS v")
            packet = bytes.fromhex(vector["packet"])
            packet = struct.pack("<I", sid) + packet[4:]
            observed = execute(c, packet)
            result["cases"][vector["name"]] = observed
            # Reuse the same descriptors, without transmitting them again.
            reuse = packet[:10] + b"\0" + packet[13:]
            assert execute(c, reuse) == observed, vector["name"]
            close_ping(c, sid)
        sid, _ = prepare(c, "SELECT ? AS v")
        prefix = struct.pack("<IBI", sid, 0, 1)
        for name, data in (("large-binary", bytes([0, 255]) * 4097),):
            payload = prefix + b"\0\1\xfc\0\xfc" + struct.pack("<H", len(data)) + data
            result["cases"][name] = execute(c, payload)
            assert len(result["cases"][name]["rows"]) == 1
        close_ping(c, sid)
        digits = "(" + " UNION ALL ".join(f"SELECT {i} AS n" for i in range(10)) + ")"
        sid, _ = prepare(c, f"SELECT ? AS v FROM {digits} a CROSS JOIN {digits} b CROSS JOIN {digits} d CROSS JOIN {digits} e LIMIT 1500")
        payload = struct.pack("<IBI", sid, 0, 1) + b"\0\1\x01\0\x2a"
        result["cases"]["rows1500"] = execute(c, payload)
        assert len(result["cases"]["rows1500"]["rows"]) == 1500
        assert len(set(result["cases"]["rows1500"]["rows"])) == 1
        close_ping(c, sid)
        sid, _ = prepare(c, "SELECT " + ",".join(f"? AS v{i}" for i in range(65)))
        payload = struct.pack("<IBI", sid, 0, 1) + bytes(9) + b"\1" + b"\x01\0" * 65 + bytes(range(65))
        result["cases"]["columns65"] = execute(c, payload)
        assert len(result["cases"]["columns65"]["columns"]) == 65
        close_ping(c, sid)
        with c.cursor() as q:
            q.execute("SELECT 1")
            assert q.fetchone() == (1,)
    result["result"] = "PASS"
    return result


def main():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--native-port", type=int)
    source.add_argument("--host")
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {"result": "FAIL", "scope": "P2 vectors only"}
    try:
        if args.host:
            import mariamem
            with mariamem.start(host_binary=args.host) as db:
                result = exercise(db.connection_info())
        else:
            result = exercise(dict(host="127.0.0.1", port=args.native_port,
                                   user="root", database="test"))
        if args.reference:
            expected = json.loads(args.reference.read_text())
            assert result["cases"] == expected["cases"], "P2 raw results differ from native"
            result["native_comparison"] = "PASS"
    except Exception as error:
        result.update(result="FAIL", error=repr(error))
        raise
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
