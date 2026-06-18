from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from langbot.pkg.entity import persistence as persistence_entities
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.utils import importutil

importutil.import_modules_in_pkg(persistence_entities)


def _normalize_postgres_url(url: str) -> str:
    if url.startswith('postgres://'):
        url = 'postgresql://' + url.removeprefix('postgres://')
    if url.startswith('postgresql://'):
        return 'postgresql+asyncpg://' + url.removeprefix('postgresql://')
    return url


def _sqlite_tables(sqlite_path: Path) -> set[str]:
    with sqlite3.connect(sqlite_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {str(row[0]) for row in rows}


def _sqlite_rows(sqlite_path: Path, table_name: str) -> list[dict[str, Any]]:
    with sqlite3.connect(sqlite_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(f'SELECT * FROM "{table_name}"').fetchall()
    return [dict(row) for row in rows]


def _coerce_value(column: sqlalchemy.Column, value: Any) -> Any:
    if value is None:
        return None
    type_name = column.type.__class__.__name__.lower()
    if 'json' in type_name and isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    if 'datetime' in type_name and isinstance(value, str):
        try:
            return datetime.datetime.fromisoformat(value)
        except ValueError:
            return value
    if 'boolean' in type_name and isinstance(value, int):
        return bool(value)
    return value


async def _table_row_count(engine: AsyncEngine, table: sqlalchemy.Table) -> int:
    async with engine.connect() as conn:
        result = await conn.execute(sqlalchemy.select(sqlalchemy.func.count()).select_from(table))
        return int(result.scalar_one())


async def _postgres_has_any_rows(engine: AsyncEngine) -> bool:
    for table in Base.metadata.sorted_tables:
        if await _table_row_count(engine, table) > 0:
            return True
    return False


async def _clear_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


async def _reset_postgres_sequences(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            integer_pk_columns = [
                column
                for column in table.primary_key.columns
                if isinstance(column.type, sqlalchemy.Integer)
            ]
            for column in integer_pk_columns:
                await conn.execute(
                    sqlalchemy.text(
                        "SELECT setval(pg_get_serial_sequence(:table_name, :column_name), "
                        f"COALESCE((SELECT MAX(\"{column.name}\") FROM \"{table.name}\"), 1), true)"
                    ),
                    {'table_name': table.name, 'column_name': column.name},
                )


async def sync_sqlite_to_postgres(sqlite_path: Path, postgres_url: str, replace: bool = False) -> int:
    if not sqlite_path.exists():
        raise FileNotFoundError(f'SQLite database not found: {sqlite_path}')

    engine = create_async_engine(_normalize_postgres_url(postgres_url))
    sqlite_table_names = _sqlite_tables(sqlite_path)
    inserted = 0
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        if replace:
            await _clear_tables(engine)
        elif await _postgres_has_any_rows(engine):
            print('PostgreSQL already contains data; skipping SQLite seed. Use --replace to overwrite.')
            return 0

        async with engine.begin() as conn:
            for table in Base.metadata.sorted_tables:
                if table.name not in sqlite_table_names:
                    continue
                rows = _sqlite_rows(sqlite_path, table.name)
                if not rows:
                    continue
                valid_columns = {column.name: column for column in table.columns}
                converted_rows = [
                    {
                        name: _coerce_value(valid_columns[name], value)
                        for name, value in row.items()
                        if name in valid_columns
                    }
                    for row in rows
                ]
                await conn.execute(table.insert(), converted_rows)
                inserted += len(converted_rows)

        if inserted:
            await _reset_postgres_sequences(engine)
    finally:
        await engine.dispose()
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser(description='Seed PostgreSQL from a bundled LangBot SQLite database.')
    parser.add_argument('--sqlite', default='data/langbot.db', help='Path to local SQLite database.')
    parser.add_argument(
        '--postgres-url',
        default=os.environ.get('DATABASE_URL') or os.environ.get('DATABASE_PUBLIC_URL', ''),
        help='PostgreSQL connection URL.',
    )
    parser.add_argument('--replace', action='store_true', help='Delete existing PostgreSQL rows before importing.')
    args = parser.parse_args()

    if not args.postgres_url:
        raise SystemExit('DATABASE_URL or --postgres-url is required.')

    inserted = asyncio.run(sync_sqlite_to_postgres(Path(args.sqlite), args.postgres_url, replace=args.replace))
    print(f'SQLite to PostgreSQL sync complete. Inserted rows: {inserted}')


if __name__ == '__main__':
    main()
