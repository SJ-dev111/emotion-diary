"""저장 경로 규칙 테스트.

배포본은 사용자별 앱 데이터 폴더를, 개발 중에는 프로젝트 루트를 쓴다.
개발 경로가 바뀌면 쓰던 일기를 못 찾게 되므로 그 점을 고정해 둔다.
"""
import unittest
from pathlib import Path
from unittest import mock

from app import config


class DataDirTest(unittest.TestCase):
    def test_dev_uses_project_root(self):
        """개발 중(frozen 아님)에는 프로젝트 루트 — 지금까지와 같아야 한다."""
        with mock.patch.object(config.sys, "frozen", False, create=True):
            expected = Path(config.__file__).resolve().parent.parent
            self.assertEqual(config.data_dir(), expected)

    def test_frozen_windows_uses_local_appdata(self):
        with mock.patch.object(config.sys, "frozen", True, create=True), \
                mock.patch.object(config.sys, "platform", "win32"), \
                mock.patch.dict(config.os.environ,
                                {"LOCALAPPDATA": r"C:\Fake\Local"}):
            self.assertEqual(config.data_dir(),
                             Path(r"C:\Fake\Local") / config.APP_NAME)

    def test_frozen_macos_uses_application_support(self):
        """macOS 배포본은 ~/Library/Application Support 아래를 쓴다."""
        import tempfile
        home = Path(tempfile.mkdtemp())
        with mock.patch.object(config.sys, "frozen", True, create=True), \
                mock.patch.object(config.sys, "platform", "darwin"), \
                mock.patch.object(config.Path, "home", return_value=home):
            self.assertEqual(
                config.data_dir(),
                home / "Library" / "Application Support" / config.APP_NAME)

    def test_macos_ignores_localappdata(self):
        """Windows 환경변수가 남아 있어도 macOS면 그 경로를 쓰지 않는다."""
        import tempfile
        home = Path(tempfile.mkdtemp())
        with mock.patch.object(config.sys, "frozen", True, create=True), \
                mock.patch.object(config.sys, "platform", "darwin"), \
                mock.patch.dict(config.os.environ,
                                {"LOCALAPPDATA": r"C:\Fake\Local"}), \
                mock.patch.object(config.Path, "home", return_value=home):
            self.assertNotIn("Fake", str(config.data_dir()))

    def test_is_macos_matches_platform(self):
        with mock.patch.object(config.sys, "platform", "darwin"):
            self.assertTrue(config.is_macos())
        with mock.patch.object(config.sys, "platform", "win32"):
            self.assertFalse(config.is_macos())

    def test_frozen_falls_back_when_env_missing(self):
        """LOCALAPPDATA가 없어도 홈 아래 경로로 이어져야 한다."""
        env = dict(config.os.environ)
        env.pop("LOCALAPPDATA", None)
        with mock.patch.object(config.sys, "frozen", True, create=True), \
                mock.patch.object(config.sys, "platform", "win32"), \
                mock.patch.dict(config.os.environ, env, clear=True), \
                mock.patch.object(config.Path, "home",
                                  return_value=Path(r"C:\Fake\Home")):
            self.assertEqual(
                config.data_dir(),
                Path(r"C:\Fake\Home") / "AppData" / "Local" / config.APP_NAME)

    def test_data_dir_is_created(self):
        import tempfile
        base = Path(tempfile.mkdtemp())
        with mock.patch.object(config.sys, "frozen", True, create=True), \
                mock.patch.object(config.sys, "platform", "win32"), \
                mock.patch.dict(config.os.environ,
                                {"LOCALAPPDATA": str(base)}):
            folder = config.data_dir()
            self.assertTrue(folder.is_dir())

    def test_db_path_sits_in_data_dir(self):
        self.assertEqual(config.db_path(),
                         config.data_dir() / config.DB_FILENAME)


class ExportDirTest(unittest.TestCase):
    def test_prefers_documents(self):
        with mock.patch.object(config.Path, "exists", return_value=True):
            self.assertEqual(config.export_dir(),
                             Path.home() / "Documents")

    def test_falls_back_to_home(self):
        with mock.patch.object(config.Path, "exists", return_value=False):
            self.assertEqual(config.export_dir(), Path.home())

    def test_is_not_the_data_dir(self):
        """숨은 데이터 폴더를 내보내기 기본값으로 쓰면 파일을 못 찾는다."""
        self.assertNotEqual(config.export_dir(), config.data_dir())


if __name__ == "__main__":
    unittest.main()
