"""좌측 네비게이션 바 — 접기/펼치기 버튼.

모든 화면의 왼편에 붙는다. 창 크기와 무관하게 기본값은 항상 펼쳐진
상태이며, 사용자가 원형 화살표 버튼을 눌렀을 때만 접힌다(자동 접힘 없음).
"""
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QPushButton, QVBoxLayout)

from app import theme
from app.services import shortcut

EXPANDED_WIDTH = 190
COLLAPSED_WIDTH = 48


def _kind(button, kind):
    button.setProperty("kind", kind)
    return button


class NavBar(QFrame):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setProperty("kind", "navBar")
        self.expanded = True

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 10, 8, 10)
        root.setSpacing(4)

        head = QHBoxLayout()
        head.addStretch()
        self.toggle_button = _kind(QPushButton("◀"), "navToggle")
        self.toggle_button.setFixedSize(30, 30)
        self.toggle_button.setToolTip("메뉴 접기/펼치기")
        self.toggle_button.clicked.connect(self._on_toggle)
        head.addWidget(self.toggle_button)
        root.addLayout(head)

        self._items = []       # (활성 키, 버튼) — 키 None이면 활성 표시 없음
        self._separators = []  # 메뉴 그룹 사이 구분선 (접으면 함께 숨김)

        def add_item(text, key, handler, sub=False, kind=None):
            button = _kind(QPushButton(text),
                           kind or ("navSub" if sub else "navItem"))
            button.setCheckable(key is not None)
            button.clicked.connect(handler)
            root.addWidget(button)
            self._items.append((key, button))
            return button

        def add_separator():
            line = QFrame()
            line.setFixedHeight(1)
            line.setStyleSheet(
                f"background-color: {theme.BORDER}; border: none;"
                " margin: 0 4px;")
            root.addWidget(line)
            self._separators.append(line)

        add_item("홈", "home", self.app.show_home)
        add_separator()
        add_item("새 일기 작성", "editor", self.app.nav_new_diary)
        add_separator()
        # 적은 일기 보기 + 리스트/캘린더 뷰는 한 그룹 (사이 구분선 없음)
        add_item("적은 일기 보기", "diary", self.app.nav_show_diaries)
        add_item("리스트 뷰", "list", self.app.show_list, sub=True)
        add_item("캘린더 뷰", "calendar", self.app.show_calendar, sub=True)
        add_separator()
        add_item("분석 보기", "analysis",
                 lambda: self.app.show_analysis(origin="home"))
        add_separator()
        add_item("감정 단어집", "dictionary",
                 lambda: self.app.show_dictionary(origin="home"))
        add_separator()
        add_item("내보내기/백업", None, self.app.show_export)
        add_separator()
        add_item("가이드", None, self.app.show_guide)
        # 배포본에서만 뜻이 있다 — 소스로 실행하면 가리킬 실행 파일이 없다
        self.shortcut_button = None
        if shortcut.is_supported():
            add_separator()
            self.shortcut_button = add_item(
                "바탕화면 바로가기", None, self.app.make_desktop_shortcut,
                kind="navAction")
            self.sync_shortcut_button()
        root.addStretch()

        # 좌측 하단: 라이트/다크 전환 (리스트·캘린더 토글과 같은 모양)
        self.theme_row = QHBoxLayout()
        self.theme_row.setSpacing(0)
        self.light_button = _kind(QPushButton("Light"), "segmentLeft")
        self.dark_button = _kind(QPushButton("Dark"), "segmentRight")
        self._theme_group = QButtonGroup(self)
        self._theme_group.setExclusive(True)
        for button, name in ((self.light_button, "light"),
                             (self.dark_button, "dark")):
            button.setCheckable(True)
            self._theme_group.addButton(button)
            button.clicked.connect(
                lambda _checked=False, n=name: self.app.apply_theme(n))
            self.theme_row.addWidget(button)
        root.addLayout(self.theme_row)
        self.sync_theme_buttons()

        self._apply(True)

    def sync_shortcut_button(self):
        """이미 바로가기가 있으면 글자로 알려 준다."""
        if self.shortcut_button is None:
            return
        made = shortcut.exists()
        self.shortcut_button.setText(
            "바로가기 다시 만들기" if made else "바탕화면 바로가기")
        self.shortcut_button.setToolTip(
            f"이미 있어요 — {shortcut.shortcut_path()}" if made
            else "바탕화면에 감정일기 바로가기를 만듭니다")

    def sync_theme_buttons(self):
        self.light_button.setChecked(theme.current_theme == "light")
        self.dark_button.setChecked(theme.current_theme == "dark")

    def retheme(self):
        """테마가 바뀌면 인라인으로 칠한 구분선 색을 다시 맞춘다."""
        for line in self._separators:
            line.setStyleSheet(
                f"background-color: {theme.BORDER}; border: none;"
                " margin: 0 4px;")
        self.sync_theme_buttons()

    # ── 접기/펼치기 ───────────────────────────────────────────

    def _on_toggle(self):
        self._apply(not self.expanded)

    def _apply(self, expanded: bool):
        self.expanded = expanded
        for button in (self.light_button, self.dark_button):
            button.setVisible(expanded)   # 접으면 테마 버튼도 함께 숨긴다
        for _key, button in self._items:
            button.setVisible(expanded)
        for line in self._separators:
            line.setVisible(expanded)
        self.toggle_button.setText("◀" if expanded else "▶")
        self.setFixedWidth(EXPANDED_WIDTH if expanded else COLLAPSED_WIDTH)

    # ── 활성 화면 표시 ────────────────────────────────────────

    def set_active(self, key):
        """현재 화면에 해당하는 항목을 강조한다. key가 None이면 모두 해제."""
        for item_key, button in self._items:
            if not button.isCheckable():
                continue
            checked = (item_key == key
                       or (item_key == "diary"
                           and key in ("list", "calendar")))
            button.setChecked(checked)
