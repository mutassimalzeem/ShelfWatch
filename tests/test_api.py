"""API contract tests against a small, isolated SQLite database."""

import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api import main as api


class TestShelfWatchAPI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.db")
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            CREATE TABLE snapshots (
                id INTEGER PRIMARY KEY,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                price REAL,
                list_price REAL,
                discount_percent REAL,
                stock_flag TEXT NOT NULL,
                category_path TEXT,
                category_rank INTEGER,
                url TEXT,
                scraped_at TIMESTAMP NOT NULL
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO snapshots
                (id, source, title, price, list_price, discount_percent,
                 stock_flag, category_path, url, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (1, "chaldal", "Miniket Rice 1kg", 100, 120, 16.7, "in_stock",
                 "Rice", "https://shop.test/rice", "2026-10-01T10:00:00+00:00"),
                (2, "chaldal", "Miniket Rice 900gm", 105, 120, 12.5, "out_of_stock",
                 "Rice", "https://shop.test/rice", "2026-10-02T10:00:00+00:00"),
                (3, "chaldal", "Soybean Oil 1L", 180, None, None, "in_stock",
                 "Oil", "https://shop.test/oil", "2026-10-02T10:00:00+00:00"),
                (4, "shwapno", "Fresh Apple 1kg", 320, None, None, "unknown",
                 "Fruit", "https://other.test/apple", "2026-10-02T10:00:00+00:00"),
            ],
        )
        conn.commit()
        conn.close()
        self.db_patch = patch.object(api, "DB_PATH", self.db_path)
        self.db_patch.start()
        self.client = TestClient(api.app)

    def tearDown(self):
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_overview_summarizes_latest_products_and_observations(self):
        response = self.client.get("/api/overview")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["products"], 3)
        self.assertEqual(data["observations"], 4)
        self.assertEqual(data["out_of_stock"], 1)
        self.assertEqual(data["retailers"], 2)
        self.assertEqual(len(data["daily_activity"]), 2)

    def test_product_search_filter_sort_and_pagination(self):
        response = self.client.get(
            "/api/products", params={"q": "rice", "source": "chaldal", "limit": 1}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["title"], "Miniket Rice 900gm")
        self.assertEqual(data["items"][0]["stock_flag"], "out_of_stock")

        page = self.client.get("/api/products", params={"limit": 1, "offset": 1})
        self.assertEqual(page.json()["total"], 3)
        self.assertEqual(len(page.json()["items"]), 1)

    def test_stockouts_returns_latest_stock_flag_not_missing_pack_size(self):
        response = self.client.get("/api/stockouts/current")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["title"] for item in response.json()], ["Miniket Rice 900gm"])
        self.assertEqual(self.client.get("/api/stockouts/current?source=shwapno").json(), [])

    def test_product_history_is_ordered_and_uses_snapshot_id(self):
        latest = self.client.get("/api/products", params={"q": "rice"}).json()["items"][0]
        response = self.client.get(f"/api/products/{latest['id']}/history")
        self.assertEqual(response.status_code, 200)
        history = response.json()["history"]
        self.assertEqual([item["price"] for item in history], [100, 105])
        self.assertEqual(self.client.get("/api/products/999/history").status_code, 404)

    def test_pack_size_watch_works_without_stored_normalized_columns(self):
        response = self.client.get("/api/shrinkflation/alerts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["title"], "Miniket Rice 900gm")
        self.assertEqual(response.json()[0]["previous_amount"], 1000.0)

    def test_pack_size_watch_uses_stored_features_when_available(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("ALTER TABLE snapshots ADD COLUMN normalized_amount REAL")
        conn.execute("ALTER TABLE snapshots ADD COLUMN normalized_unit TEXT")
        conn.executemany(
            "UPDATE snapshots SET normalized_amount = ?, normalized_unit = ? WHERE id = ?",
            [(1000, "g", 1), (900, "g", 2), (1000, "l", 3), (1000, "g", 4)],
        )
        conn.commit()
        conn.close()

        response = self.client.get("/api/shrinkflation/alerts")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["id"], 2)
        self.assertEqual(response.json()[0]["previous_amount"], 1000)

    def test_dashboard_and_static_assets_are_served(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertIn("ShelfWatch", self.client.get("/").text)
        self.assertEqual(self.client.get("/assets/app.js").status_code, 200)


if __name__ == "__main__":
    unittest.main()
