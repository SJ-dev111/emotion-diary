"""사용자 보기·공유용 내보내기 — 앱 화면을 닮은 HTML과 PDF를 만든다.

색은 theme.py 상수를 그대로 써서 앱과 같은 톤을 유지한다. HTML은 이미지를
data URI로 품고 있어 파일 하나만 옮겨도 그대로 열린다.

PDF는 같은 HTML을 QTextDocument로 그린다. QTextDocument가 지원하는 CSS는
제한적이라(둥근 모서리·flex 미지원) 브라우저로 연 HTML만큼 정교하진 않지만,
외부 라이브러리 없이 배포할 수 있다는 이점이 크다.
"""
import html as html_mod
from datetime import date, datetime

from app import config, theme
from app.services import analysis

# 내보낸 문서는 앱 테마와 무관하게 늘 라이트다. 종이로 인쇄하거나 남에게
# 보내는 결과물이라 어두운 배경이 맞지 않고, 받는 쪽 환경도 알 수 없다.
# 기분 척도·감정 카테고리 색은 원래 테마 공통이라 theme에서 직접 쓴다.
_LIGHT = theme.LIGHT

_TEMPLATE_SECTIONS = (
    ("event_text", "무슨 일이 있었나요"),
    ("emotion_text", "어떤 감정을 느꼈나요"),
    ("thought_text", "어떤 생각이 들었나요"),
)


# ── 자료 모으기 ───────────────────────────────────────────────

def gather(diary_repo, tag_repo, *, start=None, end=None,
           favorites_only=False, scope_label="전체 기간"):
    """내보낼 일기와 통계를 모은다. start/end는 'YYYY-MM-DD' 문자열."""
    rows = diary_repo.search(date=None, favorites_only=favorites_only,
                             sort_by="date", ascending=True)
    if start or end:
        low = start or "0000-00-00"
        high = end or "9999-99-99"
        rows = [row for row in rows if low <= row["date"] <= high]

    entries = []
    for row in rows:
        entries.append({
            "row": row,
            "tags": tag_repo.tags_for(row["id"]),
        })

    span_start = start or (entries[0]["row"]["date"] if entries else None)
    span_end = end or (entries[-1]["row"]["date"] if entries else None)

    moods = [item["row"]["mood_scale"] for item in entries]
    average = sum(moods) / len(moods) if moods else None
    positive = sum(1 for value in moods if value > 0)
    negative = sum(1 for value in moods if value < 0)
    neutral = len(moods) - positive - negative

    category_counts = {}
    for item in entries:
        for tag in item["tags"]:
            category_counts[tag["category"]] = (
                category_counts.get(tag["category"], 0) + tag["count"])
    word_counts = {}
    for item in entries:
        for tag in item["tags"]:
            word_counts[tag["word"]] = (
                word_counts.get(tag["word"], 0) + tag["count"])
    top_words = sorted(word_counts.items(),
                       key=lambda kv: (-kv[1], kv[0]))[:3]

    return {
        "scope_label": scope_label,
        "start": span_start,
        "end": span_end,
        "entries": entries,
        "count": len(entries),
        "average": average,
        "summary": analysis.mood_summary_sentence(positive, neutral, negative),
        "category_counts": category_counts,
        "top_words": top_words,
        "generated_at": datetime.now(),
    }


# ── HTML 만들기 ───────────────────────────────────────────────

def _esc(text) -> str:
    return html_mod.escape(str(text or ""))


def _paragraphs(text: str) -> str:
    """줄바꿈을 살려 문단으로. 빈 줄은 문단 구분으로 본다."""
    body = _esc(text).replace("\n", "<br>")
    return f"<p class='body'>{body}</p>" if body else ""


def _top_words_sentence(top_words) -> str:
    if not top_words:
        return ""
    words = ", ".join(f"'{word}'" for word, _count in top_words)
    code = ord(top_words[-1][0][-1]) - 0xAC00
    josa = "을" if 0 <= code < 11172 and code % 28 else "를"
    return f"{words}{josa} 가장 많이 사용했어요."


