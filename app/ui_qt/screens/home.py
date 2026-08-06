"""화면1 — 홈 (PySide6). 최근 일기 미리보기 + 이번 주 분석 요약."""
from datetime import date

from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget)

from app.services import analysis
from app.ui_qt.widgets.charts import MoodGauge
from app.ui_qt.widgets.common import (
    ClickFrame, clear_layout, entry_title_label, mood_badge, star_button,
    sub_label, word_chip)


def _kind(button, kind):
    button.setProperty("kind", kind)
    return button


def _card_title(text):
    label = sub_label(text, size=15)
    label.setStyleSheet(label.styleSheet() + " font-weight: bold;")
    return label


class HomeScreen(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        header = QLabel("감정일기")
        header.setStyleSheet("font-size: 26px; font-weight: bold;")
        root.addWidget(header)

        # ── 최근 일기 카드 ────────────────────────────────────
        recent_card = QFrame()
        recent_card.setProperty("kind", "card")
        recent_body = QVBoxLayout(recent_card)
        recent_body.setContentsMargins(18, 14, 18, 14)

        recent_head = QHBoxLayout()
        recent_head.addWidget(_card_title("최근 일기"))
        recent_head.addStretch()
        new_button = QPushButton("새 일기 작성")
        new_button.clicked.connect(
            lambda: self.app.show_editor(origin="home"))
        recent_head.addWidget(new_button)
        list_button = _kind(QPushButton("적은 일기 보기"), "flat")
        list_button.clicked.connect(self.app.show_list)
        recent_head.addWidget(list_button)
        recent_body.addLayout(recent_head)

        self.recent_layout = QVBoxLayout()
        self.recent_layout.setSpacing(6)
        recent_body.addLayout(self.recent_layout)
        recent_body.addStretch()
        # 최근 일기 70% : 최근 분석 30% (유효 높이 비율)
        root.addWidget(recent_card, stretch=7)

        # ── 최근 분석(이번 주) 카드 ───────────────────────────
        weekly_card = QFrame()
        weekly_card.setProperty("kind", "card")
        weekly_body = QVBoxLayout(weekly_card)
        weekly_body.setContentsMargins(18, 14, 18, 14)

        weekly_head = QHBoxLayout()
        weekly_head.addWidget(_card_title("최근 분석 · 이번 주"))
        weekly_head.addStretch()
        analysis_button = _kind(QPushButton("분석 보기"), "flat")
        analysis_button.clicked.connect(
            lambda: self.app.show_analysis(origin="home"))
        weekly_head.addWidget(analysis_button)
        weekly_body.addLayout(weekly_head)

        self.weekly_layout = QVBoxLayout()
        self.weekly_layout.setSpacing(6)
        weekly_body.addLayout(self.weekly_layout)
        weekly_body.addStretch()
        root.addWidget(weekly_card, stretch=3)

    # ── 갱신 ─────────────────────────────────────────────────

    def retheme(self):
        self.refresh()   # 카드·행을 새로 만들면서 색이 따라온다

    def refresh(self):
        self._refresh_recent()
        self._refresh_weekly()

    def _refresh_recent(self):
        clear_layout(self.recent_layout)
        rows = self.app.diary_repo.recent(limit=5)
        if not rows:
            empty = sub_label(
                "아직 작성한 일기가 없어요.\n'새 일기 작성'으로 첫 일기를 써볼까요?", 14)
            empty.setWordWrap(True)
            self.recent_layout.addWidget(empty)
            return
        for row in rows:
            self.recent_layout.addWidget(self._recent_item(row))

    def _refresh_weekly(self):
        """이번 주(일요일 시작, 분석 화면과 동일 기준) 요약."""
        clear_layout(self.weekly_layout)
        start, end, label = analysis.period_range("주간", date.today())
        self.weekly_layout.addWidget(sub_label(label, 12))

        count = self.app.diary_repo.count_between(start, end)
        if count == 0:
            self.weekly_layout.addWidget(
                sub_label("이번 주에는 아직 적은 일기가 없어요.", 13))
            return

        average = self.app.diary_repo.avg_mood_between(start, end)
        self.weekly_layout.addWidget(QLabel(f"일기 {count}개 · 평균 기분"))
        gauge = MoodGauge()
        gauge.set_value(average)
        self.weekly_layout.addWidget(gauge)

        top = self.app.tag_repo.top_words(start, end, limit=3)
        if top:
            chips = QHBoxLayout()
            chips.setSpacing(6)
            chips.addWidget(sub_label("자주 쓴 감정 단어", 12))
            for row in top:
                chips.addWidget(word_chip(row["word"], row["category"]))
            chips.addStretch()
            self.weekly_layout.addLayout(chips)

    # ── 최근 일기 행 ──────────────────────────────────────────

    def _recent_item(self, row):
        item = ClickFrame("row")
        layout = QHBoxLayout(item)
        layout.setContentsMargins(12, 8, 8, 8)

        date_label = sub_label(row["date"])
        date_label.setFixedWidth(90)
        layout.addWidget(date_label)

        layout.addWidget(entry_title_label(row["title"] or "(제목 없음)"),
                         stretch=1)

        # 이 일기에서 가장 많이 쓰인 감정 단어 3개 (많이 쓰인 순)
        for tag in self.app.tag_repo.tags_for(row["id"])[:3]:
            layout.addWidget(word_chip(tag["word"], tag["category"]))

        layout.addWidget(mood_badge(row["mood_scale"]))

        favorite = bool(row["is_favorite"])
        star = star_button(favorite)
        star.clicked.connect(
            lambda _c=False, i=row["id"], f=favorite:
            self._toggle_favorite(i, not f))
        layout.addWidget(star)

        entry_id = row["id"]
        item.clicked.connect(
            lambda i=entry_id: self.app.show_editor(i, mode="view",
                                                    origin="home"))
        return item

    def _toggle_favorite(self, entry_id, flag):
        self.app.diary_repo.set_favorite(entry_id, flag)
        self.refresh()
