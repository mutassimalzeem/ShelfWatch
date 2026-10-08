"""ShelfWatch's read-only API and small, same-origin dashboard."""

from contextlib import contextmanager
import os
import re
from typing import Generator

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, URL

from src.features.pack_parser import parse_pack_size


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(ROOT_DIR, "shelfwatch.db")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
DATABASE_URL = os.environ.get("DATABASE_URL")


def _database_engine():
    database_url = os.environ.get("DATABASE_URL", DATABASE_URL)
    if database_url:
        if database_url.startswith("postgres://"):
            database_url = "postgresql://" + database_url.removeprefix("postgres://")
        return create_engine(database_url, pool_pre_ping=True)
    return create_engine(URL.create("sqlite", database=DB_PATH))


def _execute(conn: Connection, query: str, params=None):
    if isinstance(params, (list, tuple)):
        values = iter(params)
        bindings = {}

        def bind_placeholder(_match):
            name = f"p{_match.start()}"
            bindings[name] = next(values)
            return f":{name}"

        query = re.sub(r"\?", bind_placeholder, query)
    else:
        bindings = params or {}
    return conn.execute(text(query), bindings)


def _all(conn: Connection, query: str, params=None) -> list[dict]:
    return [dict(row) for row in _execute(conn, query, params).mappings().all()]

app = FastAPI(
    title="ShelfWatch API",
    description="Grocery availability and price intelligence for Bangladesh.",
    version="1.1.0",
)
app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


@contextmanager
def _connection() -> Generator[Connection, None, None]:
    engine = _database_engine()
    try:
        with engine.connect() as conn:
            _require_snapshots(conn)
            yield conn
    finally:
        engine.dispose()


def _require_snapshots(conn: Connection) -> None:
    if conn.dialect.name == "postgresql":
        query = """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = current_schema() AND table_name = 'snapshots'
        """
    else:
        query = """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'snapshots'
        """
    exists = _execute(conn, query).first()
    if not exists:
        raise HTTPException(
            status_code=503,
            detail="The product database is not initialized. Run a collection and ingest its snapshot.",
        )


def _columns(conn: Connection) -> set[str]:
    if conn.dialect.name == "postgresql":
        rows = _execute(conn, """
            SELECT column_name AS name
            FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = 'snapshots'
        """).mappings().all()
    else:
        rows = _execute(conn, "PRAGMA table_info(snapshots)").mappings().all()
    return {row["name"] for row in rows}


LATEST_PRODUCTS = """
WITH ranked_products AS (
    SELECT id, source, title, price, list_price, discount_percent, stock_flag,
           category_path, category_rank, url, scraped_at,
           ROW_NUMBER() OVER (
               PARTITION BY source, lower(title)
               ORDER BY scraped_at DESC, id DESC
           ) AS product_rank
    FROM snapshots
)
"""


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


@app.get("/api/health")
def health() -> dict:
    with _connection() as conn:
        observations = _execute(conn, "SELECT COUNT(*) FROM snapshots").scalar_one()
        return {"status": "ok", "observations": observations}


