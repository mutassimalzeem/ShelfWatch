"""Copy the local SQLite snapshots into an empty hosted PostgreSQL database."""

import os
import sqlite3
import sys

import pandas as pd
from sqlalchemy import text

from src.storage.db import DB_PATH, _connect, init_db


SNAPSHOT_COLUMNS = (
    "id",
    "source",
    "title",
    "price",
    "list_price",
    "discount_percent",
    "stock_flag",
    "category_path",
    "category_rank",
    "url",
    "scraped_at",
)


def migrate_sqlite_to_database(sqlite_path: str = DB_PATH) -> int:
    """Copy all core snapshot fields, preserving observation IDs and UTC times."""
    if not os.environ.get("DATABASE_URL"):
        raise RuntimeError("Set DATABASE_URL to the destination PostgreSQL connection.")
    if not os.path.isfile(sqlite_path):
        raise FileNotFoundError(f"SQLite source database not found: {sqlite_path}")

    source = sqlite3.connect(f"file:{os.path.abspath(sqlite_path)}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    try:
        available_columns = {
            row["name"] for row in source.execute("PRAGMA table_info(snapshots)")
        }
        if not set(SNAPSHOT_COLUMNS).issubset(available_columns):
            raise RuntimeError("The SQLite snapshots table does not match the expected schema.")
        row_count = source.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        if row_count == 0:
            raise RuntimeError("The SQLite snapshots table is empty; nothing to migrate.")

        engine = _connect()
        try:
            with engine.begin() as destination:
                init_db(destination)
                current_rows = destination.execute(
                    text("SELECT COUNT(*) FROM snapshots")
                ).scalar_one()
                if current_rows:
                    raise RuntimeError(
                        "The destination already contains snapshots; refusing to duplicate or overwrite data."
                    )

                columns = ", ".join(SNAPSHOT_COLUMNS)
                query = f"SELECT {columns} FROM snapshots ORDER BY id"
                for batch in pd.read_sql_query(query, source, chunksize=500):
                    if destination.dialect.name == "postgresql":
                        batch["scraped_at"] = pd.to_datetime(
                            batch["scraped_at"], utc=True
                        )
                    batch.to_sql(
                        "snapshots",
                        destination,
                        if_exists="append",
                        index=False,
                        chunksize=500,
                    )

                if destination.dialect.name == "postgresql":
                    destination.execute(text("""
                        SELECT setval(
                            pg_get_serial_sequence('snapshots', 'id'),
                            COALESCE(MAX(id), 1),
                            COUNT(*) > 0
                        )
                        FROM snapshots
                    """))
        finally:
            engine.dispose()
    finally:
        source.close()

    print(f"[DB] Migrated {row_count} snapshot observations.")
    return row_count


if __name__ == "__main__":
    try:
        migrate_sqlite_to_database()
    except (FileNotFoundError, RuntimeError) as error:
        print(f"[DB] Migration failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
