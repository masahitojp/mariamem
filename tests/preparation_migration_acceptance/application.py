"""Small authored application using its ordinary, original connection settings."""
import os
from sqlalchemy import URL, create_engine, text

engine = create_engine(URL.create('mysql+pymysql', username='application',
    password='synthetic-test-secret', host='127.0.0.1',
    port=int(os.environ['MIGRATION_ORIGINAL_PORT']), database='app'))


def users():
    with engine.connect() as connection:
        return [tuple(row) for row in connection.execute(text('SELECT id,name,rating FROM users ORDER BY id'))]


def create_user():
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO users(id,name,rating) VALUES(3,'created',7)"))


def invalid_address():
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO addresses(id,user_id,email) VALUES(2,9999,'invalid@example.test')"))
