import sqlite3
import os
from datetime import datetime
from pathlib import Path


DB_PATH = Path.home() / ".lesson_recorder" / "lessons.db"


def get_connection():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                duration_seconds INTEGER DEFAULT 0,
                audio_path TEXT,
                transcript TEXT,
                notes TEXT,
                status TEXT DEFAULT 'recording'
            );
        """)


def create_lesson(title: str, audio_path: str) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO lessons (title, created_at, audio_path, status) VALUES (?, ?, ?, 'recording')",
            (title, datetime.now().isoformat(), audio_path)
        )
        return cursor.lastrowid


def update_lesson(lesson_id: int, **kwargs):
    if not kwargs:
        return
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [lesson_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE lessons SET {fields} WHERE id = ?", values)


def get_all_lessons():
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM lessons ORDER BY created_at DESC"
        ).fetchall()


def get_lesson(lesson_id: int):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM lessons WHERE id = ?", (lesson_id,)
        ).fetchone()


def delete_lesson(lesson_id: int):
    lesson = get_lesson(lesson_id)
    if lesson and lesson["audio_path"] and os.path.exists(lesson["audio_path"]):
        try:
            os.remove(lesson["audio_path"])
        except OSError:
            pass
    with get_connection() as conn:
        conn.execute("DELETE FROM lessons WHERE id = ?", (lesson_id,))
