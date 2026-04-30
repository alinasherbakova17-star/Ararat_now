import sqlite3
import datetime
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
            subscribed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_chat_id INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS best_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
        SELECT id, user_chat_id, file_id, created_at
        FROM photos
        WHERE id = ?
        """,
        (photo_id,)
    )
    row = cur.fetchone()

    conn.close()
    return row


def add_best_photo(photo_id: int):
    conn = get_connection()
    cur = conn.cursor()

    today = datetime.date.today().isoformat()

    cur.execute(
        """
        INSERT INTO best_photos (photo_id, date)
        VALUES (?, ?)
        """,
        (photo_id, today)
    )

    conn.commit()
    conn.close()


def clear_best_photos_today():
    conn = get_connection()
    cur = conn.cursor()

    today = datetime.date.today().isoformat()

    cur.execute(
        """
        DELETE FROM best_photos
        WHERE date = ?
        """,
        (today,)
    )

    conn.commit()
    conn.close()


def get_best_photos_today():
    conn = get_connection()
    cur = conn.cursor()

    today = datetime.date.today().isoformat()

    cur.execute(
        """
        SELECT bp.photo_id, p.file_id, p.user_chat_id, p.created_at
        FROM best_photos bp
        JOIN photos p ON bp.photo_id = p.id
        WHERE bp.date = ?
        ORDER BY bp.id ASC
        """,
        (today,)
    )

    rows = cur.fetchall()
    conn.close()

    return rows


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


def get_recent_photos_count(hours: int = 3):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT COUNT(*) as count
        FROM photos
        WHERE datetime(created_at) >= datetime('now', ?)
        """,
        (f"-{hours} hours",)
    )

    row = cur.fetchone()
    conn.close()

    return row["count"]

def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute("SELECT chat_id FROM users")

    users = [row["chat_id"] for row in cursor.fetchall()]

    conn.close()

    return users