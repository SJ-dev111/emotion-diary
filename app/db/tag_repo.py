"""entry_emotion_tags 갱신과 분석용 집계 (화면5)."""
import sqlite3


class TagRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def replace_tags(self, entry_id: int, tags) -> None:
        """일기 저장·수정 시 호출. tags: (word, category, count) 목록.
        기존 기록을 지우고 새로 인식된 단어들로 교체한다."""
        self.conn.execute(
            "DELETE FROM entry_emotion_tags WHERE entry_id = ?", (entry_id,)
        )
        self.conn.executemany(
            "INSERT INTO entry_emotion_tags (entry_id, word, category, count)"
            " VALUES (?, ?, ?, ?)",
            [(entry_id, word, category, count) for word, category, count in tags],
        )
        self.conn.commit()

    def tags_for(self, entry_id: int):
        return self.conn.execute(
            "SELECT * FROM entry_emotion_tags WHERE entry_id = ? ORDER BY count DESC, word",
            (entry_id,),
        ).fetchall()

    def category_counts(self, start: str, end: str) -> dict:
        """기간 내 카테고리별 감정 단어 사용량 (파이 차트 재료)."""
        rows = self.conn.execute(
            "SELECT t.category, SUM(t.count) AS total"
            " FROM entry_emotion_tags t"
            " JOIN diary_entries e ON e.id = t.entry_id"
            " WHERE e.date BETWEEN ? AND ?"
            " GROUP BY t.category",
            (start, end),
        ).fetchall()
        return {row["category"]: row["total"] for row in rows}

    def top_words(self, start: str, end: str, limit: int = 3):
        """기간 내 최다 사용 감정 단어 상위 N개: (word, category, total)."""
        return self.conn.execute(
            "SELECT t.word, t.category, SUM(t.count) AS total"
            " FROM entry_emotion_tags t"
            " JOIN diary_entries e ON e.id = t.entry_id"
            " WHERE e.date BETWEEN ? AND ?"
            " GROUP BY t.word, t.category"
            " ORDER BY total DESC, t.word"
            " LIMIT ?",
            (start, end, limit),
        ).fetchall()
