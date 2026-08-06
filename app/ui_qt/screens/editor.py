"""화면2·3 — 일기 작성/상세보기 (PySide6).

하나의 컴포넌트에서 쓰기/보기 모드를 분기한다. 저장 시 감정 인식기로
entry_emotion_tags를 갱신한다 (4단계 연동 지점).
"""
from datetime import date

from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QDateEdit, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QStackedWidget, QTextEdit,
    QVBoxLayout, QWidget)

from app import config, theme
from app.services import emotion_detector
from app.ui_qt.widgets.common import confirm
from app.ui_qt.widgets.emotion_highlighter import EmotionHighlighter
from app.ui_qt.widgets.month_calendar import MonthCalendar
from app.ui_qt.widgets.mood_slider import MoodSlider
from app.ui_qt.widgets.word_picker import WordPicker


def _kind(button: QPushButton, kind: str) -> QPushButton:
    button.setProperty("kind", kind)
    return button


class DateEdit(QDateEdit):
    """날짜 입력칸 — 누른 자리의 연/월/일을 통째로 선택한다.

    기본 동작은 누른 지점에 글자 커서를 놓는데, 커서가 구간 끝(2026|)에
    있으면 처음 누른 숫자가 먹히지 않고 다음 칸으로 넘어가 버린다.
    그래서 '2026'의 오른쪽을 눌러 1999를 치면 천의 자리가 2로 남았다.
    누를 때마다 그 구간을 통째로 선택해 두면 첫 숫자부터 덮어써진다.
    """

    def _select_current_section(self):
        """지금 커서가 놓인 구간을 통째로 선택한다."""
        self.setSelectedSection(self.currentSection())

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        # 누른 자리로 커서가 옮겨간 뒤에 선택해야 해서 한 틱 미룬다.
        # (여기서 바로 선택하면 이동 전 구간이 잡힌다)
        QTimer.singleShot(0, self._select_current_section)


class DiaryTextEdit(QTextEdit):
    """우클릭 시 기본 메뉴 대신 감정 단어 추천 팝업을 여는 입력칸."""

    def __init__(self, on_picker=None, parent=None):
        super().__init__(parent)
        self.on_picker = on_picker

    def contextMenuEvent(self, event):
        if self.isReadOnly() or self.on_picker is None:
            super().contextMenuEvent(event)
            return
        self.setTextCursor(self.cursorForPosition(event.pos()))
        self.on_picker(self)


