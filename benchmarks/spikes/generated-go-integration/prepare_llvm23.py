#!/usr/bin/env python3
"""Extract a pinned, isolated LLVM 23 toolchain and its official ICU dependency.

No host installation or SDK mutation. Inputs must already be downloaded.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile

LLVM_SHA = 'cfb31bfc713ef453248bf5bd026312f838ad6c52c25623e987cb6a340f3050d4'
ICU_SHA = 'ac68372cf4a976e6a206858fd9b28c68e49d37d650b9b8653270038a6e7bc174'
ROOT = 'LLVM-23.1.0-Linux-ARM64'
TOOLS = {'clang', 'clang++', 'clang-23', 'lld', 'ld.lld', 'wasm-ld', 'llvm-ar', 'llvm-ranlib', 'llvm-nm'}


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--llvm-archive', type=Path, required=True)
    parser.add_argument('--icu-package', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output must be fresh')
    if sha(args.llvm_archive) != LLVM_SHA or sha(args.icu_package) != ICU_SHA:
        parser.error('toolchain input checksum mismatch')
    args.output.mkdir(parents=True)
    with tarfile.open(args.llvm_archive, mode='r|xz') as archive:
        for member in archive:
            parts = Path(member.name).parts
            if not parts or parts[0] != ROOT:
                continue
            relative = Path(*parts[1:])
            selected = (len(relative.parts) == 2 and relative.parts[0] == 'bin' and relative.name in TOOLS) or (len(relative.parts) == 2 and relative.parts[0] == 'lib' and '.so' in relative.name) or str(relative).startswith('lib/clang/23/include/')
            # WASIX SDK intentionally does not expose native ARM NEON headers.
            # A native-only header cannot stand in for a WASM SIMDe header.
            if relative.name == "arm_neon.h":
                selected = False
            if selected:
                archive.extract(member, args.output, filter='data')
    data = args.icu_package.read_bytes()
    if data[:8] != b'!<arch>\n':
        raise ValueError('not a Debian archive')
    at = 8
    found = False
    while at < len(data):
        header = data[at:at+60]
        size = int(header[48:58])
        name = header[:16].decode().strip().rstrip('/')
        payload = data[at+60:at+60+size]
        at += 60+size+(size % 2)
        if name.startswith('data.tar'):
            found = True
            with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
                for member in archive:
                    filename = Path(member.name).name
                    if not filename.startswith('libicu') or '.so' not in filename:
                        continue
                    target = args.output/ROOT/'lib'/filename
                    if member.issym():
                        if Path(member.linkname).name != member.linkname:
                            raise ValueError('unexpected ICU symlink')
                        target.symlink_to(member.linkname)
                    elif member.isfile():
                        target.write_bytes(archive.extractfile(member).read())
    if not found:
        raise ValueError('ICU payload missing')
    prefix = args.output/ROOT
    files = {}
    for p in sorted(prefix.rglob('*')):
        if p.is_symlink():
            files[str(p.relative_to(prefix))] = {'symlink':str(p.readlink())}
        elif p.is_file():
            files[str(p.relative_to(prefix))] = {'sha256':sha(p)}
    manifest = {'llvm_release':'23.1.0','llvm_source_commit':'ea7d852a70e8bdfaf601d6626a760f9771b2c4b4','upstream_fix':'fd76c9bdf10383ae536d8c504dafe3bd91947d83','llvm_archive_sha256':LLVM_SHA,'icu_package_sha256':ICU_SHA,'header_profile':'WASM: native-only arm_neon.h excluded (matches WASIX SDK visibility)','files':files}
    (prefix/'toolchain-inputs.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(prefix)


if __name__ == '__main__':
    main()