def _card(inner: str, extra_class: str = "") -> str:
    """카드 한 장.

    div가 아니라 표로 감싼다. PDF를 그리는 QTextDocument는 div의 배경·
    테두리를 거의 무시하지만 표의 것은 그려 주기 때문이다. 브라우저에서는
    CSS 클래스가 그대로 먹어 둥근 모서리까지 살아난다.
    """
    return (f"<table class='card {extra_class}' width='100%'"
            f" cellpadding='14' cellspacing='0' border='0'"
            f" bgcolor='{_LIGHT['CARD']}'><tr><td>{inner}</td></tr></table>")


def entry_anchor(index: int) -> str:
    """목록에서 그 일기 쪽으로 건너뛸 때 쓰는 이름."""
    return f"entry{index}"


def _pdf_list_row(item, anchor: str = "", link: str = "") -> str:
    """PDF용 리스트 행 — 날짜·제목·감정 칩·기분·별.

    표로 짠다. QTextDocument는 div의 배경·테두리를 그리지 않는다.
    anchor를 주면 그 자리에 이름표를 심고, link를 주면 제목이 그 이름표로
    건너뛰는 링크가 된다.
    """
    row, tags = item["row"], item["tags"]
    # 칩 사이 공백은 &#160; — 인라인 margin은 QTextDocument가 무시한다
    chips = "&#160;".join(
        f"<span class='chip' style=\"background-color:"
        f" {theme.category_highlight(tag['category'])}\">&#160;"
        f"{_esc(tag['word'])}&#160;</span>"
        for tag in tags[:3])
    star = ("<span class='star'>★</span>" if row["is_favorite"]
            else "<span class='star-off'>☆</span>")
    badge_bg, badge_fg = theme.badge_colors(row["mood_scale"])
    title = _esc(row["title"]) or "(제목 없음)"
    if link:
        title = f"<a class='toc-link' href='#{link}'>{title}</a>"
    if anchor:
        title = f"<a name='{anchor}'></a>{title}"
    chips_cell = (f"<td align='right'>{chips}</td>" if chips else "")
    return (
        f"<table class='list-row' width='100%' cellpadding='7'"
        f" cellspacing='0' border='0' bgcolor='{_LIGHT['CARD']}'><tr>"
        f"<td align='left' width='96' class='row-date'>"
        f"{_esc(row['date'])}</td>"
        f"<td align='left' class='row-title'>{title}</td>"
        f"{chips_cell}"
        f"<td align='right' width='52'><span class='badge'"
        f" style=\"background-color: {badge_bg}; color: {badge_fg}\">&#160;"
        f"{theme.mood_text(row['mood_scale'])}&#160;</span></td>"
        f"<td align='center' width='28'>{star}</td>"
        f"</tr></table>")


def _entry_html(item, index: int = 0) -> str:
    """일기 한 쪽 (image4 배치) — 위에 리스트 행, 아래로 섹션 상자들."""
    row = item["row"]
    if row["mode"] == config.MODE_TEMPLATE:
        blocks = [(title, row[column])
                  for column, title in _TEMPLATE_SECTIONS]
    else:
        blocks = [("오늘의 기록", row["free_text"])]
    sections = "".join(
        f"<div class='section-title'>{title}</div>"
        + _card(_paragraphs(text) or "<p class='body'>&#160;</p>", "box")
        for title, text in blocks)
    return _pdf_list_row(item, anchor=entry_anchor(index)) + sections


def _period_text(report: dict) -> str:
    return (f"{report['start']} ~ {report['end']}"
            if report["start"] else "기록 없음")


def _legend_html(report: dict) -> str:
    return "".join(
        f"<div class='legend'><span class='dot' style=\"background-color:"
        f" {theme.category_color(name, i)}\"></span>{_esc(name)} ·"
        f" {count}회</div>"
        for i, (name, count) in enumerate(
            sorted(report["category_counts"].items(),
                   key=lambda kv: -kv[1])))


def _average_text(report: dict) -> str:
    return ("표시할 기분 기록이 없어요." if report["average"] is None
            else f"평균 {report['average']:+.1f}")


def _page_break() -> str:
    return "<div style='page-break-before: always'></div>"


