"""Small installed-wheel SQLAlchemy consumer; no dialect/capability workaround."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import sys

import mariamem
from sqlalchemy import String, URL, create_engine, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'release_users'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)


def run(args):
    if os.environ.get('MARIAMEM_NATIVE_DIR'):
        raise RuntimeError('native override present')
    if not Path(mariamem.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):
        raise RuntimeError('checkout import')
    if mariamem.__version__ != args.version:
        raise RuntimeError('wrong wheel version')
    origin = json.loads(importlib.metadata.distribution('mariamem').read_text('direct_url.json'))
    if origin['archive_info']['hashes']['sha256'] != args.wheel_sha256:
        raise RuntimeError('wrong installed wheel')
    with mariamem.start() as db:
        info = db.connection_info()
        engine = create_engine(URL.create('mysql+pymysql', username=info['user'], password=info['password'],
                                          host=info['host'], port=info['port'], database=info['database']))
        try:
            Base.metadata.create_all(engine)
            with Session(engine) as session:
                session.add(User(name='committed'))
                session.commit()
            with Session(engine) as session:
                if session.scalar(select(User.name)) != 'committed':
                    raise RuntimeError('committed row was not visible')
            with engine.begin() as connection:
                if connection.execute(text('UPDATE release_users SET name=name')).rowcount != 1:
                    raise RuntimeError('CLIENT_FOUND_ROWS semantics absent')
                if connection.scalar(text('SELECT 1')) != 1:
                    raise RuntimeError('SELECT 1 failed')
        finally:
            engine.dispose()
    return {'result': 'PASS', 'version': mariamem.__version__, 'wheel_sha256': args.wheel_sha256,
            'consumer_outside_repository': True, 'native_overrides': False,
            'matched_rowcount': 1, 'sqlalchemy': importlib.metadata.version('SQLAlchemy')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True)
    parser.add_argument('--wheel-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = {'result': 'FAIL'}
    try:
        report = run(args)
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        args.output.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
