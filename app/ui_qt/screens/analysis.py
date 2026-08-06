"""화면5 — 분석 (PySide6).

주간/월간/연간 기간 이동, 감정 카테고리 파이 차트, 최다 사용 감정 단어,
평균 기분 게이지(보라 마커), 문장형 요약, 기간 내 일기 개수.
"""
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout,
    QWidget)

from app import theme
from app.services import analysis
from app.ui_qt.widgets.charts import MoodGauge, PieChart
from app.ui_qt.widgets.common import QFrameCard, clear_layout, sub_label


def _kind(button, kind):
    button.setProperty("kind", kind)
    return button


class AnalysisScreen(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.unit = "월간"
        self.anchor = date.today()
        self.origin = "home"

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 14, 20, 16)

        top = QHBoxLayout()
        back = _kind(QPushButton("←"), "ghost")
        back.setFixedWidth(40)
        back.clicked.connect(lambda: self.app.show_origin(self.origin))
        top.addWidget(back)
        title = QLabel("분석")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        top.addWidget(title)
        top.addStretch()
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["주간", "월간", "연간"])
        self.unit_combo.setCurrentText(self.unit)
        self.unit_combo.setFixedWidth(140)   # 원형 화살표 버튼 자리 포함
        self.unit_combo.setMinimumHeight(40)
        # setFont()은 전역 QSS의 font-size에 밀려 적용되지 않아 QSS로 지정
        self.unit_combo.setStyleSheet("font-size: 15px;")
        self.unit_combo.currentTextChanged.connect(self._on_unit_change)
        top.addWidget(self.unit_combo)
        root.addLayout(top)

        period = QHBoxLayout()
        period.addStretch()
        prev_button = _kind(QPushButton("◀"), "ghost")
        prev_button.setFixedWidth(40)
        prev_button.clicked.connect(lambda: self._move(-1))
        period.addWidget(prev_button)
        self.period_label = QLabel("")
        self.period_label.setStyleSheet("font-size: 17px; font-weight: bold;")
        self.period_label.setAlignment(Qt.AlignCenter)
        self.period_label.setMinimumWidth(190)
        period.addWidget(self.period_label)
        next_button = _kind(QPushButton("▶"), "ghost")
        next_button.setFixedWidth(40)
        next_button.clicked.connect(lambda: self._move(1))
        period.addWidget(next_button)
        period.addStretch()
        root.addLayout(period)

        # 본문 카드들 (스크롤)
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(2, 4, 10, 4)
        body.setSpacing(12)

        # 카드1: 감정 카테고리 파이 차트
        emotion_card = QFrameCard()
        emotion_layout = QVBoxLayout(emotion_card)
        emotion_layout.setContentsMargins(18, 14, 18, 14)
        header1 = QLabel("이런 감정들을 많이 느꼈어요")
        header1.setStyleSheet("font-weight: bold; font-size: 15px;")
        emotion_layout.addWidget(header1)
        chart_row = QHBoxLayout()
        self.pie = PieChart()
        chart_row.addWidget(self.pie)
        self.legend_layout = QVBoxLayout()
        self.legend_layout.setSpacing(4)
        legend_wrap = QVBoxLayout()
        legend_wrap.addStretch()
        legend_wrap.addLayout(self.legend_layout)
        legend_wrap.addStretch()
        chart_row.addLayout(legend_wrap)
        chart_row.addStretch()
        emotion_layout.addLayout(chart_row)
        # 이 카드의 결론에 해당하는 문장이라 눈에 먼저 들어와야 한다
        self.top_words_label = QLabel("")
        self.top_words_label.setStyleSheet(
            f"color: {theme.PRIMARY}; font-size: 15px; font-weight: bold;"
            " margin-top: 6px;")
        self.top_words_label.setWordWrap(True)
        emotion_layout.addWidget(self.top_words_label)
        body.addWidget(emotion_card)

        # 카드2: 평균 기분 게이지 + 요약 문장
        mood_card = QFrameCard()
        mood_layout = QVBoxLayout(mood_card)
        mood_layout.setContentsMargins(18, 14, 18, 14)
        header2 = QLabel("기간 평균 기분")
        header2.setStyleSheet("font-weight: bold; font-size: 15px;")
        mood_layout.addWidget(header2)
        self.gauge = MoodGauge()
        mood_layout.addWidget(self.gauge)
        self.avg_label = QLabel("")
        mood_layout.addWidget(self.avg_label)
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("font-size: 14px;")
        self.summary_label.setWordWrap(True)
        mood_layout.addWidget(self.summary_label)
        body.addWidget(mood_card)

        # 카드3: 작성 개수
        count_card = QFrameCard()
        count_layout = QVBoxLayout(count_card)
        count_layout.setContentsMargins(18, 14, 18, 14)
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("font-weight: bold; font-size: 15px;")
        count_layout.addWidget(self.count_label)
        body.addWidget(count_card)
        body.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

    # ── 동작 ─────────────────────────────────────────────────

    def _on_unit_change(self, unit):
        self.unit = unit
        self.anchor = date.today()
        self.refresh()

    def _move(self, delta):
        self.anchor = analysis.shift_anchor(self.unit, self.anchor, delta)
        self.refresh()

    def retheme(self):
        self.top_words_label.setStyleSheet(
            f"color: {theme.PRIMARY}; font-size: 15px; font-weight: bold;"
            " margin-top: 6px;")
        self.refresh()

    # ── 갱신 ─────────────────────────────────────────────────

    def refresh(self):
        start, end, label = analysis.period_range(self.unit, self.anchor)
        self.period_label.setText(label)

        count = self.app.diary_repo.count_between(start, end)
        category_counts = self.app.tag_repo.category_counts(start, end)
        top_words = self.app.tag_repo.top_words(start, end, limit=3)
        average = self.app.diary_repo.avg_mood_between(start, end)
        positive, neutral, negative = self.app.diary_repo.mood_sign_counts(
            start, end)

        # 파이 차트 + 범례 (색은 카테고리에 고정 매핑)
        ordered = sorted(category_counts.items(),
                         key=lambda kv: kv[1], reverse=True)
        items = [(name, value, theme.category_color(name, i))
                 for i, (name, value) in enumerate(ordered)]
        self.pie.set_data(items)
        clear_layout(self.legend_layout)
        if items:
            for name, value, color in items:
                row = QHBoxLayout()
                chip = QLabel()
                chip.setFixedSize(12, 12)
                chip.setStyleSheet(
                    f"background-color: {color}; border-radius: 3px;")
                row.addWidget(chip)
                row.addWidget(QLabel(f"{name} · {value}회"))
                row.addStretch()
                self.legend_layout.addLayout(row)
        else:
            self.legend_layout.addWidget(
                sub_label("이 기간에 인식된 감정 단어가 없어요.", 13))

        if top_words:
            words = ", ".join(f"'{row['word']}'" for row in top_words)
            # 마지막 단어의 받침 유무로 조사(을/를)를 고른다
            code = ord(top_words[-1]["word"][-1]) - 0xAC00
            josa = "을" if 0 <= code < 11172 and code % 28 else "를"
            self.top_words_label.setText(
                f"{words}{josa} 가장 많이 사용했어요.")
        else:
            self.top_words_label.setText("")

        # 평균 기분
        self.gauge.set_value(average)
        if average is None:
            self.avg_label.setText("표시할 기분 기록이 없어요.")
        else:
            self.avg_label.setText(f"평균 {average:+.1f}")
        self.summary_label.setText(
            analysis.mood_summary_sentence(positive, neutral, negative))

        self.count_label.setText(
            f"이 기간 동안 {count}개의 감정일기를 적었어요!")
