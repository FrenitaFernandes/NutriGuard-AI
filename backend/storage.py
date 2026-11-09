import json
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DATABASE_PATH = BASE_DIR / "data" / "nutriguard.db"


def _now():
    return datetime.now(timezone.utc).isoformat()


def get_connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def initialize_database():
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                current_product_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                source_hash TEXT NOT NULL,
                filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL,
                preview_filename TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(session_id, source_hash)
            );
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                sources TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS analysis_jobs (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                status TEXT NOT NULL,
                result TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_products_session ON products(session_id);
            CREATE INDEX IF NOT EXISTS idx_chat_session_product
                ON chat_messages(session_id, product_id, id);
            """
        )


def create_session():
    session_id = secrets.token_urlsafe(32)
    timestamp = _now()
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO sessions(id, created_at, updated_at) VALUES (?, ?, ?)",
            (session_id, timestamp, timestamp),
        )
    return session_id


def ensure_session(session_id):
    if not session_id:
        return create_session()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if row:
            connection.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (_now(), session_id),
            )
            return session_id
    return create_session()


def save_product(session_id, source_hash, filename, stored_filename,
                 preview_filename, payload):
    timestamp = _now()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO products(
                session_id, source_hash, filename, stored_filename,
                preview_filename, payload, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id, source_hash) DO UPDATE SET
                filename=excluded.filename,
                stored_filename=excluded.stored_filename,
                preview_filename=excluded.preview_filename,
                payload=excluded.payload
            """,
            (
                session_id, source_hash, filename, stored_filename,
                preview_filename, json.dumps(payload), timestamp,
            ),
        )
        row = connection.execute(
            """
            SELECT * FROM products
            WHERE session_id = ? AND source_hash = ?
            """,
            (session_id, source_hash),
        ).fetchone()
        connection.execute(
            """
            UPDATE sessions SET current_product_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (row["id"], timestamp, session_id),
        )
        return dict(row) | {"payload": payload}


def get_current_product(session_id):
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT p.* FROM products p
            JOIN sessions s ON s.current_product_id = p.id
            WHERE s.id = ? AND p.session_id = ?
            """,
            (session_id, session_id),
        ).fetchone()
    if not row:
        return None
    return dict(row) | {"payload": json.loads(row["payload"])}


def add_message(session_id, product_id, role, content, sources=None):
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO chat_messages(
                session_id, product_id, role, content, sources, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id, product_id, role, content,
                json.dumps(sources or []), _now(),
            ),
        )


def get_messages(session_id, product_id):
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT role, content, sources, created_at
            FROM chat_messages
            WHERE session_id = ? AND product_id = ?
            ORDER BY id
            """,
            (session_id, product_id),
        ).fetchall()
    return [
        {
            "role": row["role"],
            "content": row["content"],
            "sources": json.loads(row["sources"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def clear_current_product(session_id):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT current_product_id FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if not row or row["current_product_id"] is None:
            return
        connection.execute(
            "DELETE FROM products WHERE id = ? AND session_id = ?",
            (row["current_product_id"], session_id),
        )
        connection.execute(
            """
            UPDATE sessions SET current_product_id = NULL, updated_at = ?
            WHERE id = ?
            """,
            (_now(), session_id),
        )


def create_analysis_job(session_id, job_id):
    timestamp = _now()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO analysis_jobs(id, session_id, status, created_at, updated_at)
            VALUES (?, ?, 'queued', ?, ?)
            """,
            (job_id, session_id, timestamp, timestamp),
        )


def update_analysis_job(job_id, session_id, status, result=None, error=None):
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE analysis_jobs
            SET status = ?, result = ?, error = ?, updated_at = ?
            WHERE id = ? AND session_id = ?
            """,
            (
                status,
                json.dumps(result) if result is not None else None,
                error,
                _now(),
                job_id,
                session_id,
            ),
        )


def get_analysis_job(job_id, session_id):
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, status, result, error, created_at, updated_at
            FROM analysis_jobs
            WHERE id = ? AND session_id = ?
            """,
            (job_id, session_id),
        ).fetchone()
    if not row:
        return None
    result = dict(row)
    result["result"] = json.loads(result["result"]) if result["result"] else None
    return result
