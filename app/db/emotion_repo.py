"""emotion_categories·emotion_dictionary CRUD (화면6)."""
import sqlite3

_UPDATABLE = {"category", "word", "meaning", "stems"}


class EmotionRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ── 카테고리 ───────────────────────────────────────────────

    def categories(self):
        return self.conn.execute(
            "SELECT * FROM emotion_categories ORDER BY sort_order, id"
        ).fetchall()

    def add_category(self, name: str) -> int:
        next_order = self.conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM emotion_categories"
        ).fetchone()[0]
        cur = self.conn.execute(
            "INSERT INTO emotion_categories (name, sort_order, is_default) VALUES (?, ?, 0)",
            (name, next_order),
        )
        self.conn.commit()
        return cur.lastrowid

    def rename_category(self, old_name: str, new_name: str) -> None:
        """카테고리와 소속 단어의 category를 함께 변경.
        과거 일기의 태그(entry_emotion_tags)는 스냅숏이므로 건드리지 않는다."""
        self.conn.execute(
            "UPDATE emotion_categories SET name = ? WHERE name = ?",
            (new_name, old_name),
        )
        self.conn.execute(
            "UPDATE emotion_dictionary SET category = ? WHERE category = ?",
            (new_name, old_name),
        )
        self.conn.commit()

    def delete_category(self, name: str) -> None:
        """카테고리와 소속 단어를 함께 삭제 (UI에서 확인 팝업 필수)."""
        self.conn.execute("DELETE FROM emotion_dictionary WHERE category = ?", (name,))
        self.conn.execute("DELETE FROM emotion_categories WHERE name = ?", (name,))
        self.conn.commit()

    # ── 단어 ──────────────────────────────────────────────────

    def words(self, category: str | None = None):
        if category:
            return self.conn.execute(
                "SELECT * FROM emotion_dictionary WHERE category = ? ORDER BY word",
                (category,),
            ).fetchall()
        return self.conn.execute(
            "SELECT * FROM emotion_dictionary ORDER BY category, word"
        ).fetchall()

    def get_word(self, word_id: int):
        return self.conn.execute(
            "SELECT * FROM emotion_dictionary WHERE id = ?", (word_id,)
        ).fetchone()

    def add_word(self, category: str, word: str, meaning: str = "",
                 stems: str = "", is_default: bool = False) -> int:
        cur = self.conn.execute(
            "INSERT INTO emotion_dictionary (category, word, meaning, stems, is_default)"
            " VALUES (?, ?, ?, ?, ?)",
            (category, word, meaning, stems, int(is_default)),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_word(self, word_id: int, **fields) -> None:
        unknown = set(fields) - _UPDATABLE
        if unknown:
            raise ValueError(f"수정할 수 없는 컬럼: {sorted(unknown)}")
        if not fields:
            return
        assignments = ", ".join(f"{name} = ?" for name in fields)
        self.conn.execute(
            f"UPDATE emotion_dictionary SET {assignments} WHERE id = ?",
            list(fields.values()) + [word_id],
        )
        self.conn.commit()

    def delete_word(self, word_id: int) -> None:
        self.conn.execute("DELETE FROM emotion_dictionary WHERE id = ?", (word_id,))
        self.conn.commit()

    # ── 인식기 연동 ────────────────────────────────────────────

    def all_for_matching(self):
        """감정 인식기용: (단어, 카테고리, 어간 목록) 전체."""
        rows = self.conn.execute(
            "SELECT word, category, stems FROM emotion_dictionary"
        ).fetchall()
        return [
            (row["word"], row["category"],
             [s for s in row["stems"].split(",") if s])
            for row in rows
        ]
