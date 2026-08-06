"""데이터 계층(스키마·리포지토리) 테스트. 인메모리 DB 사용."""
import sqlite3
import unittest

from app.db import database
from app.db.diary_repo import DiaryRepo
from app.db.emotion_repo import EmotionRepo
from app.db.tag_repo import TagRepo
from app.data.default_emotions import DEFAULT_CATEGORIES, DEFAULT_WORDS


def make_conn():
    conn = database.connect(":memory:")
    database.init_db(conn)
    return conn


class DiaryRepoTest(unittest.TestCase):
    def setUp(self):
        self.conn = make_conn()
        self.repo = DiaryRepo(self.conn)
        self.tags = TagRepo(self.conn)

    def tearDown(self):
        self.conn.close()

    def _entry(self, **kw):
        base = dict(date="2026-07-11", title="테스트", mood_scale=3, mode="template")
        base.update(kw)
        return self.repo.create(**base)

    def test_create_and_get(self):
        entry_id = self._entry(event_text="사건", emotion_text="감정", thought_text="생각")
        row = self.repo.get(entry_id)
        self.assertEqual(row["date"], "2026-07-11")
        self.assertEqual(row["title"], "테스트")
        self.assertEqual(row["mood_scale"], 3)
        self.assertEqual(row["event_text"], "사건")
        self.assertEqual(row["is_favorite"], 0)
        self.assertEqual(row["created_at"], row["updated_at"])

    def test_update(self):
        entry_id = self._entry()
        self.repo.update(entry_id, title="수정됨", mood_scale=-5)
        row = self.repo.get(entry_id)
        self.assertEqual(row["title"], "수정됨")
        self.assertEqual(row["mood_scale"], -5)

    def test_update_rejects_unknown_column(self):
        entry_id = self._entry()
        with self.assertRaises(ValueError):
            self.repo.update(entry_id, created_at="조작")

    def test_mood_scale_range_enforced(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self._entry(mood_scale=11)
        with self.assertRaises(sqlite3.IntegrityError):
            self._entry(mood_scale=-11)

    def test_mode_enforced(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self._entry(mode="invalid")

    def test_delete_cascades_tags(self):
        entry_id = self._entry()
        self.tags.replace_tags(entry_id, [("행복하다", "기쁨", 2)])
        self.repo.delete(entry_id)
        self.assertIsNone(self.repo.get(entry_id))
        self.assertEqual(self.tags.tags_for(entry_id), [])

    def test_delete_many(self):
        ids = [self._entry(date=f"2026-07-0{d}") for d in range(1, 4)]
        self.repo.delete_many(ids[:2])
        self.assertIsNone(self.repo.get(ids[0]))
        self.assertIsNotNone(self.repo.get(ids[2]))
        self.repo.delete_many([])  # 빈 목록은 무해해야 함

    def test_set_favorite(self):
        entry_id = self._entry()
        self.repo.set_favorite(entry_id, True)
        self.assertEqual(self.repo.get(entry_id)["is_favorite"], 1)

    def test_recent_limit_and_order(self):
        for day in range(1, 8):
            self._entry(date=f"2026-07-{day:02d}", title=f"{day}일")
        rows = self.repo.recent(limit=5)
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]["title"], "7일")  # 최신순

    def test_search_default_is_date_desc(self):
        self._entry(date="2026-07-01")
        self._entry(date="2026-07-05")
        rows = self.repo.search()
        self.assertEqual([r["date"] for r in rows], ["2026-07-05", "2026-07-01"])

    def test_search_by_title(self):
        self._entry(title="산책한 날")
        self._entry(title="비 오는 날")
        rows = self.repo.search(title="산책")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "산책한 날")

    def test_search_by_date_prefix(self):
        self._entry(date="2026-07-11")
        self._entry(date="2026-07-20")
        self._entry(date="2026-08-01")
        self.assertEqual(len(self.repo.search(date="2026-07-11")), 1)
        self.assertEqual(len(self.repo.search(date="2026-07")), 2)

    def test_search_by_emotion_word(self):
        e1 = self._entry(title="좋은 날")
        e2 = self._entry(title="나쁜 날")
        self.tags.replace_tags(e1, [("행복하다", "기쁨", 1)])
        self.tags.replace_tags(e2, [("슬프다", "슬픔", 1)])
        rows = self.repo.search(emotion_word="행복")
        self.assertEqual([r["title"] for r in rows], ["좋은 날"])

    def test_search_by_emotion_words_list(self):
        entry = self._entry(title="서러운 날")
        self.tags.replace_tags(entry, [("서럽다", "슬픔", 1)])
        # 활용형 그대로는 LIKE로 못 잡지만, 기본형 목록을 함께 주면 잡힌다
        self.assertEqual(len(self.repo.search(emotion_word="서러웠다")), 0)
        rows = self.repo.search(emotion_word="서러웠다",
                                emotion_words=["서럽다"])
        self.assertEqual([r["title"] for r in rows], ["서러운 날"])

    def test_search_unified_query(self):
        walk = self._entry(title="산책한 날", date="2026-07-05")
        work = self._entry(title="야근", date="2026-06-20")
        sad = self._entry(title="힘든 날", date="2026-07-08")
        self.tags.replace_tags(sad, [("서럽다", "슬픔", 1)])

        # 제목으로 (태그 없는 일기도 LEFT JOIN으로 잡혀야 함)
        rows = self.repo.search(query="산책")
        self.assertEqual([r["id"] for r in rows], [walk])
        # 날짜 접두로
        rows = self.repo.search(query="2026-07")
        self.assertEqual({r["id"] for r in rows}, {walk, sad})
        # 감정 단어 활용형으로 (기본형 목록 함께 전달)
        rows = self.repo.search(query="서러웠다",
                                query_emotion_words=["서럽다"])
        self.assertEqual([r["id"] for r in rows], [sad])
        # 중복 없이 1건씩
        self.tags.replace_tags(walk, [("행복하다", "기쁨", 2)])
        rows = self.repo.search(query="산책")
        self.assertEqual(len(rows), 1)

    def test_search_favorites_only(self):
        self._entry(title="일반")
        fav = self._entry(title="즐겨찾기", is_favorite=True)
        rows = self.repo.search(favorites_only=True)
        self.assertEqual([r["id"] for r in rows], [fav])

    def test_search_sort_by_mood(self):
        self._entry(mood_scale=5)
        self._entry(mood_scale=-3)
        self._entry(mood_scale=0)
        rows = self.repo.search(sort_by="mood", ascending=True)
        self.assertEqual([r["mood_scale"] for r in rows], [-3, 0, 5])

    def test_search_rejects_bad_sort(self):
        with self.assertRaises(ValueError):
            self.repo.search(sort_by="id; DROP TABLE diary_entries")

    def test_list_month(self):
        self._entry(date="2026-06-30")
        self._entry(date="2026-07-01")
        self._entry(date="2026-07-31")
        rows = self.repo.list_month(2026, 7)
        self.assertEqual([r["date"] for r in rows], ["2026-07-01", "2026-07-31"])

    def test_analysis_aggregates(self):
        self._entry(date="2026-07-01", mood_scale=4)
        self._entry(date="2026-07-02", mood_scale=-2)
        self._entry(date="2026-07-03", mood_scale=0)
        self._entry(date="2026-08-01", mood_scale=10)  # 기간 밖
        start, end = "2026-07-01", "2026-07-31"
        self.assertEqual(self.repo.count_between(start, end), 3)
        self.assertAlmostEqual(self.repo.avg_mood_between(start, end), 2 / 3)
        self.assertEqual(self.repo.mood_sign_counts(start, end), (1, 1, 1))

    def test_avg_mood_empty_period_is_none(self):
        self.assertIsNone(self.repo.avg_mood_between("2025-01-01", "2025-12-31"))