def _pdf_shell(title: str, inner: str) -> str:
    """PDF용 HTML 껍데기. 일기 한 편의 쪽 수를 잴 때도 같은 스타일이어야
    결과가 맞으므로 한곳에서 만든다."""
    return f"""<!DOCTYPE html>
<html lang='ko'><head><meta charset='utf-8'>
<title>{config.APP_NAME} — {_esc(title)}</title>
<style>
  body {{ background: {_LIGHT['BG']}; color: {_LIGHT['TEXT']};
         font-family: {theme.FONT_STACK_CSS};
         font-size: 14px; margin: 0; padding: 28px; }}
  .wrap {{ max-width: 760px; margin: 0 auto; }}
  h1 {{ font-size: 24px; margin: 0 0 4px; }}
  .sub {{ color: {_LIGHT['TEXT_SUB']}; font-size: 13px; margin-bottom: 20px; }}
  .card {{ background: {_LIGHT['CARD']}; border: 1px solid {_LIGHT['BORDER']};
          border-radius: 14px; margin-bottom: 12px;
          border-collapse: separate; }}
  .card-title {{ font-weight: bold; font-size: 15px; margin-bottom: 10px; }}
  .chart, .gauge {{ max-width: 100%; }}
  .legend {{ font-size: 13px; margin: 3px 0; }}
  .dot {{ display: inline-block; width: 11px; height: 11px;
         border-radius: 3px; margin-right: 6px; }}
  .note {{ color: {_LIGHT['TEXT_SUB']}; font-size: 13px; margin-top: 8px; }}
  .top-words {{ color: {_LIGHT['PRIMARY']}; font-size: 15px;
               font-weight: bold; margin-top: 10px; }}
  .scope-label {{ color: {_LIGHT['TEXT_SUB']}; font-size: 12px; }}
  .scope-value {{ font-size: 16px; font-weight: bold; }}
  .badge {{ font-weight: bold; font-size: 13px;
           border-radius: 6px; padding: 4px 9px; }}
  .star {{ color: {theme.STAR_ON}; }}
  .star-off {{ color: {_LIGHT['STAR_OFF']}; }}
  .chip {{ border-radius: 8px; font-size: 13px; }}
  .list-row {{ border-radius: 10px; border-collapse: separate;
              margin-bottom: 10px; }}
  .row-date {{ color: {_LIGHT['TEXT_SUB']}; font-size: 13px; }}
  .row-title {{ font-size: 15px; }}
  .section-title {{ color: {_LIGHT['PRIMARY']}; font-weight: bold;
                   font-size: 13px; margin: 12px 0 3px; }}
  .box {{ min-height: 90px; }}
  .body {{ margin: 0; line-height: 1.65; white-space: pre-wrap; }}
  .empty {{ color: {_LIGHT['TEXT_SUB']}; text-align: center; padding: 40px 0; }}
  .toc-row {{ border-radius: 10px; border-collapse: separate;
             margin-bottom: 5px; }}
  .toc-head {{ color: {_LIGHT['TEXT_SUB']}; font-weight: bold;
              font-size: 12px; }}
  .toc-date {{ color: {_LIGHT['TEXT_SUB']}; font-size: 13px; }}
  .toc-title {{ font-size: 14px; }}
  .toc-link {{ color: {_LIGHT['PRIMARY']}; font-weight: bold; }}
</style></head><body><div class='wrap'>
{inner}
</div></body></html>"""


def _toc_row(cells: str, background: str) -> str:
    """목록 한 줄. 앱 리스트 뷰의 카드 행을 종이에 옮긴 모양."""
    return (f"<table class='toc-row' width='100%' cellpadding='7'"
            f" cellspacing='0' border='0' bgcolor='{background}'>"
            f"<tr>{cells}</tr></table>")