class EditorScreen(QWidget):
    """mode: 'write'(새 일기·수정 중) / 'view'(읽기 전용)

    on_saved / on_deleted 콜백으로 화면 전환을 위임한다.
    콜백이 없으면(검증판) 저장 후 안내만 띄운다.
    """

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.on_back = None
        self.on_saved = None
        self.on_deleted = None
        self.entry_id = None
        self.mode = "write"
        self._favorite = False
        self._editable = True

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 12, 20, 16)
        self._build_top_bar(root)
        self._build_body(root)
        self._build_bottom_bar(root)

        # 감정 단어 실시간 하이라이트 (4개 입력칸 공용)
        self._highlighters = [
            EmotionHighlighter(box.document())
            for box in (self.event_box, self.emotion_box,
                        self.thought_box, self.free_box)]

        # Ctrl+Space → 감정 단어 자동완성 팝업
        shortcut = QShortcut(QKeySequence("Ctrl+Space"), self)
        shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        shortcut.activated.connect(self._open_picker)
        self._picker = None

    # ── 레이아웃 ──────────────────────────────────────────────

    def _build_top_bar(self, root):
        bar = QHBoxLayout()
        self.back_button = _kind(QPushButton("←"), "ghost")
        self.back_button.setFixedWidth(40)
        self.back_button.clicked.connect(self._go_back)
        bar.addWidget(self.back_button)
        bar.addStretch()

        self.star_button = _kind(QPushButton("☆"), "ghost")
        self.star_button.setFixedWidth(40)
        self.star_button.clicked.connect(self._toggle_favorite)
        bar.addWidget(self.star_button)
        root.addLayout(bar)

    def _build_body(self, root):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 12, 4)

        head = QHBoxLayout()
        self.title_edit = QLineEdit()
        self.title_edit.setObjectName("titleEntry")
        self.title_edit.setPlaceholderText("제목")
        self.title_edit.setMinimumHeight(44)
        head.addWidget(self.title_edit, stretch=1)

        self.date_edit = DateEdit()
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setCalendarPopup(True)   # 캘린더 팝업으로 날짜 선택
        # 캘린더로 고르는 것과 별개로 칸에 직접 입력할 수도 있다.
        # QDateEdit이 연/월/일 자리를 나눠 받으므로 형식이 깨질 일은 없고,
        # 범위를 벗어난 값은 아래 setDateRange가 막는다.
        # keyboardTracking은 기본값(켜짐) 그대로 둔다 — 끄면 타이핑한 값이
        # 화면에만 보이고 date()에는 반영되지 않아, 곧바로 저장할 때 옛
        # 날짜가 들어간다.
        # 직접 입력 범위는 캘린더의 연도 목록과 같게 맞춘다 — 목록에 없는
        # 연도를 타이핑으로만 넣을 수 있으면 둘이 어긋나 헷갈린다.
        self.date_edit.setDateRange(
            QDate(MonthCalendar._YEAR_MIN, 1, 1),
            QDate(MonthCalendar._YEAR_MAX, 12, 31))
        # 위/아래 스핀 버튼을 없앤다. QSS로 화살표를 감춰 놨을 뿐 자리는
        # 그대로 남아, 오른쪽 빈 곳(캘린더 버튼 왼편)을 누르면 숫자가
        # 하나씩 오르내렸다. 날짜는 캘린더나 직접 입력으로 정한다.
        self.date_edit.setButtonSymbols(QDateEdit.NoButtons)
        self.date_edit.setFixedWidth(190)
        self.date_edit.setMinimumHeight(42)
        # 연/월 드롭다운 형식이 같고 이번 달만 보이는 캘린더로 교체
        self._calendar = MonthCalendar()
        self.date_edit.setCalendarWidget(self._calendar)
        head.addWidget(self.date_edit)
        layout.addLayout(head)

        self.mood_slider = MoodSlider()
        layout.addWidget(self.mood_slider)

        self.picker_hint = QLabel("우클릭하면 감정 단어 추천을 볼 수 있어요.")
        self.picker_hint.setAlignment(Qt.AlignCenter)
        self._style_picker_hint()
        layout.addWidget(self.picker_hint)

        toggle = QHBoxLayout()
        toggle.addStretch()
        self.btn_template = _kind(QPushButton("템플릿 작성"), "segment")
        self.btn_free = _kind(QPushButton("자율 작성"), "segment")
        group = QButtonGroup(self)
        group.setExclusive(True)
        for index, button in enumerate((self.btn_template, self.btn_free)):
            button.setCheckable(True)
            group.addButton(button)
            toggle.addWidget(button)
            button.clicked.connect(
                lambda _c=False, i=index: self.stack.setCurrentIndex(i))
        self.btn_template.setChecked(True)
        layout.addLayout(toggle)

        self.stack = QStackedWidget()
        template_page = QWidget()
        template_layout = QVBoxLayout(template_page)
        template_layout.setContentsMargins(0, 0, 0, 0)
        self.event_box = self._labeled_box(template_layout, "사건")
        self.emotion_box = self._labeled_box(template_layout, "감정")
        self.thought_box = self._labeled_box(template_layout, "생각")
        self.stack.addWidget(template_page)

        free_page = QWidget()
        free_layout = QVBoxLayout(free_page)
        free_layout.setContentsMargins(0, 0, 0, 0)
        self.free_box = DiaryTextEdit(on_picker=self._open_picker_for)
        self.free_box.setMinimumHeight(380)
        free_layout.addWidget(self.free_box)
        self.stack.addWidget(free_page)
        layout.addWidget(self.stack)
        layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

    def _labeled_box(self, layout, label_text):
        label = QLabel(label_text)
        label.setProperty("kind", "section")
        layout.addWidget(label)
        box = DiaryTextEdit(on_picker=self._open_picker_for)
        box.setMinimumHeight(110)
        layout.addWidget(box)
        return box

    def _build_bottom_bar(self, root):
        bar = QHBoxLayout()
        bar.addStretch()
        self.edit_button = QPushButton("수정")
        self.edit_button.clicked.connect(self._start_edit)
        self.delete_button = _kind(QPushButton("삭제"), "danger")
        self.delete_button.clicked.connect(self._delete)
        self.cancel_edit_button = _kind(QPushButton("수정 취소"), "flat")
        self.cancel_edit_button.clicked.connect(self._cancel_edit)
        self.save_button = QPushButton("작성완료")
        self.save_button.setMinimumWidth(140)
        self.save_button.clicked.connect(self._save)
        bar.addWidget(self.edit_button)
        bar.addWidget(self.delete_button)
        bar.addWidget(self.cancel_edit_button)
        bar.addWidget(self.save_button)
        root.addLayout(bar)

    # ── 모드·데이터 로드 ──────────────────────────────────────

    def reload_vocab(self):
        """단어집이 바뀌었을 수 있으니 하이라이트용 어휘를 새로 읽는다."""
        vocab = self.ctx.emotion_repo.all_for_matching()
        for highlighter in self._highlighters:
            highlighter.set_vocab(vocab)

    def _open_picker(self):
        """Ctrl+Space: 포커스된 입력칸(없으면 모드 기본 칸)에 추천 팝업."""
        boxes = (self.event_box, self.emotion_box,
                 self.thought_box, self.free_box)
        focused = QApplication.focusWidget()
        if focused in boxes:
            box = focused
        else:
            box = (self.free_box if self.btn_free.isChecked()
                   else self.emotion_box)
        self._open_picker_for(box)

    def _open_picker_for(self, box):
        """우클릭·Ctrl+Space 공용: 해당 입력칸에 추천 팝업을 띄운다."""
        if box.isReadOnly():
            return
        if self._picker is not None and self._picker.isVisible():
            self._picker.close()
        box.setFocus()
        self._picker = WordPicker(box, self.ctx)
        self._picker.show_and_focus()

    def load(self, entry_id=None, mode="write", preset_date=None):
        self.entry_id = entry_id
        self.mode = mode
        self.reload_vocab()

        self.title_edit.clear()
        for box in (self.event_box, self.emotion_box,
                    self.thought_box, self.free_box):
            box.clear()

        if entry_id is None:
            date_text = preset_date or date.today().isoformat()
            self.date_edit.setDate(QDate.fromString(date_text, "yyyy-MM-dd"))
            self.btn_template.setChecked(True)
            self.stack.setCurrentIndex(0)
            self.mood_slider.set(0)
            self._set_favorite_view(False)
        else:
            row = self.ctx.diary_repo.get(entry_id)
            self.title_edit.setText(row["title"])
            self.date_edit.setDate(
                QDate.fromString(row["date"], "yyyy-MM-dd"))
            self.mood_slider.set(row["mood_scale"])
            is_template = row["mode"] == config.MODE_TEMPLATE
            (self.btn_template if is_template
             else self.btn_free).setChecked(True)
            self.stack.setCurrentIndex(0 if is_template else 1)
            self.event_box.setPlainText(row["event_text"])
            self.emotion_box.setPlainText(row["emotion_text"])
            self.thought_box.setPlainText(row["thought_text"])
            self.free_box.setPlainText(row["free_text"])
            self._set_favorite_view(bool(row["is_favorite"]))

        view = mode == "view"
        self._set_editable(not view)
        self.save_button.setText("작성완료")
        self.save_button.setVisible(not view)
        self.edit_button.setVisible(view)
        self.delete_button.setVisible(view)       # 삭제는 열람 중에만
        self.cancel_edit_button.setVisible(False)  # 수정 중에만 표시
        if not view:
            self.title_edit.setFocus()

    def _set_editable(self, editable: bool):
        self._editable = editable
        self.title_edit.setReadOnly(not editable)
        self.date_edit.setEnabled(editable)
        self.mood_slider.set_enabled(editable)
        self.btn_template.setEnabled(editable)
        self.btn_free.setEnabled(editable)
        for box in (self.event_box, self.emotion_box,
                    self.thought_box, self.free_box):
            box.setReadOnly(not editable)

    # ── 즐겨찾기 ──────────────────────────────────────────────

    def _set_favorite_view(self, flag: bool):
        self._favorite = flag
        color = theme.STAR_ON if flag else theme.STAR_OFF
        self.star_button.setText("★" if flag else "☆")
        self.star_button.setStyleSheet(
            f"color: {color}; font-size: 20px; padding: 0px;"
            " background: transparent; border: none;")

    def _toggle_favorite(self):
        self._set_favorite_view(not self._favorite)
        if self.entry_id is not None:   # 열람 중에도 즉시 저장
            self.ctx.diary_repo.set_favorite(self.entry_id, self._favorite)

    # ── 저장·수정·삭제 ────────────────────────────────────────

    def _start_edit(self):
        self.mode = "write"
        self._set_editable(True)
        self.save_button.setText("수정 완료")
        self.save_button.setVisible(True)
        self.edit_button.setVisible(False)
        self.delete_button.setVisible(False)
        self.cancel_edit_button.setVisible(True)   # 수정 취소로 열람 복귀

    def _cancel_edit(self):
        """수정을 취소하고 저장된 내용 그대로 열람 모드로 되돌아간다."""
        self.load(self.entry_id, mode="view")

    def _save(self):
        # 날짜를 타이핑하던 중이라면 그 값을 먼저 확정한다. 그러지 않으면
        # 화면에 보이는 날짜와 저장되는 날짜가 어긋날 수 있다.
        self.date_edit.interpretText()
        template_selected = self.btn_template.isChecked()
        fields = dict(
            date=self.date_edit.date().toString("yyyy-MM-dd"),
            title=self.title_edit.text().strip(),
            mood_scale=self.mood_slider.get(),
            mode=(config.MODE_TEMPLATE if template_selected
                  else config.MODE_FREE),
            event_text=self.event_box.toPlainText(),
            emotion_text=self.emotion_box.toPlainText(),
            thought_text=self.thought_box.toPlainText(),
            free_text=self.free_box.toPlainText(),
            is_favorite=self._favorite,
        )
        if self.entry_id is None:
            self.entry_id = self.ctx.diary_repo.create(**fields)
        else:
            self.ctx.diary_repo.update(self.entry_id, **fields)

        # 감정 단어 태그 갱신 (활성 작성 모드의 텍스트만 집계)
        if template_selected:
            detect_text = "\n".join([fields["event_text"],
                                     fields["emotion_text"],
                                     fields["thought_text"]])
        else:
            detect_text = fields["free_text"]
        vocab = self.ctx.emotion_repo.all_for_matching()
        self.ctx.tag_repo.replace_tags(
            self.entry_id, emotion_detector.count_tags(detect_text, vocab))

        # 저장이 끝났으니 '작성 중' 상태를 해제한다 —
        # 네비게이션의 '새 일기 작성'이 이 일기로 되돌아오지 않도록
        self.mode = "view"

        if self.on_saved:
            self.on_saved()
        else:
            QMessageBox.information(self, "저장 완료", "일기가 저장되었어요.")
            self.load()

    def _delete(self):
        if not confirm(
                self, "삭제 확인",
                "이 일기를 삭제할까요?\n삭제한 일기는 되돌릴 수 없어요.",
                yes="삭제", no="취소"):
            return
        self.ctx.diary_repo.delete(self.entry_id)
        if self.on_deleted:
            self.on_deleted()
        else:
            self.load()

    def _go_back(self):
        if self.on_back:
            self.on_back()

    def _style_picker_hint(self):
        self.picker_hint.setStyleSheet(
            f"color: {theme.PRIMARY}; font-size: 14px; font-weight: bold;")

    def retheme(self):
        """테마 전환 — 색을 직접 써 넣은 안내 문구와 감정 단어 하이라이트를
        다시 칠한다."""
        self._style_picker_hint()
        self._calendar.retheme()
        for highlighter in self._highlighters:
            highlighter.rehighlight()

    def has_content(self):
        """작성 중인 내용이 하나라도 있는지 — 네비게이션 이동 시
        새 일기를 새로 시작할지, 쓰던 내용으로 복귀할지 판단에 쓴다."""
        return bool(self.title_edit.text().strip()
                    or self.event_box.toPlainText().strip()
                    or self.emotion_box.toPlainText().strip()
                    or self.thought_box.toPlainText().strip()
                    or self.free_box.toPlainText().strip())
