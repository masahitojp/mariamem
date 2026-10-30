"""Command/callback entry for the existing authored users/addresses corpus."""
import json
import os
from pathlib import Path


def prepare(info, migrations):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import URL, create_engine, text
    source = URL.create('mysql+pymysql', username=info['user'], password=info['password'],
                        host=info['host'], port=info['port'], database=info['database'])
    bootstrap = create_engine(source, pool_size=1, max_overflow=0)
    try:
        with bootstrap.begin() as connection:
            connection.execute(text('CREATE DATABASE app'))
    finally:
        bootstrap.dispose()
    target = create_engine(source.set(database='app'), pool_size=1, max_overflow=0)
    try:
        config = Config()
        config.set_main_option('script_location', str(migrations))
        config.set_main_option('sqlalchemy.url', target.url.render_as_string(hide_password=False).replace('%', '%%'))
        command.upgrade(config, 'head')
        with target.begin() as connection:
            connection.execute(text("INSERT INTO users(id,name,rating) VALUES(2,'seed',5)"))
            connection.execute(text("INSERT INTO addresses(id,user_id,email) VALUES(1,2,'seed@example.test')"))
    finally:
        target.dispose()
    with Path(os.environ['P1_EVENT_FILE']).open('a') as output:
        output.write(json.dumps({'event':'prepared','worker':os.environ.get('PYTEST_XDIST_WORKER','main')})+'\n')


if __name__ == '__main__':
    prepare(json.loads(os.environ['MARIAMEM_PREPARE_CONNECTION_INFO']),
            Path(os.environ['P1_MIGRATION_SOURCE']))
