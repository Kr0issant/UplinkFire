import sqlite3


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    """Convert a sqlite3.Row to a plain dict. Returns None if row is None."""
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows: list[sqlite3.Row] | None) -> list[dict]:
    """Convert a list of sqlite3.Row objects to a list of plain dicts."""
    return [dict(r) for r in rows] if rows else []
