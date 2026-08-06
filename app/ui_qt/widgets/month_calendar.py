"""날짜 선택용 캘린더 — 기본 QCalendarWidget의 거슬리는 점을 다듬는다.

세 가지를 손봤다.
1. 연도를 월과 같은 드롭다운 버튼으로. 기본 캘린더는 월은 메뉴 버튼,
   연도는 스핀박스라 나란히 있는데도 생김새가 달랐다.
2. 이번 달 날짜만 표시. 앞뒤 달의 흐린 날짜는 그리지 않는다.
3. 넉넉한 최소 크기. 팝업이 입력칸 너비에 눌려 잘리지 않게 한다.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import (
    QCalendarWidget, QListWidget, QListWidgetItem, QMenu, QToolButton,
    QWidgetAction)

from app import theme


class MonthCalendar(QCalendarWidget):
    """날짜 선택 캘린더. 연도 메뉴는 최근 연도가 위에 오는 내림차순이다."""

    # 연도 목록 범위 — 2000~2099년으로 고정한다. 고른 연도에 따라 범위가
    # 움직이면(예전 방식) 먼 과거로 간 뒤 올해로 돌아올 수 없었다.
    _YEAR_MIN = 2000
    _YEAR_MAX = 2099

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setGridVisible(False)
        self.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.setHorizontalHeaderFormat(QCalendarWidget.ShortDayNames)
        self.setMinimumSize(324, 288)

        self._apply_header_format()

        # 연도 버튼에 메뉴를 달아 월 버튼과 형식을 맞춘다. InstantPopup이면
        # clicked가 나가지 않아 기본 동작(스핀박스로 바뀜)도 함께 막힌다.
        self._year_button = self.findChild(QToolButton,
                                           "qt_calendar_yearbutton")
        # 메뉴에 항목을 그냥 나열하면 목록이 화면보다 길 때 뒤쪽 연도에
        # 닿을 수 없다(QMenu의 스크롤이 제대로 붙지 않는다). 스크롤바가
        # 확실히 있는 목록 위젯을 메뉴 안에 넣는다.
        self._year_menu = QMenu(self)
        self._year_list = QListWidget()
        self._year_list.setFixedWidth(124)
        self._year_list.setFixedHeight(320)
        self._year_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        # 전역 목록·스크롤바 스타일은 항목이 크고 손잡이가 옅어 이 좁은
        # 팝업에서는 잘 안 보인다. 연도 목록에만 촘촘한 스타일을 준다.
        self._year_list.setStyleSheet(f"""
            QListWidget {{
                border: none; background: transparent;
                font-size: 13px; outline: none;
            }}
            QListWidget::item {{ padding: 3px 6px; border-radius: 6px; }}
            QListWidget::item:selected {{
                background-color: {theme.PRIMARY};
                color: white; font-weight: bold;
            }}
            QScrollBar:vertical {{
                background: transparent; width: 10px; margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {theme.TEXT_SUB}; border-radius: 4px;
                min-height: 24px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{ background: transparent; }}
        """)
        self._year_list.itemActivated.connect(self._on_year_item)
        self._year_list.itemClicked.connect(self._on_year_item)
        holder = QWidgetAction(self._year_menu)
        holder.setDefaultWidget(self._year_list)
        self._year_menu.addAction(holder)
        if self._year_button is not None:
            self._year_button.setMenu(self._year_menu)
            self._year_button.setPopupMode(QToolButton.InstantPopup)
            # 열자마자 지금 연도가 보이도록 그 자리로 스크롤한다
            self._year_menu.aboutToShow.connect(self._focus_current_year)

        self._fill_year_list()
        self.currentPageChanged.connect(self._sync_year_selection)
        self._sync_year_selection()

    # ── 연도 목록 ────────────────────────────────────────────

    def _fill_year_list(self):
        """연도 항목을 한 번만 만든다 (2000~2099년 고정).

        고른 연도를 기준으로 다시 만들면 목록이 그때그때 이동해, 한번 먼
        과거로 가면 돌아올 수 없다.
        """
        self._year_list.clear()
        # 최근 연도가 위 — 내림차순
        for year in range(self._YEAR_MAX, self._YEAR_MIN - 1, -1):
            item = QListWidgetItem(f"{year}년")
            item.setData(Qt.UserRole, year)
            item.setTextAlignment(Qt.AlignCenter)
            self._year_list.addItem(item)

    def _sync_year_selection(self, *_args):
        """보고 있는 연도에 맞춰 선택 표시만 옮긴다(목록은 그대로).

        범위 밖 연도(직접 입력으로 갈 수 있다)면 선택을 비운다 — 엉뚱한
        연도가 골라진 것처럼 보이지 않게.
        """
        current = self.yearShown()
        for index in range(self._year_list.count()):
            item = self._year_list.item(index)
            if item.data(Qt.UserRole) == current:
                self._year_list.setCurrentItem(item)
                return
        self._year_list.clearSelection()
        self._year_list.setCurrentItem(None)

    def _on_year_item(self, item):
        self._year_menu.close()
        self._set_year(item.data(Qt.UserRole))

    def _focus_current_year(self):
        """메뉴를 열 때 지금 연도가 보이도록 목록을 그 자리로 옮긴다.
        그러지 않으면 늘 맨 위(가장 나중 연도)부터 보인다."""
        item = self._year_list.currentItem()
        if item is not None:
            self._year_list.scrollToItem(
                item, QListWidget.PositionAtCenter)

    def _set_year(self, year):
        self.setCurrentPage(year, self.monthShown())

    # ── 요일 머리글 ───────────────────────────────────────────

    def _apply_header_format(self):
        """요일 머리글(일~토)의 색을 현재 테마에 맞춘다.

        QTextCharFormat에 색을 한 번 구워 넣으면 그 값이 고정돼, 테마가
        바뀌어도 따라오지 않는다(다크에서 흰 배경에 밝은 글자가 얹혀
        안 보였다). 그래서 테마가 바뀔 때 retheme()이 이 함수를 다시 부른다.

        배경은 카드색으로 회색 칸을 지우고, 평일 글자는 본문색으로 또렷하게.
        토·일은 뜻이 있는 색이라 그대로 붉게 둔다.
        """
        weekday = QTextCharFormat()
        weekday.setBackground(QColor(theme.CARD))
        weekday.setForeground(QColor(theme.TEXT))
        self.setHeaderTextFormat(weekday)

        weekend = QTextCharFormat()
        weekend.setBackground(QColor(theme.CARD))
        weekend.setForeground(QColor(theme.DANGER))
        self.setWeekdayTextFormat(Qt.Saturday, weekend)
        self.setWeekdayTextFormat(Qt.Sunday, weekend)

    def retheme(self):
        """테마 전환 — 색을 구워 넣은 요일 머리글을 다시 칠한다."""
        self._apply_header_format()

    # ── 이번 달만 그리기 ──────────────────────────────────────

    def paintCell(self, painter, rect, date):
        if (date.month() != self.monthShown()
                or date.year() != self.yearShown()):
            painter.fillRect(rect, QColor(theme.CARD))
            return
        super().paintCell(painter, rect, date)
