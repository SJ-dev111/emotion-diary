"""공유용 내보내기(HTML) 테스트 — Qt 없이 순수 로직만 확인한다."""
import unittest

from app import theme
from app.db import database
from app.db.diary_repo import DiaryRepo
from app.db.tag_repo import TagRepo
from app.services import report


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.conn = database.connect(":memory:")
        database.init_db(self.conn)
        self.diary = DiaryRepo(self.conn)
        self.tags = TagRepo(self.conn)

    def tearDown(self):
        self.conn.close()

    def _add(self, date_text, title, mood, favorite=False, **fields):
        entry_id = self.diary.create(date=date_text, title=title,
                                     mood_scale=mood, is_favorite=favorite,
                                     **fields)
        return entry_id

    def _gather(self, **kwargs):
        return report.gather(self.diary, self.tags, **kwargs)

    # ── 자료 모으기 ──────────────────────────────────────────

    def test_gather_orders_by_date_and_counts(self):
        self._add("2026-07-03", "나중", 4)
        self._add("2026-07-01", "먼저", -2)
        data = self._gather()
        self.assertEqual([item["row"]["title"] for item in data["entries"]],
                         ["먼저", "나중"])
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["start"], "2026-07-01")
        self.assertEqual(data["end"], "2026-07-03")
        self.assertAlmostEqual(data["average"], 1.0)

    def test_gather_filters_by_period(self):
        self._add("2026-06-30", "범위 밖", 1)
        self._add("2026-07-05", "범위 안", 1)
        data = self._gather(start="2026-07-01", end="2026-07-31")
        self.assertEqual([item["row"]["title"] for item in data["entries"]],
                         ["범위 안"])

    def test_gather_filters_favorites(self):
        self._add("2026-07-01", "보통", 1)
        self._add("2026-07-02", "즐겨찾기", 1, favorite=True)
        data = self._gather(favorites_only=True)
        self.assertEqual([item["row"]["title"] for item in data["entries"]],
                         ["즐겨찾기"])

    def test_gather_aggregates_tags(self):
        first = self._add("2026-07-01", "가", 3)
        second = self._add("2026-07-02", "나", 5)
        self.tags.replace_tags(first, [("행복하다", "기쁨", 2)])
        self.tags.replace_tags(second, [("행복하다", "기쁨", 1),
                                        ("슬프다", "슬픔", 4)])
        data = self._gather()
        self.assertEqual(data["category_counts"], {"기쁨": 3, "슬픔": 4})
        self.assertEqual(data["top_words"], [("슬프다", 4), ("행복하다", 3)])

    def test_gather_handles_empty(self):
        data = self._gather()
        self.assertEqual(data["count"], 0)
        self.assertIsNone(data["average"])
        self.assertIsNone(data["start"])

    # ── PDF용 HTML ────────────────────────────────────────────────

    def test_pdf_includes_entry_content(self):
        entry_id = self._add("2026-07-01", "산책", 7,
                             event_text="공원에 갔다")
        self.tags.replace_tags(entry_id, [("행복하다", "기쁨", 2)])
        html = report.build_pdf_html(self._gather())
        self.assertIn("산책", html)
        self.assertIn("공원에 갔다", html)
        self.assertIn("행복하다", html)
        self.assertIn("+7", html)
        self.assertIn("무슨 일이 있었나요", html)

    def test_pdf_uses_free_text_for_free_mode(self):
        self._add("2026-07-01", "자유", 0, mode="free",
                  free_text="자유롭게 적은 글")
        html = report.build_pdf_html(self._gather())
        self.assertIn("자유롭게 적은 글", html)
        self.assertNotIn("무슨 일이 있었나요", html)

    def test_pdf_escapes_user_text(self):
        self._add("2026-07-01", "<script>alert(1)</script>", 0)
        html = report.build_pdf_html(self._gather())
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_pdf_embeds_chart_images(self):
        self._add("2026-07-01", "가", 1)
        html = report.build_pdf_html(self._gather(), "data:image/png;base64,AAA",
                                 "data:image/png;base64,BBB")
        self.assertIn("data:image/png;base64,AAA", html)
        self.assertIn("data:image/png;base64,BBB", html)

    def test_pdf_splits_analysis_and_toc_pages(self):
        self._add("2026-07-01", "가", 1)
        html = report.build_pdf_html(self._gather())
        # 분석|목록 사이 1 + 일기 1 = 쪽 나눔 2회
        self.assertEqual(html.count("page-break-before: always"), 2)
        self.assertLess(html.index("<h1>감정일기</h1>"), html.index("<h1>목록</h1>"))

    def test_pdf_scope_section_shows_range_and_count(self):
        self._add("2026-07-01", "가", 1)
        html = report.build_pdf_html(self._gather())
        self.assertIn("<div class='scope-label'>범위</div>", html)
        self.assertIn("<div class='scope-label'>기간</div>", html)
        self.assertIn("<div class='scope-value'>1개</div>", html)

    def test_pdf_toc_has_no_page_numbers(self):
        self._add("2026-07-01", "가", 1)
        html = report.build_pdf_html(self._gather())
        self.assertNotIn("toc-page", html)

    def test_pdf_toc_has_header_row(self):
        self._add("2026-07-01", "가", 1)
        html = report.build_pdf_html(self._gather())
        self.assertIn("<td align='left' width='96' class='toc-head'>날짜</td>",
                      html)
        self.assertIn("<td align='left' class='toc-head'>제목</td>", html)

    def test_pdf_toc_title_links_to_entry_anchor(self):
        self._add("2026-07-01", "첫째", 1)
        self._add("2026-07-02", "둘째", 1)
        html = report.build_pdf_html(self._gather())
        for index, title in enumerate(("첫째", "둘째")):
            anchor = report.entry_anchor(index)
            self.assertIn(f"<a class='toc-link' href='#{anchor}'>{title}</a>",
                          html)
            self.assertIn(f"<a name='{anchor}'></a>", html)

    def test_pdf_toc_orders_entries_ascending(self):
        self._add("2026-07-09", "나중", 1)
        self._add("2026-07-01", "먼저", 1)
        html = report._toc_html(self._gather())
        self.assertLess(html.index("먼저"), html.index("나중"))

    def test_pdf_toc_omits_emotion_words(self):
        entry_id = self._add("2026-07-01", "산책", 7)
        self.tags.replace_tags(entry_id, [("행복하다", "기쁨", 2)])
        toc = report._toc_html(self._gather())
        self.assertNotIn("행복하다", toc)
        self.assertIn("산책", toc)
        self.assertIn("+7", toc)

    def test_pdf_entry_page_uses_list_row_and_boxes(self):
        entry_id = self._add("2026-07-01", "산책", 7, event_text="공원에 갔다")
        self.tags.replace_tags(entry_id, [("행복하다", "기쁨", 2)])
        html = report._entry_html(self._gather()["entries"][0], 0)
        self.assertIn("class='list-row'", html)      # 위쪽 리스트 행
        self.assertIn("행복하다", html)               # 감정 칩은 일기 쪽엔 있다
        self.assertIn("공원에 갔다", html)
        # 세 항목 모두 빈칸이라도 상자를 낸다
        self.assertEqual(html.count("class='card box'"), 3)

    def test_pdf_list_page_only_when_no_entries(self):
        html = report.build_pdf_html(self._gather())
        self.assertIn("<h1>목록</h1>", html)
        self.assertEqual(html.count("page-break-before: always"), 1)


    def test_top_words_sentence_picks_josa(self):
        self.assertIn("'행복'을", report._top_words_sentence([("행복", 2)]))
        self.assertIn("'분노'를", report._top_words_sentence([("분노", 2)]))
        self.assertEqual(report._top_words_sentence([]), "")

    # ── 페이지형 HTML ────────────────────────────────────────

    def test_paged_page_titles_start_with_analysis(self):
        self._add("2026-07-02", "둘째 날", 1)
        self._add("2026-07-01", "첫째 날", 1)
        titles = report._page_titles(self._gather())
        self.assertEqual(titles,
                         ["분석", "적은 일기 보기", "첫째 날", "둘째 날"])

    def test_paged_untitled_entry_gets_placeholder(self):
        self._add("2026-07-01", "", 1)
        self.assertEqual(report._page_titles(self._gather())[2], "(제목 없음)")

    def test_paged_nav_shows_entry_date_with_slashes(self):
        self._add("2026-07-19", "산책", 1)
        html = report.build_paged_html(self._gather())
        self.assertIn("<span class='nav-date'>2026/07/19</span>", html)

    def test_paged_section_items_share_bold_sage_format(self):
        self._add("2026-07-01", "가", 1)
        html = report.build_paged_html(self._gather())
        # 분석·적은 일기 보기가 같은 'section' 서식을 쓴다
        self.assertIn("<button class='nav-item section active' data-page='0'>",
                      html)
        self.assertIn("<button class='nav-item section' data-page='1'>", html)
        self.assertIn(f".nav-item.section {{ color: {theme.PRIMARY};"
                      " font-weight: bold; }", html)

    def test_paged_entry_items_are_indented(self):
        self._add("2026-07-01", "가", 1)
        html = report.build_paged_html(self._gather())
        self.assertIn("<button class='nav-item sub' data-page='2'>", html)
        self.assertIn(".nav-item.sub { margin-left: 16px;", html)

    def test_paged_nav_has_no_page_numbers(self):
        self._add("2026-07-01", "산책", 1)
        html = report.build_paged_html(self._gather())
        self.assertNotIn("nav-num", html)
        self.assertNotIn("leader", html)

    def test_paged_sidebar_stays_left_when_narrow(self):
        html = report.build_paged_html(self._gather())
        # .layout을 세로로 쌓거나 사이드바를 흐름에 되돌리는 규칙이 없어야
        # 위로 올라가지 않는다 (.list의 세로 쌓기는 목록이라 무관)
        self.assertNotIn(".layout { flex-direction: column", html)
        self.assertNotIn("position: static", html)
        # 좁은 화면 규칙 블록(다음 @media 전까지)이 사이드바를 안 건드린다
        narrow = html.split("@media (max-width: 720px)")[1].split("@media")[0]
        self.assertNotIn("sidebar", narrow)

    def test_paged_sidebar_has_collapse_toggle(self):
        html = report.build_paged_html(self._gather())
        self.assertIn("<button class='toggle'", html)
        # 기본은 펼침 — 접힘 표시는 눌러야 붙는다
        self.assertNotIn("<div class='layout collapsed'", html)
        self.assertIn(".layout.collapsed .sidebar", html)

    def test_paged_makes_analysis_list_and_entry_pages(self):
        self._add("2026-07-01", "가", 1)
        self._add("2026-07-02", "나", 1)
        html = report.build_paged_html(self._gather())
        # 분석 1 + 적은 일기 보기 1 + 일기 2
        self.assertEqual(html.count("<section class='page"), 4)

    def test_paged_list_page_rows_link_to_entry_pages(self):
        self._add("2026-07-01", "가", 1)
        self._add("2026-07-02", "나", 1)
        html = report.build_paged_html(self._gather())
        self.assertIn("<button class='list-row' data-page='2'>", html)
        self.assertIn("<button class='list-row' data-page='3'>", html)

    def test_paged_shows_only_first_page_initially(self):
        self._add("2026-07-01", "가", 1)
        html = report.build_paged_html(self._gather())
        self.assertIn("<section class='page show' data-page='0'>", html)
        self.assertIn("<section class='page' data-page='1'>", html)

    def test_paged_marks_first_nav_item_active(self):
        self._add("2026-07-01", "가", 1)
        html = report.build_paged_html(self._gather())
        self.assertEqual(html.count("nav-item section active"), 1)

    def test_paged_orders_entries_ascending(self):
        self._add("2026-07-09", "나중", 1)
        self._add("2026-07-01", "먼저", 1)
        html = report.build_paged_html(self._gather())
        self.assertLess(html.index("먼저"), html.index("나중"))

    def test_paged_includes_entry_body_and_chips(self):
        entry_id = self._add("2026-07-01", "산책", 7, event_text="공원에 갔다")
        self.tags.replace_tags(entry_id, [("행복하다", "기쁨", 2)])
        html = report.build_paged_html(self._gather())
        self.assertIn("공원에 갔다", html)
        self.assertIn("행복하다", html)
        self.assertIn("무슨 일이 있었나요", html)

    def test_paged_escapes_user_text(self):
        self._add("2026-07-01", "<script>alert(1)</script>", 0)
        html = report.build_paged_html(self._gather())
        self.assertNotIn("<script>alert(1)</script>", html)

    def test_paged_keeps_two_pages_when_no_entries(self):
        html = report.build_paged_html(self._gather())
        # 일기가 없어도 분석과 적은 일기 보기 두 쪽은 남는다
        self.assertEqual(html.count("<section class='page"), 2)
        self.assertIn("이 범위에 적은 일기가 없어요", html)

    def test_default_filename(self):
        self._add("2026-07-01", "가", 1)
        name = report.default_filename(self._gather(), "pdf")
        self.assertTrue(name.endswith("2026-07-01.pdf"))

    def test_write_html_round_trip(self):
        import tempfile
        from pathlib import Path
        self._add("2026-07-01", "산책", 7)
        path = Path(tempfile.mkdtemp()) / "out.html"
        report.write_html(path, report.build_pdf_html(self._gather()))
        self.assertIn("산책", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
