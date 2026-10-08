"""ShelfWatch's read-only API and small, same-origin dashboard."""

from contextlib import contextmanager
import os
import sqlite3
from typing import Iterator

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.features.pack_parser import parse_pack_size


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(ROOT_DIR, "shelfwatch.db")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI(
    title="ShelfWatch API",
    description="Grocery availability and price intelligence for Bangladesh.",
    version="1.1.0",
)
app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


@contextmanager
def _connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        _require_snapshots(conn)
        yield conn
    finally:
        conn.close()


def _require_snapshots(conn: sqlite3.Connection) -> None:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'snapshots'"
    ).fetchone()
    if not exists:
        raise HTTPException(
            status_code=503,
            detail="The product database is not initialized. Run the scraper and ingest its CSV.",
        )


def _columns(conn: sqlite3.Connection) -> set[str]:
    return {row["name"] for row in conn.execute("PRAGMA table_info(snapshots)")}


LATEST_PRODUCTS = """
WITH ranked_products AS (
    SELECT id, source, title, price, list_price, discount_percent, stock_flag,
           category_path, category_rank, url, scraped_at,
           ROW_NUMBER() OVER (
               PARTITION BY source, COALESCE(NULLIF(url, ''), title)
               ORDER BY scraped_at DESC, id DESC
           ) AS product_rank
    FROM snapshots
)
"""


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/health")
def health() -> dict:
    with _connection() as conn:
        return {"status": "ok", "observations": conn.execute(
            "SELECT COUNT(*) FROM snapshots"
        ).fetchone()[0]}


@app.get("/api/overview")
def get_overview() -> dict:
    with _connection() as conn:
        current = conn.execute(
            LATEST_PRODUCTS
            + """
            SELECT COUNT(*) AS products,
                   SUM(CASE WHEN stock_flag = 'out_of_stock' THEN 1 ELSE 0 END) AS out_of_stock,
                   SUM(CASE WHEN price IS NULL THEN 1 ELSE 0 END) AS unpriced,
                   COUNT(DISTINCT source) AS retailers
            FROM ranked_products
            WHERE product_rank = 1
            """
        ).fetchone()
        observations = conn.execute(
            "SELECT COUNT(*) FROM snapshots"
        ).fetchone()[0]
        latest = conn.execute(
            "SELECT MAX(scraped_at) FROM snapshots"
        ).fetchone()[0]
        retailers = conn.execute(
            LATEST_PRODUCTS
            + """
            SELECT source, COUNT(*) AS products,
                   SUM(CASE WHEN stock_flag = 'out_of_stock' THEN 1 ELSE 0 END) AS out_of_stock
            FROM ranked_products
            WHERE product_rank = 1
            GROUP BY source
            ORDER BY source
            """
        ).fetchall()
        activity = conn.execute(
            """
            SELECT substr(scraped_at, 1, 10) AS day, COUNT(*) AS observations
            FROM snapshots
            GROUP BY day
            ORDER BY day DESC
            LIMIT 14
            """
        ).fetchall()

    return {
        "products": current["products"] or 0,
        "observations": observations,
        "out_of_stock": current["out_of_stock"] or 0,
        "unpriced": current["unpriced"] or 0,
        "retailers": current["retailers"] or 0,
        "last_updated": latest,
        "retailer_breakdown": [dict(row) for row in retailers],
        "daily_activity": [dict(row) for row in reversed(activity)],
    }