@app.get("/api/overview")
def get_overview() -> dict:
    with _connection() as conn:
        current = _execute(
            conn,
            LATEST_PRODUCTS
            + """
            SELECT COUNT(*) AS products,
                   SUM(CASE WHEN stock_flag = 'out_of_stock' THEN 1 ELSE 0 END) AS out_of_stock,
                   SUM(CASE WHEN price IS NULL THEN 1 ELSE 0 END) AS unpriced,
                   COUNT(DISTINCT source) AS retailers
            FROM ranked_products
            WHERE product_rank = 1
            """
        ).mappings().first()
        observations = _execute(
            conn, "SELECT COUNT(*) FROM snapshots"
        ).scalar_one()
        latest = _execute(
            conn, "SELECT MAX(scraped_at) FROM snapshots"
        ).scalar_one()
        retailers = _all(
            conn,
            LATEST_PRODUCTS
            + """
            SELECT source, COUNT(*) AS products,
                   SUM(CASE WHEN stock_flag = 'out_of_stock' THEN 1 ELSE 0 END) AS out_of_stock
            FROM ranked_products
            WHERE product_rank = 1
            GROUP BY source
            ORDER BY source
            """
        )
        activity = _all(
            conn,
            """
            SELECT substr(CAST(scraped_at AS TEXT), 1, 10) AS day,
                   COUNT(*) AS observations
            FROM snapshots
            GROUP BY day
            ORDER BY day DESC
            LIMIT 14
            """
        )

    return {
        "products": current["products"] or 0,
        "observations": observations,
        "out_of_stock": current["out_of_stock"] or 0,
        "unpriced": current["unpriced"] or 0,
        "retailers": current["retailers"] or 0,
        "last_updated": latest,
        "retailer_breakdown": retailers,
        "daily_activity": list(reversed(activity)),
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
        "price_low": "price IS NULL, price ASC, lower(title)",
        "price_high": "price IS NULL, price DESC, lower(title)",
        "name": "lower(title) ASC",
    }[sort]
    where = " AND ".join(conditions)

    with _connection() as conn:
        total = _execute(
            conn,
            LATEST_PRODUCTS + f"SELECT COUNT(*) FROM ranked_products WHERE {where}",
            params,
        ).scalar_one()
        rows = _all(
            conn,
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
        )

    return {
        "items": rows,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.get("/api/products/{snapshot_id}/history")
def get_product_history(snapshot_id: int) -> dict:
    with _connection() as conn:
        product = _execute(
            conn,
            "SELECT source, title, url FROM snapshots WHERE id = ?",
            (snapshot_id,),
        ).mappings().first()
        if product is None:
            raise HTTPException(status_code=404, detail="Product snapshot not found.")

        titles = [
            row["title"]
            for row in _all(
                conn,
                "SELECT DISTINCT title FROM snapshots WHERE source = ?",
                (product["source"],),
            )
            if _pack_family_key(row["title"]) == _pack_family_key(product["title"])
        ]
        placeholders = ", ".join("?" for _ in titles)
        history = _all(
            conn,
            f"""
            SELECT id, title, price, list_price, discount_percent, stock_flag,
                   scraped_at
            FROM snapshots
            WHERE source = ? AND title IN ({placeholders})
            ORDER BY scraped_at, id
            """,
            [product["source"], *titles],
        )

        history = [
            {key: value for key, value in row.items() if key != "title"}
            for row in history
        ]

    return {
        "source": product["source"],
        "title": product["title"],
        "history": history,
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
        rows = _all(
            conn,
            LATEST_PRODUCTS
            + """
            SELECT id, source, title, url, price, stock_flag, scraped_at
            FROM ranked_products
            WHERE product_rank = 1 AND stock_flag = 'out_of_stock'
            """
            + source_clause
            + " ORDER BY scraped_at DESC, lower(title)",
            params,
        )
    return rows


_PACK_SIZE_SUFFIX = re.compile(
    r"(?<!\w)\d+(?:[.,]\d+)?\s*"
    r"(?:kgs?|kilos?|kilograms?|gms?|grams?|g|ml|millilit(?:er|re)s?|"
    r"ltrs?|lit(?:er|re)s?|l|pcs?|pieces?|counts?|ct|packs?|sachets?)\b",
    re.IGNORECASE,
)


def _pack_family_key(title: str) -> str:
    return " ".join(_PACK_SIZE_SUFFIX.sub(" ", title).casefold().split())


def _pack_alerts(rows: list[dict], use_stored_features: bool) -> list[dict]:
    previous: dict[tuple[str, str], tuple[float, str]] = {}
    observations: dict[tuple[str, str, str], dict] = {}

    for row in rows:
        if use_stored_features:
            amount = row["normalized_amount"]
            unit = row["normalized_unit"]
            if amount is None or unit not in ("g", "kg", "ml", "l"):
                continue
            dimension = "volume" if unit in ("ml", "l") else "weight"
        else:
            _, unit, amount = parse_pack_size(row["title"])
            if amount is None or unit == "piece":
                continue
            dimension = "volume" if unit in ("ml", "l") else "weight"

        family = _pack_family_key(row["title"])
        timestamp = str(row["scraped_at"])
        key = (row["source"], family)
        observation_key = (row["source"], family, timestamp)
        observations[observation_key] = {
            **row,
            "normalized_amount": amount,
            "normalized_unit": unit,
            "_family": family,
            "_dimension": dimension,
        }

    alerts = []
    for observation in sorted(
        observations.values(),
        key=lambda row: (row["source"], row["scraped_at"], row["id"]),
    ):
        key = (observation["source"], observation["_family"])
        current_amount = observation["normalized_amount"]
        current_dimension = observation["_dimension"]
        prior = previous.get(key)
        if (
            prior
            and prior[1] == current_dimension
            and current_amount < prior[0]
        ):
            alerts.append({
                "id": observation["id"],
                "source": observation["source"],
                "title": observation["title"],
                "url": observation["url"],
                "price": observation["price"],
                "normalized_amount": current_amount,
                "normalized_unit": observation["normalized_unit"],
                "scraped_at": observation["scraped_at"],
                "previous_amount": prior[0],
            })
        previous[key] = (current_amount, current_dimension)

    return sorted(alerts, key=lambda alert: str(alert["scraped_at"]), reverse=True)


def _shrinkflation_from_features(conn: Connection) -> list[dict]:
    rows = _all(
        conn,
        """
        SELECT id, source, title, url, price, normalized_amount, normalized_unit,
               scraped_at
        FROM snapshots
        WHERE normalized_amount IS NOT NULL
        ORDER BY source, scraped_at, id
        """
    )
    return _pack_alerts(rows, use_stored_features=True)


def _shrinkflation_from_titles(conn: Connection) -> list[dict]:
    rows = _all(
        conn,
        """
        SELECT id, source, title, url, price, scraped_at
        FROM snapshots
        ORDER BY source, lower(title), scraped_at, id
        """
    )
    return _pack_alerts(rows, use_stored_features=False)


@app.get("/api/shrinkflation/alerts")
def get_shrinkflation_alerts() -> list[dict]:
    with _connection() as conn:
        if {"normalized_amount", "normalized_unit"}.issubset(_columns(conn)):
            return _shrinkflation_from_features(conn)
        return _shrinkflation_from_titles(conn)
