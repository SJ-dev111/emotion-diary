"""화면4-1 — 일기 목록 리스트 뷰 (PySide6).

검색(제목/날짜/감정 단어, 실시간), 정렬 메뉴(기준·방향 라디오 선택),
즐겨찾기 필터, 선택 삭제, 캘린더 뷰 전환.
"""
from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QHBoxLayout, QLabel, QLineEdit, QMenu,
    QPushButton, QScrollArea, QVBoxLayout, QWidget)

from app import theme
from app.services import emotion_detector
from app.ui_qt.widgets.common import (
    ClickFrame, clear_layout, confirm, entry_title_label, mood_badge,
    star_button, sub_label, word_chip)


def _kind(button, kind):
    button.setProperty("kind", kind)
    return button


def _outline_style(active: bool = False) -> str:
    """정렬·즐겨찾기 버튼 공용 외곽선 스타일 (초록 글자).

    둘이 나란히 붙어 한 그룹처럼 보여야 해서 한곳에서 만든다.
    """
    border = theme.PRIMARY if active else theme.BORDER
    weight = "bold" if active else "normal"
    return (f"background: transparent; color: {theme.PRIMARY};"
            f" border: 1px solid {border}; border-radius: 8px;"
            f" padding: 6px 12px; font-weight: {weight};")


