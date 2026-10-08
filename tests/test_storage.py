"""Storage ingestion and hosted-database migration contracts."""

import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from sqlalchemy.engine import URL

from src.storage import db, migrate_to_postgres


class TestDatabaseStorage(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "shelfwatch.db")
        self.csv_path = os.path.join(self.temp_dir.name, "snapshot.csv")
        self.database_patch = patch.dict(os.environ, {"DATABASE_URL": ""})
        self.database_patch.start()
        self.db_path_patch = patch.object(db, "DB_PATH", self.db_path)
        self.db_path_patch.start()

    def tearDown(self):
        self.db_path_patch.stop()
        self.database_patch.stop()
        self.temp_dir.cleanup()

    def _write_csv(self):
        with open(self.csv_path, "w", encoding="utf-8") as csv_file:
            csv_file.write(
                "source,title,price,list_price,discount_percent,stock_flag,"
                "category_path,category_rank,url,scraped_at\n"
                "chaldal,Rice 1kg,100,120,16.7,in_stock,Rice,1,"
                "https://shop.test/rice,2026-10-01T10:00:00+00:00\n"
                "shwapno,Oil 1L,180,,,in_stock,Oil,1,"
                "https://shop.test/oil,2026-10-01T10:00:00+00:00\n"
            )

    def test_sqlite_csv_ingestion_is_idempotent(self):
        self._write_csv()
        self.assertEqual(db.ingest_latest_csv(self.csv_path), 2)
        self.assertEqual(db.ingest_latest_csv(self.csv_path), 0)

        conn = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0], 2)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM ingest_log").fetchone()[0], 1)
        finally:
            conn.close()

    def test_sqlite_data_migration_preserves_ids_and_refuses_overwrite(self):
        self._write_csv()
        db.ingest_latest_csv(self.csv_path)
        target_path = os.path.join(self.temp_dir.name, "hosted.db")
        target_url = URL.create("sqlite", database=target_path).render_as_string(
            hide_password=False
        )
        with patch.dict(os.environ, {"DATABASE_URL": target_url}):
            self.assertEqual(
                migrate_to_postgres.migrate_sqlite_to_database(self.db_path), 2
            )
            conn = sqlite3.connect(target_path)
            try:
                rows = conn.execute(
                    "SELECT id, title FROM snapshots ORDER BY id"
                ).fetchall()
            finally:
                conn.close()
            self.assertEqual(rows, [(1, "Rice 1kg"), (2, "Oil 1L")])
            with self.assertRaisesRegex(RuntimeError, "already contains snapshots"):
                migrate_to_postgres.migrate_sqlite_to_database(self.db_path)


if __name__ == "__main__":
    unittest.main()
