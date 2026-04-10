"""SQLite database initialization and access."""

import aiosqlite

from dks_mod.config import settings

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await aiosqlite.connect(settings.db_path)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
    return _db


async def close_db():
    global _db
    if _db is not None:
        await _db.close()
        _db = None


async def init_db():
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS api_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            server_ids TEXT NOT NULL,  -- JSON array
            description TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_used TEXT,
            revoked INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS webhooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            event_types TEXT NOT NULL,  -- JSON array
            secret TEXT,  -- shared secret for HMAC
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            active INTEGER DEFAULT 1,
            FOREIGN KEY (token_id) REFERENCES api_tokens(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS webhook_deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            webhook_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            status_code INTEGER,
            attempts INTEGER DEFAULT 0,
            last_attempt TEXT,
            success INTEGER DEFAULT 0,
            FOREIGN KEY (webhook_id) REFERENCES webhooks(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS servers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            ip TEXT NOT NULL,
            public_ip TEXT,
            customer_id TEXT NOT NULL,
            grpc_port INTEGER DEFAULT 50051,
            olympus_port INTEGER DEFAULT 3000,
            tacview_path TEXT,
            active INTEGER DEFAULT 1
        );

        -- Add public_ip column if upgrading from older schema
        -- SQLite ignores duplicate column errors only via separate execute, not executescript

    """)
    await db.commit()

    # Migrate existing servers table -- add columns if not present
    for migration in [
        "ALTER TABLE servers ADD COLUMN public_ip TEXT",
        "ALTER TABLE servers ADD COLUMN olympus_enabled INTEGER DEFAULT 0",
    ]:
        try:
            await db.execute(migration)
            await db.commit()
        except Exception:
            pass  # Column already exists
