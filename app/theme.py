"""색상 팔레트와 폰트 — 눈이 편한 라이트/다크 테마.

이 모듈의 색 상수는 set_theme()으로 갈아 끼운다. 화면 코드는 모두
`theme.BG`처럼 쓸 때마다 읽으므로, 값을 바꾸고 QSS를 다시 만들면
프로그램 전체가 따라온다.

기분 척도·감정 카테고리 색은 뜻을 담고 있어(빨강=나쁨, 노랑=기쁨)
테마와 무관하게 고정이다. 아래 '테마 공통' 절에 모아 두었다.
"""

FONT_FAMILY = "맑은 고딕"

# 폰트를 동봉하지 않고 시스템에 있는 것을 쓴다. 맑은 고딕이 없는 환경
# (비한국어 Windows·macOS·Linux)에서도 한글이 깨지지 않도록 대체 목록을
# 준다 — Qt가 설치된 첫 번째를 알아서 고른다.
FONT_STACK = (
    FONT_FAMILY,          # 맑은 고딕 (한국어 Windows 기본)
    "Malgun Gothic",      # 같은 폰트의 영문 이름
    "나눔고딕",
    "NanumGothic",
    "Noto Sans KR",
    "Apple SD Gothic Neo",   # macOS
    "sans-serif",
)

# CSS·QSS의 font-family에 그대로 넣을 수 있는 형태
FONT_STACK_CSS = ", ".join(f"'{name}'" for name in FONT_STACK)


def qfont(point_size: int, bold: bool = False):
    """대체 목록이 적용된 QFont.

    PySide6는 함수 안에서 불러온다 — theme만 쓰는 테스트가 Qt 없이도
    돌아가게 하기 위해서다.
    """
    from PySide6.QtGui import QFont

    font = QFont()
    font.setFamilies(list(FONT_STACK))
    font.setPointSize(point_size)
    font.setBold(bold)
    return font

LIGHT = {
    "BG": "#F6F4EF",           # 창 배경 (따뜻한 오프화이트)
    "CARD": "#FFFFFF",         # 카드·입력칸 배경
    "BORDER": "#E3DFD6",
    "TEXT": "#3A3A3A",
    "TEXT_SUB": "#8A867C",
    "TEXT_FAINT": "#B7B2A6",   # 배경보다 살짝 진한 은은한 안내 문구용
    "PRIMARY": "#6B9080",      # 차분한 세이지 그린
    "PRIMARY_HOVER": "#5A7D6E",
    "DANGER": "#D9645E",
    "DANGER_HOVER": "#C25550",
    "STAR_OFF": "#C9C5BB",
}

# 다크는 순검정 대신 살짝 푸른 기가 도는 진회색을 쓴다. 대비가 너무
# 세면 눈이 쉽게 피로해지므로 글자도 순백 대신 밝은 회색으로 낮췄다.
DARK = {
    "BG": "#1E2023",
    "CARD": "#282B2F",
    "BORDER": "#3A3E44",
    "TEXT": "#E4E2DD",
    "TEXT_SUB": "#A6A29A",
    "TEXT_FAINT": "#6E6A63",
    "PRIMARY": "#7FA894",      # 어두운 배경에서 또렷하도록 한 단계 밝게
    "PRIMARY_HOVER": "#93B9A6",
    "DANGER": "#E2776F",
    "DANGER_HOVER": "#EC8B83",
    "STAR_OFF": "#5A5750",
}

THEMES = {"light": LIGHT, "dark": DARK}
DEFAULT_THEME = "light"
current_theme = DEFAULT_THEME

# ── 테마 공통 (뜻이 있는 색이라 다크에서도 그대로) ──────────────

STAR_ON = "#F2B84B"

# 기분 척도 색 (음수 빨강 ~ 중립 회색 ~ 양수 초록)
# 회색과 섞이는 구조라 중립에 가까울수록 채도가 자연스럽게 옅어진다
MOOD_NEG = "#E05B5B"
MOOD_NEU = "#B8B8B8"
MOOD_POS = "#5FA97C"


def set_theme(name: str) -> None:
    """색 상수를 그 테마 값으로 갈아 끼운다.

    실제 화면 반영은 QSS를 다시 만들어야 하므로 AppWindow.apply_theme()이
    이 함수를 부른 뒤 이어서 처리한다.
    """
    if name not in THEMES:
        raise ValueError(f"없는 테마: {name}")
    global current_theme
    current_theme = name
    globals().update(THEMES[name])


set_theme(DEFAULT_THEME)


