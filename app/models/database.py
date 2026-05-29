import sqlite3
import sys

if sqlite3.sqlite_version_info < (3, 35, 0):
    try:
        import pysqlite3

        sys.modules["sqlite3"] = pysqlite3
        sqlite3 = pysqlite3
    except ImportError:
        pass

import chromadb
from chromadb.config import Settings as ChromaSettings
from app.config import DATABASE_PATH, CHROMA_PATH

# ── SQLite ──

def get_db() -> sqlite3.Connection:
    import os
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _ensure_dirs():
    import os
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    os.makedirs(CHROMA_PATH, exist_ok=True)


def _migrate_sources(conn):
    """Safe migration: add new columns if they don't exist. Preserves existing data."""
    existing = [row[1] for row in conn.execute("PRAGMA table_info(sources)").fetchall()]
    migrations = [
        ("category", "TEXT DEFAULT 'overseas_ai'"),
        ("language", "TEXT DEFAULT 'en'"),
        ("priority", "INTEGER DEFAULT 3"),
        ("status", "TEXT DEFAULT 'active'"),
        ("description", "TEXT DEFAULT ''"),
    ]
    for col, col_type in migrations:
        if col not in existing:
            conn.execute(f"ALTER TABLE sources ADD COLUMN {col} {col_type}")
            conn.commit()


def init_db():
    _ensure_dirs()
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sources (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            url         TEXT NOT NULL UNIQUE,
            type        TEXT NOT NULL CHECK(type IN ('rss','url')),
            enabled     INTEGER DEFAULT 1,
            category    TEXT DEFAULT 'overseas_ai',
            language    TEXT DEFAULT 'en',
            priority    INTEGER DEFAULT 3,
            status      TEXT DEFAULT 'active',
            description TEXT DEFAULT '',
            created_at  TEXT DEFAULT (datetime('now','localtime')),
            updated_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS articles (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id    INTEGER REFERENCES sources(id) ON DELETE SET NULL,
            title        TEXT NOT NULL,
            url          TEXT NOT NULL UNIQUE,
            content      TEXT,
            summary      TEXT,
            published_at TEXT,
            collected_at TEXT DEFAULT (datetime('now','localtime')),
            relevance    REAL DEFAULT 0.5
        );

        CREATE TABLE IF NOT EXISTS article_insights (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
            category   TEXT NOT NULL CHECK(category IN ('trend','decision','risk','event')),
            content    TEXT NOT NULL,
            confidence REAL DEFAULT 0.5,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS daily_reports (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            report_date   TEXT NOT NULL UNIQUE,
            title         TEXT NOT NULL,
            summary       TEXT,
            file_path     TEXT NOT NULL,
            article_count INTEGER DEFAULT 0,
            created_at    TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS report_sections (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id    INTEGER REFERENCES daily_reports(id) ON DELETE CASCADE,
            section_type TEXT NOT NULL CHECK(section_type IN ('headlines','trends','decisions','risks','events')),
            title        TEXT NOT NULL,
            content      TEXT NOT NULL,
            sort_order   INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS qa_history (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            question   TEXT NOT NULL,
            answer     TEXT NOT NULL,
            sources    TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS collect_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id    INTEGER,
            status       TEXT CHECK(status IN ('success','error')),
            message      TEXT,
            articles_new INTEGER DEFAULT 0,
            created_at   TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS feishu_push_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            report_date   TEXT,
            status        TEXT NOT NULL CHECK(status IN ('success','error')),
            message       TEXT,
            response_code INTEGER,
            created_at    TEXT DEFAULT (datetime('now','localtime'))
        );
    """)
    # Safe migration for existing databases (preserves data)
    _migrate_sources(conn)
    conn.commit()
    conn.close()


# ── ChromaDB ──

_chroma_client = None

def get_chroma() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(
            path=CHROMA_PATH,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _chroma_client


def init_chroma():
    client = get_chroma()
    existing = client.list_collections()
    if "article_chunks" not in existing:
        client.create_collection("article_chunks")
    if "report_chunks" not in existing:
        client.create_collection("report_chunks")
