"""화면4-2 — 일기 목록 캘린더 뷰 (PySide6).

월간 캘린더. 제목·감정 단어 검색만 제공(날짜 탐색은 캘린더가 겸함).
일기 있는 날: 첫 일기 제목 +N, 일기별 척도색 점, 즐겨찾기 시 우측 상단 ★.
날짜 클릭 → 그날 목록 팝업(+새 일기 추가), 빈 날 클릭 → 그 날짜로 새 일기.
"""
import calendar
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from app import theme
from app.services import emotion_detector
from app.ui_qt.widgets.common import (
    ClickFrame, clear_layout, elided_title_label, entry_title_label,
    mood_badge, star_button, style_star, sub_label, word_chip)

WEEKDAY_HEADERS = ["일", "월", "화", "수", "목", "금", "토"]


def _kind(button, kind):
    button.setProperty("kind", kind)
    return button


class DiaryCalendarScreen(QWidget):
    _BASE_HEIGHT = 560   # 이 높이를 기준(1.0배)으로 화살표·숫자 크기를 키운다
    _BASE_ARROW_PX = 16
    _BASE_MONTH_PX = 17
    _BASE_DAY_PX = 11
    _BASE_CELL_HEIGHT = 58   # 예전(76)보다 작게 — 캘린더 전체를 아담하게

    def __init__(self, app):
        super().__init__()
        self.app = app
        today = date.today()
        self.year, self.month = today.year, today.month
        self._day_font_px = self._BASE_DAY_PX
        self._cell_min_height = self._BASE_CELL_HEIGHT
        self._last_scale = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 14, 20, 16)
        self._build_search_row(root)
        self._build_month_row(root)

        grid_frame = QFrame()
        grid_frame.setProperty("kind", "card")
        self.grid = QGridLayout(grid_frame)
        self.grid.setContentsMargins(6, 6, 6, 6)
        self.grid.setSpacing(3)
        for col in range(7):
            self.grid.setColumnStretch(col, 1)
        root.addWidget(grid_frame, stretch=1)
        # 하단 이동 버튼(분석 보기·새 일기 작성)은 네비게이션 바가 대신한다

    # ── 상단 컨트롤 ───────────────────────────────────────────

    def _build_search_row(self, root):
        row = QHBoxLayout()
        back = _kind(QPushButton("←"), "ghost")
        back.setFixedWidth(40)
        back.clicked.connect(self.app.show_home)
        row.addWidget(back)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("검색어 입력 — 제목·감정 단어 통합 검색")
        self.search_edit.setMinimumHeight(42)
        self.search_edit.setStyleSheet("font-size: 15px;")
        self.search_edit.textChanged.connect(lambda _t: self.refresh())
        row.addWidget(self.search_edit, stretch=1)

        self.btn_list = _kind(QPushButton("리스트"), "segmentLeft")
        self.btn_calendar = _kind(QPushButton("캘린더"), "segmentRight")
        group = QButtonGroup(self)
        group.setExclusive(True)
        segment = QHBoxLayout()
        segment.setSpacing(0)          # 스위치처럼 붙여서 표시
        for button in (self.btn_list, self.btn_calendar):
            button.setCheckable(True)
            group.addButton(button)
            segment.addWidget(button)
        row.addLayout(segment)
        self.btn_calendar.setChecked(True)
        self.btn_list.clicked.connect(self._to_list)
        root.addLayout(row)

    def _build_month_row(self, root):
        row = QHBoxLayout()
        row.addStretch()
        self.prev_button = _kind(QPushButton("◀"), "ghost")
        self.prev_button.setFixedWidth(40)
        self.prev_button.clicked.connect(lambda: self._move_month(-1))
        row.addWidget(self.prev_button)
        self.month_label = QLabel("")
        self.month_label.setStyleSheet(
            f"font-size: {self._BASE_MONTH_PX}px; font-weight: bold;")
        self.month_label.setAlignment(Qt.AlignCenter)
        self.month_label.setFixedWidth(140)
        row.addWidget(self.month_label)
        self.next_button = _kind(QPushButton("▶"), "ghost")
        self.next_button.setFixedWidth(40)
        self.next_button.clicked.connect(lambda: self._move_month(1))
        row.addWidget(self.next_button)
        row.addStretch()
        root.addLayout(row)

    # ── 창 크기에 따른 확대 ───────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_scale(event.size().height())

    def _apply_scale(self, height):
        """창(화면)이 기준 높이보다 커지면 화살표·월 텍스트·날짜 숫자를
        비례해서 키운다. 기준보다 작아지지는 않게 1.0배 아래로는 고정."""
        scale = max(1.0, min(1.6, height / self._BASE_HEIGHT))
        arrow_px = round(self._BASE_ARROW_PX * scale)
        month_px = round(self._BASE_MONTH_PX * scale)
        day_px = round(self._BASE_DAY_PX * scale)
        cell_height = round(self._BASE_CELL_HEIGHT * scale)
        key = (arrow_px, month_px, day_px, cell_height)
        if key == self._last_scale:
            return
        self._last_scale = key
        # 완전히 자체 완결된 스타일을 써서 QSS 병합 순서에 기대지 않는다
        arrow_style = f"""
            QPushButton {{
                background-color: transparent;
                color: {theme.TEXT};
                border: none;
                font-size: {arrow_px}px;
                padding: 4px 2px;
            }}
            QPushButton:hover {{ background-color: {theme.BORDER}; }}
        """
        self.prev_button.setStyleSheet(arrow_style)
        self.next_button.setStyleSheet(arrow_style)
        self.month_label.setStyleSheet(
            f"font-size: {month_px}px; font-weight: bold;")
        self._day_font_px = day_px
        self._cell_min_height = cell_height
        self.refresh()   # 날짜 숫자 폰트·칸 높이를 새로 반영하려면 다시 그린다

    def retheme(self):
        """테마 전환 — 색을 직접 써 넣은 좌우 화살표를 다시 칠한다."""
        self._last_scale = None      # 같은 배율이어도 다시 칠하도록
        self._apply_scale(self.height())

    # ── 동작 ─────────────────────────────────────────────────

    def _to_list(self):
        self.btn_calendar.setChecked(True)   # 돌아올 때를 대비해 원위치
        self.app.show_list()

    def _move_month(self, delta):
        month = self.month + delta
        if month == 0:
            self.year, self.month = self.year - 1, 12
        elif month == 13:
            self.year, self.month = self.year + 1, 1
        else:
            self.month = month
        self.refresh()

    def _month_rows(self):
        """검색 조건을 반영한 이번 달 일기 목록 (날짜·작성 순)."""
        text = self.search_edit.text().strip()
        if not text:
            return self.app.diary_repo.list_month(self.year, self.month)
        # 통합 검색 (제목·감정 단어 — 날짜 탐색은 캘린더가 겸함)
        rows = self.app.diary_repo.search(
            query=text,
            query_emotion_words=emotion_detector.match_words(
                text, self.app.emotion_repo.all_for_matching()))
        prefix = f"{self.year:04d}-{self.month:02d}-"
        rows = [r for r in rows if r["date"].startswith(prefix)]
        return sorted(rows, key=lambda r: (r["date"], r["created_at"]))

    # ── 캘린더 렌더링 ─────────────────────────────────────────

    def refresh(self):
        self.month_label.setText(f"{self.year} / {self.month:02d}")
        clear_layout(self.grid)

        by_day = {}
        for row in self._month_rows():
            day = int(row["date"][8:10])
            by_day.setdefault(day, []).append(row)

        # 일곱 요일이 남는 폭을 똑같이 나눠 갖게 한다. 지정하지 않으면
        # 마지막 열이 여유 폭을 혼자 가져가 토요일 칸만 넓어진다.
        for col in range(7):
            self.grid.setColumnStretch(col, 1)

        for col, name in enumerate(WEEKDAY_HEADERS):
            color = (theme.DANGER if col == 0
                     else theme.PRIMARY if col == 6 else theme.TEXT_SUB)
            label = QLabel(name)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet(
                f"color: {color}; font-weight: bold; font-size: 12px;")
            self.grid.addWidget(label, 0, col)

        weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(
            self.year, self.month)
        for row_idx, week in enumerate(weeks, start=1):
            self.grid.setRowStretch(row_idx, 1)
            for col_idx, day in enumerate(week):
                if day == 0:
                    continue
                cell = self._day_cell(day, by_day.get(day, []))
                self.grid.addWidget(cell, row_idx, col_idx)

    def _day_cell(self, day, rows):
        cell = ClickFrame("dayFilled" if rows else "dayEmpty")
        cell.setMinimumHeight(self._cell_min_height)
        layout = QVBoxLayout(cell)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(1)

        head = QHBoxLayout()
        head.addWidget(sub_label(str(day), self._day_font_px))
        head.addStretch()
        if rows and any(r["is_favorite"] for r in rows):
            # 즐겨찾기된 일기가 하나라도 있으면 우측 상단에 노란 별 하나
            fav = QLabel("★")
            fav.setStyleSheet(f"color: {theme.STAR_ON}; font-size: 12px;")
            head.addWidget(fav)
        layout.addLayout(head)

        date_str = f"{self.year:04d}-{self.month:02d}-{day:02d}"
        if rows:
            first = rows[0]
            title = first["title"] or "(제목 없음)"
            if len(rows) > 1:
                title += f" +{len(rows) - 1}"
            # 글자 수로 자르지 않고 칸 폭에 맞춰 줄인다. 고정 길이로 자르면
            # 긴 제목이 칸의 최소 너비를 밀어 올려 그 열만 넓어졌다.
            layout.addWidget(elided_title_label(title, 11))

            dots = QHBoxLayout()
            dots.setSpacing(2)
            for r in rows[:4]:   # 일기마다 자기 척도 색의 점
                dot = QLabel("●")
                dot.setStyleSheet(
                    f"color: {theme.mood_color(r['mood_scale'])};"
                    " font-size: 9px;")
                dots.addWidget(dot)
            dots.addStretch()
            layout.addLayout(dots)
            # 빈 칸과 마찬가지로 남는 세로 공간을 아래로 몰아준다. 없으면
            # 여유 공간이 항목마다 나뉘어 날짜 숫자가 아래로 밀린다.
            layout.addStretch()
            cell.clicked.connect(
                lambda d=date_str, r=rows: self._open_day(d, r))
        else:
            layout.addStretch()
            # 빈 날짜도 팝업으로: 안내 문구 + '이 날짜에 새 일기 추가' 버튼
            cell.clicked.connect(
                lambda d=date_str: self._open_day(d, []))
        return cell

    def _open_day(self, date_str, rows):
        popup = DayEntriesPopup(self, self.app, date_str, rows)
        popup.exec()


