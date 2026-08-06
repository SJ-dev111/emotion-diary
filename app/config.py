"""앱 전역 상수와 경로."""
import os
import sys
from pathlib import Path

APP_NAME = "감정일기"
APP_NAME_EN = "EmotionDiary"   # exe·배포 폴더 이름 (경로 문제를 피해 영문)
APP_VERSION = "1.0.0"
SCHEMA_VERSION = 1

MOOD_MIN = -10
MOOD_MAX = 10

MODE_TEMPLATE = "template"
MODE_FREE = "free"

DB_FILENAME = "emotion_diary.db"


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def asset_path(*parts: str) -> Path:
    """앱에 딸린 자산(아이콘 등)의 실제 경로.

    PyInstaller로 묶으면 .py가 아카이브 안으로 들어가 __file__ 기준 경로가
    실제 파일을 가리키지 못할 수 있다. 배포본에서는 풀어 놓은 폴더
    (sys._MEIPASS)를 기준으로 잡는다.
    """
    base = Path(getattr(sys, "_MEIPASS", "")) if getattr(
        sys, "frozen", False) else _project_root()
    return base.joinpath("app", "ui_qt", "assets", *parts)


def is_macos() -> bool:
    return sys.platform == "darwin"


def data_dir() -> Path:
    """일기 DB가 놓이는 폴더.

    배포본은 운영체제가 앱 데이터를 두라고 정한 자리를 쓴다. 실행 파일 옆에
    두면 'C:\\Program Files\\'나 '/Applications'처럼 쓰기 권한이 없는 곳에
    설치했을 때 첫 실행부터 DB를 만들지 못한다.

        macOS  : ~/Library/Application Support/감정일기
        Windows: %LOCALAPPDATA%\\감정일기

    개발 중에는 지금까지처럼 프로젝트 루트를 쓴다 — 경로가 바뀌면 쓰던
    일기를 못 찾게 되고, 파일을 바로 열어 보기도 불편해진다.
    """
    if getattr(sys, "frozen", False):
        if is_macos():
            root = Path.home() / "Library" / "Application Support"
        else:
            base = os.environ.get("LOCALAPPDATA")
            root = Path(base) if base else Path.home() / "AppData" / "Local"
        folder = root / APP_NAME
    else:
        folder = _project_root()
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def export_dir() -> Path:
    """내보내기·백업 대화상자가 처음 보여 줄 폴더.

    데이터 폴더는 숨은 경로라 내보낸 파일을 사용자가 찾지 못한다. 저장
    위치는 대화상자에서 직접 고르므로 여기서는 눈에 익은 곳만 제안한다.
    """
    documents = Path.home() / "Documents"
    return documents if documents.exists() else Path.home()


def db_path() -> Path:
    return data_dir() / DB_FILENAME
