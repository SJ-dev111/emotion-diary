"""백업용 내보내기·복원 — DB 전체를 JSON 한 파일로 왕복시킨다.

일기와 감정 태그, 사용자가 추가한 카테고리·단어를 담는다. 기본 단어
(is_default=1)는 앱이 첫 실행 때 스스로 시드하므로 제외한다. 그래야
파일이 작고, 앱 업데이트로 기본 단어 목록이 늘어나도 옛 백업이 그것을
되살리지 않는다.

id는 저장하지 않는다. 태그를 일기 안에 중첩해 두면 복원 시 새 id를
발급해도 관계가 유지되므로, id 충돌을 아예 만들지 않는 편이 안전하다.
"""
import json
import sqlite3
from datetime import datetime

from app import config

FORMAT = "emotion-diary-backup"

_ENTRY_COLUMNS = (
    "date", "title", "mood_scale", "mode",
    "event_text", "emotion_text", "thought_text", "free_text",
    "is_favorite", "created_at", "updated_at",
)


class BackupError(Exception):
    """백업 파일이 이 앱의 것이 아니거나 읽을 수 없을 때."""


# ── 내보내기 ──────────────────────────────────────────────────

def build_backup(conn) -> dict:
    """DB 내용을 JSON으로 직렬화 가능한 dict로 만든다."""
    entries = []
    for row in conn.execute(
            "SELECT * FROM diary_entries ORDER BY date, created_at, id"):
        entry = {name: row[name] for name in _ENTRY_COLUMNS}
        entry["tags"] = [
            {"word": tag["word"], "category": tag["category"],
             "count": tag["count"]}
            for tag in conn.execute(
                "SELECT word, category, count FROM entry_emotion_tags"
                " WHERE entry_id = ? ORDER BY id", (row["id"],))
        ]
        entries.append(entry)

    categories = [
        {"name": row["name"], "sort_order": row["sort_order"]}
        for row in conn.execute(
            "SELECT name, sort_order FROM emotion_categories"
            " WHERE is_default = 0 ORDER BY sort_order, id")
    ]
    words = [
        {"category": row["category"], "word": row["word"],
         "meaning": row["meaning"], "stems": row["stems"]}
        for row in conn.execute(
            "SELECT category, word, meaning, stems FROM emotion_dictionary"
            " WHERE is_default = 0 ORDER BY category, word")
    ]

    return {
        "format": FORMAT,
        "app": config.APP_NAME,
        "schema_version": config.SCHEMA_VERSION,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "entries": entries,
        "emotion_categories": categories,
        "emotion_dictionary": words,
    }


def export_backup(conn, path) -> dict:
    """백업 파일을 쓰고 항목 수를 돌려준다."""
    data = build_backup(conn)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    return summarize(data)


def summarize(data: dict) -> dict:
    return {
        "entries": len(data.get("entries", [])),
        "categories": len(data.get("emotion_categories", [])),
        "words": len(data.get("emotion_dictionary", [])),
    }


# ── 복원 ─────────────────────────────────────────────────────

def load_backup(path) -> dict:
    """백업 파일을 읽고 형식을 검증한다."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise BackupError(f"파일을 읽을 수 없어요: {exc}") from exc
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise BackupError("감정일기 백업 파일이 아니에요.")
    version = data.get("schema_version")
    if version != config.SCHEMA_VERSION:
        raise BackupError(
            f"지원하지 않는 백업 버전이에요 (파일 {version},"
            f" 현재 {config.SCHEMA_VERSION}).")
    if not isinstance(data.get("entries"), list):
        raise BackupError("백업 파일에 일기 목록이 없어요.")
    return data


def _entry_key(entry) -> tuple:
    """병합 시 같은 일기로 볼 기준 — 날짜·제목·작성 시각."""
    return (entry["date"], entry["title"], entry["created_at"])


def restore_backup(conn, data: dict, mode: str = "merge") -> dict:
    """백업을 DB에 적용한다.

    mode='overwrite': 기존 일기·사용자 단어를 지우고 백업 상태로 되돌린다.
    mode='merge':     기존 데이터를 두고 없는 것만 더한다. 날짜·제목·작성
                      시각이 모두 같은 일기는 중복으로 보고 건너뛴다.

    전체를 한 트랜잭션으로 묶어, 중간에 실패하면 아무것도 바뀌지 않는다.
    """
    if mode not in ("overwrite", "merge"):
        raise ValueError(f"지원하지 않는 복원 방식: {mode}")

    added = {"entries": 0, "categories": 0, "words": 0, "skipped": 0}
    try:
        with conn:   # 예외 발생 시 자동 롤백
            if mode == "overwrite":
                conn.execute("DELETE FROM entry_emotion_tags")
                conn.execute("DELETE FROM diary_entries")
                conn.execute("DELETE FROM emotion_dictionary"
                             " WHERE is_default = 0")
                conn.execute("DELETE FROM emotion_categories"
                             " WHERE is_default = 0")
                existing = set()
            else:
                existing = {
                    (row["date"], row["title"], row["created_at"])
                    for row in conn.execute(
                        "SELECT date, title, created_at FROM diary_entries")
                }

            for entry in data["entries"]:
                if _entry_key(entry) in existing:
                    added["skipped"] += 1
                    continue
                existing.add(_entry_key(entry))
                values = [entry.get(name, "") for name in _ENTRY_COLUMNS]
                placeholders = ",".join("?" * len(_ENTRY_COLUMNS))
                cur = conn.execute(
                    f"INSERT INTO diary_entries ({','.join(_ENTRY_COLUMNS)})"
                    f" VALUES ({placeholders})", values)
                entry_id = cur.lastrowid
                conn.executemany(
                    "INSERT INTO entry_emotion_tags"
                    " (entry_id, word, category, count) VALUES (?, ?, ?, ?)",
                    [(entry_id, tag["word"], tag["category"], tag["count"])
                     for tag in entry.get("tags", [])])
                added["entries"] += 1

            # 카테고리·단어는 UNIQUE 제약이 있어 중복이면 조용히 무시된다
            for category in data.get("emotion_categories", []):
                cur = conn.execute(
                    "INSERT OR IGNORE INTO emotion_categories"
                    " (name, sort_order, is_default) VALUES (?, ?, 0)",
                    (category["name"], category.get("sort_order", 0)))
                added["categories"] += cur.rowcount
            for word in data.get("emotion_dictionary", []):
                cur = conn.execute(
                    "INSERT OR IGNORE INTO emotion_dictionary"
                    " (category, word, meaning, stems, is_default)"
                    " VALUES (?, ?, ?, ?, 0)",
                    (word["category"], word["word"],
                     word.get("meaning", ""), word.get("stems", "")))
                added["words"] += cur.rowcount
    except (KeyError, TypeError, ValueError) as exc:
        # 파일 구조가 어긋난 경우 — 키가 없거나 자료형이 엉뚱하다
        raise BackupError(f"백업 파일이 손상된 것 같아요: {exc}") from exc
    except sqlite3.Error as exc:
        # 값이 스키마 제약을 어긴 경우 — 기분 척도가 범위 밖이거나 mode가
        # 엉뚱한 값이거나 날짜가 비어 있는 등. 트랜잭션이 되돌려졌으므로
        # 기존 일기는 그대로다.
        raise BackupError(
            f"백업 파일에 넣을 수 없는 값이 있어요: {exc}") from exc
    return added


def restore_file(conn, path, mode: str = "merge") -> dict:
    return restore_backup(conn, load_backup(path), mode)
