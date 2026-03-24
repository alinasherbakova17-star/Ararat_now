import sqlite3

def add_photo(chat_id: int, file_id: str):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            file_id TEXT
        )
    """)

    cur.execute(
        "INSERT INTO photos (chat_id, file_id) VALUES (?, ?)",
        (chat_id, file_id)
    )

    conn.commit()
    conn.close()


def get_last_photos(limit=5):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT file_id FROM photos
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))

    rows = cur.fetchall()
    conn.close()

    return [row["file_id"] for row in rows]