def _toc_html(report: dict) -> str:
    """목록 쪽. 맨 위는 '날짜 / 제목' 구분 행이고, 그 아래로 일기가 날짜
    오름차순으로 놓인다. 제목은 그 일기 쪽으로 건너뛰는 링크다."""
    rows = [_toc_row(
        "<td align='left' width='96' class='toc-head'>날짜</td>"
        "<td align='left' class='toc-head'>제목</td>",
        _LIGHT['BORDER'])]
    for index, item in enumerate(report["entries"]):
        row = item["row"]
        star = ("<span class='star'>★</span>" if row["is_favorite"]
                else "<span class='star-off'>☆</span>")
        badge_bg, badge_fg = theme.badge_colors(row["mood_scale"])
        rows.append(_toc_row(
            f"<td align='left' width='96' class='toc-date'>"
            f"{_esc(row['date'])}</td>"
            f"<td align='left' class='toc-title'>"
            f"<a class='toc-link' href='#{entry_anchor(index)}'>"
            f"{_esc(row['title']) or '(제목 없음)'}</a></td>"
            f"<td align='right' width='52'><span class='badge'"
            f" style=\"background-color: {badge_bg};"
            f" color: {badge_fg}\">&#160;"
            f"{theme.mood_text(row['mood_scale'])}&#160;</span></td>"
            f"<td align='center' width='28'>{star}</td>",
            _LIGHT['CARD']))
    return "".join(rows)


def build_pdf_html(report: dict, pie_image: str = "", gauge_image: str = "",
                   ) -> str:
    """PDF용 HTML. 1쪽 분석, 2쪽 목록, 그다음부터 일기가 한 편씩."""
    period = _period_text(report)
    legend = _legend_html(report)
    average_text = _average_text(report)
    # width 속성을 함께 준다 — QTextDocument는 CSS의 max-width를 안 본다
    pie_tag = (f"<img class='chart' width='210' src='{pie_image}'>"
               if pie_image else "")
    gauge_tag = (f"<img class='gauge' width='440' src='{gauge_image}'>"
                 if gauge_image else "")
    # 일기는 한 쪽에 하나 — 앞에 강제 쪽 나눔을 둔다
    entries_html = "".join(
        _page_break() + _entry_html(item, index)
        for index, item in enumerate(report["entries"]))

    scope_card = _card(
        "<table width='100%' cellspacing='0' cellpadding='0' border='0'><tr>"
        "<td align='left' width='150'>"
        "<div class='scope-label'>범위</div>"
        f"<div class='scope-value'>{_esc(report['scope_label'])}</div></td>"
        "<td align='left'>"
        "<div class='scope-label'>기간</div>"
        f"<div class='scope-value'>{_esc(period)}</div></td>"
        "<td align='left' width='90'>"
        "<div class='scope-label'>일기</div>"
        f"<div class='scope-value'>{report['count']}개</div></td>"
        "</tr></table>", "scope")

    emotion_card = _card(
        "<div class='card-title'>이런 감정들을 많이 느꼈어요</div>"
        f"<table width='100%' cellspacing='0' cellpadding='0' border='0'><tr>"
        f"<td width='230' align='left'>{pie_tag}</td>"
        f"<td align='left' valign='middle'>{legend}</td></tr></table>"
        f"<div class='top-words'>"
        f"{_esc(_top_words_sentence(report['top_words']))}</div>")
    mood_card = _card(
        "<div class='card-title'>기간 평균 기분</div>"
        # 이미지를 블록으로 감싸지 않으면 QTextDocument가 제목 줄에 얹는다
        f"<div>{gauge_tag}</div><div>{_esc(average_text)}</div>"
        f"<div class='note'>{_esc(report['summary'])}</div>")

    return _pdf_shell(
        period,
        f"""  <h1>{config.APP_NAME}</h1>
  {scope_card}
  {emotion_card}
  {mood_card}
{_page_break()}
  <h1>목록</h1>
  <div class='sub'>제목을 누르면 그 일기로 넘어가요.</div>
  {_toc_html(report)}
  {entries_html}""")


# ── 페이지형 HTML (사이드바 + 한 장에 일기 하나) ────────────────

def _page_titles(report: dict) -> list:
    """사이드바에 쓸 페이지 이름 — 분석, 적은 일기 보기, 그다음 일기들."""
    titles = ["분석", "적은 일기 보기"]
    titles += [(item["row"]["title"] or "(제목 없음)")
               for item in report["entries"]]
    return titles


def _slash_date(date_text: str) -> str:
    """'2026-07-19' → '2026/07/19'."""
    return _esc(date_text).replace("-", "/")


