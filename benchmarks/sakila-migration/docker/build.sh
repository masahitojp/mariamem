#!/bin/sh
set -eu
if [ "$#" -ne 1 ]; then
    echo "usage: $0 image-id-file" >&2
    exit 2
fi
assets=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
stage=$(mktemp -d "${TMPDIR:-/tmp}/sakila-image.XXXXXX")
trap 'rm -r "$stage"' EXIT
mkdir "$stage/packages"
cp "$assets/Dockerfile" "$stage/"
python3 - "$assets/packages.json" "$stage/packages" <<'PY'
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
import sys
from urllib.request import urlopen

manifest = json.loads(Path(sys.argv[1]).read_text())
destination = Path(sys.argv[2])

def download(package):
    filename = package["Filename"]
    with urlopen(manifest["archive"] + filename, timeout=60) as response:
        content = response.read()
    if sha256(content).hexdigest() != package["SHA256"]:
        raise ValueError(f"Checksum mismatch for {filename}")
    (destination / Path(filename).name).write_bytes(content)

with ThreadPoolExecutor(max_workers=4) as executor:
    list(executor.map(download, manifest["packages"]))
PY
docker build --platform linux/arm64 --iidfile "$1" "$stage"
