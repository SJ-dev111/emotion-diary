"""바탕화면 바로가기 만들기.

배포본에서만 뜻이 있다. 소스로 실행할 때는 가리킬 실행 파일이 없어서
`is_supported()`가 False가 되고, UI도 관련 버튼을 감춘다.

    Windows: .lnk 파일 (PowerShell의 WScript.Shell로 만든다)
    macOS  : .app 을 가리키는 심볼릭 링크

macOS에서 Finder 별칭(alias) 대신 심볼릭 링크를 쓰는 이유는, 별칭을
만들려면 osascript로 Finder를 조종해야 하고 그 순간 "'감정일기'가 Finder를
제어하려 합니다" 권한 팝업이 뜨기 때문이다. 링크는 그런 것 없이 더블클릭
으로 앱이 열린다.
"""
import os
import sys
from pathlib import Path

from app import config


class ShortcutError(Exception):
    """바로가기를 만들지 못했을 때."""


def target_path() -> Path | None:
    """바로가기가 가리킬 대상. 배포본이 아니면 None.

    Windows는 exe 자체, macOS는 실행 파일이 아니라 그것을 감싼 .app
    번들을 가리켜야 한다 — Finder에서 앱으로 취급되는 단위가 번들이다.
    """
    if not getattr(sys, "frozen", False):
        return None
    executable = Path(sys.executable).resolve()
    if config.is_macos():
        # .../EmotionDiary.app/Contents/MacOS/EmotionDiary → .../EmotionDiary.app
        for parent in executable.parents:
            if parent.suffix == ".app":
                return parent
        return executable
    return executable


def desktop_dir() -> Path:
    """이 컴퓨터의 바탕화면 폴더.

    Windows에서 바탕화면이 늘 `~/Desktop`인 것은 아니다. OneDrive를 쓰거나
    한국어 환경이면 `~/OneDrive/바탕 화면` 같은 다른 자리로 옮겨져 있다.
    실제 위치는 레지스트리에 적혀 있으므로 그것을 먼저 본다.
    """
    if os.name == "nt":
        try:
            import winreg
            key = (r"Software\Microsoft\Windows\CurrentVersion"
                   r"\Explorer\User Shell Folders")
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
                raw, _ = winreg.QueryValueEx(handle, "Desktop")
            path = Path(os.path.expandvars(raw))
            if path.is_dir():
                return path
        except OSError:
            pass          # 레지스트리를 못 읽으면 아래 기본값으로
    return Path.home() / "Desktop"


def shortcut_path() -> Path:
    """만들어질 바로가기 파일의 경로."""
    suffix = ".lnk" if os.name == "nt" else ""
    return desktop_dir() / f"{config.APP_NAME}{suffix}"


def is_supported() -> bool:
    """이 환경에서 바로가기를 만들 수 있는지."""
    return target_path() is not None and desktop_dir().is_dir()


def exists() -> bool:
    """이미 바탕화면에 바로가기가 있는지."""
    path = shortcut_path()
    # 링크가 깨져 있어도 파일 자체는 있는 것으로 본다 (덮어쓰면 되므로)
    return path.exists() or path.is_symlink()


def create() -> Path:
    """바탕화면에 바로가기를 만들고 그 경로를 돌려준다."""
    target = target_path()
    if target is None:
        raise ShortcutError(
            "소스로 실행 중이라 바로가기를 만들 수 없습니다. "
            "배포본에서 사용해 주세요.")
    desktop = desktop_dir()
    if not desktop.is_dir():
        raise ShortcutError(f"바탕화면 폴더를 찾지 못했습니다: {desktop}")

    path = shortcut_path()
    if os.name == "nt":
        _create_windows(target, path)
    else:
        _create_symlink(target, path)
    return path


# Windows가 바로가기를 만들 때 쓰는 COM 인터페이스들
_CLSID_SHELL_LINK = "{00021401-0000-0000-C000-000000000046}"
_IID_ISHELL_LINK_W = "{000214F9-0000-0000-C000-000000000046}"
_IID_IPERSIST_FILE = "{0000010B-0000-0000-C000-000000000046}"

