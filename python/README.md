# mariamem

Disposable, in-memory MariaDB for Python tests. Start an isolated database,
connect with a MySQL client, and close it when the test finishes. Snapshot and
Fork support independent test databases from a prepared state.

```sh
# macOS arm64
python -m pip install mariamem PyMySQL
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

For the platforms and installation commands for the current release, see the
[installation guide](https://github.com/masahitojp/mariamem#installation).
The macOS arm64 wheel is published on PyPI. For Ubuntu 24.04 x86_64, download
the matching wheel from GitHub Releases.
The wheel includes the generated-Go host; Go and a separate MariaDB server are
not required at runtime. Python 3.11 or newer is required.

See the [Python guide](https://github.com/masahitojp/mariamem/blob/main/docs/python.md),
[API reference](https://github.com/masahitojp/mariamem/blob/main/docs/python-reference.md)
and [releases](https://github.com/masahitojp/mariamem/releases).

mariamem is distributed under GPL-2.0-only. Distribution includes license notices;
corresponding source is provided with the matching GitHub release.
