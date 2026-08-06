"""전역 QSS 스타일시트 — theme.py의 색상 팔레트를 Qt에 적용한다."""
from app import config, theme

# ::drop-down을 QSS로 꾸미면 기본 화살표가 사라져서 이미지로 직접 그린다.
# 배포본에서도 찾을 수 있도록 경로는 config가 정한다.
_ARROW_DOWN = config.asset_path("arrow_down.png").as_posix()


def build_qss() -> str:
    return f"""
    QWidget {{
        background-color: {theme.BG};
        color: {theme.TEXT};
        font-family: {theme.FONT_STACK_CSS};
        font-size: 14px;
    }}
    QLineEdit, QTextEdit, QDateEdit {{
        background-color: {theme.CARD};
        border: 1px solid {theme.BORDER};
        border-radius: 8px;
        padding: 6px 8px;
        selection-background-color: {theme.PRIMARY};
    }}
    QLineEdit#titleEntry {{
        font-size: 20px;
        font-weight: bold;
    }}
    /* 날짜 선택: 원형 화살표 버튼 → 캘린더 팝업 (직접 입력은 막음) */
    QDateEdit {{
        padding: 8px 42px 8px 12px;   /* 오른쪽은 원형 화살표 버튼 자리 */
        font-size: 15px;
    }}
    QDateEdit::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: center right;
        width: 26px;
        height: 26px;
        margin-right: 7px;   /* 둥근 모서리에 잘리지 않도록 여유를 더 둔다 */
        border: 1px solid {theme.BORDER};
        border-radius: 13px;
        background-color: {theme.BG};
    }}
    QDateEdit::down-arrow {{
        image: url("{_ARROW_DOWN}");
        width: 11px;
        height: 11px;
    }}
    QComboBox {{
        background-color: {theme.CARD};
        border: 1px solid {theme.BORDER};
        border-radius: 8px;
        padding: 6px 34px 6px 10px;   /* 오른쪽은 원형 화살표 버튼 자리 */
    }}
    /* 화살표를 작은 원이 둘러싼 디자인 — 콤보 모서리를 가리지 않는다 */
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: center right;
        width: 22px;
        height: 22px;
        margin-right: 5px;
        border: 1px solid {theme.BORDER};
        border-radius: 11px;
        background-color: {theme.BG};
    }}
    QComboBox::down-arrow {{
        image: url("{_ARROW_DOWN}");
        width: 10px;
        height: 10px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {theme.CARD};
        selection-background-color: {theme.PRIMARY};
        selection-color: white;
    }}
    QPushButton {{
        background-color: {theme.PRIMARY};
        color: white;
        border: none;
        border-radius: 8px;
        padding: 9px 16px;
        font-weight: bold;
    }}
    QPushButton:hover {{ background-color: {theme.PRIMARY_HOVER}; }}
    QPushButton:disabled {{
        background-color: {theme.BORDER};
        color: {theme.TEXT_SUB};
    }}
    QPushButton[kind="flat"] {{
        background-color: transparent;
        color: {theme.TEXT};
        border: 1px solid {theme.BORDER};
        font-weight: normal;
    }}
    QPushButton[kind="flat"]:hover {{ background-color: {theme.BORDER}; }}
    QPushButton[kind="flat"]:disabled {{
        background-color: transparent;
        color: {theme.TEXT_SUB};
    }}
    QPushButton[kind="flatDanger"] {{
        background-color: transparent;
        color: {theme.DANGER};
        border: 1px solid {theme.DANGER};
        font-weight: normal;
    }}
    QPushButton[kind="flatDanger"]:hover {{ background-color: {theme.BORDER}; }}
    QPushButton[kind="ghost"] {{
        background-color: transparent;
        color: {theme.TEXT};
        border: none;
        font-size: 16px;
        padding: 4px 2px;   /* 기본 패딩이 크면 ←·◀ 같은 글리프가 잘린다 */
    }}
    QPushButton[kind="ghost"]:hover {{ background-color: {theme.BORDER}; }}
    QPushButton[kind="danger"] {{ background-color: {theme.DANGER}; }}
    QPushButton[kind="danger"]:hover {{ background-color: {theme.DANGER_HOVER}; }}
    QPushButton[kind="segment"] {{
        background-color: transparent;
        color: {theme.TEXT_SUB};
        border: 1px solid {theme.BORDER};
        font-weight: normal;
        padding: 6px 14px;
    }}
    QPushButton[kind="segment"]:checked {{
        background-color: {theme.PRIMARY};
        color: white;
        border-color: {theme.PRIMARY};
    }}
    /* 스위치처럼 붙는 2단 토글 (좌/우) */
    QPushButton[kind="segmentLeft"], QPushButton[kind="segmentRight"] {{
        background-color: transparent;
        color: {theme.TEXT_SUB};
        border: 1px solid {theme.BORDER};
        font-weight: normal;
        padding: 6px 14px;
    }}
    QPushButton[kind="segmentLeft"] {{
        border-top-right-radius: 0;
        border-bottom-right-radius: 0;
    }}
    QPushButton[kind="segmentRight"] {{
        border-top-left-radius: 0;
        border-bottom-left-radius: 0;
        border-left: none;
    }}
    QPushButton[kind="segmentLeft"]:checked,
    QPushButton[kind="segmentRight"]:checked {{
        background-color: {theme.PRIMARY};
        color: white;
        border-color: {theme.PRIMARY};
    }}
    QPushButton[compact="true"] {{
        padding: 6px 6px;   /* 고정폭 소형 버튼용 — 텍스트 잘림 방지 */
    }}
    /* 좌측 네비게이션 바 */
    QFrame[kind="navBar"] {{
        background-color: {theme.CARD};
        border: none;
        border-right: 1px solid {theme.BORDER};
    }}
    QPushButton[kind="navItem"], QPushButton[kind="navSub"],
    QPushButton[kind="navAction"] {{
        background-color: transparent;
        color: {theme.TEXT};
        border: none;
        border-radius: 8px;
        padding: 8px 12px;
        text-align: left;
        font-weight: normal;
    }}
    /* 화면 이동이 아니라 무언가를 실행하는 항목 (바탕화면 바로가기) */
    QPushButton[kind="navAction"] {{
        color: {theme.PRIMARY};
        font-weight: bold;
    }}
    QPushButton[kind="navAction"]:hover {{
        background-color: {theme.BORDER};
    }}
    QPushButton[kind="navSub"] {{
        margin-left: 18px;   /* '적은 일기 보기'에 속한 토글은 들여쓰기 */
        padding: 6px 12px;
        font-size: 13px;
    }}
    QPushButton[kind="navItem"]:hover, QPushButton[kind="navSub"]:hover {{
        background-color: {theme.BORDER};
    }}
    QPushButton[kind="navItem"]:checked, QPushButton[kind="navSub"]:checked {{
        background-color: {theme.PRIMARY};
        color: white;
        font-weight: bold;
    }}
    QPushButton[kind="navToggle"] {{
        background-color: {theme.CARD};
        color: {theme.TEXT};
        border: 1px solid {theme.BORDER};
        border-radius: 15px;   /* 원형 화살표 버튼 (30x30) */
        padding: 0;
        font-size: 12px;
        font-weight: normal;
    }}
    QPushButton[kind="navToggle"]:hover {{ background-color: {theme.BORDER}; }}
    QFrame[kind="card"] {{
        background-color: {theme.CARD};
        border: 1px solid {theme.BORDER};
        border-radius: 12px;
    }}
    QFrame[kind="row"] {{
        background-color: {theme.CARD};   /* 목록 행은 흰색 — 배경과 구분 */
        border: 1px solid {theme.BORDER};
        border-radius: 8px;
    }}
    QFrame[kind="dayFilled"] {{
        background-color: {theme.BG};
        border: 1px solid {theme.BORDER};
        border-radius: 8px;
    }}
    QFrame[kind="dayEmpty"] {{
        background-color: transparent;
        border: 1px solid {theme.BORDER};
        border-radius: 8px;
    }}
    QCheckBox {{ background: transparent; }}
    QCheckBox::indicator {{
        width: 16px; height: 16px;
        border: 1px solid {theme.BORDER};
        border-radius: 4px;
        background: {theme.CARD};
    }}
    QCheckBox::indicator:checked {{
        background-color: {theme.PRIMARY};
        border-color: {theme.PRIMARY};
    }}
    QRadioButton {{ background: transparent; spacing: 7px; }}
    QRadioButton::indicator {{
        width: 15px; height: 15px;
        border: 1px solid {theme.BORDER};
        border-radius: 8px;
        background: {theme.CARD};
    }}
    QRadioButton::indicator:checked {{
        /* 두꺼운 테두리로 가운데 점을 만들면 Qt가 모서리를 각지게 그린다.
           체크박스와 같이 꽉 채워 표시한다. */
        border-color: {theme.PRIMARY};
        background: {theme.PRIMARY};
    }}
    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{
        background: transparent; width: 14px;
        margin: 6px 4px 6px 2px;   /* 둥근 모서리 안에서 잘리지 않게 여백 */
    }}
    QScrollBar::handle:vertical {{
        background: {theme.BORDER}; border-radius: 4px; min-height: 30px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QLabel {{ background: transparent; }}
    QLabel[kind="section"] {{
        color: {theme.PRIMARY};
        font-weight: bold;
        font-size: 13px;
    }}
    QListWidget {{
        background-color: {theme.CARD};
        border: 1px solid {theme.BORDER};
        border-radius: 8px;
        padding: 4px;
    }}
    QListWidget::item {{
        padding: 6px 8px;
        border-radius: 6px;
    }}
    QListWidget::item:selected {{
        background-color: {theme.PRIMARY};
        color: white;
    }}
    QMenu {{
        background-color: {theme.CARD};
        border: 1px solid {theme.BORDER};
        border-radius: 8px;
        padding: 6px;
        /* 항목이 화면보다 많으면 여러 열로 펼치지 말고 스크롤한다.
           연도 목록(101개)이 네 열로 벌어져 화면을 덮는 것을 막는다. */
        menu-scrollable: 1;
    }}
    QMenu::scroller {{
        height: 18px;
        background-color: {theme.CARD};
    }}
    QMenu::item {{
        padding: 6px 24px 6px 8px;
        border-radius: 6px;
    }}
    QMenu::item:selected {{
        background-color: {theme.PRIMARY};
        color: white;
    }}
    QMenu::separator {{
        height: 1px;
        background: {theme.BORDER};
        margin: 4px 8px;
    }}
    QPushButton::menu-indicator {{
        subcontrol-origin: padding;
        subcontrol-position: center right;
        width: 10px;
        right: 6px;
    }}
    QDialog {{ background-color: {theme.BG}; }}
    /* 가이드 팝업 탭 */
    QTabWidget::pane {{
        border: 1px solid {theme.BORDER};
        border-radius: 8px;
        background-color: {theme.BG};
        top: -1px;
    }}
    QTabBar::tab {{
        background-color: transparent;
        color: {theme.TEXT_SUB};
        border: 1px solid {theme.BORDER};
        border-bottom: none;
        border-top-left-radius: 8px;
        border-top-right-radius: 8px;
        padding: 8px 18px;
        margin-right: 2px;
    }}
    QTabBar::tab:selected {{
        background-color: {theme.CARD};
        color: {theme.TEXT};
        font-weight: bold;
    }}
    /* 날짜 캘린더 팝업 — 상단(연/월 이동) 바를 진하게 해 가시성 확보 */
    QCalendarWidget QWidget {{ background-color: {theme.CARD}; }}
    QCalendarWidget QWidget#qt_calendar_navigationbar {{
        background-color: {theme.PRIMARY};
        min-height: 36px;
    }}
    QCalendarWidget QToolButton {{
        color: white;
        background-color: transparent;
        border: none;
        border-radius: 6px;
        padding: 4px 16px 4px 10px;   /* 오른쪽은 화살표 자리 */
        font-size: 14px;
        font-weight: bold;
    }}
    QCalendarWidget QToolButton:hover {{
        background-color: {theme.PRIMARY_HOVER};
    }}
    QCalendarWidget QToolButton::menu-indicator {{
        /* 기본 위치는 글자 아래라 연/월 버튼이 두 줄처럼 보인다 */
        subcontrol-origin: padding;
        subcontrol-position: center right;
        width: 10px;
    }}
    QCalendarWidget QSpinBox {{
        background-color: {theme.CARD};
        color: {theme.TEXT};
        border: 1px solid {theme.BORDER};
        border-radius: 4px;
        padding: 2px 4px;
        font-size: 14px;
        selection-background-color: {theme.PRIMARY};
        selection-color: white;
    }}
    QCalendarWidget QAbstractItemView {{
        selection-background-color: {theme.PRIMARY};
        selection-color: white;
    }}
    """
