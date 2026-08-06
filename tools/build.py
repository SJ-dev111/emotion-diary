"""배포본 빌드 — 아이콘·라이선스 준비부터 zip까지 한 번에.

실행: python tools/build.py
결과: dist/EmotionDiary/            (압축을 푼 모습 그대로)
      dist/EmotionDiary-1.0.0-win64.zip
"""
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import config  # noqa: E402

IS_MACOS = config.is_macos()

DIST = ROOT / "dist"
BUILD = ROOT / "build"
# macOS는 .app 번들, Windows는 폴더 + .exe
APP_DIR = DIST / (f"{config.APP_NAME_EN}.app" if IS_MACOS
                  else config.APP_NAME_EN)
# 라이선스·설명서를 넣을 자리. .app은 안이 정해진 구조라 Resources 아래 둔다
EXTRAS_DIR = (APP_DIR / "Contents" / "Resources") if IS_MACOS else APP_DIR
SPEC = ROOT / "emotion_diary.spec"
LICENSES = ROOT / "LICENSES"
README_SRC = ROOT / "packaging" / "README.txt"
VERSION_INFO = ROOT / "packaging" / "version_info.txt"
PLATFORM_TAG = "macOS-arm64" if IS_MACOS else "win64"


def step(text: str) -> None:
    print(f"\n▶ {text}")


def folder_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def mb(size: int) -> str:
    return f"{size / 1024 / 1024:.1f} MB"


def check_version_match() -> None:
    """version_info.txt의 버전이 config.APP_VERSION과 어긋나면 멈춘다.

    이 파일은 Windows exe의 속성(자세히 탭)에만 쓰이므로 macOS에서는
    확인할 것이 없다.
    """
    if IS_MACOS:
        return
    text = VERSION_INFO.read_text(encoding="utf-8")
    found = set(re.findall(r"'(?:File|Product)Version', '([^']+)'", text))
    if found != {config.APP_VERSION}:
        raise SystemExit(
            f"버전이 어긋납니다: config={config.APP_VERSION}, "
            f"version_info.txt={sorted(found)}\n"
            f"{VERSION_INFO} 를 맞춰 주세요.")


def ensure_icon() -> None:
    # Windows는 .ico, macOS는 .icns를 쓴다 (make_icon.py가 둘 다 만든다)
    icon = config.asset_path("app_icon.icns" if IS_MACOS else "app_icon.ico")
    if icon.exists():
        print(f"  아이콘 있음 — {icon.name} ({icon.stat().st_size:,} bytes)")
        return
    print(f"  {icon.name} 이 없어 새로 그립니다")
    subprocess.run([sys.executable, str(ROOT / "tools" / "make_icon.py")],
                   check=True, cwd=ROOT)
    if not icon.exists():
        raise SystemExit(f"아이콘을 만들지 못했습니다: {icon}")


def ensure_licenses() -> None:
    needed = ["LGPL-3.0.txt", "GPL-3.0.txt", "NOTICE.txt"]
    missing = [n for n in needed if not (LICENSES / n).exists()]
    if not missing:
        print(f"  라이선스 {len(needed)}개 준비됨")
        return
    if "NOTICE.txt" in missing:
        raise SystemExit(f"LICENSES/NOTICE.txt 가 없습니다 (직접 작성하는 파일)")
    print(f"  {missing} 가 없어 내려받습니다")
    subprocess.run([sys.executable, str(ROOT / "tools" / "fetch_licenses.py")],
                   check=True, cwd=ROOT)


def clean() -> None:
    for path in (BUILD, DIST):
        if path.exists():
            shutil.rmtree(path)
            print(f"  지움 {path.name}/")


def app_binary() -> Path:
    """실제로 실행되는 파일. macOS는 .app 안쪽에 들어 있다."""
    if IS_MACOS:
        return APP_DIR / "Contents" / "MacOS" / config.APP_NAME_EN
    return APP_DIR / f"{config.APP_NAME_EN}.exe"


def run_pyinstaller() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
         str(SPEC)],
        cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(f"PyInstaller 실패 (코드 {result.returncode})")
    if not app_binary().exists():
        raise SystemExit(f"실행 파일이 만들어지지 않았습니다: {app_binary()}")


def copy_extras() -> None:
    EXTRAS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copytree(LICENSES, EXTRAS_DIR / "LICENSES", dirs_exist_ok=True)
    shutil.copy2(README_SRC, EXTRAS_DIR / "README.txt")
    print(f"  LICENSES/, README.txt → {EXTRAS_DIR.name}/")




def make_zip() -> Path:
    name = f"{config.APP_NAME_EN}-{config.APP_VERSION}-{PLATFORM_TAG}.zip"
    target = DIST / name
    if target.exists():
        target.unlink()

    if IS_MACOS:
        # 파이썬 zipfile로 .app을 담으면 실행 권한과 심볼릭 링크가 사라져
        # 받는 쪽에서 열리지 않는다. macOS 기본 도구인 ditto는 그것을 지킨다.
        result = subprocess.run(
            ["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent",
             str(APP_DIR), str(target)])
        if result.returncode != 0:
            raise SystemExit(f"ditto 압축 실패 (코드 {result.returncode})")
    else:
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED,
                             compresslevel=9) as archive:
            for file in sorted(APP_DIR.rglob("*")):
                if file.is_file():
                    # 풀면 EmotionDiary/ 폴더가 생기도록 경로를 잡는다
                    archive.write(file, file.relative_to(DIST))
    return target


def main() -> None:
    print(f"감정일기 {config.APP_VERSION} 배포본 빌드")

    step("준비 확인")
    check_version_match()
    ensure_icon()
    ensure_licenses()

    step("이전 빌드 정리")
    clean()

    step("PyInstaller 실행 (몇 분 걸립니다)")
    run_pyinstaller()

    step("라이선스·설명서 넣기")
    copy_extras()

    step("압축")
    archive = make_zip()

    files = sum(1 for f in APP_DIR.rglob("*") if f.is_file())
    print(f"""
빌드 완료
  {'번들' if IS_MACOS else '폴더'} : {APP_DIR}
         {mb(folder_size(APP_DIR))}, 파일 {files:,}개
  zip  : {archive.name}
         {mb(archive.stat().st_size)}
""")
    if IS_MACOS:
        print(f"""▶ 실행할 것
  {APP_DIR}   (Finder에서 더블클릭)

  ※ 서명하지 않은 앱이라 처음 열 때 '개발자를 확인할 수 없음' 경고가 뜹니다.
     앱에 마우스 오른쪽 → '열기' → 다시 '열기'를 누르면 실행되고,
     그 뒤로는 그냥 더블클릭하면 됩니다.
  ※ Apple Silicon(M1 이후) 전용입니다.""")
    else:
        print(f"""▶ 실행할 파일
  {app_binary()}

  ※ dist/ 안의 것을 실행하세요. build/ 폴더에도 같은 이름의 exe가 생기지만
     그것은 라이브러리가 빠진 중간 산출물이라 열리지 않습니다
     ("Failed to load Python DLL python312.dll").
  ※ exe만 따로 꺼내도 옆의 _internal 폴더를 못 찾아 같은 오류가 납니다.
     남에게 줄 때는 위 zip을 통째로 건네세요.""")


if __name__ == "__main__":
    main()
