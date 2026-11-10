"""Read-only source facts. Run after acquire.py in a disposable workspace."""
import hashlib
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parents[3]
manifest = json.loads((root / 'evidence/source-files.json').read_text())
source = root / 'temp/upstream'
for name, identity in manifest['files'].items():
    data = (source / name).read_bytes()
    assert hashlib.sha256(data).hexdigest() == identity['sha256'], name

locale = (source / 'sql/sql_locale.cc').read_text()
locale_list = locale.split('MY_LOCALE *my_locales[]=')[1].split('};', 1)[0]
locale_entries = len(re.findall(r'&my_locale_[A-Za-z_0-9]+', locale_list))
json_source = (source / 'sql/json_schema.cc').read_text()
keywords = json_source.split(
    'static st_json_schema_keyword_map json_schema_func_array[]=')[1].split('};', 1)[0]
print(json.dumps({
    'mariadb_source_commit': manifest['mariadb_source_commit'],
    'verified_files': len(manifest['files']),
    'locale_entries': locale_entries,
    'locale_typelib_visits_per_init': locale_entries * 5,
    'locale_visits_include_shared_typelibs': True,
    'json_schema_keyword_entries': keywords.count('STRING_WITH_LEN('),
    'json_schema_hash_initial_capacity': 1024,
    'counts_are_source_facts_not_runtime_costs': True,
}, indent=2))
