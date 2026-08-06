"""감정일기 앱 진입점 (PySide6)."""
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app import config
from app.ui_qt.app_window import AppWindow
from app.ui_qt.style import build_qss


def main() -> None:
    qapp = QApplication(sys.argv)
    # 이름을 정해 두면 창 제목·작업표시줄 묶음과 Qt 표준 경로가 이 앱 것으로
    # 잡힌다. 표시용 이름만 한글로 둔다.
    qapp.setApplicationName(config.APP_NAME_EN)
    qapp.setApplicationDisplayName(config.APP_NAME)
    qapp.setApplicationVersion(config.APP_VERSION)
    qapp.setOrganizationName(config.APP_NAME_EN)

    icon_file = config.asset_path("app_icon.ico")
    if icon_file.exists():
        qapp.setWindowIcon(QIcon(str(icon_file)))

    qapp.setStyleSheet(build_qss())
    window = AppWindow()
    window.show()
    sys.exit(qapp.exec())


if __name__ == "__main__":
    main()
