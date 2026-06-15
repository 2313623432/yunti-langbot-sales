import datetime
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import sqlalchemy
import pytest

from scripts import sync_sqlite_to_postgres


def test_normalize_postgres_url_supports_railway_postgres_scheme():
    assert (
        sync_sqlite_to_postgres._normalize_postgres_url('postgres://user:pass@example.com:5432/db')
        == 'postgresql+asyncpg://user:pass@example.com:5432/db'
    )


def test_coerce_value_converts_json_datetime_and_bool():
    json_column = sqlalchemy.Column('payload', sqlalchemy.JSON)
    datetime_column = sqlalchemy.Column('created_at', sqlalchemy.DateTime)
    bool_column = sqlalchemy.Column('enabled', sqlalchemy.Boolean)

    assert sync_sqlite_to_postgres._coerce_value(json_column, '{"a": 1}') == {'a': 1}
    assert sync_sqlite_to_postgres._coerce_value(json_column, json.dumps(['x'])) == ['x']
    assert sync_sqlite_to_postgres._coerce_value(datetime_column, '2026-06-15T10:30:00') == datetime.datetime(
        2026, 6, 15, 10, 30
    )
    assert sync_sqlite_to_postgres._coerce_value(bool_column, 1) is True
    assert sync_sqlite_to_postgres._coerce_value(bool_column, 0) is False


@pytest.mark.asyncio
async def test_reset_postgres_sequences_sets_integer_primary_keys(monkeypatch):
    test_table = sqlalchemy.Table(
        'example_table',
        sqlalchemy.MetaData(),
        sqlalchemy.Column('id', sqlalchemy.Integer, primary_key=True),
        sqlalchemy.Column('name', sqlalchemy.String),
    )
    executed = []

    class FakeConnection:
        async def execute(self, statement, params=None):
            executed.append((str(statement), params))

    class FakeBegin:
        async def __aenter__(self):
            return FakeConnection()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeEngine:
        def begin(self):
            return FakeBegin()

    monkeypatch.setattr(sync_sqlite_to_postgres.Base, 'metadata', SimpleNamespace(sorted_tables=[test_table]))

    await sync_sqlite_to_postgres._reset_postgres_sequences(FakeEngine())

    assert len(executed) == 1
    statement, params = executed[0]
    assert 'setval' in statement
    assert 'MAX("id")' in statement
    assert params == {'table_name': 'example_table', 'column_name': 'id'}
