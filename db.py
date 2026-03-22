import sqlite3
from pathlib import Path

DB_PATH = Path("bot_data.db")


def get_connection():
    return sqlite3.connect(DB_PATH)


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
        "INSERT OR IGNORE INTO users (chat_id, language, subscribed) VALUES (?, ?, ?)",
        (chat_id, None, 0)
    )

    conn.commit()
    conn.close()


def set_user_language(chat_id: int, language: str):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "INSERT OR IGNORE INTO users (chat_id, language, subscribed) VALUES (?, ?, ?)",
        (chat_id, language, 0)
    )

    cur.execute(
        "UPDATE users SET language = ? WHERE chat_id = ?",
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

    if row:
        return row[0]
    return None


def subscribe_user(chat_id: int):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "INSERT OR IGNORE INTO users (chat_id, language, subscribed) VALUES (?, ?, ?)",
        (chat_id, None, 1)
    )

    cur.execute(
        "UPDATE users SET subscribed = 1 WHERE chat_id = ?",
        (chat_id,)
    )

    conn.commit()
    conn.close()


def unsubscribe_user(chat_id: int):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "UPDATE users SET subscribed = 0 WHERE chat_id = ?",
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

    if row:
        return bool(row[0])
    return False


def get_all_subscribed_users():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT chat_id FROM users WHERE subscribed = 1"
    )
    rows = cur.fetchall()

    conn.close()

    return [row[0] for row in rows]