@app.get("/api/products")
def get_products(
    q: str | None = Query(default=None, max_length=120),
    source: str | None = Query(default=None, max_length=80),
    stock_flag: str | None = Query(
        default=None, pattern="^(in_stock|out_of_stock|unknown)$"
    ),
    sort: str = Query(default="recent", pattern="^(recent|price_low|price_high|name)$"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    conditions = ["product_rank = 1"]
    params: list[object] = []
    if q:
        conditions.append("(title LIKE ? OR category_path LIKE ?)")
        term = f"%{q.strip()}%"
        params.extend((term, term))
    if source:
        conditions.append("source = ?")
        params.append(source)
    if stock_flag:
        conditions.append("stock_flag = ?")
        params.append(stock_flag)

    ordering = {
        "recent": "scraped_at DESC, id DESC",
        "price_low": "price IS NULL, price ASC, title COLLATE NOCASE",
        "price_high": "price IS NULL, price DESC, title COLLATE NOCASE",
        "name": "title COLLATE NOCASE ASC",
    }[sort]
    where = " AND ".join(conditions)

    with _connection() as conn:
        total = conn.execute(
            LATEST_PRODUCTS + f"SELECT COUNT(*) FROM ranked_products WHERE {where}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            LATEST_PRODUCTS
            + f"""
            SELECT id, source, title, price, list_price, discount_percent,
                   stock_flag, category_path, category_rank, url, scraped_at
            FROM ranked_products
            WHERE {where}
            ORDER BY {ordering}
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()

    return {
        "items": [dict(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/products/{snapshot_id}/history")
def get_product_history(snapshot_id: int) -> dict:
    with _connection() as conn:
        product = conn.execute(
            "SELECT source, title, url FROM snapshots WHERE id = ?",
            (snapshot_id,),
        ).fetchone()
        if product is None:
            raise HTTPException(status_code=404, detail="Product snapshot not found.")

        if product["url"]:
            history = conn.execute(
                """
                SELECT id, price, list_price, discount_percent, stock_flag, scraped_at
                FROM snapshots
                WHERE source = ? AND url = ?
                ORDER BY scraped_at, id
                """,
                (product["source"], product["url"]),
            ).fetchall()
        else:
            history = conn.execute(
                """
                SELECT id, price, list_price, discount_percent, stock_flag, scraped_at
                FROM snapshots
                WHERE source = ? AND (url IS NULL OR url = '') AND title = ?
                ORDER BY scraped_at, id
                """,
                (product["source"], product["title"]),
            ).fetchall()

    return {
        "source": product["source"],
        "title": product["title"],
        "history": [dict(row) for row in history],
    }


@app.get("/api/stockouts/current")
def get_current_stockouts(
    source: str | None = Query(default=None, max_length=80),
) -> list[dict]:
    params: list[object] = []
    source_clause = ""
    if source:
        source_clause = " AND source = ?"
        params.append(source)
    with _connection() as conn:
        rows = conn.execute(
            LATEST_PRODUCTS
            + """
            SELECT id, source, title, url, price, stock_flag, scraped_at
            FROM ranked_products
            WHERE product_rank = 1 AND stock_flag = 'out_of_stock'
            """
            + source_clause
            + " ORDER BY scraped_at DESC, title COLLATE NOCASE",
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def _shrinkflation_from_features(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        WITH product_history AS (
            SELECT id, source, title, url, price, normalized_amount, normalized_unit,
                   scraped_at,
                   LAG(normalized_amount) OVER (
                       PARTITION BY source, COALESCE(NULLIF(url, ''), title)
                       ORDER BY scraped_at, id
                   ) AS previous_amount,
                   LAG(normalized_unit) OVER (
                       PARTITION BY source, COALESCE(NULLIF(url, ''), title)
                       ORDER BY scraped_at, id
                   ) AS previous_unit
            FROM snapshots
            WHERE normalized_amount IS NOT NULL
        )
        SELECT id, source, title, url, price, normalized_amount, normalized_unit,
               scraped_at, previous_amount
        FROM product_history
        WHERE previous_amount IS NOT NULL
          AND normalized_amount < previous_amount
          AND (
              (normalized_unit IN ('g', 'kg') AND previous_unit IN ('g', 'kg'))
              OR (normalized_unit IN ('ml', 'l') AND previous_unit IN ('ml', 'l'))
          )
        ORDER BY scraped_at DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _shrinkflation_from_titles(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, source, title, url, price, scraped_at
        FROM snapshots
        ORDER BY source, COALESCE(NULLIF(url, ''), title), scraped_at, id
        """
    ).fetchall()
    previous: dict[tuple[str, str], tuple[float, str]] = {}
    alerts = []
    for row in rows:
        value, unit, amount = parse_pack_size(row["title"])
        if amount is None or unit == "piece":
            continue
        key = (row["source"], row["url"] or row["title"])
        prior = previous.get(key)
        current_dimension = "volume" if unit in ("ml", "l") else "weight"
        if prior and prior[1] == current_dimension and amount < prior[0]:
            alerts.append({
                "id": row["id"],
                "source": row["source"],
                "title": row["title"],
                "url": row["url"],
                "price": row["price"],
                "normalized_amount": amount,
                "normalized_unit": unit,
                "scraped_at": row["scraped_at"],
                "previous_amount": prior[0],
            })
        previous[key] = (amount, current_dimension)
    return sorted(alerts, key=lambda alert: alert["scraped_at"], reverse=True)


@app.get("/api/shrinkflation/alerts")
def get_shrinkflation_alerts() -> list[dict]:
    with _connection() as conn:
        if {"normalized_amount", "normalized_unit"}.issubset(_columns(conn)):
            return _shrinkflation_from_features(conn)
        return _shrinkflation_from_titles(conn)
