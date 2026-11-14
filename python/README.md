# mariamem

Disposable, in-memory MariaDB for Python tests. Start an isolated database,
connect with a MySQL client, and close it when the test finishes. Snapshot and
Fork support independent test databases from a prepared state.

```sh
pip install mariamem PyMySQL
```

```python
import mariamem
import pymysql

with mariamem.start() as db:
    with pymysql.connect(**db.connection_info()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            assert cursor.fetchone() == (1,)
```

The 0.6.2 wheels support:

- macOS 15 or newer on arm64.
- Linux on x86_64 and aarch64, with glibc 2.28+ or musl 1.2+.
- Windows build 22000 or newer on x86_64 and arm64, using native Python
  for the selected architecture.

The wheel includes the generated-Go host; Go and a separate MariaDB server are
not required at runtime. Python 3.11 or newer is required.

See the [Python guide](https://github.com/masahitojp/mariamem/blob/722dfd1dbc1c077759b5c4062e1695066467bea4/docs/python.md),
[API reference](https://github.com/masahitojp/mariamem/blob/722dfd1dbc1c077759b5c4062e1695066467bea4/docs/python.md)
and [releases](https://github.com/masahitojp/mariamem/releases).

mariamem is distributed under GPL-2.0-only. Distribution includes license notices;
corresponding source is provided with the matching GitHub release.
