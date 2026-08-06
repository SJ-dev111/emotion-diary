"""메인 윈도우 (PySide6) — DB 연결을 소유하고 화면 전환을 관리한다."""
from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QMainWindow, QMessageBox, QStackedWidget,
    QWidget)

from app import config, theme
from app.db import database
from app.services import shortcut
from app.db.diary_repo import DiaryRepo
from app.db.emotion_repo import EmotionRepo
from app.db.tag_repo import TagRepo
from app.ui_qt.screens.analysis import AnalysisScreen
from app.ui_qt.screens.diary_calendar import DiaryCalendarScreen
from app.ui_qt.screens.diary_list import DiaryListScreen
from app.ui_qt.screens.dictionary import DictionaryScreen
from app.ui_qt.screens.editor import EditorScreen
from app.ui_qt.screens.home import HomeScreen
from app.ui_qt.style import build_qss
from app.ui_qt.widgets.common import confirm
from app.ui_qt.widgets.export_dialog import ExportDialog
from app.ui_qt.widgets.guide_popup import GuideDialog
from app.ui_qt.widgets.nav_bar import NavBar


class AppWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(config.APP_NAME)
        # 최소 너비 = 화면 절반, 최대는 제한 없음(전체 화면 가능)
        screen = QGuiApplication.primaryScreen()
        min_width = (screen.availableGeometry().width() // 2
                     if screen else 840)
        self.setMinimumSize(min_width, 640)
        self.resize(max(960, min_width), 780)

        self.conn = database.connect()
        database.init_db(self.conn)
        self.diary_repo = DiaryRepo(self.conn)
        self.emotion_repo = EmotionRepo(self.conn)
        self.tag_repo = TagRepo(self.conn)

        self._last_diary_view = "list"   # '적은 일기 보기'가 기억하는 뷰

        # 좌측 네비게이션 바 + 화면 스택
        central = QWidget()
        central_layout = QHBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        self.nav_bar = NavBar(self)
        central_layout.addWidget(self.nav_bar)
        self.stack = QStackedWidget()
        central_layout.addWidget(self.stack, stretch=1)
        self.setCentralWidget(central)

        self.home = HomeScreen(self)
        self.editor = EditorScreen(self)   # ctx = self (repo 속성 보유)
        self.diary_list = DiaryListScreen(self)
        self.diary_calendar = DiaryCalendarScreen(self)
        self.dictionary = DictionaryScreen(self)
        self.analysis = AnalysisScreen(self)
        for screen in (self.home, self.editor, self.diary_list,
                       self.diary_calendar, self.dictionary, self.analysis):
            self.stack.addWidget(screen)

        self.show_home()
        self._restore_theme()

        # 첫 실행이면 가이드를 자동으로 띄운다 (화면7 온보딩)
        QTimer.singleShot(400, self.maybe_show_first_run_guide)

    # ── 가이드 (화면7) ────────────────────────────────────────

    def show_guide(self):
        GuideDialog(self).exec()

    # ── 내보내기 (백업 · 공유용) ───────────────────────────────

    def show_export(self):
        ExportDialog(self).exec()

    # ── 테마 ─────────────────────────────────────────────────

    def apply_theme(self, name: str, remember: bool = True) -> None:
        """라이트/다크 전환.

        전역 QSS만 다시 깔면 클래스로 지정한 색은 따라오지만, 위젯에
        직접 써 넣은 색(정렬 버튼, 구분선 등)은 그대로 남는다. 그래서
        그런 색을 가진 화면에는 retheme()을 두고 여기서 불러 준다.
        """
        theme.set_theme(name)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_qss())
        for screen in (self.home, self.editor, self.diary_list,
                       self.diary_calendar, self.dictionary, self.analysis):
            retheme = getattr(screen, "retheme", None)
            if retheme is not None:
                retheme()
        self.nav_bar.retheme()
        if remember:
            database.set_meta(self.conn, "theme", name)

    def _restore_theme(self) -> None:
        """지난번에 고른 테마로 시작한다."""
        saved = database.get_meta(self.conn, "theme", theme.DEFAULT_THEME)
        if saved in theme.THEMES and saved != theme.current_theme:
            self.apply_theme(saved, remember=False)
        else:
            self.nav_bar.sync_theme_buttons()

    def maybe_show_first_run_guide(self):
        import sqlite3
        try:
            first_run = database.get_meta(self.conn, "guide_shown") != "1"
            if first_run:
                database.set_meta(self.conn, "guide_shown", "1")
        except sqlite3.ProgrammingError:
            return   # 타이머가 울리기 전에 창이 닫혀 DB가 정리된 경우
        if first_run:
            self.show_guide()
        # 바로가기는 가이드와 따로 묻는다. 같이 묶으면 이미 쓰고 있던
        # 사람은 가이드를 본 적이 있다는 이유로 영영 물어보지 못한다.
        self.maybe_offer_desktop_shortcut()

    def maybe_offer_desktop_shortcut(self):
        """첫 실행에 한 번, 바탕화면 바로가기를 만들지 묻는다.

        거절해도 사이드바의 '바탕화면 바로가기'로 언제든 만들 수 있다.
        """
        import sqlite3
        if not shortcut.is_supported() or shortcut.exists():
            return
        try:
            if database.get_meta(self.conn, "shortcut_asked") == "1":
                return
            database.set_meta(self.conn, "shortcut_asked", "1")
        except sqlite3.ProgrammingError:
            return
        if not confirm(
                self, "바탕화면 바로가기",
                "바탕화면에 감정일기 바로가기를 만들까요?\n\n"
                "폴더를 열지 않고 바로 실행할 수 있어요.\n"
                "나중에 왼쪽 메뉴에서도 만들 수 있습니다.",
                yes="만들기", no="아니요", default_yes=True):
            return
        self._create_shortcut()

    def make_desktop_shortcut(self):
        """사이드바의 '바탕화면 바로가기' 버튼."""
        if shortcut.exists() and not confirm(
                self, "바탕화면 바로가기",
                f"바탕화면에 이미 바로가기가 있어요.\n\n"
                f"{shortcut.shortcut_path()}\n\n다시 만들까요?",
                yes="다시 만들기", no="취소"):
            return
        self._create_shortcut()

    def _create_shortcut(self):
        try:
            path = shortcut.create()
        except shortcut.ShortcutError as error:
            QMessageBox.warning(self, "바탕화면 바로가기", str(error))
            return
        QMessageBox.information(
            self, "바탕화면 바로가기",
            f"바탕화면에 바로가기를 만들었어요.\n\n{path}")
        self.nav_bar.sync_shortcut_button()

    # ── 화면 전환 ─────────────────────────────────────────────

    def _show_nav(self, active_key):
        """네비게이션 바를 표시하고 현재 화면 항목을 강조한다."""
        self.nav_bar.set_active(active_key)
        self.nav_bar.setVisible(True)

    def show_home(self):
        self._show_nav("home")
        self.home.refresh()
        self.stack.setCurrentWidget(self.home)

    def show_list(self):
        self._last_diary_view = "list"
        self._show_nav("list")
        self.diary_list.refresh()
        self.stack.setCurrentWidget(self.diary_list)

    def show_calendar(self):
        self._last_diary_view = "calendar"
        self._show_nav("calendar")
        self.diary_calendar.refresh()
        self.stack.setCurrentWidget(self.diary_calendar)

    def show_dictionary(self, origin="home"):
        self._show_nav("dictionary")
        self.dictionary.origin = origin
        self.dictionary.refresh()
        self.stack.setCurrentWidget(self.dictionary)

    def return_to_editor(self):
        """작성 중이던 편집기로 복귀 — 내용을 유지하고, 새로 추가한
        단어가 바로 인식되도록 어휘만 다시 읽는다."""
        self._show_nav("editor" if self.editor.entry_id is None else None)
        self.editor.reload_vocab()
        self.stack.setCurrentWidget(self.editor)

    def show_analysis(self, origin="home"):
        self._show_nav("analysis")
        self.analysis.origin = origin
        self.analysis.refresh()
        self.stack.setCurrentWidget(self.analysis)

    def show_editor(self, entry_id=None, mode="write", origin="home",
                    preset_date=None):
        self._show_nav("editor" if entry_id is None else None)
        go_back = lambda: self.show_origin(origin)  # noqa: E731
        self.editor.on_back = go_back
        self.editor.on_saved = go_back
        self.editor.on_deleted = go_back
        self.editor.load(entry_id, mode, preset_date)
        self.stack.setCurrentWidget(self.editor)

    # ── 네비게이션 바 전용 동작 ────────────────────────────────

    def nav_new_diary(self):
        """'새 일기 작성' 항목: 작성/수정 중이던 내용이 있으면 그대로
        복귀해 잃지 않게 하고, 아니면 새 일기를 시작한다."""
        editor = self.editor
        if editor.mode == "write" and (editor.entry_id is not None
                                       or editor.has_content()):
            self.return_to_editor()
        else:
            self.show_editor(origin="home")

    def nav_show_diaries(self):
        """'적은 일기 보기' 항목: 마지막으로 보던 뷰로 연다."""
        (self.show_calendar if self._last_diary_view == "calendar"
         else self.show_list)()

    def show_origin(self, origin: str):
        """편집기에서 돌아갈 때: 진입했던 화면으로 복귀."""
        {"home": self.show_home,
         "list": self.show_list,
         "calendar": self.show_calendar}.get(origin, self.show_home)()

    def closeEvent(self, event):
        self.conn.close()
        super().closeEvent(event)
