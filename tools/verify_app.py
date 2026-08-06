"""빌드한 배포본이 실제로 도는지 확인한다 (화면 없이).

빌드가 됐다고 실행되는 것은 아니라서, 앱을 띄워 저장 경로·감정 인식·
내보내기까지 확인한다. GitHub Actions의 macOS 서버에는 화면이 없으므로
Qt를 offscreen 모드로 돌린다.

개발자에게 Mac이 없어 눈으로 볼 수 없는 만큼, 여기서 최대한 많이 확인한다.

실행: python tools/verify_app.py
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 한국어 Windows 콘솔(cp949)은 '—' 같은 기호를 못 찍고 죽는다.
# 확인 결과보다 출력 때문에 멈추는 일이 없도록 대체 문자로 넘긴다.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

# 화면이 없는 서버에서도 창을 만들 수 있게 한다 (실제 창은 뜨지 않는다)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# 배포본과 같은 조건을 만든다 — frozen이면 앱 데이터 폴더를 쓴다.
# 실제 사용자 홈을 건드리지 않으려고 임시 폴더를 홈인 척 쓰는데, 진짜 홈에
# 있는 것들(Desktop 등)을 만들어 두지 않으면 그것을 찾는 검사가 애먼 데서
# 실패한다.
_fake_home = Path(tempfile.mkdtemp(prefix="verify_home_"))
sys.frozen = True
(_fake_home / "Desktop").mkdir()
if sys.platform == "darwin":
    (_fake_home / "Library" / "Application Support").mkdir(parents=True)
else:
    os.environ["LOCALAPPDATA"] = str(_fake_home / "AppData" / "Local")

from app import config, theme  # noqa: E402

# 홈을 임시 폴더로 돌려, 실제 사용자 일기를 건드리지 않는다
Path.home = staticmethod(lambda: _fake_home)   # type: ignore[method-assign]

failures = []


def check(name, cond, extra=""):
    print(("OK   " if cond else "FAIL ") + name + (f"  {extra}" if extra
                                                   else ""))
    if not cond:
        failures.append(name)


def main() -> None:
    print(f"플랫폼: {sys.platform} | Qt 화면: {os.environ['QT_QPA_PLATFORM']}")
    print(f"임시 홈: {_fake_home}\n")

    from PySide6.QtGui import QFontInfo  # noqa: E402
    from PySide6.QtWidgets import QApplication  # noqa: E402

    qapp = QApplication([])

    from app.services import report  # noqa: E402
    from app.ui_qt.app_window import AppWindow  # noqa: E402
    from app.ui_qt.style import build_qss  # noqa: E402
    from app.ui_qt.widgets.export_dialog import _render_charts  # noqa: E402

    qapp.setStyleSheet(build_qss())

    # 1) 저장 경로가 이 운영체제의 표준 자리인지
    data = config.data_dir()
    if sys.platform == "darwin":
        expected = _fake_home / "Library" / "Application Support" / config.APP_NAME
    else:
        expected = Path(os.environ["LOCALAPPDATA"]) / config.APP_NAME
    check("저장 폴더가 표준 위치", data == expected, str(data))

    # 2) 자산(드롭다운 화살표)이 실제로 읽히는지
    arrow = config.asset_path("arrow_down.png")
    check("화살표 이미지 존재", arrow.exists(), str(arrow))

    # 3) 창을 띄운다 — 여기서 죽으면 실사용에서도 못 연다
    win = AppWindow()
    win.maybe_show_first_run_guide = lambda: None
    win.resize(1200, 800)
    win.show()
    qapp.processEvents()
    check("창 생성", win.isVisible())
    check("DB 파일 생성", config.db_path().exists(),
          f"{config.db_path().stat().st_size:,} bytes")

    # 4) 한글 폰트
    # offscreen 모드는 시스템 폰트를 하나도 읽어 들이지 않는다(화면이 없어
    # 폰트 엔진이 뜨지 않는다). 그래서 '실제로 어떤 폰트로 그려지는지'는
    # 여기서 판정할 수 없고, 폰트 목록이 앱에 제대로 실려 있는지만 본다.
    from PySide6.QtGui import QFontDatabase  # noqa: E402
    has_system_fonts = len(QFontDatabase.families()) > 0
    resolved = QFontInfo(theme.qfont(10)).family()
    if has_system_fonts:
        check("한글 폰트 해석", resolved in theme.FONT_STACK, resolved)
    else:
        print(f"SKIP 한글 폰트 해석 — offscreen이라 시스템 폰트 없음"
              f" (스택 {len(theme.FONT_STACK)}종은 앱에 실려 있음)")
        check("폰트 대체 목록 존재", len(theme.FONT_STACK) >= 5)

    # 5) 일기를 쓰고 감정 인식까지 — 앱의 핵심 흐름
    entry = win.diary_repo.create(
        date="2026-07-28", title="배포본 확인", mood_scale=6,
        event_text="한글이 깨지지 않아야 한다. 겹받침: 앉았다, 훑다.")
    win.tag_repo.replace_tags(entry, [("행복하다", "기쁨", 2)])
    win.show_home()
    qapp.processEvents()
    check("일기 저장·조회", len(win.diary_repo.search()) == 1)

    # 6) 화면 전환이 모두 도는지
    for name, show in (("리스트", win.show_list), ("캘린더", win.show_calendar),
                       ("분석", win.show_analysis), ("단어집", win.show_dictionary),
                       ("편집기", lambda: win.show_editor(origin="home"))):
        show()
        qapp.processEvents()
    check("모든 화면 전환", True)

    # 7) 내보내기 — 차트·HTML·PDF
    gathered = report.gather(win.diary_repo, win.tag_repo, scope_label="전체")
    pie, gauge = _render_charts(gathered)
    check("차트 렌더", pie.startswith("data:image/png;base64,"))

    out = Path(tempfile.mkdtemp(prefix="verify_out_"))
    report.write_html(out / "r.html",
                      report.build_paged_html(gathered, pie, gauge))
    report.write_pdf(out / "r.pdf", gathered, pie, gauge)
    html = (out / "r.html").read_text(encoding="utf-8")
    check("HTML 내보내기", "배포본 확인" in html and "행복하다" in html)
    raw = (out / "r.pdf").read_bytes()
    check("PDF 내보내기", raw[:5] == b"%PDF-" and len(raw) > 5000,
          f"{len(raw):,} bytes")
    # 폰트 임베드는 시스템 폰트가 있어야 일어난다 — offscreen에서는 확인 불가
    if has_system_fonts:
        check("PDF에 한글 폰트 임베드", b"/FontFile" in raw)
    else:
        print("SKIP PDF 폰트 임베드 — offscreen이라 시스템 폰트 없음")

    # 8) 바탕화면 위치 — 운영체제마다 다른 자리라 여기서 본다
    from app.services import shortcut  # noqa: E402
    desktop = shortcut.desktop_dir()
    check("바탕화면 폴더 찾음", desktop.is_dir(), str(desktop))
    check("바로가기 이름", shortcut.shortcut_path().stem == config.APP_NAME)

    # 9) 다크 테마 전환과 저장
    win.nav_bar.dark_button.click()
    qapp.processEvents()
    check("다크 테마 전환", theme.current_theme == "dark")

    win.close()
    print()
    if failures:
        print("VERIFY FAIL:", failures)
        sys.exit(1)
    print("VERIFY OK")


if __name__ == "__main__":
    main()
