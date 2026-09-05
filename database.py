"""SQLite-хранилище: путешествия и расходы. У каждого пользователя своя история."""
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "travel_wallet.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                home_country TEXT NOT NULL,
                home_currency TEXT NOT NULL,
                dest_country TEXT NOT NULL,
                dest_currency TEXT NOT NULL,
                rate REAL NOT NULL,
                balance_home REAL NOT NULL,
                balance_dest REAL NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL REFERENCES trips(id),
                amount_dest REAL NOT NULL,
                amount_home REAL NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def create_trip(
    user_id: int,
    home_country: str,
    home_currency: str,
    dest_country: str,
    dest_currency: str,
    rate: float,
    balance_home: float,
    balance_dest: float,
) -> int:
    with get_connection() as conn:
        conn.execute("UPDATE trips SET is_active = 0 WHERE user_id = ?", (user_id,))
        cursor = conn.execute(
            """
            INSERT INTO trips (
                user_id, home_country, home_currency, dest_country, dest_currency,
                rate, balance_home, balance_dest, is_active, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                user_id, home_country, home_currency, dest_country, dest_currency,
                rate, balance_home, balance_dest, datetime.now().isoformat(timespec="seconds"),
            ),
        )
        return cursor.lastrowid


def get_active_trip(user_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM trips WHERE user_id = ? AND is_active = 1", (user_id,)
        ).fetchone()


def get_trips(user_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM trips WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
        ).fetchall()


def get_trip(trip_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM trips WHERE id = ?", (trip_id,)).fetchone()


def set_active_trip(user_id: int, trip_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE trips SET is_active = 0 WHERE user_id = ?", (user_id,))
        conn.execute(
            "UPDATE trips SET is_active = 1 WHERE id = ? AND user_id = ?", (trip_id, user_id)
        )


def update_rate(trip_id: int, new_rate: float) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE trips SET rate = ? WHERE id = ?", (new_rate, trip_id))


def add_expense(trip_id: int, amount_dest: float, amount_home: float) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO expenses (trip_id, amount_dest, amount_home, created_at) VALUES (?, ?, ?, ?)",
            (trip_id, amount_dest, amount_home, datetime.now().isoformat(timespec="seconds")),
        )
        conn.execute(
            "UPDATE trips SET balance_dest = balance_dest - ?, balance_home = balance_home - ? WHERE id = ?",
            (amount_dest, amount_home, trip_id),
        )


def get_history(trip_id: int, limit: int = 10) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM expenses WHERE trip_id = ? ORDER BY created_at DESC LIMIT ?",
            (trip_id, limit),
        ).fetchall()
