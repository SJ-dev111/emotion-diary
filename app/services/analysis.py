"""화면5(분석)용 기간 계산과 문장형 요약."""
import calendar
from datetime import date, timedelta


def period_range(unit: str, anchor: date) -> tuple[str, str, str]:
    """(시작일 ISO, 종료일 ISO, 표시 라벨). unit: 주간/월간/연간.

    주간은 캘린더 뷰와 동일하게 일요일 시작.
    """
    if unit == "주간":
        start = anchor - timedelta(days=(anchor.weekday() + 1) % 7)
        end = start + timedelta(days=6)
        label = f"{start.strftime('%Y.%m.%d')} ~ {end.strftime('%m.%d')}"
    elif unit == "월간":
        start = anchor.replace(day=1)
        last_day = calendar.monthrange(anchor.year, anchor.month)[1]
        end = anchor.replace(day=last_day)
        label = f"{anchor.year} / {anchor.month:02d}"
    elif unit == "연간":
        start = date(anchor.year, 1, 1)
        end = date(anchor.year, 12, 31)
        label = str(anchor.year)
    else:
        raise ValueError(f"지원하지 않는 기간 단위: {unit}")
    return start.isoformat(), end.isoformat(), label


def shift_anchor(unit: str, anchor: date, delta: int) -> date:
    """이전(-1)/다음(+1) 기간으로 기준일을 이동."""
    if unit == "주간":
        return anchor + timedelta(weeks=delta)
    if unit == "월간":
        month = anchor.month + delta
        year = anchor.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        return date(year, month, 1)
    if unit == "연간":
        return date(anchor.year + delta, 1, 1)
    raise ValueError(f"지원하지 않는 기간 단위: {unit}")


def mood_summary_sentence(positive: int, neutral: int, negative: int) -> str:
    """긍정/부정 일기 개수 비교 문장 (화면5 하단 요약)."""
    total = positive + neutral + negative
    if total == 0:
        return "이 기간에는 작성한 일기가 없어요."
    if positive > negative:
        return "기분이 좋은 날이 더 많았어요!"
    if negative > positive:
        return "기분이 힘든 날이 조금 더 많았어요. 마음을 돌봐 주세요."
    return "좋은 날과 힘든 날이 비슷하게 있었어요."
