"""Download two immutable successful-C-input artifacts; verify ZIP before extraction."""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import zipfile

RUN = 42433100335
ARTIFACTS = {
    'guest': (13598059891, '953a2589b5c846ef118c99020a7e6505ff83d0e2d8dc5f617fcdf778467c6f90'),
    'reference': (13597914099, '5785b4ace826613149f1b769a03ca218129ab53234327403d6c0f2f8293e76d6'),
}


def extract(path, output, expected):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError('artifact ZIP digest mismatch')
    with zipfile.ZipFile(path) as archive:
        for item in archive.infolist():
            name = Path(item.filename)
            if name.is_absolute() or '..' in name.parts or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('unsafe artifact member')
        archive.extractall(output)


def main():
    p = argparse.ArgumentParser(); p.add_argument('--output', type=Path, required=True); a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    records = {}
    for name, (identity, expected) in ARTIFACTS.items():
        metadata = json.loads(subprocess.check_output(['gh', 'api', f'repos/masahitojp/mariamem/actions/artifacts/{identity}']))
        assert metadata['workflow_run']['id'] == RUN and metadata['expired'] is False
        assert metadata['digest'] == 'sha256:'+expected
        path = a.output/(name+'.zip')
        with path.open('wb') as stream:
            subprocess.run(['gh','api',f'repos/masahitojp/mariamem/actions/artifacts/{identity}/zip'], stdout=stream, check=True)
        extract(path, a.output/name, expected)
        records[name] = {'run_id':RUN, 'artifact_id':identity, 'zip_sha256':expected, 'metadata':metadata}
    (a.output/'acquisition.json').write_text(json.dumps(records, indent=2)+'\n')

if __name__ == '__main__': main()
