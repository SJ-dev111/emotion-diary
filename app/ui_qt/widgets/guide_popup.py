"""화면7 — 가이드 팝업 (탭 2개: 프로그램 사용법 / 감정일기 작성 가이드).

첫 실행 시 자동으로 열리고, 이후 네비게이션 바의 '가이드'로 재열람한다.
탭1은 프로그램 조작법 요약, 탭2는 사건/감정/생각 작성 예시·팁과
이론적 근거(CBT 사고기록지)를 담는다.
"""
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QScrollArea, QTabWidget,
    QVBoxLayout, QWidget)

from app import theme
from app.ui_qt.widgets.common import QFrameCard, sub_label

# ── 안내 문구 ────────────────────────────────────────────────

DISCLAIMER = (
    "이 프로그램은 의료기기가 아니며, 전문가의 상담·진단·치료를 대신하지"
    " 않습니다. 마음이 많이 힘드시다면 혼자 견디지 마시고 도움을 받으세요."
    "  ·  자살예방 상담전화 109 (24시간)  ·  정신건강 상담전화 1577-0199"
)

# ── 탭1: 프로그램 사용법 ─────────────────────────────────────

_USAGE = [
    ("화면 이동",
     "왼쪽 네비게이션 바로 모든 화면을 오갈 수 있어요. 위쪽의 원형 화살표"
     " 버튼을 누르면 바가 접히고, 다시 누르면 펼쳐져요. '가이드' 아래의"
     " '바탕화면 바로가기'를 누르면 바탕화면에 바로가기가 생겨서 폴더를"
     " 열지 않고 실행할 수 있어요. 맨 아래에서 라이트/다크 테마를 고를 수"
     " 있어요."),
    ("일기 쓰기",
     "'새 일기 작성'에서 제목과 날짜(원형 버튼 → 캘린더에서 선택), 오늘의"
     " 기분 척도(-10 ~ +10)를 정하고 일기를 적어요. 사건·감정·생각 세 칸을"
     " 채우는 템플릿 작성과, 한 칸에 자유롭게 쓰는 자율 작성 중 고를 수"
     " 있어요. 저장하면 일기 속 감정 단어가 자동으로 인식·집계돼요."),
    ("감정 단어 추천",
     "일기를 쓰다가 단어를 적고 우클릭(또는 Ctrl+Space)하면 감정 단어"
     " 추천 팝업이 떠요. 쓰던 글자에 맞는 단어와 활용형을 골라 바로 넣을"
     " 수 있고, 단어집에 없는 단어라면 그 자리에서 추가할 수도 있어요."),
    ("일기 찾아보기",
     "'적은 일기 보기'에서 리스트 뷰와 캘린더 뷰로 지난 일기를 봐요."
     " 검색창 하나로 제목·날짜·감정 단어(활용형 포함)를 통합 검색하고,"
     " '정렬' 메뉴로 날짜순/점수순·오름/내림차순을 고를 수 있어요."
     " ★를 눌러 즐겨찾기하고, '선택 삭제'로 여러 개를 한 번에 지워요."),
    ("분석 보기",
     "주간/월간/연간 기간별로 감정 카테고리 비율(파이 차트), 평균 기분,"
     " 가장 많이 쓴 감정 표현을 확인할 수 있어요. 홈 화면에도 이번 주"
     " 요약이 표시돼요."),
    ("감정 단어집",
     "감정 단어를 카테고리별로 관리해요. 단어를 추가하면 인식용 어간이"
     " 자동으로 만들어져서, 일기 속 다양한 활용형('행복했다', '행복해서'"
     " 등)도 알아봐요. 카테고리 추가/이름 변경/삭제와 단어 선택 삭제도"
     " 여기서 할 수 있어요."),
]

# ── 탭2: 감정일기 작성 가이드 ────────────────────────────────

_SECTIONS = [
    ("사건", "감정을 유발했던 사건을 적어요.",
     "팀 회의에서 내가 준비한 발표 자료에 대해 팀장님이 여러 번 질문을 했다.",
     "사건 그 자체를 객관적으로 적어 보세요. 카메라로 찍은 장면을 설명하듯,"
     " 해석이나 평가 없이 '무슨 일이 있었는지'만 담는 게 포인트예요."),
    ("감정", "그 사건으로 어떤 감정을 느꼈는지 적어요.",
     "당황스러웠다. 그리고 조금 억울하고 불안했다.",
     "감정과 생각을 구분해 보세요. \"무시당한 느낌이다\"는 사실 생각(해석)에"
     " 가깝고, \"서운하다\", \"화나다\"처럼 한 단어로 표현되는 것이 감정이에요."
     " 감정 단어가 잘 떠오르지 않으면 입력 중 우클릭으로 감정 단어집을"
     " 참고하세요. 여러 감정을 동시에 느꼈다면 그대로 다 적어도 좋아요 —"
     " 예: 화나면서도 슬펐다."),
    ("생각", "그 사건으로 어떤 생각이 들었는지 적어요.",
     "'내 준비가 부족했나?', '팀장님이 나를 못 미더워하는 건 아닐까'라는"
     " 생각이 들었다.",
     "구체적으로 적을수록 좋아요. 머릿속을 스친 생각을 그대로 문장으로 옮겨"
     " 두면, 나중에 그 생각이 사실이었는지 차분히 되돌아보기 쉬워져요."),
]