def _nav_html(report: dict) -> str:
    """사이드바 항목. 분석·적은 일기 보기는 같은 서식(초록 굵게)이고,
    일기들은 '적은 일기 보기' 아래에 들여쓴다."""
    items = [
        "<button class='nav-item section active' data-page='0'>"
        "<span class='nav-label'>분석</span></button>",
        "<button class='nav-item section' data-page='1'>"
        "<span class='nav-label'>적은 일기 보기</span></button>"]
    for index, item in enumerate(report["entries"], start=2):
        row = item["row"]
        items.append(
            f"<button class='nav-item sub' data-page='{index}'>"
            f"<span class='nav-label'>"
            f"{_esc(row['title']) or '(제목 없음)'}</span>"
            f"<span class='nav-date'>{_slash_date(row['date'])}</span>"
            "</button>")
    return "".join(items)


def _list_row_html(item, page_index=None) -> str:
    """앱 '적은 일기 보기' 리스트 뷰의 행 — 날짜·제목·감정 칩·기분·별.

    page_index를 주면 그 일기 쪽으로 넘어가는 버튼이 된다.
    """
    row, tags = item["row"], item["tags"]
    chips = "".join(
        f"<span class='chip' style=\"background-color:"
        f" {theme.category_highlight(tag['category'])}\">"
        f"{_esc(tag['word'])}</span>"
        for tag in tags[:3])
    star = ("<span class='star'>★</span>" if row["is_favorite"]
            else "<span class='star-off'>☆</span>")
    badge_bg, badge_fg = theme.badge_colors(row["mood_scale"])
    tag_name, attrs = ("div", "")
    if page_index is not None:
        tag_name = "button"
        attrs = f" data-page='{page_index}'"
    return (
        f"<{tag_name} class='list-row'{attrs}>"
        f"<span class='row-date'>{_esc(row['date'])}</span>"
        f"<span class='row-title'>"
        f"{_esc(row['title']) or '(제목 없음)'}</span>"
        f"<span class='row-chips'>{chips}</span>"
        f"<span class='badge' style=\"background-color: {badge_bg};"
        f" color: {badge_fg}\">"
        f"{theme.mood_text(row['mood_scale'])}</span>"
        f"{star}</{tag_name}>")


def _scope_card(report: dict) -> str:
    """분석 쪽 맨 위 — 내보낸 범위와 일기 개수를 한 섹션으로."""
    return f"""
    <div class='card scope'>
      <div class='scope-item'>
        <div class='scope-label'>범위</div>
        <div class='scope-value'>{_esc(report['scope_label'])}</div>
      </div>
      <div class='scope-item'>
        <div class='scope-label'>기간</div>
        <div class='scope-value'>{_esc(_period_text(report))}</div>
      </div>
      <div class='scope-item'>
        <div class='scope-label'>일기</div>
        <div class='scope-value'>{report['count']}개</div>
      </div>
    </div>"""


def _analysis_page(report: dict, pie_image: str, gauge_image: str) -> str:
    pie_tag = (f"<img class='chart' src='{pie_image}' alt='감정 분포'>"
               if pie_image else "")
    gauge_tag = (f"<img class='gauge' src='{gauge_image}' alt='평균 기분'>"
                 if gauge_image else "")
    return f"""
    <div class='page-head'><h1>분석</h1></div>
    {_scope_card(report)}
    <div class='card'>
      <div class='card-title'>이런 감정들을 많이 느꼈어요</div>
      <div class='chart-row'>
        <div class='chart-box'>{pie_tag}</div>
        <div class='legend-box'>{_legend_html(report)}</div>
      </div>
      <div class='top-words'>{_esc(_top_words_sentence(report['top_words']))}</div>
    </div>
    <div class='card'>
      <div class='card-title'>기간 평균 기분</div>
      {gauge_tag}
      <div class='avg'>{_esc(_average_text(report))}</div>
      <div class='note'>{_esc(report['summary'])}</div>
    </div>"""