class DiaryListScreen(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.sort_by = "date"
        self.ascending = False        # 기본: 날짜 내림차순(최신순)
        self.favorites_only = False
        self.select_mode = False      # 선택 삭제 모드 (체크박스 표시)
        self._checks = []             # (QCheckBox, entry_id)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 14, 20, 16)
        self._build_search_row(root)
        self._build_control_row(root)

        self.list_container = QVBoxLayout()
        self.list_container.setSpacing(6)
        container_widget = QWidget()
        outer = QVBoxLayout(container_widget)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.addLayout(self.list_container)
        outer.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container_widget)
        # 흰색 행이 크림색 배경 위에서 또렷하도록 카드 래퍼 없이 배치
        root.addWidget(scroll, stretch=1)
        # 하단 이동 버튼(분석 보기·새 일기 작성)은 네비게이션 바가 대신한다

    # ── 상단 컨트롤 ───────────────────────────────────────────

    def _build_search_row(self, root):
        row = QHBoxLayout()
        back = _kind(QPushButton("←"), "ghost")
        back.setFixedWidth(40)
        back.clicked.connect(self.app.show_home)
        row.addWidget(back)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            "검색어 입력 — 제목·날짜·감정 단어 통합 검색 (날짜는 2026-07 형식도 가능)")
        self.search_edit.textChanged.connect(lambda _t: self.refresh())
        row.addWidget(self.search_edit, stretch=1)
        root.addLayout(row)

    def _build_control_row(self, root):
        row = QHBoxLayout()
        self.delete_button = _kind(QPushButton("선택 삭제"), "flatDanger")
        self.delete_button.clicked.connect(self._delete_selected)
        row.addWidget(self.delete_button)
        self.cancel_button = _kind(QPushButton("취소"), "flat")
        self.cancel_button.clicked.connect(
            lambda: self._set_select_mode(False))
        self.cancel_button.setVisible(False)   # 선택 모드에서만 표시
        row.addWidget(self.cancel_button)
        row.addStretch()

        # 정렬 메뉴 버튼 — 기준(날짜순/점수순)과 방향(오름/내림)을
        # 한 메뉴에서 라디오로 고른다 (Windows 탐색기 정렬 메뉴 방식)
        # 즐겨찾기 버튼과 크기·글자색을 맞춰 한 그룹처럼 보이게 한다
        self.sort_button = QPushButton("↑↓ 정렬")
        self.sort_button.setStyleSheet(_outline_style())
        menu = QMenu(self)
        key_group = QActionGroup(menu)
        self.act_date = menu.addAction("날짜순")
        self.act_mood = menu.addAction("점수순")
        for action in (self.act_date, self.act_mood):
            action.setCheckable(True)
            key_group.addAction(action)
        self.act_date.setChecked(True)
        menu.addSeparator()
        direction_group = QActionGroup(menu)
        self.act_asc = menu.addAction("오름차순")
        self.act_desc = menu.addAction("내림차순")
        for action in (self.act_asc, self.act_desc):
            action.setCheckable(True)
            direction_group.addAction(action)
        self.act_desc.setChecked(True)
        self.act_date.triggered.connect(
            lambda: self._set_sort(sort_by="date"))
        self.act_mood.triggered.connect(
            lambda: self._set_sort(sort_by="mood"))
        self.act_asc.triggered.connect(
            lambda: self._set_sort(ascending=True))
        self.act_desc.triggered.connect(
            lambda: self._set_sort(ascending=False))
        self.sort_button.setMenu(menu)
        row.addWidget(self.sort_button)

        self.fav_button = QPushButton("★ 즐겨찾기")
        self.fav_button.clicked.connect(self._toggle_favorites)
        self._style_fav_button()
        row.addWidget(self.fav_button)

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
        self.btn_list.setChecked(True)
        self.btn_calendar.clicked.connect(self._to_calendar)
        root.addLayout(row)

    # ── 동작 ─────────────────────────────────────────────────

    def _to_calendar(self):
        self.btn_list.setChecked(True)   # 돌아올 때를 대비해 원위치
        self.app.show_calendar()

    def _set_sort(self, sort_by=None, ascending=None):
        if sort_by is not None:
            self.sort_by = sort_by
        if ascending is not None:
            self.ascending = ascending
        self.refresh()

    def _toggle_favorites(self):
        self.favorites_only = not self.favorites_only
        self._style_fav_button()
        self.refresh()

    def retheme(self):
        """테마 전환 — 색을 직접 써 넣은 정렬·즐겨찾기 버튼을 다시 칠한다."""
        self.sort_button.setStyleSheet(_outline_style())
        self._style_fav_button()
        self.refresh()

    def _style_fav_button(self):
        # 켜짐/꺼짐은 색이 아니라 테두리와 굵기로 구분한다 — 정렬 버튼과
        # 같은 초록 글자색을 유지하기 위해서.
        self.fav_button.setStyleSheet(_outline_style(self.favorites_only))

    def _delete_selected(self):
        """1번 누르면 선택 모드 진입(체크박스 표시), 선택 후 다시 누르면
        확인 팝업 → 삭제. 아무것도 선택하지 않고 다시 누르면 모드 해제."""
        if not self.select_mode:
            self._set_select_mode(True)
            return
        ids = [entry_id for check, entry_id in self._checks
               if check.isChecked()]
        if not ids:
            self._set_select_mode(False)   # 취소로 간주
            return
        if not confirm(
                self, "삭제 확인",
                f"선택한 일기 {len(ids)}개를 삭제할까요?\n"
                "삭제한 일기는 되돌릴 수 없어요.",
                yes="삭제", no="취소"):
            return
        self.app.diary_repo.delete_many(ids)
        self._set_select_mode(False)

    def _set_select_mode(self, active: bool):
        self.select_mode = active
        self.cancel_button.setVisible(active)
        if active:
            self.delete_button.setText("선택한 일기 삭제")
            self.delete_button.setStyleSheet(
                f"background-color: {theme.DANGER}; color: white;"
                " border: none; border-radius: 8px; padding: 9px 16px;"
                " font-weight: bold;")
        else:
            self.delete_button.setText("선택 삭제")
            self.delete_button.setStyleSheet("")   # QSS flatDanger로 복귀
        self.refresh()

    def _toggle_row_favorite(self, entry_id, flag):
        self.app.diary_repo.set_favorite(entry_id, flag)
        self.refresh()

    # ── 목록 렌더링 ───────────────────────────────────────────

    def refresh(self):
        clear_layout(self.list_container)
        self._checks = []

        text = self.search_edit.text().strip()
        kwargs = dict(favorites_only=self.favorites_only,
                      sort_by=self.sort_by, ascending=self.ascending)
        if text:
            # 항상 통합 검색: 제목·날짜·감정 단어(활용형 포함)를 한 번에
            kwargs["query"] = text
            kwargs["query_emotion_words"] = emotion_detector.match_words(
                text, self.app.emotion_repo.all_for_matching())
        rows = self.app.diary_repo.search(**kwargs)

        if not rows:
            empty = sub_label("조건에 맞는 일기가 없어요.", 14)
            self.list_container.addWidget(empty)
            return
        for row in rows:
            self.list_container.addWidget(self._render_row(row))

    def _render_row(self, row):
        item = ClickFrame("row")
        layout = QHBoxLayout(item)
        layout.setContentsMargins(10, 6, 8, 6)

        check = None
        if self.select_mode:   # 체크박스는 선택 삭제 모드에서만 표시
            check = QCheckBox()
            layout.addWidget(check)
            self._checks.append((check, row["id"]))

        date_label = sub_label(row["date"])
        date_label.setFixedWidth(90)
        layout.addWidget(date_label)

        layout.addWidget(entry_title_label(row["title"] or "(제목 없음)"),
                         stretch=1)

        # 이 일기에서 가장 많이 쓰인 감정 단어 3개 (카테고리 색 하이라이트)
        for tag in self.app.tag_repo.tags_for(row["id"])[:3]:
            layout.addWidget(word_chip(tag["word"], tag["category"]))

        layout.addWidget(mood_badge(row["mood_scale"]))

        favorite = bool(row["is_favorite"])
        star = star_button(favorite)
        star.clicked.connect(
            lambda _c=False, i=row["id"], f=favorite:
            self._toggle_row_favorite(i, not f))
        layout.addWidget(star)

        entry_id = row["id"]
        if self.select_mode:
            # 선택 모드에서는 행 클릭이 체크 토글로 동작
            item.clicked.connect(
                lambda c=check: c.setChecked(not c.isChecked()))
        else:
            item.clicked.connect(
                lambda i=entry_id: self.app.show_editor(i, mode="view",
                                                        origin="list"))
        return item
