import sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "database.db"

default_settings = [
    ("wait_duration", "20"),
    ("upload_duration", "7200"),
    ("captcha_duration", "120"),
    ("auto_logout", "False")
]

class Database:
    def __init__(self):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.executescript('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
                CREATE TABLE IF NOT EXISTS accounts (
                    id TEXT PRIMARY KEY,
                    email TEXT,
                    password TEXT,
                    free_space INT,
                    created_at TEXT,
                    last_accessed TEXT
                );
                CREATE TABLE IF NOT EXISTS files (
                    id TEXT PRIMARY KEY,
                    file_name TEXT,
                    size INT,
                    chunk_size INT,
                    num_chunks INT,
                    upload_datetime TEXT
                );
                CREATE TABLE IF NOT EXISTS file_chunks (
                    id TEXT PRIMARY KEY,
                    file_id TEXT REFERENCES files(id),
                    account_id TEXT REFERENCES accounts(id),
                    chunk_no INT,
                    size INT,
                    download_url TEXT
                );
            ''')
            cursor.executemany(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                default_settings
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def get_setting(self, setting: str, cast_to: type = str, default = None) -> any:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (setting,))
            row = cursor.fetchone()

            return default if row is None else cast_to(row[0])
        
    def set_setting(self, setting: str, value: any):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", 
                (setting, str(value))
            )
            conn.commit()

    def get_account(self, id: str) -> sqlite3.Row:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM accounts WHERE id = ?", (id,))
            row = cursor.fetchone()

            return row

    def get_accounts(self, min_free_space: int = None) -> list[sqlite3.Row]:
        with self._connect() as conn:
            cursor = conn.cursor()
            if min_free_space is not None:
                cursor.execute("SELECT * FROM accounts WHERE free_space >= ?", (min_free_space,))
            else:
                cursor.execute("SELECT * FROM accounts")
            rows = cursor.fetchall()
        
            return rows

    def add_account(self, email: str, password: str, free_space: int = 10000000000):
        id = uuid.uuid4().hex
        timestamp = datetime.now(timezone.utc).isoformat()
        
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO accounts (id, email, password, free_space, created_at, last_accessed) VALUES (?, ?, ?, ?, ?, ?)",
                (id, email, password, free_space, timestamp, timestamp)
            )
            conn.commit()

    