def _list_page(report: dict) -> str:
    """앱의 '적은 일기 보기' 리스트 뷰를 옮긴 쪽. 행을 누르면 그 일기로."""
    rows = "".join(_list_row_html(item, index)
                   for index, item in enumerate(report["entries"], start=2))
    if not rows:
        rows = "<div class='empty'>이 범위에 적은 일기가 없어요.</div>"
    return f"""
    <div class='page-head'>
      <h1>적은 일기 보기</h1>
      <div class='sub'>일기 {report['count']}개 · 눌러서 펼쳐 보기</div>
    </div>
    <div class='list'>{rows}</div>"""


def _entry_page(item) -> str:
    """일기 한 편 (image4 배치) — 위에 리스트 행, 아래로 섹션 상자들."""
    row = item["row"]
    if row["mode"] == config.MODE_TEMPLATE:
        blocks = [(title, row[column])
                  for column, title in _TEMPLATE_SECTIONS]
    else:
        blocks = [("오늘의 기록", row["free_text"])]
    sections = "".join(
        f"<div class='section'><div class='section-title'>{title}</div>"
        f"<div class='section-box'>"
        f"{_paragraphs(text) or '<p class=body></p>'}</div></div>"
        for title, text in blocks)
    return f"<div class='list'>{_list_row_html(item)}</div>{sections}"


