"""Record actual connector availability and import errors without patching it."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import ssl
import sys
import sysconfig


def capture():
    import mysql.connector as connector
    r={'python':sys.version,'os':platform.system(),'architecture':platform.machine(),'openssl':ssl.OPENSSL_VERSION,'python_minor':'.'.join(map(str,sys.version_info[:2])),'soabi':sysconfig.get_config_var('SOABI'),'connector':connector.__version__,'connector_have_cext':connector.HAVE_CEXT}
    root=Path(connector.__file__).parent
    sources={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*.py'))}
    r['connector_sources_sha256']=hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest()
    spec=importlib.util.find_spec('_mysql_connector')
    if spec and spec.origin:
        p=Path(spec.origin);r['extension_file']=p.name;r['extension_sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
    try:
        import _mysql_connector
        r['direct_import']='PASS'
    except (ImportError,OSError) as e:
        r['direct_import']='FAIL';r['import_error']=str(e)
    return r


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--require-cext',action='store_true');a=p.parse_args()
    r=capture();a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n')
    if a.require_cext and (r['direct_import']!='PASS' or not r['connector_have_cext']):raise SystemExit('required native C-extension control unavailable; see environment receipt')

if __name__=='__main__':main()
