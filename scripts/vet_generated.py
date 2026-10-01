#!/usr/bin/env python3
"""Go vet adapter: scope only unreachable to generated pure-function packages.

go vet also analyzes dependencies, so selecting target package lists alone does
not scope an analyzer. Inspect each standard vet configuration instead.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def main():
    tool = os.environ['MARIAMEM_VET_TOOL']
    args = sys.argv[1:]
    if args == ['-V=full']:
        version = subprocess.check_output([tool,*args],text=True).strip()
        identity = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]
        print(version+'-mariamem-scope-'+identity)
        return
    if args and args[-1].endswith('.cfg'):
        config = json.loads(Path(args[-1]).read_text())
        if re.search(r'/internal/generatedgo/code/p[0-9]+$',config.get('ImportPath','')):
            args = ['-unreachable=false',*args]
    result = subprocess.run([tool,*args])
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
