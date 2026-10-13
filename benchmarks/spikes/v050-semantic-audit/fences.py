"""Construct small fence inputs and extract pinned libc ar members.

The linked sysroot reduction is evidence about an optimization stage, not an
independent rebuild of the complete adopted MariaDB guest.
"""
import argparse
import hashlib
from pathlib import Path


def uleb(n):
    out = bytearray()
    while True:
        out.append((n & 127) | (128 if n >= 128 else 0))
        n >>= 7
        if not n:
            return bytes(out)


def section(kind, payload):
    return bytes([kind])+uleb(len(payload))+payload


def fixture(functions):
    bodies = [b"\0\xfe\x03\0\x0b"] + [b"\0"+b"\x01"*1024+b"\x0b"]*(functions-1)
    return (b"\0asm\x01\0\0\0" + section(1,b"\x01\x60\0\0")
            + section(3,uleb(functions)+b"\0"*functions)
            + section(5,b"\x01\x03\x01\x01")
            + section(7,b"\x01\x01f\0\0")
            + section(10,uleb(functions)+b"".join(uleb(len(b))+b for b in bodies)))


def extract_ar(path, output):
    raw = path.read_bytes()
    assert raw.startswith(b"!<arch>\n")
    cursor, names, found = 8, b"", set()
    wanted = {"pthread_create.o", "pthread_join.o"}
    while cursor < len(raw):
        header = raw[cursor:cursor+60]
        assert header[58:60] == b"`\n"
        size = int(header[48:58])
        name = header[:16].decode().strip()
        data = raw[cursor+60:cursor+60+size]
        if name == "//":
            names = data
        elif name.startswith("/") and name[1:].isdigit():
            name = names[int(name[1:]):].split(b"/\n",1)[0].decode()
        else:
            name = name.rstrip("/")
        if name in wanted:
            assert name not in found
            (output/name).write_bytes(data)
            found.add(name)
        cursor += 60+size+(size%2)
    assert found == wanted


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--libc", type=Path)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    for name,n in (("fence.wasm",1),("fence-multi.wasm",1025)):
        data = fixture(n)
        (a.output/name).write_bytes(data)
        print(name, len(data), hashlib.sha256(data).hexdigest())
    if a.libc:
        extract_ar(a.libc,a.output)


if __name__ == "__main__":
    main()
