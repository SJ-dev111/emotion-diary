"""기분 척도 슬라이더 (-10 ~ +10) — 값에 따라 슬라이더 색이 함께 변한다."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QSlider, QWidget

from app import theme


class MoodSlider(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setColumnStretch(2, 1)

        title = QLabel("오늘의 기분은")
        grid.addWidget(title, 0, 0)

        self.value_label = QLabel("0")
        self.value_label.setFixedWidth(46)
        self.value_label.setAlignment(Qt.AlignCenter)
        grid.addWidget(self.value_label, 0, 1)

        # 이모지·슬라이더 손잡이가 잘리지 않도록 세로 여유를 넉넉히 잡는다
        sad = QLabel("🙁")
        sad.setStyleSheet("font-size: 22px;")
        sad.setFixedSize(50, 50)
        sad.setAlignment(Qt.AlignCenter)
        grid.addWidget(sad, 1, 0, Qt.AlignRight | Qt.AlignVCenter)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(-10, 10)
        self.slider.setPageStep(1)
        self.slider.setMinimumHeight(34)   # 손잡이(18px+여유)가 온전히 보이게
        self.slider.valueChanged.connect(self._on_change)
        grid.addWidget(self.slider, 1, 1, 1, 2)

        happy = QLabel("🙂")
        happy.setStyleSheet("font-size: 22px;")
        happy.setFixedSize(50, 50)
        happy.setAlignment(Qt.AlignCenter)
        grid.addWidget(happy, 1, 3, Qt.AlignLeft | Qt.AlignVCenter)

        hint = QWidget()
        hint_grid = QGridLayout(hint)
        hint_grid.setContentsMargins(0, 0, 0, 0)
        for col, (text, align) in enumerate(
                [("-10", Qt.AlignLeft), ("0", Qt.AlignCenter),
                 ("+10", Qt.AlignRight)]):
            label = QLabel(text)
            label.setStyleSheet(f"color: {theme.TEXT_SUB}; font-size: 11px;")
            hint_grid.addWidget(label, 0, col, align)
            hint_grid.setColumnStretch(col, 1)
        grid.addWidget(hint, 2, 1, 1, 2)

        self._on_change(0)

    def _on_change(self, value: int) -> None:
        color = theme.mood_color(value)
        self.value_label.setText(theme.mood_text(value))
        self.value_label.setStyleSheet(
            f"color: {color}; font-size: 16px; font-weight: bold;")
        self.slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 6px; background: {theme.BORDER}; border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: {color}; border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {color}; width: 18px; height: 18px;
                margin: -6px 0; border-radius: 9px;
            }}
        """)

    def get(self) -> int:
        return self.slider.value()

    def set(self, value: int) -> None:
        self.slider.setValue(value)
        self._on_change(value)

    def set_enabled(self, enabled: bool) -> None:
        self.slider.setEnabled(enabled)
