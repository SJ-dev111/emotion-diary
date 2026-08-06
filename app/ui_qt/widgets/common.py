"""화면들이 공용하는 소형 위젯·헬퍼."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QFrame, QLabel, QMessageBox, QPushButton, QSizePolicy)

from app import theme


def confirm(parent, title: str, text: str, yes: str = "예",
            no: str = "아니오", default_yes: bool = False) -> bool:
    """예/아니오 확인 창. 누른 것이 '예'면 True.

    QMessageBox.question()을 그대로 쓰면 버튼이 'Yes'/'No'로 나온다. Qt의
    표준 버튼 글자는 Qt 번역 파일에서 오는데 PySide6에는 한국어 번역이
    들어 있지 않다. 번역을 따로 구해다 동봉하느니, 쓰는 곳이 몇 곳뿐이라
    버튼 글자를 직접 넣는다. 지우는 동작이면 yes="삭제"처럼 무엇을 하는
    버튼인지 밝혀 주는 편이 낫다.
    """
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QMessageBox.Question)
    yes_button = box.addButton(yes, QMessageBox.YesRole)
    no_button = box.addButton(no, QMessageBox.NoRole)
    box.setDefaultButton(yes_button if default_yes else no_button)
    # Esc는 늘 '아니오'로 (되돌릴 수 없는 동작이 실수로 실행되지 않게)
    box.setEscapeButton(no_button)
    box.exec()
    return box.clickedButton() is yes_button


class QFrameCard(QFrame):
    """둥근 카드 프레임 (QSS kind=card)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("kind", "card")


class ClickFrame(QFrame):
    """클릭 가능한 카드/행 프레임."""

    clicked = Signal()

    def __init__(self, kind: str = "row", parent=None):
        super().__init__(parent)
        self.setProperty("kind", kind)
        self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        if (event.button() == Qt.LeftButton
                and self.rect().contains(event.position().toPoint())):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


def mood_badge(value: int) -> QLabel:
    """척도 점수를 색 배지로 표시.

    척도 색은 뜻이 있어 그대로 두고, 글자만 배경 밝기에 맞춘다. 흰색으로
    고정하면 중립(밝은 회색) 근처에서 숫자가 배경에 묻힌다.
    """
    background, text_color = theme.badge_colors(value)
    label = QLabel(theme.mood_text(value))
    label.setFixedSize(44, 26)
    label.setAlignment(Qt.AlignCenter)
    label.setStyleSheet(
        f"background-color: {background}; color: {text_color};"
        " border-radius: 6px; font-weight: bold; font-size: 13px;")
    return label


def style_star(button: QPushButton, favorite: bool) -> None:
    color = theme.STAR_ON if favorite else theme.STAR_OFF
    button.setText("★" if favorite else "☆")
    # padding 0 — 기본 버튼 패딩이 남아 있으면 별 글리프가 잘려 보인다
    button.setStyleSheet(
        f"color: {color}; font-size: 18px; padding: 0px;"
        " background: transparent; border: none;")


def star_button(favorite: bool) -> QPushButton:
    button = QPushButton()
    button.setFixedSize(32, 30)
    button.setCursor(Qt.PointingHandCursor)
    style_star(button, favorite)
    return button


def word_chip(word: str, category: str) -> QLabel:
    """감정 단어 칩 — 카테고리 색 배경의 작은 라벨.

    글자색을 테마 기본색으로 두면 다크에서 밝은 파스텔 위에 밝은 글자가
    얹혀 읽히지 않는다. 배경과 짝이 맞는 색을 theme에서 받아 쓴다.
    """
    label = QLabel(word)
    label.setStyleSheet(
        f"background-color: {theme.category_chip(category)};"
        f" color: {theme.category_chip_text(category)}; border-radius: 6px;"
        " padding: 2px 7px; font-size: 11px; font-weight: bold;")
    return label


def entry_title_label(text: str, size: int = 14) -> QLabel:
    """목록·카드에 쓰는 일기 제목 — 굵게 해서 날짜·감정 단어와 구분한다."""
    label = QLabel(text)
    label.setStyleSheet(f"font-weight: bold; font-size: {size}px;")
    return label


class ElidedLabel(QLabel):
    """폭이 모자라면 끝을 '…'로 줄이는 라벨.

    긴 글이 칸의 최소 너비를 밀어 올리지 않게 한다. 캘린더처럼 칸 폭이
    똑같이 나뉘어야 하는 곳에서 쓴다.
    """

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._full_text = text
        # Ignored: 내용이 요구하는 폭을 레이아웃 계산에서 빼 버린다
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(0)

    def setText(self, text: str) -> None:
        self._full_text = text
        self._update_elided()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_elided()

    def _update_elided(self) -> None:
        metrics = QFontMetrics(self.font())
        super().setText(
            metrics.elidedText(self._full_text, Qt.ElideRight, self.width()))


def elided_title_label(text: str, size: int = 14) -> ElidedLabel:
    """캘린더 칸용 제목 — 굵게 + 폭에 맞춰 '…' 줄임."""
    label = ElidedLabel(text)
    label.setStyleSheet(f"font-weight: bold; font-size: {size}px;")
    return label


def sub_label(text: str, size: int = 12) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(f"color: {theme.TEXT_SUB}; font-size: {size}px;")
    return label


def clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            # setParent(None)으로 즉시 화면에서 떼어낸다 —
            # deleteLater만 하면 삭제 전까지 부모 좌상단에 유령처럼 남는다
            widget.setParent(None)
            widget.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())
