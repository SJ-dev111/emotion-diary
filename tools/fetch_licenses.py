"""배포본에 넣을 라이선스 전문을 내려받는다.

PySide6 wheel에는 LGPL 전문이 들어 있지 않아(상용 라이선스 참조 파일만
있다) 따로 받아야 한다. LGPL v3는 "GPL v3에 추가 허가를 얹은 것"이라 두
전문을 함께 넣는다 — Qt 공식 배포도 같은 방식이다.

받는 곳은 Qt 소스 저장소(qt/qtbase)의 LICENSES 폴더다. 우리가 재배포하는
것이 Qt이므로, Qt가 자기 배포본에 넣는 바로 그 파일을 쓰는 것이 맞다.
gnu.org 원본은 내용이 같으며 대체 경로로 남겨 두었다.

한 번 받아 두면 LICENSES/ 에 남으므로 다시 실행할 일은 없다.
실행: python tools/fetch_licenses.py
"""
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LICENSES = ROOT / "LICENSES"

_QT = "https://raw.githubusercontent.com/qt/qtbase/dev/LICENSES"

# 파일명: (받을 주소들 — 앞에서부터 시도, 최소 크기)
SOURCES = {
    "LGPL-3.0.txt": (
        [f"{_QT}/LGPL-3.0-only.txt", "https://www.gnu.org/licenses/lgpl-3.0.txt"],
        6000),
    "GPL-3.0.txt": (
        [f"{_QT}/GPL-3.0-only.txt", "https://www.gnu.org/licenses/gpl-3.0.txt"],
        30000),
}


def fetch(name: str, urls: list, min_size: int) -> None:
    target = LICENSES / name
    if target.exists() and target.stat().st_size >= min_size:
        print(f"  건너뜀 {name} (이미 있음, {target.stat().st_size:,} bytes)")
        return

    errors = []
    for url in urls:
        print(f"  받는 중 {name} … ", end="", flush=True)
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                text = response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"실패({type(exc).__name__}), 다음 경로 시도")
            errors.append(f"{url}: {exc}")
            continue
        # 받은 것이 정말 그 라이선스 전문인지 확인하고 저장한다
        if "GNU" not in text[:400] or len(text) < min_size:
            print("받은 내용이 라이선스 전문이 아님, 다음 경로 시도")
            errors.append(f"{url}: 내용 확인 실패 ({len(text)} bytes)")
            continue
        target.write_text(text, encoding="utf-8")
        print(f"{len(text.splitlines()):,}줄 ({len(text):,} bytes)")
        return

    raise SystemExit(
        f"\n{name} 을 받지 못했습니다.\n" + "\n".join(errors)
        + f"\n\n위 주소 중 하나에서 직접 받아 {target} 에 저장해 주세요.")


def main() -> None:
    LICENSES.mkdir(exist_ok=True)
    print(f"라이선스 전문 → {LICENSES}")
    for name, (urls, min_size) in SOURCES.items():
        fetch(name, urls, min_size)
    missing = [n for n in SOURCES if not (LICENSES / n).exists()]
    if missing:
        sys.exit(f"빠진 파일: {missing}")
    print("완료")


if __name__ == "__main__":
    main()
