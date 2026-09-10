import sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "database.db"
TEMP_DIR_PATH = Path(__file__).resolve().parent.parent / "temp"
DEFAULT_CHUNK_SIZE = 512  # MiB

default_settings = [
    ("timeout_duration", "20"),
    ("upload_duration", "7200"),
    ("captcha_duration", "120"),
    ("auto_logout", "False"),
    ("first_name", "John"),
    ("last_name", "Doe"),
    ("temp_dir_path", str(TEMP_DIR_PATH)),
    ("chunk_size", str(DEFAULT_CHUNK_SIZE)),
    ("upload_strategy", "least_scatter"), # "least_scatter" / "least_leftovers"
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
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def run_read_query(self, query: str, params: list | tuple = None, n: int = 1) -> sqlite3.Row | list[sqlite3.Row]:
        if params is None: params = []
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))

            if n == 0:
                return cursor.fetchall()
            elif n == 1:
                return cursor.fetchone()
            else:
                return cursor.fetchmany(n)

    def run_write_query(self, query: str, params: list | tuple = None):
        if params is None: params = []
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            conn.commit()

    # === Settings ===

    def get_setting(self, setting: str, cast_to: type = str, default = None) -> any:
        row = self.run_read_query("SELECT value FROM settings WHERE key = ?", (setting,), 1)
        return default if row is None else cast_to(row[0])
        
    def set_setting(self, setting: str, value: any):
        self.run_write_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (setting, str(value)))

    def get_all_settings(self) -> dict:
        rows = self.run_read_query("SELECT key, value FROM settings", n=0)
        return {r["key"]: r["value"] for r in rows} if rows else {}

    # === Accounts ===

    def get_account(self, id: str) -> sqlite3.Row:
        return self.run_read_query("SELECT * FROM accounts WHERE id = ?", (id,), 1)

    def get_accounts(self, min_free_space: int = None) -> list[sqlite3.Row]:
        if min_free_space is not None:
            return self.run_read_query("SELECT * FROM accounts WHERE free_space >= ?", (min_free_space,), 0)
        else:
            return self.run_read_query("SELECT * FROM accounts", n = 0)

    def add_account(self, email: str, password: str, free_space: int = 10000000000) -> str:
        id = uuid.uuid4().hex
        timestamp = datetime.now(timezone.utc).isoformat()
        
        self.run_write_query(
            "INSERT INTO accounts (id, email, password, free_space, created_at, last_accessed) VALUES (?, ?, ?, ?, ?, ?)",
            (id, email, password, free_space, timestamp, timestamp)
        )

        return id

    def update_account_free_space(self, id: str, free_space: int):
        self.run_write_query("UPDATE accounts SET free_space = ? WHERE id = ?", (free_space, id))

    def update_account_last_accessed(self, id: str):
        timestamp = datetime.now(timezone.utc).isoformat()
        self.run_write_query("UPDATE accounts SET last_accessed = ? WHERE id = ?", (timestamp, id))

    def update_account(self, id: str, email: str = None, password: str = None, free_space: int = None):
        fields, params = [], []
        if email is not None:      fields.append("email = ?");      params.append(email)
        if password is not None:   fields.append("password = ?");   params.append(password)
        if free_space is not None: fields.append("free_space = ?"); params.append(free_space)
        if not fields:
            return
        params.append(id)
        self.run_write_query(f"UPDATE accounts SET {', '.join(fields)} WHERE id = ?", params)

    def delete_account(self, id: str):
        self.run_write_query("DELETE FROM accounts WHERE id = ?", (id,))

    # === Files ===

    def get_file(self, id: str) -> sqlite3.Row:
        return self.run_read_query("SELECT * FROM files WHERE id = ?", (id,), 1)

    def get_files(self, file_name: str = None) -> list[sqlite3.Row]:
        if file_name is not None:
            return self.run_read_query("SELECT * FROM files WHERE file_name = ?", (file_name,), 0)
        else:
            return self.run_read_query("SELECT * FROM files", n = 0)

    def add_file(self, file_name: str, size: int, chunk_size: int, num_chunks: int) -> str:
        id = uuid.uuid4().hex
        timestamp = datetime.now(timezone.utc).isoformat()

        self.run_write_query(
            "INSERT INTO files (id, file_name, size, chunk_size, num_chunks, upload_datetime) VALUES (?, ?, ?, ?, ?, ?)",
            (id, file_name, size, chunk_size, num_chunks, timestamp)
        )

        return id

    def delete_file(self, id: str):
        self.run_write_query("DELETE FROM files WHERE id = ?", (id,))

    # === File Chunks ===

    def get_chunk(self, id: str) -> sqlite3.Row:
        return self.run_read_query("SELECT * FROM file_chunks WHERE id = ?", (id,), 1)

    def get_chunks(self, file_id: str = None, account_id: str = None) -> list[sqlite3.Row]:
        query = "SELECT * FROM file_chunks WHERE 1=1"
        params = []

        if file_id is not None:
            query += " AND file_id = ?"
            params.append(file_id)
        if account_id is not None:
            query += " AND account_id = ?"
            params.append(account_id)

        return self.run_read_query(query, params, 0)

    def add_chunk(self, file_id: str, account_id: str, chunk_no: int, size: int, download_url: str) -> str:
        id = uuid.uuid4().hex

        self.run_write_query(
            "INSERT INTO file_chunks (id, file_id, account_id, chunk_no, size, download_url) VALUES (?, ?, ?, ?, ?, ?)",
            (id, file_id, account_id, chunk_no, size, download_url)
        )

        return id

    def delete_chunk(self, id: str):
        self.run_write_query("DELETE FROM file_chunks WHERE id = ?", (id,))

    def delete_chunks(self, file_id: str = None, account_id: str = None):
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

        self.run_write_query(query, params)
    