def build_paged_html(report: dict, pie_image: str = "",
                     gauge_image: str = "") -> str:
    """왼쪽 사이드바로 넘기는 페이지형 HTML.

    1쪽 분석, 2쪽 적은 일기 보기, 그 뒤로 일기 한 편씩 날짜 오름차순.
    브라우저에서 열어 보는 용도라 자바스크립트로 페이지를 전환한다
    (파일 하나로 완결).
    """
    pages = [_analysis_page(report, pie_image, gauge_image),
             _list_page(report)]
    pages += [_entry_page(item) for item in report["entries"]]
    pages_html = "".join(
        f"<section class='page{' show' if i == 0 else ''}'"
        f" data-page='{i}'>{body}</section>"
        for i, body in enumerate(pages))

    return f"""<!DOCTYPE html>
<html lang='ko'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{config.APP_NAME} — {_esc(_period_text(report))}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: {_LIGHT['BG']}; color: {_LIGHT['TEXT']};
    font-family: {theme.FONT_STACK_CSS};
    font-size: 14px; }}
  .layout {{ display: flex; min-height: 100vh; align-items: stretch; }}

  .sidebar {{ width: 268px; flex: none; background: {_LIGHT['CARD']};
    border-right: 1px solid {_LIGHT['BORDER']}; padding: 16px 14px;
    position: sticky; top: 0; height: 100vh; overflow-y: auto; }}
  .sidebar h2 {{ font-size: 16px; margin: 0 0 4px; }}
  .sidebar .sub {{ color: {_LIGHT['TEXT_SUB']}; font-size: 12px;
    margin-bottom: 14px; }}
  .side-head {{ display: flex; justify-content: flex-end;
    margin-bottom: 6px; }}
  .toggle {{ width: 30px; height: 30px; flex: none; cursor: pointer;
    border: 1px solid {_LIGHT['BORDER']}; border-radius: 15px;
    background: {_LIGHT['CARD']}; color: {_LIGHT['TEXT']}; font: inherit;
    font-size: 12px; line-height: 1; }}
  .toggle:hover {{ background: {_LIGHT['BORDER']}; }}
  .nav-item {{ display: flex; align-items: baseline; gap: 8px; width: 100%;
    background: none; border: none; border-radius: 8px; padding: 9px 10px;
    margin-bottom: 2px; font: inherit; color: {_LIGHT['TEXT']};
    text-align: left; cursor: pointer; }}
  .nav-item:hover {{ background: {_LIGHT['BORDER']}; }}
  .nav-item.active {{ background: {_LIGHT['PRIMARY']}; color: #FFFFFF;
    font-weight: bold; }}
  /* 분석·적은 일기 보기는 같은 서식 (세이지 그린 굵게) */
  .nav-item.section {{ color: {_LIGHT['PRIMARY']}; font-weight: bold; }}
  /* 활성일 때는 초록 배경이라 글자는 흰색이어야 읽힌다 */
  .nav-item.section.active {{ color: #FFFFFF; }}
  .nav-item.sub {{ margin-left: 16px; width: calc(100% - 16px);
    font-size: 13px; }}
  .nav-label {{ white-space: nowrap; overflow: hidden;
    text-overflow: ellipsis; }}
  .nav-date {{ flex: none; margin-left: auto; font-size: 12px; opacity: .75;
    font-variant-numeric: tabular-nums; }}

  /* 접힌 상태 — 펼침 버튼만 남긴다 */
  .layout.collapsed .sidebar {{ width: 60px; padding: 16px 14px; }}
  .layout.collapsed .sidebar h2,
  .layout.collapsed .sidebar .sub,
  .layout.collapsed .nav-item {{ display: none; }}
  .layout.collapsed .side-head {{ justify-content: center; }}

  main {{ flex: 1 1 auto; padding: 34px 40px; max-width: 860px; }}
  .page {{ display: none; }}
  .page.show {{ display: block; }}
  .page-head {{ margin-bottom: 18px; }}
  h1 {{ font-size: 25px; margin: 0 0 4px; }}
  .sub {{ color: {_LIGHT['TEXT_SUB']}; font-size: 13px; }}
  .card {{ background: {_LIGHT['CARD']}; border: 1px solid {_LIGHT['BORDER']};
    border-radius: 14px; padding: 20px 22px; margin-bottom: 14px; }}
  .card-title {{ font-weight: bold; font-size: 15px; margin-bottom: 12px; }}
  .chart-row {{ display: flex; gap: 24px; align-items: center;
    flex-wrap: wrap; }}
  .chart {{ width: 210px; max-width: 100%; }}
  .gauge {{ width: 100%; max-width: 460px; }}
  .legend {{ font-size: 13px; margin: 4px 0; }}
  .dot {{ display: inline-block; width: 11px; height: 11px;
    border-radius: 3px; margin-right: 7px; }}
  .avg {{ margin-top: 6px; }}
  .note {{ color: {_LIGHT['TEXT_SUB']}; font-size: 13px; margin-top: 10px; }}
  .top-words {{ color: {_LIGHT['PRIMARY']}; font-size: 16px;
    font-weight: bold; margin-top: 12px; }}

  /* 범위·기간·일기 개수 (분석 쪽 맨 위) */
  .scope {{ display: flex; gap: 34px; flex-wrap: wrap; }}
  .scope-label {{ color: {_LIGHT['TEXT_SUB']}; font-size: 12px;
    margin-bottom: 3px; }}
  .scope-value {{ font-size: 17px; font-weight: bold; }}

  /* 앱 리스트 뷰의 행 */
  .list {{ display: flex; flex-direction: column; gap: 8px; }}
  .list-row {{ display: flex; align-items: center; gap: 12px; width: 100%;
    background: {_LIGHT['CARD']}; border: 1px solid {_LIGHT['BORDER']};
    border-radius: 12px; padding: 12px 16px; font: inherit;
    color: {_LIGHT['TEXT']}; text-align: left; }}
  button.list-row {{ cursor: pointer; }}
  button.list-row:hover {{ border-color: {_LIGHT['PRIMARY']}; }}
  .row-date {{ flex: none; color: {_LIGHT['TEXT_SUB']}; font-size: 13px;
    font-variant-numeric: tabular-nums; }}
  .row-title {{ flex: 1 1 auto; font-size: 15px; font-weight: bold;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .row-chips {{ flex: none; display: flex; gap: 6px; }}
  .badge {{ flex: none; font-weight: bold; font-size: 13px;
    border-radius: 6px; padding: 5px 11px; }}
  .star {{ flex: none; color: {theme.STAR_ON}; }}
  .star-off {{ flex: none; color: {_LIGHT['STAR_OFF']}; }}
  .chip {{ border-radius: 8px; padding: 3px 10px; font-size: 13px;
    white-space: nowrap; }}

  .section {{ margin-top: 18px; }}
  .section-title {{ color: {_LIGHT['PRIMARY']}; font-weight: bold;
    font-size: 13px; margin-bottom: 6px; }}
  .section-box {{ background: {_LIGHT['CARD']};
    border: 1px solid {_LIGHT['BORDER']}; border-radius: 12px;
    padding: 16px 18px; min-height: 96px; }}
  .body {{ margin: 0; line-height: 1.75; white-space: pre-wrap; }}
  .empty {{ color: {_LIGHT['TEXT_SUB']}; padding: 30px 0; }}
  .foot {{ color: {_LIGHT['TEXT_FAINT']}; font-size: 12px; margin-top: 26px; }}

  /* 창이 좁아져도 사이드바는 왼쪽에 그대로 둔다 — 접는 건 버튼으로만 */
  @media (max-width: 720px) {{
    main {{ padding: 22px 18px; }}
  }}
  /* 인쇄할 땐 사이드바를 빼고 모든 쪽을 한 장씩 이어서 낸다 */
  @media print {{
    .sidebar {{ display: none; }}
    .page {{ display: block; page-break-after: always; }}
    main {{ max-width: none; padding: 0; }}
  }}
</style></head><body>
<div class='layout'>
  <nav class='sidebar'>
    <div class='side-head'>
      <button class='toggle' title='메뉴 접기/펼치기'>◀</button>
    </div>
    <h2>{config.APP_NAME}</h2>
    <div class='sub'>{_esc(_period_text(report))}</div>
    {_nav_html(report)}
  </nav>
  <main>
    {pages_html}
    <div class='foot'>{config.APP_NAME}에서
      {report['generated_at']:%Y-%m-%d} 내보냄</div>
  </main>
</div>
<script>
  const layout = document.querySelector('.layout');
  const navItems = document.querySelectorAll('.nav-item');
  const pages = document.querySelectorAll('.page');

  // 사이드바는 항상 펼친 채로 시작하고, 버튼을 눌렀을 때만 접힌다
  const toggle = document.querySelector('.toggle');
  toggle.addEventListener('click', () => {{
    const collapsed = layout.classList.toggle('collapsed');
    toggle.textContent = collapsed ? '\\u25B6' : '\\u25C0';
  }});

  function show(target) {{
    pages.forEach(p => p.classList.toggle('show', p.dataset.page === target));
    navItems.forEach(b => b.classList.toggle('active',
      b.dataset.page === target));
    window.scrollTo(0, 0);
  }}
  // 사이드바 항목과 '적은 일기 보기'의 각 행 모두 같은 이동을 쓴다
  document.querySelectorAll('[data-page]').forEach(el => {{
    if (el.tagName === 'BUTTON') {{
      el.addEventListener('click', () => show(el.dataset.page));
    }}
  }});
</script>
</body></html>"""


