"""SQLite 연결, 스키마 초기화, 기본 데이터 시드."""
import sqlite3

from app import config
from app.data.default_emotions import DEFAULT_CATEGORIES, DEFAULT_WORDS

_SCHEMA = """
CREATE TABLE IF NOT EXISTS diary_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    mood_scale INTEGER NOT NULL CHECK (mood_scale BETWEEN -10 AND 10),
    mode TEXT NOT NULL CHECK (mode IN ('template', 'free')),
    event_text TEXT NOT NULL DEFAULT '',
    emotion_text TEXT NOT NULL DEFAULT '',
    thought_text TEXT NOT NULL DEFAULT '',
    free_text TEXT NOT NULL DEFAULT '',
    is_favorite INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_entries_date ON diary_entries(date);

CREATE TABLE IF NOT EXISTS emotion_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_default INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS emotion_dictionary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    word TEXT NOT NULL UNIQUE,
    meaning TEXT NOT NULL DEFAULT '',
    stems TEXT NOT NULL DEFAULT '',
    is_default INTEGER NOT NULL DEFAULT 0
);

-- word/category는 단어집 id가 아니라 텍스트 스냅숏으로 저장한다.
-- 단어집을 나중에 수정해도 과거 일기의 분석 기록이 바뀌지 않게 하기 위함.
CREATE TABLE IF NOT EXISTS entry_emotion_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL REFERENCES diary_entries(id) ON DELETE CASCADE,
    word TEXT NOT NULL,
    category TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_tags_entry ON entry_emotion_tags(entry_id);
CREATE INDEX IF NOT EXISTS idx_tags_word ON entry_emotion_tags(word);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def connect(path=None) -> sqlite3.Connection:
    """DB에 연결한다. path 생략 시 기본 위치, ':memory:'는 테스트용."""
    conn = sqlite3.connect(str(path) if path else str(config.db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """테이블 생성 + (비어 있을 때만) 기본 카테고리·감정 단어 시드."""
    conn.executescript(_SCHEMA)
    _seed_defaults(conn)
    conn.execute(
        "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)",
        (str(config.SCHEMA_VERSION),),
    )
    conn.commit()


def get_meta(conn: sqlite3.Connection, key: str, default=None):
    row = conn.execute(
        "SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value))
    conn.commit()


def _seed_defaults(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT COUNT(*) FROM emotion_categories").fetchone()[0] == 0:
        for order, name in enumerate(DEFAULT_CATEGORIES):
            conn.execute(
                "INSERT INTO emotion_categories (name, sort_order, is_default) VALUES (?, ?, 1)",
                (name, order),
            )
    if conn.execute("SELECT COUNT(*) FROM emotion_dictionary").fetchone()[0] == 0:
        for category, word, meaning, stems in DEFAULT_WORDS:
            conn.execute(
                "INSERT INTO emotion_dictionary (category, word, meaning, stems, is_default)"
                " VALUES (?, ?, ?, ?, 1)",
                (category, word, meaning, ",".join(stems)),
            )
