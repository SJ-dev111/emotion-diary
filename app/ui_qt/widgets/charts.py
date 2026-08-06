"""분석 화면용 QPainter 차트 — 파이 차트, 기분 척도 게이지.

QtCharts(GPL)를 쓰지 않고 직접 그린다. 조각 사이 2px 카드색 간격,
마커에 2px 흰 테두리 등은 dataviz 가이드의 마크 규격을 따른다.
"""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget

from app import theme


class PieChart(QWidget):
    """(라벨, 값, 색) 목록을 받아 파이로 그린다. 범례는 화면 쪽에서 담당."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []          # (label, value, color_hex)
        self.setFixedSize(190, 190)

    def set_data(self, items) -> None:
        self._items = [it for it in items if it[1] > 0]
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height()) - 8
        rect = QRectF((self.width() - side) / 2,
                      (self.height() - side) / 2, side, side)

        total = sum(value for _l, value, _c in self._items)
        if total == 0:
            painter.setPen(QPen(QColor(theme.BORDER), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(rect)
            return

        start_angle = 90 * 16          # 12시 방향에서 시작, 시계 방향
        gap_pen = QPen(QColor(theme.CARD), 2)   # 조각 사이 2px 간격
        for _label, value, color in self._items:
            span = -value / total * 360 * 16
            painter.setPen(gap_pen)
            painter.setBrush(QColor(color))
            painter.drawPie(rect, int(start_angle), int(span))
            start_angle += span


class MoodGauge(QWidget):
    """-10(빨강) ~ 0(회색) ~ +10(초록) 그라데이션 + 평균 위치 보라 마커."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = None
        self.setMinimumHeight(78)   # 마커 위 점수 텍스트가 들어갈 여유 포함

    def set_value(self, value) -> None:
        """value: 평균 기분 척도(float) 또는 None(데이터 없음)."""
        self._value = value
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        margin = 16
        bar = QRectF(margin, 34, self.width() - 2 * margin, 12)

        gradient = QLinearGradient(bar.left(), 0, bar.right(), 0)
        gradient.setColorAt(0.0, QColor(theme.MOOD_NEG))
        gradient.setColorAt(0.5, QColor(theme.MOOD_NEU))
        gradient.setColorAt(1.0, QColor(theme.MOOD_POS))
        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawRoundedRect(bar, 6, 6)

        font = theme.qfont(8)
        painter.setFont(font)
        painter.setPen(QColor(theme.TEXT_SUB))
        text_y = int(bar.bottom()) + 16
        painter.drawText(int(bar.left()), text_y, "-10")
        painter.drawText(int(bar.center().x()) - 4, text_y, "0")
        painter.drawText(int(bar.right()) - 22, text_y, "+10")

        if self._value is not None:
            x = bar.left() + (self._value + 10) / 20 * bar.width()
            x = max(bar.left(), min(bar.right(), x))

            # 마커 바로 위에 평균 점수 숫자를 적는다
            value_font = theme.qfont(10, bold=True)
            painter.setFont(value_font)
            painter.setPen(QColor(theme.MOOD_MARKER))
            value_text = f"{self._value:+.1f}"
            text_width = painter.fontMetrics().horizontalAdvance(value_text)
            text_x = min(max(x - text_width / 2, 0),
                        self.width() - text_width)
            painter.drawText(QPointF(text_x, bar.top() - 10), value_text)

            painter.setBrush(QColor(theme.MOOD_MARKER))
            painter.setPen(QPen(QColor(theme.CARD), 2))   # 흰 테두리
            painter.drawEllipse(QPointF(x, bar.center().y()), 9, 9)
