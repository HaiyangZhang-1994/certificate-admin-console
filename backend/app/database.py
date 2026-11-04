"""Connections use explicit transactions, including SQLite read snapshots."""

import os
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url

from app.models.schema import metadata


def make_engine(url=None, busy_timeout=3000):
    url = url or os.getenv("DATABASE_URL", "sqlite:///./backend/data/certificates.db")
    database = make_url(url).database
    if database and database != ":memory:":
        Path(database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def configure(connection, _record):
        connection.isolation_level = None
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"PRAGMA busy_timeout={int(busy_timeout)}")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine


@contextmanager
def transaction(engine, write=False):
    with engine.connect() as connection:
        try:
            connection.exec_driver_sql("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise


def initialize(engine):
    metadata.create_all(engine)
