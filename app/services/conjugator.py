"""한국어 용언 활용 규칙 엔진.

같은 규칙을 두 곳에서 공용한다:
① 인식용 어간 생성 (generate_stems) — 단어집에 새 단어를 추가할 때
② 자동완성 활용형 생성 (forms) — 단어 선택 시 7개 형태 제시

형태소 분석기 없이 대표 활용 패턴(하다/되다/나다 축약, ㅂ 불규칙,
ㅡ 탈락, ㅣ→ㅕ 축약, 모음조화)만 문자열 변환으로 구현한다.
"""

_CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"

# 중성 인덱스 (유니코드 조합 순서)
_A, _EO, _YEO, _O, _WA, _U, _WEO, _EU, _I = 0, 4, 6, 8, 9, 13, 14, 18, 20
# 종성 인덱스
_JONG_NONE, _JONG_N, _JONG_L, _JONG_M, _JONG_B, _JONG_SS = 0, 4, 8, 16, 17, 20

FORM_LABELS = ("기본형", "과거형", "관형형", "연결형", "명사형", "의문형", "변화형")


def decompose(ch: str):
    """음절 → (초성, 중성, 종성) 인덱스. 한글 음절이 아니면 None."""
    code = ord(ch) - 0xAC00
    if not 0 <= code < 11172:
        return None
    return code // 588, (code % 588) // 28, code % 28


def compose(cho: int, jung: int, jong: int = 0) -> str:
    return chr(0xAC00 + cho * 588 + jung * 28 + jong)


def is_hangul(ch: str) -> bool:
    return decompose(ch) is not None


def _set_jong(s: str, jong: int) -> str:
    """마지막 음절의 받침을 교체."""
    cho, jung, _ = decompose(s[-1])
    return s[:-1] + compose(cho, jung, jong)


def _set_jung(s: str, jung: int) -> str:
    """마지막 음절의 모음을 교체하고 받침 제거."""
    cho, _, _ = decompose(s[-1])
    return s[:-1] + compose(cho, jung, 0)


def _last_vowel(s: str):
    for ch in reversed(s):
        d = decompose(ch)
        if d:
            return d[1]
    return None


def _is_bright(s: str) -> bool:
    """모음조화: 어간의 마지막 모음이 양성(ㅏ/ㅗ)인가."""
    return _last_vowel(s) in (_A, _O)


def _contract(stem: str) -> str:
    """어간 + 아/어 축약형 (무섭→무서워, 슬프→슬퍼, 지치→지쳐, 열받→열받아)."""
    cho, jung, jong = decompose(stem[-1])
    if jong == _JONG_B:                     # ㅂ 불규칙
        return _set_jong(stem, _JONG_NONE) + "워"
    if jong == _JONG_NONE:
        if jung == _EU:                     # ㅡ 탈락 (+모음조화)
            return _set_jung(stem, _A if _is_bright(stem[:-1]) else _EO)
        if jung == _I:                      # ㅣ + ㅓ → ㅕ
            return _set_jung(stem, _YEO)
        if jung == _O:                      # ㅗ + ㅏ → ㅘ
            return _set_jung(stem, _WA)
        if jung == _U:                      # ㅜ + ㅓ → ㅝ
            return _set_jung(stem, _WEO)
        return stem                         # ㅏ·ㅓ·ㅐ·ㅔ·ㅕ 등은 그대로
    return stem + ("아" if _is_bright(stem) else "어")


def _is_verb_like(word: str) -> bool:
    return len(word) >= 2 and word.endswith("다") and is_hangul(word[-2])


def generate_stems(word: str) -> list[str]:
    """인식(자모 접두 매칭)용 어간 목록을 자동 생성."""
    word = word.strip()
    if word.endswith(("하다", "되다")) and len(word) > 2:
        return [word[:-2]]
    if word.endswith("나다") and len(word) > 2:
        x = word[:-2]
        d = decompose(x[-1])
        particle = "이" if d and d[2] else "가"   # 신이 나 / 화가 나
        return [x + "나", f"{x}{particle} 나"]
    if _is_verb_like(word):
        stem = word[:-1]
        stems = [stem]
        _, _, jong = decompose(stem[-1])
        if jong == _JONG_B:
            # 무섭 → 무서우 (자모 매칭이 무서운·무서움·무서워까지 커버)
            stems.append(_set_jong(stem, _JONG_NONE) + "우")
        else:
            contracted = _contract(stem)
            if contracted != stem and not contracted.startswith(stem):
                stems.append(contracted)   # 슬프 → 슬퍼, 지치 → 지쳐
        return stems
    return [word]  # 용언이 아닌 단어(명사 등)는 그대로


def forms(word: str) -> list[tuple[str, str]]:
    """자동완성용 활용형 목록: (라벨, 형태). 어색한 형태는 생략된다."""
    word = word.strip()
    if word.endswith("하다") and len(word) > 2:
        x = word[:-2]
        result = (word, x + "했다", x + "한", x + "해서",
                  x + "함", x + "할까", x + "해졌다")
    elif word.endswith("되다") and len(word) > 2:
        x = word[:-2]
        result = (word, x + "됐다", x + "되는", x + "돼서",
                  x + "됨", x + "될까", None)
    elif word.endswith("나다") and len(word) > 2:
        x = word[:-2]
        result = (word, x + "났다", x + "난", x + "나서",
                  x + "남", x + "날까", None)
    elif _is_verb_like(word):
        stem = word[:-1]
        contracted = _contract(stem)
        _, _, jong = decompose(stem[-1])
        if jong == _JONG_B:
            base = _set_jong(stem, _JONG_NONE)
            attr, noun, ques = base + "운", base + "움", base + "울까"
        elif jong == _JONG_NONE:
            attr = _set_jong(stem, _JONG_N)
            noun = _set_jong(stem, _JONG_M)
            ques = _set_jong(stem, _JONG_L) + "까"
        else:
            attr, noun, ques = stem + "은", stem + "음", stem + "을까"
        past = _set_jong(contracted, _JONG_SS) + "다"
        result = (word, past, attr, contracted + "서",
                  noun, ques, contracted + "졌다")
    else:
        return [("기본형", word)]
    return [(label, form)
            for label, form in zip(FORM_LABELS, result) if form]
