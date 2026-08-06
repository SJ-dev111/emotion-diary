"""감정 단어 자동완성 팝업 (화면2 — 우클릭 또는 Ctrl+Space).

탐색 흐름:
- 커서 앞에 쓰다 만 한글(시드)이 있으면 → 자모 어간 매칭으로 필터된
  단어 목록을 바로 보여준다 ("서러웠" → 서럽다).
- 시드가 없으면 → 카테고리 목록을 먼저 보여주고, 카테고리를 고르면
  그 안의 단어들을 보여준다 (감정 단어가 잘 안 떠오를 때의 탐색 경로).
- 단어를 고르면 활용형 목록에서 하나를 골라 커서에 삽입한다.
  삽입 시 시드(뒤 스페이스 하나 포함)를 대체한다.
"""
import re

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QLineEdit, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout,
    QWidget)

from app.services import conjugator, emotion_detector
from app.ui_qt.widgets.common import QFrameCard

_BACK_TO_WORDS = "← 단어 다시 선택"
_BACK_TO_CATEGORIES = "← 카테고리 다시 선택"
_SEED_PATTERN = re.compile(r"([가-힣]+)\s?$")


class WordPicker(QWidget):
    """Qt.Popup 대신 활성화되는 프레임 없는 창을 쓴다 — Popup 창은
    활성화되지 않아 한글 IME 조합이 아래 입력칸으로 새는 문제가 있다.
    바깥 클릭 등으로 비활성화되면 스스로 닫혀 팝업처럼 동작한다."""

    def __init__(self, textedit, ctx):
        super().__init__(textedit.window(),
                         Qt.Tool | Qt.FramelessWindowHint)
        self.box = textedit
        self.ctx = ctx
        self.stage = "categories"     # categories / words / forms
        self.category = None          # words 단계의 카테고리 범위
        self.setFixedSize(300, 340)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        frame = QFrameCard()
        outer.addWidget(frame)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("단어 검색")
        layout.addWidget(self.filter_edit)
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        # 새 단어/카테고리가 필요할 때 단어집 화면으로
        manage = QPushButton("단어집에서 추가·관리 →")
        manage.setProperty("kind", "flat")
        manage.setStyleSheet("font-size: 12px; padding: 5px;")
        manage.clicked.connect(self._open_dictionary)
        layout.addWidget(manage)

        self.filter_edit.installEventFilter(self)
        self.list_widget.itemActivated.connect(self._on_item)
        self.list_widget.itemClicked.connect(self._on_item)

        seed, _span = self._current_seed()
        self.filter_edit.setText(seed)   # textChanged 연결 전이라 조용히 세팅
        self.filter_edit.textChanged.connect(self._on_filter_changed)
        if seed:
            self._refill_words()         # 인식된 조각이 있으면 바로 추천
        else:
            self._show_categories()      # 없으면 카테고리부터 탐색

        rect = textedit.cursorRect()
        global_pos = textedit.viewport().mapToGlobal(rect.bottomLeft())
        self.move(global_pos.x(), global_pos.y() + 4)

    def show_and_focus(self) -> None:
        self.show()
        self.activateWindow()   # IME 입력이 팝업의 검색칸으로 향하도록
        self.raise_()
        self.filter_edit.setFocus()

    def event(self, e):
        # 바깥을 클릭해 창이 비활성화되면 팝업처럼 닫힌다
        if e.type() == QEvent.WindowDeactivate:
            self.close()
        return super().event(e)

    # ── 시드 ─────────────────────────────────────────────────

    def _current_seed(self) -> tuple[str, int]:
        """(필터용 시드, 대체할 문자 수). 시드 뒤 스페이스 하나까지 대체 범위."""
        cursor = self.box.textCursor()
        before = cursor.block().text()[:cursor.positionInBlock()]
        match = _SEED_PATTERN.search(before)
        if not match:
            return "", 0
        return match.group(1), len(match.group(0))

    # ── 목록 구성 ─────────────────────────────────────────────

    def _on_filter_changed(self, text: str) -> None:
        if text.strip():
            self.category = None      # 검색어가 있으면 전체에서 매칭
            self._refill_words()
        else:
            self._show_categories()

    def _show_categories(self) -> None:
        self.stage = "categories"
        self.category = None
        self.list_widget.clear()
        for row in self.ctx.emotion_repo.categories():
            count = len(self.ctx.emotion_repo.words(row["name"]))
            item = QListWidgetItem(f'{row["name"]}  ·  {count}개')
            item.setData(Qt.UserRole, ("category", row["name"]))
            self.list_widget.addItem(item)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)

    def _refill_words(self) -> None:
        self.stage = "words"
        self.list_widget.clear()
        query = self.filter_edit.text().strip()
        if self.category and not query:
            back = QListWidgetItem(_BACK_TO_CATEGORIES)
            back.setData(Qt.UserRole, ("categories", None))
            self.list_widget.addItem(back)
            rows = self.ctx.emotion_repo.words(self.category)
        else:
            rows = self.ctx.emotion_repo.words()
            if query:
                vocab = self.ctx.emotion_repo.all_for_matching()
                allowed = set(emotion_detector.match_words(query, vocab))
                rows = [r for r in rows
                        if query in r["word"] or r["word"] in allowed]
        for row in rows:
            self._add_word_item(row["word"], row["category"])

        if query and not rows:
            self._fill_no_match(query)
        self._select_first_actionable()

    def _add_word_item(self, word, category):
        item = QListWidgetItem(f"{word}  ·  {category}")
        item.setData(Qt.UserRole, ("word", word))
        self.list_widget.addItem(item)

    def _add_info_item(self, text):
        item = QListWidgetItem(text)
        item.setData(Qt.UserRole, ("noop", None))
        item.setFlags(Qt.NoItemFlags)   # 회색 안내 문구 (선택 불가)
        self.list_widget.addItem(item)

    def _fill_no_match(self, query):
        """단어집에서 아무것도 못 찾았을 때: 확장 어휘 사전으로 제안."""
        suggestion = emotion_detector.suggest_from_lexicon(query)
        if suggestion is None:
            self._add_info_item("추천할 단어가 없어요.")
            return
        word, category = suggestion
        self._add_info_item(f"'{word}' — '{category}' 계열 감정으로 보여요")
        add_item = QListWidgetItem(f"＋ 단어집({category})에 '{word}' 추가하기")
        add_item.setData(Qt.UserRole, ("addword", (word, category)))
        self.list_widget.addItem(add_item)
        self._add_info_item(f"─ '{category}' 카테고리의 단어들 ─")
        for row in self.ctx.emotion_repo.words(category):
            self._add_word_item(row["word"], row["category"])

    def _select_first_actionable(self):
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            kind = (item.data(Qt.UserRole) or ("noop",))[0]
            if kind in ("word", "addword", "category", "form"):
                self.list_widget.setCurrentRow(index)
                return
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)

    def _show_forms(self, word: str) -> None:
        self.stage = "forms"
        self.list_widget.clear()
        back = QListWidgetItem(_BACK_TO_WORDS)
        back.setData(Qt.UserRole, ("words", None))
        self.list_widget.addItem(back)
        for label, form in conjugator.forms(word):
            item = QListWidgetItem(f"{form}  ({label})")
            item.setData(Qt.UserRole, ("form", form))
            self.list_widget.addItem(item)
        self.list_widget.setCurrentRow(
            1 if self.list_widget.count() > 1 else 0)

    # ── 선택·삽입 ─────────────────────────────────────────────

    def _on_item(self, item: QListWidgetItem) -> None:
        kind, value = item.data(Qt.UserRole)
        if kind == "category":
            self.category = value
            self._refill_words()
        elif kind == "categories":
            self._show_categories()
        elif kind == "word":
            self._show_forms(value)
        elif kind == "words":
            if self.filter_edit.text().strip() or self.category:
                self._refill_words()
            else:
                self._show_categories()
        elif kind == "addword":
            self._add_unknown_word(*value)
        elif kind == "form":
            self._insert(value)
        # "noop"은 안내 문구 — 아무 동작 없음

    def _insert(self, form: str) -> None:
        cursor = self.box.textCursor()
        _seed, span = self._current_seed()
        if span:   # 쓰다 만 글자(+뒤 스페이스)를 선택한 형태로 대체
            cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor,
                                span)
        cursor.insertText(form)
        self.box.setTextCursor(cursor)
        self.close()
        self.box.setFocus()

    def _add_unknown_word(self, word: str, category: str) -> None:
        """확장 사전이 제안한 단어를 단어집 등록 대화상자로 넘긴다."""
        from app.ui_qt.screens.dictionary import WordDialog

        self.hide()
        dialog = WordDialog(self.box.window(), self.ctx, category=category)
        dialog.word_edit.setText(word)
        if dialog.exec():
            # 방금 등록한 단어가 바로 하이라이트·추천되도록
            self.ctx.editor.reload_vocab()
        self.close()
        self.box.setFocus()

    def _open_dictionary(self) -> None:
        self.close()
        self.ctx.show_dictionary(origin="editor")

    # ── 키보드 탐색 ───────────────────────────────────────────

    def eventFilter(self, obj, event):
        if obj is self.filter_edit and event.type() == QEvent.KeyPress:
            key = event.key()
            if key in (Qt.Key_Down, Qt.Key_Up):
                delta = 1 if key == Qt.Key_Down else -1
                row = self.list_widget.currentRow() + delta
                row = max(0, min(self.list_widget.count() - 1, row))
                self.list_widget.setCurrentRow(row)
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter):
                item = self.list_widget.currentItem()
                if item:
                    self._on_item(item)
                return True
            if key == Qt.Key_Escape:
                self.close()
                return True
        return super().eventFilter(obj, event)