class DayEntriesPopup(QDialog):
    """날짜 칸 클릭 시 그날 일기 목록 + 새 일기 추가 버튼을 보여주는 팝업."""

    def __init__(self, screen, app, date_str, rows):
        super().__init__(screen)
        self.screen = screen          # 즐겨찾기 토글 후 캘린더 갱신용
        self.app = app
        self.date_str = date_str
        self.setWindowTitle(date_str)
        self.resize(400, 380)
        self.setModal(True)

        root = QVBoxLayout(self)
        header_text = (f"{date_str}의 일기 {len(rows)}개" if rows
                       else date_str)
        header = QLabel(header_text)
        header.setStyleSheet("font-size: 15px; font-weight: bold;")
        root.addWidget(header)

        container = QWidget()
        body = QVBoxLayout(container)
        body.setContentsMargins(2, 2, 2, 2)
        body.setSpacing(6)
        if rows:
            for row in rows:
                body.addWidget(self._render_row(row))
            body.addStretch()
        else:
            # 빈 날짜 안내는 팝업 정중앙(가로·세로 모두)에 표시
            body.addStretch()
            empty = sub_label("작성한 일기가 없습니다.", 14)
            empty.setAlignment(Qt.AlignCenter)
            body.addWidget(empty)
            body.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        root.addWidget(scroll, stretch=1)

        add_button = QPushButton("＋ 이 날짜에 새 일기 추가")
        add_button.clicked.connect(self._add_new)
        root.addWidget(add_button)

    def _render_row(self, row):
        item = ClickFrame("row")
        layout = QHBoxLayout(item)
        layout.setContentsMargins(12, 6, 8, 6)

        layout.addWidget(entry_title_label(row["title"] or "(제목 없음)"),
                         stretch=1)

        # 이 일기에서 가장 많이 쓰인 감정 단어 3개 (카테고리 색 하이라이트)
        for tag in self.app.tag_repo.tags_for(row["id"])[:3]:
            layout.addWidget(word_chip(tag["word"], tag["category"]))

        layout.addWidget(mood_badge(row["mood_scale"]))

        state = {"favorite": bool(row["is_favorite"])}
        star = star_button(state["favorite"])

        def toggle_favorite(_checked=False, entry_id=row["id"]):
            state["favorite"] = not state["favorite"]
            self.app.diary_repo.set_favorite(entry_id, state["favorite"])
            style_star(star, state["favorite"])
            self.screen.refresh()     # 캘린더의 ★ 표시도 갱신

        star.clicked.connect(toggle_favorite)
        layout.addWidget(star)

        entry_id = row["id"]
        item.clicked.connect(lambda i=entry_id: self._open_entry(i))
        return item

    def _add_new(self):
        self.accept()
        self.app.show_editor(origin="calendar", preset_date=self.date_str)

    def _open_entry(self, entry_id):
        self.accept()
        self.app.show_editor(entry_id, mode="view", origin="calendar")
