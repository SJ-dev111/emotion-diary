"""백업 내보내기·복원 테스트."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from app import config
from app.db import database
from app.db.diary_repo import DiaryRepo
from app.db.emotion_repo import EmotionRepo
from app.db.tag_repo import TagRepo
from app.services import backup


class BackupTest(unittest.TestCase):
    def setUp(self):
        self.conn = database.connect(":memory:")
        database.init_db(self.conn)
        self.diary = DiaryRepo(self.conn)
        self.emotion = EmotionRepo(self.conn)
        self.tags = TagRepo(self.conn)
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        self.conn.close()

    def _seed(self):
        entry_id = self.diary.create(date="2026-07-01", title="산책",
                                     mood_scale=7, event_text="걸었다")
        self.tags.replace_tags(entry_id, [("행복하다", "기쁨", 2)])
        self.emotion.add_category("설렘")
        self.emotion.add_word("설렘", "두근거리다", "기대되는", "두근")
        return entry_id

    def _fresh_conn(self):
        conn = database.connect(":memory:")
        database.init_db(conn)
        return conn

    # ── 내보내기 ─────────────────────────────────────────────

    def test_backup_contains_entries_and_tags(self):
        self._seed()
        data = backup.build_backup(self.conn)
        self.assertEqual(data["format"], backup.FORMAT)
        self.assertEqual(data["schema_version"], config.SCHEMA_VERSION)
        self.assertEqual(len(data["entries"]), 1)
        entry = data["entries"][0]
        self.assertEqual(entry["title"], "산책")
        self.assertEqual(entry["tags"],
                         [{"word": "행복하다", "category": "기쁨", "count": 2}])
        self.assertNotIn("id", entry)

    def test_backup_excludes_default_dictionary(self):
        self._seed()
        data = backup.build_backup(self.conn)
        self.assertEqual([c["name"] for c in data["emotion_categories"]],
                         ["설렘"])
        self.assertEqual([w["word"] for w in data["emotion_dictionary"]],
                         ["두근거리다"])

    def test_export_writes_readable_file(self):
        self._seed()
        path = self.tmp / "backup.json"
        counts = backup.export_backup(self.conn, path)
        self.assertEqual(counts["entries"], 1)
        loaded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(loaded["entries"][0]["title"], "산책")

    # ── 복원 ────────────────────────────────────────────────

    def test_round_trip_restores_everything(self):
        self._seed()
        data = backup.build_backup(self.conn)

        target = self._fresh_conn()
        added = backup.restore_backup(target, data, "overwrite")
        self.assertEqual(added["entries"], 1)

        rows = DiaryRepo(target).search()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "산책")
        self.assertEqual(rows[0]["mood_scale"], 7)
        tags = TagRepo(target).tags_for(rows[0]["id"])
        self.assertEqual([t["word"] for t in tags], ["행복하다"])
        names = [c["name"] for c in EmotionRepo(target).categories()]
        self.assertIn("설렘", names)
        target.close()

    def test_overwrite_clears_existing_entries(self):
        self._seed()
        data = backup.build_backup(self.conn)

        target = self._fresh_conn()
        DiaryRepo(target).create(date="2026-01-01", title="지워질 일기")
        backup.restore_backup(target, data, "overwrite")
        titles = [row["title"] for row in DiaryRepo(target).search()]
        self.assertEqual(titles, ["산책"])
        target.close()

    def test_merge_keeps_existing_and_skips_duplicates(self):
        self._seed()
        data = backup.build_backup(self.conn)

        target = self._fresh_conn()
        DiaryRepo(target).create(date="2026-01-01", title="남아야 할 일기")
        first = backup.restore_backup(target, data, "merge")
        self.assertEqual(first["entries"], 1)
        # 같은 백업을 한 번 더 — 중복이므로 늘지 않아야 한다
        second = backup.restore_backup(target, data, "merge")
        self.assertEqual(second["entries"], 0)
        self.assertEqual(second["skipped"], 1)

        titles = sorted(row["title"] for row in DiaryRepo(target).search())
        self.assertEqual(titles, ["남아야 할 일기", "산책"])
        target.close()

    def test_restore_is_atomic_on_bad_entry(self):
        self._seed()
        data = backup.build_backup(self.conn)
        data["entries"].append({"date": "2026-07-02"})   # 필수 항목 누락

        target = self._fresh_conn()
        with self.assertRaises(backup.BackupError):
            backup.restore_backup(target, data, "merge")
        # 앞선 정상 일기까지 롤백되어야 한다
        self.assertEqual(DiaryRepo(target).search(), [])
        target.close()

    # ── 검증 ────────────────────────────────────────────────

    def test_load_rejects_foreign_file(self):
        path = self.tmp / "other.json"
        path.write_text('{"format": "다른앱"}', encoding="utf-8")
        with self.assertRaises(backup.BackupError):
            backup.load_backup(path)

    def test_load_rejects_future_schema_version(self):
        path = self.tmp / "future.json"
        path.write_text(json.dumps({
            "format": backup.FORMAT,
            "schema_version": config.SCHEMA_VERSION + 1,
            "entries": [],
        }), encoding="utf-8")
        with self.assertRaises(backup.BackupError):
            backup.load_backup(path)

    def test_load_rejects_broken_json(self):
        path = self.tmp / "broken.json"
        path.write_text("{ not json", encoding="utf-8")
        with self.assertRaises(backup.BackupError):
            backup.load_backup(path)

    def _corrupt(self, **overrides):
        """정상 백업의 사본을 만들고 일기 항목만 망가뜨린다.

        원본을 매번 다시 시드하면 카테고리가 UNIQUE에 걸리므로 사본을 쓴다.
        """
        if not getattr(self, "_seeded", False):
            self._seed()
            self._seeded = True
        data = copy.deepcopy(backup.build_backup(self.conn))
        data["entries"][0].update(overrides)
        return data

    def test_restore_reports_schema_violations_as_backup_error(self):
        """스키마 제약을 어긴 값은 sqlite 예외가 새어 나가지 않고
        BackupError로 안내돼야 한다 (UI가 잡는 유일한 예외)."""
        cases = {
            "기분 척도 범위 밖": {"mood_scale": 999},
            "기분 척도가 문자열": {"mood_scale": "많이"},
            "mode 값이 엉뚱함": {"mode": "해킹"},
            "date 가 null": {"date": None},
            "is_favorite 가 dict": {"is_favorite": {"a": 1}},
        }
        for name, overrides in cases.items():
            with self.subTest(name):
                target = self._fresh_conn()
                with self.assertRaises(backup.BackupError):
                    backup.restore_backup(target, self._corrupt(**overrides),
                                          "merge")
                target.close()

    def test_restore_keeps_existing_data_when_value_is_invalid(self):
        """복원이 실패해도 트랜잭션이 되돌아가 기존 일기가 남아야 한다."""
        data = self._corrupt(mood_scale=999)
        target = self._fresh_conn()
        DiaryRepo(target).create(date="2026-01-01", title="남아야 할 일기")
        with self.assertRaises(backup.BackupError):
            backup.restore_backup(target, data, "overwrite")
        titles = [row["title"] for row in DiaryRepo(target).search()]
        self.assertEqual(titles, ["남아야 할 일기"])
        target.close()

    def test_restore_rejects_unknown_mode(self):
        with self.assertRaises(ValueError):
            backup.restore_backup(self.conn, backup.build_backup(self.conn),
                                  "무엇")


if __name__ == "__main__":
    unittest.main()
