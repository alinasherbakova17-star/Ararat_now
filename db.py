import sqlite3
from pathlib import Path

DATA_DIR = Path("/opt/render/project/src/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "bot_data.db"


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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_chat_id INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_best_of_day INTEGER DEFAULT 0
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

    cur.execute("SELECT chat_id FROM users WHERE subscribed = 1")
    rows = cur.fetchall()

    conn.close()

    return [row["chat_id"] for row in rows]


def add_photo(user_chat_id: int, file_id: str) -> int:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO photos (user_chat_id, file_id)
        VALUES (?, ?)
        """,
        (user_chat_id, file_id)
    )

    photo_id = cur.lastrowid

    conn.commit()
    conn.close()

    return photo_id


def get_photo_by_id(photo_id: int):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, user_chat_id, file_id, created_at, is_best_of_day
        FROM photos
        WHERE id = ?
        """,
        (photo_id,)
    )
    row = cur.fetchone()

    conn.close()
    return row


def clear_best_photo_of_day():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE photos
        SET is_best_of_day = 0
        WHERE is_best_of_day = 1
        """
    )

    conn.commit()
    conn.close()


def set_best_photo_of_day(photo_id: int):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("UPDATE photos SET is_best_of_day = 0 WHERE is_best_of_day = 1")
    cur.execute(
        """
        UPDATE photos
        SET is_best_of_day = 1
        WHERE id = ?
        """,
        (photo_id,)
    )

    conn.commit()
    conn.close()


def get_best_photo_of_day():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, user_chat_id, file_id, created_at, is_best_of_day
        FROM photos
        WHERE is_best_of_day = 1
        ORDER BY id DESC
        LIMIT 1
        """
    )
    row = cur.fetchone()

    conn.close()
    return row
    def get_total_users():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) as count FROM users")
    result = cur.fetchone()["count"]

    conn.close()
    return result


def get_total_subscribed():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) as count FROM users WHERE subscribed = 1")
    result = cur.fetchone()["count"]

    conn.close()
    return result


def get_photos_count():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) as count FROM photos")
    result = cur.fetchone()["count"]

    conn.close()
    return result


def get_today_users():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*) as count
        FROM users
        WHERE DATE(rowid, 'unixepoch') = DATE('now')
    """)

    result = cur.fetchone()["count"]
    conn.close()
    return result