def _blend(color_a: str, color_b: str, t: float) -> str:
    """두 hex 색을 t(0~1) 비율로 섞는다."""
    a = [int(color_a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(color_b[i:i + 2], 16) for i in (1, 3, 5)]
    mixed = [round(x + (y - x) * t) for x, y in zip(a, b)]
    return "#{:02X}{:02X}{:02X}".format(*mixed)


def mood_color(value: float) -> str:
    """-10(빨강) ~ 0(노랑) ~ +10(초록) 그라데이션 위의 색."""
    value = max(-10, min(10, value))
    if value <= 0:
        return _blend(MOOD_NEG, MOOD_NEU, (value + 10) / 10)
    return _blend(MOOD_NEU, MOOD_POS, value / 10)


def mood_text(value: int) -> str:
    """목록·배지에 쓰는 척도 표기 (+7, 0, -5)."""
    return f"+{value}" if value > 0 else str(value)


# 감정 단어 하이라이트 배경색 (카테고리별 파스텔 톤)
CATEGORY_HIGHLIGHT = {
    "기쁨": "#F5E6A8",
    "슬픔": "#C9DFF4",
    "분노": "#F6C6BE",
    "불안": "#DCD0F0",
    "기타": "#DDDDD0",
}
DEFAULT_HIGHLIGHT = "#E4E4DC"   # 사용자 추가 카테고리용


def category_highlight(category: str) -> str:
    """카테고리 고유색 (라이트 기준 파스텔). 색 계열의 기준값."""
    return CATEGORY_HIGHLIGHT.get(category, DEFAULT_HIGHLIGHT)


# 다크에서 파스텔을 카드색에 섞는 비율. 높을수록 배경에 가까워진다.
_DARK_TINT = 0.78


def category_chip(category: str) -> str:
    """감정 단어 칩·하이라이트의 배경색.

    라이트는 파스텔 그대로. 다크는 같은 색을 카드색에 섞어 어둡게 깐다.
    파스텔을 그대로 두면 어두운 화면에서 홀로 밝게 떠 눈이 아프고, 그 위의
    글자도 묻힌다. 색 계열(노랑은 노랑, 파랑은 파랑)은 그대로 남는다.
    """
    base = category_highlight(category)
    if current_theme == "dark":
        return _blend(base, CARD, _DARK_TINT)
    return base


def category_chip_text(category: str) -> str:
    """칩 위 글자색 — 배경과 대비가 서도록 고른다.

    다크에서는 원래 파스텔을 글자에 쓴다. 어두운 바탕 위에서 또렷하면서
    카테고리 색도 그대로 읽힌다.
    """
    base = category_highlight(category)
    if current_theme == "dark":
        return base
    return on_color(base)


def _relative_luminance(color: str) -> float:
    """WCAG 상대 휘도 — 0(검정) ~ 1(흰색)."""
    def channel(value: int) -> float:
        v = value / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _contrast(color_a: str, color_b: str) -> float:
    """두 색의 WCAG 명암비 (1~21)."""
    high = max(_relative_luminance(color_a), _relative_luminance(color_b))
    low = min(_relative_luminance(color_a), _relative_luminance(color_b))
    return (high + 0.05) / (low + 0.05)


def badge_colors(value: float) -> tuple:
    """기분 배지의 (배경, 글자) 색.

    척도 색을 그대로 쓰되, 중간 밝기라 흰색·검정 어느 글자로도 대비가
    모자란 구간(진한 빨강 부근)에서는 배경만 글자 반대쪽으로 조금 민다.
    색 계열은 그대로 남고 숫자는 또렷해진다.
    """
    background = mood_color(value)
    text = on_color(background)
    # 글자가 검정이면 배경을 밝게, 흰색이면 어둡게 밀어 간격을 벌린다
    toward = "#FFFFFF" if text == "#2B2B2B" else "#000000"
    for step in range(0, 46, 5):
        candidate = _blend(background, toward, step / 100)
        if _contrast(text, candidate) >= 4.5:
            return candidate, text
    return background, text


def on_color(background: str) -> str:
    """배경 위에 얹을 글자색 — 흰색과 검정 중 대비가 큰 쪽을 고른다.

    카테고리 색이 파스텔 톤이라 대부분 검정이 뽑히지만, 진한 색을 새로
    쓰게 되면 자동으로 흰색으로 넘어간다.
    """
    luminance = _relative_luminance(background)
    white_contrast = 1.05 / (luminance + 0.05)
    black_contrast = (luminance + 0.05) / 0.05
    return "#2B2B2B" if black_contrast >= white_contrast else "#FFFFFF"


# 분석 화면 파이 차트 카테고리 색
# (dataviz 검증 팔레트를 흰색 35% 블렌드한 파스텔 톤 — 구분성 유지)
CATEGORY_COLOR = {
    "기쁨": "#CFB06B",
    "슬픔": "#8CACD1",
    "분노": "#EB9494",
    "불안": "#BEABE6",
    "기타": "#6AC3AE",
}
# 사용자 추가 카테고리용 (색은 항상 범례와 함께 표시된다)
_FALLBACK_CATEGORY_COLORS = ["#D798B6", "#ABB380", "#94ACC5", "#C5AF95"]

MOOD_MARKER = "#8E6BD9"   # 평균 기분 마커 (보라)


def category_color(category: str, index: int = 0) -> str:
    if category in CATEGORY_COLOR:
        return CATEGORY_COLOR[category]
    return _FALLBACK_CATEGORY_COLORS[index % len(_FALLBACK_CATEGORY_COLORS)]