# 인터페이스가 함수를 늘어놓은 순서. IUnknown의 셋(0~2) 다음부터가 본체다.
_QUERY_INTERFACE, _RELEASE = 0, 2
_SET_DESCRIPTION, _SET_WORKING_DIR = 7, 9
_SET_ICON_LOCATION, _SET_PATH = 17, 20
_PERSIST_SAVE = 6


def _create_windows(target: Path, path: Path) -> None:
    """Windows 바로가기(.lnk)를 COM으로 직접 만든다.

    처음에는 PowerShell의 WScript.Shell을 불렀는데, 그것은 ANSI 시절
    컴포넌트라 **시스템 코드페이지에 없는 글자를 다루지 못한다**. 한국어
    Windows에서는 '감정일기'가 cp949에 있어 넘어갔지만, 영문 Windows에서는
    '????'가 되며 실패했다(공개 저장소 CI가 잡았다). 바로가기 이름만이 아니라
    **대상 경로에 한글이 섞여도** 같은 문제가 생긴다 — 사용자가 한글 폴더에
    풀어 두는 것은 흔한 일이다.

    IShellLinkW는 이름 그대로 유니코드 인터페이스라 코드페이지와 무관하다.
    ctypes로 직접 부르므로 pywin32 같은 의존성도 필요 없고, 프로세스를
    새로 띄우지 않아 콘솔이 번쩍일 일도 없다.
    """
    import ctypes
    from ctypes import POINTER, byref, c_void_p

    ole32 = ctypes.OleDLL("ole32")

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16),
                    ("Data3", ctypes.c_uint16), ("Data4", ctypes.c_ubyte * 8)]

    ole32.CLSIDFromString.argtypes = [ctypes.c_wchar_p, POINTER(GUID)]

    def guid(text: str) -> GUID:
        value = GUID()
        ole32.CLSIDFromString(text, byref(value))
        return value

    def method(pointer, index, *argtypes):
        """인터페이스의 index번째 함수를 부를 수 있게 꺼내 온다."""
        table = ctypes.cast(pointer,
                            POINTER(POINTER(c_void_p))).contents
        proto = ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, *argtypes)
        return proto(table[index])

    def release(pointer):
        table = ctypes.cast(pointer, POINTER(POINTER(c_void_p))).contents
        proto = ctypes.WINFUNCTYPE(ctypes.c_ulong, c_void_p)
        proto(table[_RELEASE])(pointer)

    # Qt가 이미 COM을 켜 두었으면 S_FALSE가 오고, 그때는 우리가 끄지 않는다
    started = ole32.CoInitialize(None) == 0
    try:
        link = c_void_p()
        ole32.CoCreateInstance(
            byref(guid(_CLSID_SHELL_LINK)), None, 1,   # INPROC_SERVER
            byref(guid(_IID_ISHELL_LINK_W)), byref(link))
        try:
            method(link, _SET_PATH, ctypes.c_wchar_p)(link, str(target))
            method(link, _SET_WORKING_DIR, ctypes.c_wchar_p)(
                link, str(target.parent))
            method(link, _SET_ICON_LOCATION, ctypes.c_wchar_p, ctypes.c_int)(
                link, str(target), 0)
            method(link, _SET_DESCRIPTION, ctypes.c_wchar_p)(
                link, config.APP_NAME)

            persist = c_void_p()
            method(link, _QUERY_INTERFACE, POINTER(GUID), POINTER(c_void_p))(
                link, byref(guid(_IID_IPERSIST_FILE)), byref(persist))
            try:
                method(persist, _PERSIST_SAVE, ctypes.c_wchar_p, ctypes.c_int)(
                    persist, str(path), 1)
            finally:
                release(persist)
        finally:
            release(link)
    except OSError as error:
        raise ShortcutError(
            f"바로가기를 만들지 못했습니다.\n\n경로: {path}\n{error}") from error
    finally:
        if started:
            ole32.CoUninitialize()

    if not path.exists():
        raise ShortcutError(f"바로가기가 만들어지지 않았습니다.\n\n경로: {path}")


def _create_symlink(target: Path, path: Path) -> None:
    try:
        if path.exists() or path.is_symlink():
            path.unlink()
        path.symlink_to(target)
    except OSError as error:
        raise ShortcutError(f"바로가기를 만들지 못했습니다: {error}") from error
