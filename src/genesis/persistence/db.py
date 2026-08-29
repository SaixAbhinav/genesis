import json
import sqlite3
from pathlib import Path

from genesis.world.state import WorldState

SCHEMA = """
CREATE TABLE IF NOT EXISTS world (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    state_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    minute INTEGER NOT NULL,
    type TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.executescript(SCHEMA)
    return conn


def save_state(conn: sqlite3.Connection, state: WorldState) -> None:
    conn.execute(
        "INSERT INTO world (id, state_json) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET state_json = excluded.state_json",
        (state.to_json(),))
    conn.commit()


def load_state(conn: sqlite3.Connection) -> WorldState | None:
    row = conn.execute("SELECT state_json FROM world WHERE id = 1").fetchone()
    return WorldState.from_json(row[0]) if row else None


def append_events(conn: sqlite3.Connection, events: list[dict]) -> None:
    conn.executemany(
        "INSERT INTO events (minute, type, payload_json) VALUES (?, ?, ?)",
        [(ev["minute"], ev["type"], json.dumps(ev)) for ev in events])
    conn.commit()


def load_events(conn: sqlite3.Connection, since_minute: int = 0) -> list[dict]:
    rows = conn.execute(
        "SELECT payload_json FROM events WHERE minute >= ? ORDER BY id",
        (since_minute,)).fetchall()
    return [json.loads(r[0]) for r in rows]
