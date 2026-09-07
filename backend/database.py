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
                    file_id TEXT REFERENCES files(id) ON DELETE CASCADE,
                    account_id TEXT REFERENCES accounts(id) ON DELETE CASCADE,
                    chunk_no INT,
                    size INT,
                    download_url TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_chunks_file_id ON file_chunks(file_id);
                CREATE INDEX IF NOT EXISTS idx_chunks_account_id ON file_chunks(account_id);
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

    # === Settings ===

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

    # === Accounts ===

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

    def add_account(self, email: str, password: str, free_space: int = 10000000000) -> str:
        id = uuid.uuid4().hex
        timestamp = datetime.now(timezone.utc).isoformat()
        
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO accounts (id, email, password, free_space, created_at, last_accessed) VALUES (?, ?, ?, ?, ?, ?)",
                (id, email, password, free_space, timestamp, timestamp)
            )
            conn.commit()

        return id

    def update_account_space(self, id: str, free_space: int):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE accounts SET free_space = ? WHERE id = ?", (free_space, id))
            conn.commit()

    def delete_account(self, id: str):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM accounts WHERE id = ?", (id,))
            conn.commit()

    # === Files ===

    def get_file(self, id: str) -> sqlite3.Row:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM files WHERE id = ?", (id,))
            row = cursor.fetchone()

            return row

    def get_files(self, file_name: str = None) -> list[sqlite3.Row]:
        with self._connect() as conn:
            cursor = conn.cursor()
            if file_name is not None:
                cursor.execute("SELECT * FROM files WHERE file_name = ?", (file_name,))
            else:
                cursor.execute("SELECT * FROM files")
            rows = cursor.fetchall()
        
            return rows

    def add_file(self, file_name: str, size: int, chunk_size: int, num_chunks: int) -> str:
        id = uuid.uuid4().hex
        timestamp = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO files (id, file_name, size, chunk_size, num_chunks, upload_datetime) VALUES (?, ?, ?, ?, ?, ?)",
                (id, file_name, size, chunk_size, num_chunks, timestamp)
            )
            conn.commit()

        return id

    def delete_file(self, id: str):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM files WHERE id = ?", (id,))
            conn.commit()

    # === File Chunks ===

    def get_chunk(self, id: str) -> sqlite3.Row:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM file_chunks WHERE id = ?", (id,))
            row = cursor.fetchone()

            return row

    def get_chunks(self, file_id: str = None, account_id: str = None) -> list[sqlite3.Row]:
        query = "SELECT * FROM file_chunks WHERE 1=1"
        params = []

        if file_id is not None:
            query += " AND file_id = ?"
            params.append(file_id)
        if account_id is not None:
            query += " AND account_id = ?"
            params.append(account_id)

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
        
            return rows

    def add_chunk(self, file_id: str, account_id: str, chunk_no: int, size: int, download_url: str) -> str:
        id = uuid.uuid4().hex

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO file_chunks (id, file_id, account_id, chunk_no, size, download_url) VALUES (?, ?, ?, ?, ?, ?)",
                (id, file_id, account_id, chunk_no, size, download_url)
            )
            conn.commit()

        return id

    def delete_chunk(self, id: str):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM file_chunks WHERE id = ?", (id,))
            conn.commit()

    def delete_chunks(self, file_id: str, account_id: str):
        query = "DELETE FROM file_chunks WHERE 1=1"
        params = []

        if file_id is None and account_id is None:
            return
        if file_id is not None:
            query += " AND file_id = ?"
            params.append(file_id)
        if account_id is not None:
            query += " AND account_id = ?"
            params.append(account_id)

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            conn.commit()
    