_THEORY = (
    "사건-감정-생각의 3단 구조는 인지행동치료(CBT)의 사고기록지"
    "(thought record)에서 온 형식이에요.\n\n"
    "감정을 글로 표현하는 것만으로도 정서를 가라앉히는 데 도움이 되고"
    "(정서 명명 효과), 사건·감정·생각을 분리해 보는 연습은 자동으로 떠오르는"
    " 생각과 실제 사실을 구분하는 힘을 길러줘요.\n\n"
    "꾸준히 기록하면 나의 감정 패턴을 발견하고, 나를 힘들게 하는 생각 습관을"
    " 알아차리는 데 도움이 됩니다."
)


class GuideDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("가이드")
        self.resize(640, 720)
        self.setModal(True)

        root = QVBoxLayout(self)
        title = QLabel("가이드")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        root.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._usage_tab(), "프로그램 사용법")
        tabs.addTab(self._writing_tab(), "감정일기 작성 가이드")
        root.addWidget(tabs, stretch=1)

        # 어느 탭을 보고 있든 눈에 들어오도록 탭 바깥 맨 아래에 둔다
        disclaimer = QLabel(DISCLAIMER)
        disclaimer.setWordWrap(True)
        disclaimer.setStyleSheet(
            f"color: {theme.TEXT_SUB}; font-size: 12px;"
            f" border-top: 1px solid {theme.BORDER};"
            " padding-top: 8px; margin-top: 2px;")
        root.addWidget(disclaimer)

        buttons = QHBoxLayout()
        buttons.addStretch()
        close_button = QPushButton("닫기")
        close_button.setMinimumWidth(120)
        close_button.clicked.connect(self.accept)
        buttons.addWidget(close_button)
        root.addLayout(buttons)

    # ── 탭 구성 ──────────────────────────────────────────────

    def _scroll_tab(self, intro_text):
        """스크롤 가능한 탭 본문 (안내 문장 + 카드 목록) 틀을 만든다."""
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(2, 6, 10, 6)
        body.setSpacing(12)
        intro = sub_label(intro_text, 13)
        intro.setWordWrap(True)
        body.addWidget(intro)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        return scroll, body

    def _usage_tab(self):
        scroll, body = self._scroll_tab(
            "감정일기의 화면별 사용법을 간단히 정리했어요.")
        for name, desc in _USAGE:
            card = QFrameCard()
            layout = QVBoxLayout(card)
            layout.setContentsMargins(16, 12, 16, 12)
            layout.setSpacing(6)
            title = QLabel(name)
            title.setStyleSheet(
                f"color: {theme.PRIMARY}; font-weight: bold;"
                " font-size: 15px;")
            layout.addWidget(title)
            desc_label = QLabel(desc)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("font-size: 13px;")
            layout.addWidget(desc_label)
            body.addWidget(card)
        body.addStretch()
        return scroll

    def _writing_tab(self):
        scroll, body = self._scroll_tab(
            "사건 → 감정 → 생각 순서로 적는 감정일기 작성법이에요.")
        for name, desc, example, tip in _SECTIONS:
            body.addWidget(self._section(name, desc, example, tip))
        body.addWidget(self._theory_card())
        body.addStretch()
        return scroll

    # ── 카드 ─────────────────────────────────────────────────

    def _section(self, name, desc, example, tip):
        card = QFrameCard()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        title = QLabel(name)
        title.setStyleSheet(
            f"color: {theme.PRIMARY}; font-weight: bold; font-size: 15px;")
        layout.addWidget(title)

        desc_label = QLabel(desc)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        example_label = QLabel(f"예시)  {example}")
        example_label.setWordWrap(True)
        example_label.setStyleSheet(
            f"background-color: {theme.BG}; border: 1px solid {theme.BORDER};"
            " border-radius: 8px; padding: 10px; font-size: 13px;")
        layout.addWidget(example_label)

        tip_label = QLabel(f"💡 {tip}")
        tip_label.setWordWrap(True)
        tip_label.setStyleSheet(
            f"color: {theme.TEXT_SUB}; font-size: 12px;")
        layout.addWidget(tip_label)
        return card

    def _theory_card(self):
        card = QFrameCard()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)
        title = QLabel("이론적 근거와 기대효과")
        title.setStyleSheet(
            f"color: {theme.PRIMARY}; font-weight: bold; font-size: 15px;")
        layout.addWidget(title)
        body = QLabel(_THEORY)
        body.setWordWrap(True)
        body.setStyleSheet("font-size: 13px;")
        layout.addWidget(body)
        return card
