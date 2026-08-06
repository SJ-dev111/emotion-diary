"""감정 단어 인식기 — 자모 단위 어간 접두 매칭 + 부정 감지.

- 텍스트와 어간을 자모(초·중·종성, 복합 모음·겹받침 분해)로 펼친 뒤
  접두 일치를 검사한다. "슬픔"(슬프+ㅁ), "무서웠다"(무서우+ㅓㅆ)처럼
  음절 단위로는 못 잡는 활용형을 커버한다.
- 매칭은 어절 시작에서만 인정한다 ("영화나 봤다"가 '화나다'로 잡히는
  오인식 방지).
- 매칭 직후 "지 않/지 못/지 말", 직전 "안 /못 "이 있으면 부정으로 보고
  제외한다 ("행복하지 않았다"가 기쁨으로 집계되는 오류 방지).
"""
import re
from typing import NamedTuple

from app.services import conjugator as cj

_CHO_JAMO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
_JUNG_JAMO = ["ㅏ", "ㅐ", "ㅑ", "ㅒ", "ㅓ", "ㅔ", "ㅕ", "ㅖ", "ㅗ", "ㅗㅏ",
              "ㅗㅐ", "ㅗㅣ", "ㅛ", "ㅜ", "ㅜㅓ", "ㅜㅔ", "ㅜㅣ", "ㅠ", "ㅡ",
              "ㅡㅣ", "ㅣ"]
_JONG_JAMO = ["", "ㄱ", "ㄲ", "ㄱㅅ", "ㄴ", "ㄴㅈ", "ㄴㅎ", "ㄷ", "ㄹ", "ㄹㄱ",
              "ㄹㅁ", "ㄹㅂ", "ㄹㅅ", "ㄹㅌ", "ㄹㅍ", "ㄹㅎ", "ㅁ", "ㅂ", "ㅂㅅ",
              "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]

_NEG_AFTER = re.compile(r"지\s?(않|못|말)")


class Match(NamedTuple):
    word: str        # 단어집의 기본형
    category: str
    start: int       # 원문 문자 인덱스 (하이라이트용)
    end: int         # 매칭된 어절의 끝 (exclusive)


def _to_jamo(text: str):
    """텍스트를 자모 문자열로 펼치고, 자모 위치 → 원문 인덱스 맵을 만든다."""
    jamo_chars = []
    index_map = []
    for i, ch in enumerate(text):
        d = cj.decompose(ch)
        if d:
            cho, jung, jong = d
            piece = _CHO_JAMO[cho] + _JUNG_JAMO[jung] + _JONG_JAMO[jong]
        else:
            piece = ch
        for jamo in piece:
            jamo_chars.append(jamo)
            index_map.append(i)
    return "".join(jamo_chars), index_map


def _eojeol_end(text: str, last_char_idx: int) -> int:
    """매칭이 끝난 문자부터 어절 끝(한글이 아닌 문자 직전)까지 확장."""
    j = last_char_idx + 1
    while j < len(text) and cj.is_hangul(text[j]):
        j += 1
    return j


def _negated(text: str, start: int, end: int) -> bool:
    before = text[:start].rstrip()
    if (before and before[-1] in "안못"
            and (len(before) == 1 or not cj.is_hangul(before[-2]))):
        return True
    segment = text[start:min(len(text), end + 5)]
    return bool(_NEG_AFTER.search(segment))


def detect(text: str, vocab) -> list[Match]:
    """vocab: (word, category, stems) 목록 — EmotionRepo.all_for_matching().

    부정된 표현은 결과에서 제외된다 (하이라이트도 집계도 안 함).
    """
    if not text:
        return []
    text_jamo, index_map = _to_jamo(text)
    matches = []
    for word, category, stems in vocab:
        spans = {}   # 같은 단어의 어간 여러 개가 같은 지점에 걸리면 1회로
        for stem in stems:
            if not stem:
                continue
            stem_jamo, _ = _to_jamo(stem)
            pos = text_jamo.find(stem_jamo)
            while pos != -1:
                start = index_map[pos]
                if start == 0 or not cj.is_hangul(text[start - 1]):
                    last_idx = index_map[pos + len(stem_jamo) - 1]
                    end = _eojeol_end(text, last_idx)
                    spans[start] = max(end, spans.get(start, 0))
                pos = text_jamo.find(stem_jamo, pos + 1)
        for start, end in spans.items():
            if _negated(text, start, end):
                continue
            matches.append(Match(word, category, start, end))
    matches.sort(key=lambda m: (m.start, -m.end))
    return matches


def match_words(query: str, vocab) -> list[str]:
    """부분 입력(활용형 조각 포함)과 어간이 맞는 기본형 단어 목록.

    자동완성 추천과 감정 단어 검색이 공용한다. 예:
    "서러" → 서럽다, "서러웠다" → 서럽다, "행복" → 행복하다.
    """
    query = query.strip()
    if not query:
        return []
    query_jamo, _ = _to_jamo(query)
    matched = []
    for word, _category, stems in vocab:
        if query in word:
            matched.append(word)
            continue
        for stem in stems:
            stem_jamo, _ = _to_jamo(stem)
            if (stem_jamo.startswith(query_jamo)
                    or query_jamo.startswith(stem_jamo)):
                matched.append(word)
                break
    return matched


def suggest_from_lexicon(query: str):
    """단어집에 없는 감정 표현을 확장 어휘 사전에서 찾아 (기본형, 카테고리) 제안.

    "허탈했다" → ("허탈하다", "슬픔"). 못 찾으면 None.
    분류는 제안일 뿐이며, 최종 카테고리는 사용자가 등록 시 결정한다.
    """
    from app.data.emotion_lexicon import EXTENDED_LEXICON

    query = query.strip()
    if len(query) < 2:
        return None
    query_jamo, _ = _to_jamo(query)
    best = None
    best_overlap = 0
    for word, category in EXTENDED_LEXICON.items():
        for stem in cj.generate_stems(word):
            stem_jamo, _ = _to_jamo(stem)
            if (stem_jamo.startswith(query_jamo)
                    or query_jamo.startswith(stem_jamo)):
                overlap = min(len(stem_jamo), len(query_jamo))
                if overlap > best_overlap:
                    best, best_overlap = (word, category), overlap
    return best


def count_tags(text: str, vocab) -> list[tuple[str, str, int]]:
    """저장 시 entry_emotion_tags에 기록할 (word, category, count) 목록."""
    counts = {}
    for m in detect(text, vocab):
        key = (m.word, m.category)
        counts[key] = counts.get(key, 0) + 1
    return [(word, category, n)
            for (word, category), n in sorted(counts.items())]
