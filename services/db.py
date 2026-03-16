import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "sabi.db"

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    with conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS mood_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                anxiety INTEGER,
                stress INTEGER,
                mood INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
    conn.close()

def save_message(user_id: str, role: str, text: str):
    conn = get_db()
    with conn:
        conn.execute(
            "INSERT INTO messages (user_id, role, text) VALUES (?, ?, ?)",
            (user_id, role, text)
        )
    conn.close()

def save_mood(user_id: str, anxiety: int, stress: int, mood: int):
    conn = get_db()
    with conn:
        conn.execute(
            "INSERT INTO mood_logs (user_id, anxiety, stress, mood) VALUES (?, ?, ?, ?)",
            (user_id, anxiety, stress, mood)
        )
    conn.close()

def get_chat_history(user_id: str, limit: int = 50):
    conn = get_db()
    cur = conn.execute(
        "SELECT role, text, created_at FROM messages WHERE user_id = ? ORDER BY created_at ASC LIMIT ?",
        (user_id, limit)
    )
    rows = cur.fetchall()
    conn.close()
    return [{"role": r["role"], "text": r["text"], "created_at": r["created_at"]} for r in rows]

def get_dynamics(user_id: str, limit: int = 14):
    conn = get_db()
    cur = conn.execute(
        "SELECT anxiety, stress, mood, created_at FROM mood_logs WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    )
    rows = cur.fetchall()
    conn.close()
    # Возвращаем в правильном хронологическом порядке
    return [{"anxiety": r["anxiety"], "stress": r["stress"], "mood": r["mood"], "created_at": r["created_at"]} for r in reversed(rows)]