class MetaTest(unittest.TestCase):
    def test_get_set_meta(self):
        conn = make_conn()
        self.assertIsNone(database.get_meta(conn, "guide_shown"))
        self.assertEqual(database.get_meta(conn, "guide_shown", "0"), "0")
        database.set_meta(conn, "guide_shown", "1")
        self.assertEqual(database.get_meta(conn, "guide_shown"), "1")
        database.set_meta(conn, "guide_shown", "2")   # upsert
        self.assertEqual(database.get_meta(conn, "guide_shown"), "2")
        self.assertEqual(database.get_meta(conn, "schema_version"), "1")
        conn.close()


class EmotionRepoTest(unittest.TestCase):
    def setUp(self):
        self.conn = make_conn()
        self.repo = EmotionRepo(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_seed_loaded(self):
        names = [row["name"] for row in self.repo.categories()]
        self.assertEqual(names, DEFAULT_CATEGORIES)
        self.assertEqual(len(self.repo.words()), len(DEFAULT_WORDS))
        self.assertEqual(len(self.repo.words("기쁨")), 7)

    def test_seed_runs_once(self):
        database.init_db(self.conn)  # 재실행해도 중복 시드 없어야 함
        self.assertEqual(len(self.repo.words()), len(DEFAULT_WORDS))

    def test_add_and_update_word(self):
        word_id = self.repo.add_word("슬픔", "서운하다", "기대에 못 미쳐 섭섭하다", "서운")
        self.repo.update_word(word_id, meaning="마음이 섭섭하다", stems="서운,서운했")
        row = self.repo.get_word(word_id)
        self.assertEqual(row["stems"], "서운,서운했")
        self.assertEqual(row["is_default"], 0)

    def test_duplicate_word_raises(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.add_word("기쁨", "행복하다")

    def test_rename_category_moves_words(self):
        self.repo.rename_category("분노", "화")
        names = [row["name"] for row in self.repo.categories()]
        self.assertIn("화", names)
        self.assertNotIn("분노", names)
        self.assertEqual(len(self.repo.words("화")), 6)
        self.assertEqual(self.repo.words("분노"), [])

    def test_delete_category_removes_words(self):
        self.repo.delete_category("기타")
        self.assertEqual(self.repo.words("기타"), [])
        self.assertNotIn("기타", [row["name"] for row in self.repo.categories()])

    def test_add_category_appends_last(self):
        self.repo.add_category("복합감정")
        names = [row["name"] for row in self.repo.categories()]
        self.assertEqual(names[-1], "복합감정")

    def test_all_for_matching_parses_stems(self):
        matching = {word: stems for word, _, stems in self.repo.all_for_matching()}
        self.assertEqual(matching["무섭다"], ["무섭", "무서우"])
        self.assertEqual(matching["화나다"], ["화나", "화가 나"])


class TagRepoTest(unittest.TestCase):
    def setUp(self):
        self.conn = make_conn()
        self.diary = DiaryRepo(self.conn)
        self.repo = TagRepo(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_replace_tags_overwrites(self):
        entry_id = self.diary.create(date="2026-07-11")
        self.repo.replace_tags(entry_id, [("행복하다", "기쁨", 1), ("슬프다", "슬픔", 2)])
        self.repo.replace_tags(entry_id, [("불안하다", "불안", 3)])
        rows = self.repo.tags_for(entry_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["word"], rows[0]["count"]), ("불안하다", 3))

    def test_category_counts_filters_by_date(self):
        in_range = self.diary.create(date="2026-07-05")
        out_range = self.diary.create(date="2026-08-05")
        self.repo.replace_tags(in_range, [("행복하다", "기쁨", 2), ("불안하다", "불안", 1)])
        self.repo.replace_tags(out_range, [("슬프다", "슬픔", 5)])
        counts = self.repo.category_counts("2026-07-01", "2026-07-31")
        self.assertEqual(counts, {"기쁨": 2, "불안": 1})

    def test_top_words_sums_across_entries(self):
        e1 = self.diary.create(date="2026-07-01")
        e2 = self.diary.create(date="2026-07-02")
        self.repo.replace_tags(e1, [("행복하다", "기쁨", 1), ("슬프다", "슬픔", 3)])
        self.repo.replace_tags(e2, [("행복하다", "기쁨", 4)])
        top = self.repo.top_words("2026-07-01", "2026-07-31", limit=3)
        self.assertEqual([(r["word"], r["total"]) for r in top],
                         [("행복하다", 5), ("슬프다", 3)])


if __name__ == "__main__":
    unittest.main()
