import sqlite3
from pathlib import Path

DATA_DIR = Path("/opt/render/project/src/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "bot_data.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            language TEXT,
            subscribed INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


def ensure_user(chat_id: int):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR IGNORE INTO users (chat_id, language, subscribed)
        VALUES (?, NULL, 0)
        """,
        (chat_id,)
    )

    conn.commit()
    conn.close()


def set_user_language(chat_id: int, language: str):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR IGNORE INTO users (chat_id, language, subscribed)
        VALUES (?, ?, 0)
        """,
        (chat_id, language)
    )

    cur.execute(
        """
        UPDATE users
        SET language = ?
        WHERE chat_id = ?
        """,
        (language, chat_id)
    )

    conn.commit()
    conn.close()


def get_user_language(chat_id: int):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT language FROM users WHERE chat_id = ?",
        (chat_id,)
    )
    row = cur.fetchone()

    conn.close()

    if row and row["language"]:
        return row["language"]
    return None


def subscribe_user(chat_id: int):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR IGNORE INTO users (chat_id, language, subscribed)
        VALUES (?, NULL, 1)
        """,
        (chat_id,)
    )

    cur.execute(
        """
        UPDATE users
        SET subscribed = 1
        WHERE chat_id = ?
        """,
        (chat_id,)
    )

    conn.commit()
    conn.close()


def unsubscribe_user(chat_id: int):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE users
        SET subscribed = 0
        WHERE chat_id = ?
        """,
        (chat_id,)
    )

    conn.commit()
    conn.close()


def is_user_subscribed(chat_id: int) -> bool:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT subscribed FROM users WHERE chat_id = ?",
        (chat_id,)
    )
    row = cur.fetchone()

    conn.close()

    if row is None:
        return False

    return bool(row["subscribed"])


def get_all_subscribed_users():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT chat_id FROM users WHERE subscribed = 1"
    )
    rows = cur.fetchall()

    conn.close()

    return [row["chat_id"] for row in rows]