"""화면6 — 감정 단어집 (PySide6).

왼쪽 카테고리 목록(추가/이름변경/삭제), 오른쪽 단어 목록(추가/편집/선택 삭제).
단어 추가 시 인식용 어간(stems)은 규칙 엔진이 자동 생성하고, 고급 사용자는
직접 수정할 수 있다.
"""
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QListWidget, QMessageBox, QPushButton, QScrollArea,
    QVBoxLayout, QWidget)

from app import theme
from app.services import conjugator
from app.ui_qt.widgets.common import (
    ClickFrame, clear_layout, confirm, sub_label)


def _kind(button, kind):
    button.setProperty("kind", kind)
    return button


class DictionaryScreen(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 14, 20, 16)

        self.origin = "home"
        self.select_mode = False      # 단어 선택 삭제 모드 (체크박스 표시)
        self._word_checks = []        # (QCheckBox, word_id)

        top = QHBoxLayout()
        back = _kind(QPushButton("←"), "ghost")
        back.setFixedWidth(40)
        back.clicked.connect(self._go_back)
        top.addWidget(back)
        title = QLabel("감정 단어집")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        top.addWidget(title)
        top.addStretch()
        self.add_word_button = QPushButton("＋ 단어 추가")
        self.add_word_button.clicked.connect(self._add_word)
        top.addWidget(self.add_word_button)
        self.select_button = _kind(QPushButton("선택 삭제"), "flatDanger")
        self.select_button.clicked.connect(self._delete_selected)
        top.addWidget(self.select_button)
        self.cancel_select_button = _kind(QPushButton("취소"), "flat")
        self.cancel_select_button.clicked.connect(
            lambda: self._set_select_mode(False))
        self.cancel_select_button.setVisible(False)   # 선택 모드에서만 표시
        top.addWidget(self.cancel_select_button)
        root.addLayout(top)

        body = QHBoxLayout()
        body.setSpacing(14)
        root.addLayout(body, stretch=1)

        # 왼쪽: 카테고리
        left = QVBoxLayout()
        left_title = sub_label("카테고리", 13)
        left.addWidget(left_title)
        self.cat_list = QListWidget()
        self.cat_list.setFixedWidth(180)
        self.cat_list.currentRowChanged.connect(self._on_category_changed)
        left.addWidget(self.cat_list, stretch=1)

        # 카테고리 관리 메뉴 — 하나의 테두리 안에 붙여서 카테고리 목록에
        # 속한 동작이라는 것이 한눈에 보이게 한다 (메뉴/컨텍스트 메뉴 느낌)
        left.addWidget(sub_label("카테고리 관리", 11))
        manage_frame = QFrame()
        manage_frame.setProperty("kind", "card")
        manage_layout = QVBoxLayout(manage_frame)
        manage_layout.setContentsMargins(0, 0, 0, 0)
        manage_layout.setSpacing(0)
        items = [
            ("＋ 카테고리 추가", self._add_category, False),
            ("카테고리 이름 변경", self._rename_category, False),
            ("카테고리 삭제", self._delete_category, True),
        ]
        self._manage_buttons = []   # (버튼, top, bottom, danger)
        self._dividers = []
        for i, (text, handler, danger) in enumerate(items):
            top_edge, bottom_edge = (i == 0), (i == len(items) - 1)
            button = self._menu_button(text, handler, top=top_edge,
                                       bottom=bottom_edge, danger=danger)
            self._manage_buttons.append((button, top_edge, bottom_edge,
                                         danger))
            manage_layout.addWidget(button)
            if i < len(items) - 1:
                divider = QFrame()
                divider.setFixedHeight(1)
                self._dividers.append(divider)
                manage_layout.addWidget(divider)
        self._style_dividers()
        left.addWidget(manage_frame)
        body.addLayout(left)

        # 오른쪽: 단어 목록 — 흰색 행이 배경 위에서 또렷하도록 카드 래퍼 없이
        self.words_layout = QVBoxLayout()
        self.words_layout.setSpacing(6)
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.addLayout(self.words_layout)   # 세로 여백은 렌더링 때 넣는다
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        body.addWidget(scroll, stretch=1)

    def _style_dividers(self):
        for divider in self._dividers:
            divider.setStyleSheet(
                f"background-color: {theme.BORDER}; border: none;")

    def retheme(self):
        """테마 전환 — 색을 직접 써 넣은 관리 메뉴와 구분선을 다시 칠한다."""
        for button, top, bottom, danger in self._manage_buttons:
            self._style_menu_button(button, top, bottom, danger)
        self._style_dividers()
        self._paint_categories()
        self.refresh()

    def _menu_button(self, text, handler, top=False, bottom=False,
                     danger=False):
        """카테고리 관리 카드 안의 메뉴형 버튼 (모서리는 카드 위치에 맞춘다)."""
        button = QPushButton(text)
        self._style_menu_button(button, top, bottom, danger)
        button.clicked.connect(handler)
        return button

    def _style_menu_button(self, button, top=False, bottom=False,
                           danger=False):
        top_radius = 12 if top else 0
        bottom_radius = 12 if bottom else 0
        color = theme.DANGER if danger else theme.TEXT
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {color};
                border: none;
                border-top-left-radius: {top_radius}px;
                border-top-right-radius: {top_radius}px;
                border-bottom-left-radius: {bottom_radius}px;
                border-bottom-right-radius: {bottom_radius}px;
                padding: 10px 14px;
                text-align: left;
                font-weight: normal;
            }}
            QPushButton:hover {{ background-color: {theme.BORDER}; }}
        """)

    def _go_back(self):
        if self.origin == "editor":
            # 작성 중이던 편집기로 복귀 (내용 유지 + 새 단어 즉시 인식)
            self.app.return_to_editor()
        else:
            self.app.show_home()

    # ── 갱신 ─────────────────────────────────────────────────

    def refresh(self):
        keep = self._current_category()
        names = [row["name"] for row in self.app.emotion_repo.categories()]
        self.cat_list.blockSignals(True)
        self.cat_list.clear()
        self.cat_list.addItems(names)
        row = names.index(keep) if keep in names else 0
        if names:
            self.cat_list.setCurrentRow(row)
        self.cat_list.blockSignals(False)
        self._paint_categories()
        self._render_words()

    def _on_category_changed(self, _row):
        self._paint_categories()
        self._render_words()

    def _paint_categories(self):
        """선택된 카테고리를 그 카테고리의 감정 단어 색으로 칠한다.

        일기 작성 화면에서 단어에 씌우는 색과 같아, 어느 카테고리를 보고
        있는지 색만으로도 알 수 있다. 글자색은 배경 밝기에 따라 흰색과
        검정 중 대비가 큰 쪽을 쓴다.

        항목별 배경(setBackground)은 전역 QSS의 ::item:selected 규칙에
        가려 화면에 나오지 않는다. 위젯 자신의 스타일시트는 전역보다
        우선하므로, 선택된 색을 여기에 직접 써 넣는다.
        """
        # 목록을 감싸는 상자 테두리는 없앤다 — 카테고리 색 자체가 경계를
        # 만들어 주므로 테두리까지 두르면 답답해 보인다.
        base = ("QListWidget { border: none; background: transparent; }")
        item = self.cat_list.currentItem()
        if item is None:
            self.cat_list.setStyleSheet(base)
            return
        background = theme.category_chip(item.text())
        self.cat_list.setStyleSheet(
            base
            + "QListWidget::item:selected {"
            f" background-color: {background};"
            f" color: {theme.on_color(background)};"
            " font-weight: bold; }")

    def _current_category(self):
        item = self.cat_list.currentItem()
        return item.text() if item else None

    def _render_words(self):
        clear_layout(self.words_layout)
        self._word_checks = []
        category = self._current_category()
        rows = self.app.emotion_repo.words(category) if category else []
        if not rows:
            # 빈 카테고리 안내는 목록 영역 정중앙(가로·세로 모두)에 표시
            self.words_layout.addStretch()
            empty = sub_label(
                "이 카테고리에 단어가 없어요. '＋ 단어 추가'로 등록해 보세요.", 13)
            empty.setAlignment(Qt.AlignCenter)
            self.words_layout.addWidget(empty)
            self.words_layout.addStretch()
            return
        for row in rows:
            self.words_layout.addWidget(self._word_row(row))
        self.words_layout.addStretch()

    def _word_row(self, row):
        frame = ClickFrame("row")   # 흰색 행 — 배경과 구분
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 4, 6, 4)

        check = None
        if self.select_mode:   # 체크박스는 선택 삭제 모드에서만 표시
            check = QCheckBox()
            layout.addWidget(check)
            self._word_checks.append((check, row["id"]))

        text_col = QVBoxLayout()
        word_label = QLabel(row["word"])
        word_label.setStyleSheet("font-weight: bold;")
        text_col.addWidget(word_label)
        if row["meaning"]:
            meaning = sub_label(row["meaning"])
            meaning.setWordWrap(True)
            text_col.addWidget(meaning)
        layout.addLayout(text_col, stretch=1)

        edit = _kind(QPushButton("수정"), "flat")
        edit.setProperty("compact", "true")
        edit.setFixedWidth(56)
        edit.clicked.connect(lambda _c=False, r=row: self._edit_word(r))
        layout.addWidget(edit)

        if self.select_mode:
            # 선택 모드에서는 행 클릭이 체크 토글로 동작
            frame.clicked.connect(
                lambda c=check: c.setChecked(not c.isChecked()))
        else:
            frame.setCursor(Qt.ArrowCursor)   # 평소에는 행 클릭 동작 없음
        return frame

    # ── 단어 ─────────────────────────────────────────────────

    def _add_word(self):
        dialog = WordDialog(self, self.app, category=self._current_category())
        dialog.exec()
        self.refresh()   # 취소해도 팝업 안에서 카테고리를 추가했을 수 있다

    def _edit_word(self, row):
        dialog = WordDialog(self, self.app,
                            category=row["category"], word_row=row)
        dialog.exec()
        self.refresh()

    def _delete_selected(self):
        """1번 누르면 선택 모드 진입(체크박스 표시), 선택 후 다시 누르면
        확인 팝업 → 삭제. 아무것도 선택하지 않고 다시 누르면 모드 해제."""
        if not self.select_mode:
            self._set_select_mode(True)
            return
        ids = [word_id for check, word_id in self._word_checks
               if check.isChecked()]
        if not ids:
            self._set_select_mode(False)   # 취소로 간주
            return
        if not confirm(
                self, "단어 삭제",
                f"선택한 단어 {len(ids)}개를 단어집에서 삭제할까요?\n"
                "(이미 작성한 일기의 분석 기록은 유지됩니다)",
                yes="삭제", no="취소"):
            return
        for word_id in ids:
            self.app.emotion_repo.delete_word(word_id)
        self._set_select_mode(False)

    def _set_select_mode(self, active: bool):
        self.select_mode = active
        self.cancel_select_button.setVisible(active)
        # 선택 삭제 중에는 단어 추가 기능을 잠시 숨긴다
        self.add_word_button.setVisible(not active)
        if active:
            self.select_button.setStyleSheet(
                f"background-color: {theme.DANGER}; color: white;"
                " border: none; border-radius: 8px; padding: 9px 16px;"
                " font-weight: bold;")
        else:
            self.select_button.setStyleSheet("")   # QSS flatDanger로 복귀
        self._render_words()

    # ── 카테고리 ──────────────────────────────────────────────

    def _add_category(self):
        name, ok = QInputDialog.getText(self, "카테고리 추가", "새 카테고리 이름:")
        name = (name or "").strip()
        if not ok or not name:
            return
        try:
            self.app.emotion_repo.add_category(name)
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "카테고리 추가", "이미 있는 카테고리예요.")
            return
        self.refresh()
        self.cat_list.setCurrentRow(self.cat_list.count() - 1)

    def _rename_category(self):
        current = self._current_category()
        if not current:
            return
        name, ok = QInputDialog.getText(
            self, "카테고리 이름 변경", "새 이름:", text=current)
        name = (name or "").strip()
        if not ok or not name or name == current:
            return
        try:
            self.app.emotion_repo.rename_category(current, name)
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "이름 변경", "이미 있는 카테고리 이름이에요.")
            return
        self.refresh()

    def _delete_category(self):
        current = self._current_category()
        if not current:
            return
        count = len(self.app.emotion_repo.words(current))
        if not confirm(
                self, "카테고리 삭제",
                f"'{current}' 카테고리와 소속 단어 {count}개를 모두"
                " 삭제할까요?\n삭제한 단어는 되돌릴 수 없어요.\n"
                "(이미 작성한 일기의 분석 기록은 유지됩니다)",
                yes="삭제", no="취소"):
            return
        self.app.emotion_repo.delete_category(current)
        self.refresh()


class WordDialog(QDialog):
    """단어 추가/편집 대화상자. 어간(stems)은 비워두면 자동 생성.

    카테고리 드롭다운 맨 아래의 '＋ 새 카테고리 추가'를 고르면 이름 입력
    팝업이 뜨고, 추가한 카테고리가 드롭다운에 바로 선택된 채 반영된다.
    """

    ADD_CATEGORY_LABEL = "＋ 새 카테고리 추가"

    def __init__(self, parent, app, category=None, word_row=None):
        super().__init__(parent)
        self.app = app
        self.word_row = word_row
        self.setWindowTitle("단어 편집" if word_row else "단어 추가")
        self.setFixedWidth(380)
        self._stems_touched = word_row is not None

        layout = QVBoxLayout(self)

        layout.addWidget(sub_label("카테고리", 12))
        self.category_combo = QComboBox()
        names = [row["name"] for row in app.emotion_repo.categories()]
        self.category_combo.addItems(names)
        self.category_combo.addItem(self.ADD_CATEGORY_LABEL)   # 항상 맨 아래
        target = word_row["category"] if word_row else category
        if target in names:
            self.category_combo.setCurrentText(target)
        self._prev_category = self.category_combo.currentText()
        self.category_combo.activated.connect(self._on_category_activated)
        layout.addWidget(self.category_combo)

        layout.addWidget(sub_label("단어 (기본형, 예: 서운하다)", 12))
        self.word_edit = QLineEdit(word_row["word"] if word_row else "")
        self.word_edit.textChanged.connect(self._on_word_changed)
        layout.addWidget(self.word_edit)

        layout.addWidget(sub_label("뜻 (선택)", 12))
        self.meaning_edit = QLineEdit(word_row["meaning"] if word_row else "")
        layout.addWidget(self.meaning_edit)

        layout.addWidget(sub_label("인식용 어간 — 쉼표로 구분, 비워두면 자동 생성", 12))
        self.stems_edit = QLineEdit(word_row["stems"] if word_row else "")
        self.stems_edit.textEdited.connect(
            lambda _t: setattr(self, "_stems_touched", True))
        layout.addWidget(self.stems_edit)
        hint = sub_label("특정 표현이 인식되지 않으면 여기에 어간을 추가하세요.", 11)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = _kind(QPushButton("취소"), "flat")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        save = QPushButton("저장")
        save.clicked.connect(self._save)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def _on_category_activated(self, index):
        text = self.category_combo.itemText(index)
        if text != self.ADD_CATEGORY_LABEL:
            self._prev_category = text
            return
        name, ok = QInputDialog.getText(self, "카테고리 추가", "새 카테고리 이름:")
        name = (name or "").strip()
        if not ok or not name:
            # 취소하면 이전에 고르던 카테고리로 되돌린다
            self.category_combo.setCurrentText(self._prev_category)
            return
        try:
            self.app.emotion_repo.add_category(name)
        except sqlite3.IntegrityError:
            pass   # 이미 있는 카테고리면 그 카테고리를 그대로 선택
        if self.category_combo.findText(name) < 0:
            # '＋ 새 카테고리 추가' 항목 바로 위(기존 목록 맨 아래)에 삽입
            self.category_combo.insertItem(
                self.category_combo.count() - 1, name)
        self.category_combo.setCurrentText(name)
        self._prev_category = name

    def _on_word_changed(self, text):
        if not self._stems_touched:
            word = text.strip()
            self.stems_edit.setText(
                ",".join(conjugator.generate_stems(word)) if word else "")

    def _save(self):
        word = self.word_edit.text().strip()
        if not word:
            QMessageBox.warning(self, "단어", "단어를 입력해 주세요.")
            return
        stems = self.stems_edit.text().strip()
        if not stems:
            stems = ",".join(conjugator.generate_stems(word))
        category = self.category_combo.currentText()
        meaning = self.meaning_edit.text().strip()
        try:
            if self.word_row:
                self.app.emotion_repo.update_word(
                    self.word_row["id"], category=category, word=word,
                    meaning=meaning, stems=stems)
            else:
                self.app.emotion_repo.add_word(category, word, meaning, stems)
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "단어", "이미 단어집에 있는 단어예요.")
            return
        self.accept()
