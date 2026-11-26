# mariamem

Disposable, in-memory MariaDB for Python tests. Start an isolated database,
connect with a MySQL client, and close it when the test finishes. Snapshot and
Fork support independent test databases from a prepared state.

```sh
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

Prebuilt wheels are published on PyPI for macOS 15+ arm64, Linux x86_64 and
aarch64 (glibc 2.28+ / musl 1.2+), and Windows build 22000+ x86_64 and arm64.
For platform details and release-specific installation commands, see the
[installation guide](https://github.com/masahitojp/mariamem#installation) and
[GitHub Releases](https://github.com/masahitojp/mariamem/releases).
The wheel includes the generated-Go host; Go and a separate MariaDB server are
not required at runtime. Python 3.11 or newer is required.

See the [Python guide](https://github.com/masahitojp/mariamem/blob/main/docs/python.md),
[API reference](https://github.com/masahitojp/mariamem/blob/main/docs/python-reference.md)
and [releases](https://github.com/masahitojp/mariamem/releases).

mariamem is distributed under GPL-2.0-only. Distribution includes license notices;
corresponding source is provided with the matching GitHub release.
