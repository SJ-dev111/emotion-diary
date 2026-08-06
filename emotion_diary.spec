# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 설정 — onedir(폴더형) 배포.

단일 exe가 아니라 폴더로 묶는다. Qt 라이브러리가 별도 파일로 남아 사용자가
같은 버전의 다른 빌드로 바꿔 넣을 수 있어야 LGPL v3 조건을 충족한다.

Windows는 폴더 + EmotionDiary.exe, macOS는 EmotionDiary.app 번들로 나온다.
(.app도 속을 보면 폴더라 Qt 라이브러리는 그대로 교체 가능하다.)

빌드는 tools/build.py 로 한다 (아이콘 생성·라이선스 복사·zip까지 처리).
"""
import sys
from pathlib import Path

SPEC_DIR = Path(SPECPATH)
IS_MACOS = sys.platform == "darwin"
ASSETS = SPEC_DIR / "app" / "ui_qt" / "assets"

# 앱이 실제로 쓰는 Qt 모듈은 QtCore·QtGui·QtWidgets 셋뿐이다.
# 나머지는 넣어 봐야 용량만 키우므로 뺀다.
EXCLUDED_QT = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick", "PySide6.QtWebChannel", "PySide6.QtWebSockets",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets",
    "PySide6.QtQuick3D", "PySide6.QtQuickControls2",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic", "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtPositioning",
    "PySide6.QtSerialPort", "PySide6.QtSerialBus",
    "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtHelp", "PySide6.QtDesigner",
    "PySide6.QtUiTools", "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtSvg",
    "PySide6.QtSvgWidgets", "PySide6.QtNetworkAuth", "PySide6.QtRemoteObjects",
    "PySide6.QtScxml", "PySide6.QtSensors", "PySide6.QtSpatialAudio",
    "PySide6.QtStateMachine", "PySide6.QtTextToSpeech", "PySide6.QtConcurrent",
    "PySide6.QtHttpServer", "PySide6.QtGraphs", "PySide6.QtLocation",
]

# 이 앱과 무관한 표준/서드파티 모듈
EXCLUDED_OTHER = [
    "tkinter", "unittest", "pydoc", "doctest", "pdb",
    "numpy", "PIL", "matplotlib", "setuptools", "pip",
]

a = Analysis(
    ["main.py"],
    pathex=[str(SPEC_DIR)],
    binaries=[],
    # 드롭다운 화살표 PNG와 앱 아이콘. config.asset_path()가 여기서 찾는다.
    datas=[("app/ui_qt/assets", "app/ui_qt/assets")],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDED_QT + EXCLUDED_OTHER,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,          # onedir: 라이브러리는 COLLECT로 뺀다
    name="EmotionDiary",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                      # UPX 압축은 백신 오탐을 부른다
    console=False,                  # GUI 앱 — 검은 콘솔 창을 띄우지 않는다
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # 아이콘 형식이 갈린다 — Windows는 .ico, macOS는 .icns만 읽는다.
    # version(파일 속성)은 Windows 전용이라 macOS에서는 넘기지 않는다.
    icon=str(ASSETS / ("app_icon.icns" if IS_MACOS else "app_icon.ico")),
    **({} if IS_MACOS
       else {"version": str(SPEC_DIR / "packaging" / "version_info.txt")}),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="EmotionDiary",
)

if IS_MACOS:
    # macOS는 폴더가 아니라 .app 번들이어야 더블클릭으로 열리고 Dock에도
    # 제대로 뜬다. 속은 여전히 폴더라 Qt 라이브러리는 교체할 수 있다.
    app = BUNDLE(
        coll,
        name="EmotionDiary.app",
        icon=str(ASSETS / "app_icon.icns"),
        bundle_identifier="com.emotiondiary.app",
        version="1.0.0",
        info_plist={
            # Finder·메뉴 막대에 보이는 이름은 한글로
            "CFBundleName": "감정일기",
            "CFBundleDisplayName": "감정일기",
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion": "1.0.0",
            # 레티나 화면에서 흐릿하게 확대되지 않도록
            "NSHighResolutionCapable": True,
            # 문서 기반 앱이 아니라 창 하나로 도는 일반 앱
            "LSApplicationCategoryType": "public.app-category.productivity",
            "NSHumanReadableCopyright": "",
        },
    )
