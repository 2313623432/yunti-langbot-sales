import datetime
import json

import sqlalchemy

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
