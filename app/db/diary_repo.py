"""diary_entries CRUD와 목록·검색·분석용 집계 질의."""
import sqlite3
from datetime import datetime

_UPDATABLE = {
    "date", "title", "mood_scale", "mode",
    "event_text", "emotion_text", "thought_text", "free_text", "is_favorite",
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class DiaryRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ── 기본 CRUD ──────────────────────────────────────────────

    def create(self, *, date, title="", mood_scale=0, mode="template",
               event_text="", emotion_text="", thought_text="", free_text="",
               is_favorite=False) -> int:
        now = _now()
        cur = self.conn.execute(
            "INSERT INTO diary_entries"
            " (date, title, mood_scale, mode, event_text, emotion_text,"
            "  thought_text, free_text, is_favorite, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (date, title, mood_scale, mode, event_text, emotion_text,
             thought_text, free_text, int(is_favorite), now, now),
        )
        self.conn.commit()
        return cur.lastrowid

    def get(self, entry_id: int):
        return self.conn.execute(
            "SELECT * FROM diary_entries WHERE id = ?", (entry_id,)
        ).fetchone()

    def update(self, entry_id: int, **fields) -> None:
        unknown = set(fields) - _UPDATABLE
        if unknown:
            raise ValueError(f"수정할 수 없는 컬럼: {sorted(unknown)}")
        if not fields:
            return
        assignments = ", ".join(f"{name} = ?" for name in fields)
        params = [int(v) if isinstance(v, bool) else v for v in fields.values()]
        self.conn.execute(
            f"UPDATE diary_entries SET {assignments}, updated_at = ? WHERE id = ?",
            params + [_now(), entry_id],
        )
        self.conn.commit()

    def delete(self, entry_id: int) -> None:
        self.delete_many([entry_id])

    def delete_many(self, entry_ids) -> None:
        ids = list(entry_ids)
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        self.conn.execute(
            f"DELETE FROM diary_entries WHERE id IN ({placeholders})", ids
        )
        self.conn.commit()

    def set_favorite(self, entry_id: int, flag: bool) -> None:
        self.update(entry_id, is_favorite=flag)

    # ── 목록·검색 (화면1, 4-1, 4-2) ────────────────────────────

    def recent(self, limit: int = 5):
        """홈 화면 미리보기용 최신순 목록."""
        return self.conn.execute(
            "SELECT * FROM diary_entries ORDER BY date DESC, created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()

    def search(self, *, query=None, query_emotion_words=None,
               title=None, date=None, emotion_word=None,
               emotion_words=None, favorites_only=False,
               sort_by="date", ascending=False):
        """리스트 뷰 질의. sort_by는 'date' 또는 'mood', 기본은 날짜 내림차순.

        query: 통합 검색 — 제목·날짜(접두)·감정 단어를 OR로 함께 찾는다.
        emotion_words/query_emotion_words: 활용형 검색 대응 — 검색어를
        자모 매칭으로 풀어낸 기본형 목록(emotion_detector.match_words
        결과)을 함께 넘기면 그 단어들의 태그도 매칭된다.
        """
        if sort_by not in ("date", "mood"):
            raise ValueError(f"지원하지 않는 정렬 기준: {sort_by}")
        sql = "SELECT DISTINCT e.* FROM diary_entries e"
        where, params = [], []
        # 통합 검색은 태그 없는 일기도 제목·날짜로 잡아야 하므로 LEFT JOIN
        if query or query_emotion_words or emotion_word or emotion_words:
            sql += " LEFT JOIN entry_emotion_tags t ON t.entry_id = e.id"
        if query or query_emotion_words:
            terms = []
            if query:
                terms += ["e.title LIKE ?", "e.date LIKE ?", "t.word LIKE ?"]
                params += [f"%{query}%", f"{query}%", f"%{query}%"]
            if query_emotion_words:
                placeholders = ",".join("?" * len(query_emotion_words))
                terms.append(f"t.word IN ({placeholders})")
                params.extend(query_emotion_words)
            where.append("(" + " OR ".join(terms) + ")")
        if emotion_word or emotion_words:
            terms = []
            if emotion_word:
                terms.append("t.word LIKE ?")
                params.append(f"%{emotion_word}%")
            if emotion_words:
                placeholders = ",".join("?" * len(emotion_words))
                terms.append(f"t.word IN ({placeholders})")
                params.extend(emotion_words)
            where.append("(" + " OR ".join(terms) + ")")
        if title:
            where.append("e.title LIKE ?")
            params.append(f"%{title}%")
        if date:
            # 접두 일치: "2026-07-11"은 그날, "2026-07"은 그 달 전체
            where.append("e.date LIKE ?")
            params.append(f"{date}%")
        if favorites_only:
            where.append("e.is_favorite = 1")
        if where:
            sql += " WHERE " + " AND ".join(where)
        column = "e.mood_scale" if sort_by == "mood" else "e.date"
        direction = "ASC" if ascending else "DESC"
        sql += f" ORDER BY {column} {direction}, e.created_at {direction}"
        return self.conn.execute(sql, params).fetchall()

    def list_month(self, year: int, month: int):
        """캘린더 뷰용: 해당 월의 일기를 날짜·작성 순으로."""
        return self.conn.execute(
            "SELECT * FROM diary_entries WHERE date LIKE ?"
            " ORDER BY date ASC, created_at ASC",
            (f"{year:04d}-{month:02d}-%",),
        ).fetchall()

    # ── 분석용 집계 (화면5) ────────────────────────────────────

    def count_between(self, start: str, end: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM diary_entries WHERE date BETWEEN ? AND ?",
            (start, end),
        ).fetchone()[0]

    def avg_mood_between(self, start: str, end: str):
        """기간 평균 기분 척도. 일기가 없으면 None."""
        return self.conn.execute(
            "SELECT AVG(mood_scale) FROM diary_entries WHERE date BETWEEN ? AND ?",
            (start, end),
        ).fetchone()[0]

    def mood_sign_counts(self, start: str, end: str):
        """(긍정, 중립, 부정) 일기 개수. 문장형 요약의 재료."""
        row = self.conn.execute(
            "SELECT"
            " SUM(CASE WHEN mood_scale > 0 THEN 1 ELSE 0 END),"
            " SUM(CASE WHEN mood_scale = 0 THEN 1 ELSE 0 END),"
            " SUM(CASE WHEN mood_scale < 0 THEN 1 ELSE 0 END)"
            " FROM diary_entries WHERE date BETWEEN ? AND ?",
            (start, end),
        ).fetchone()
        return (row[0] or 0, row[1] or 0, row[2] or 0)