# ── 파일로 쓰기 ───────────────────────────────────────────────

def write_html(path, html_text: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html_text)


def _pdf_writer(path):
    from PySide6.QtGui import QPageSize, QPdfWriter
    from PySide6.QtCore import QMarginsF

    writer = QPdfWriter(str(path))
    writer.setPageSize(QPageSize(QPageSize.A4))
    writer.setPageMargins(QMarginsF(12, 12, 12, 12))
    writer.setResolution(96)
    return writer


def _document(html_text: str, writer):
    from PySide6.QtCore import QSizeF
    from PySide6.QtGui import QTextDocument

    document = QTextDocument()
    document.setDefaultFont(_pdf_font())
    document.setHtml(html_text)
    document.setPageSize(QSizeF(writer.width(), writer.height()))
    return document


def write_pdf(path, report: dict, pie_image: str = "",
              gauge_image: str = "") -> None:
    """PDF로 저장한다.

    목록은 쪽 번호 대신 링크로 넘어가므로, 쪽 수를 미리 잴 필요가 없다.
    """
    writer = _pdf_writer(path)
    _document(build_pdf_html(report, pie_image, gauge_image),
              writer).print_(writer)


def _pdf_font():
    # 시스템에 있는 한글 폰트를 쓴다 (동봉하지 않음) — theme.FONT_STACK 참고
    return theme.qfont(10)


def default_filename(report: dict, extension: str) -> str:
    """감정일기_2026-07-20.pdf 형태의 기본 파일명."""
    stamp = report.get("start") or date.today().isoformat()
    return f"{config.APP_NAME}_{stamp}.{extension}"
