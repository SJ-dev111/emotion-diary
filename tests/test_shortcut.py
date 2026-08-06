"""바탕화면 바로가기 서비스."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import config
from app.services import shortcut


class TargetPathTest(unittest.TestCase):
    def test_source_run_has_no_target(self):
        """소스로 실행 중이면 가리킬 실행 파일이 없다."""
        with mock.patch.object(sys, "frozen", False, create=True):
            self.assertIsNone(shortcut.target_path())

    def test_windows_points_at_exe(self):
        exe = Path(r"C:\Apps\EmotionDiary\EmotionDiary.exe")
        with mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.object(sys, "executable", str(exe)), \
                mock.patch.object(config, "is_macos", return_value=False), \
                mock.patch.object(Path, "resolve", lambda self: self):
            self.assertEqual(shortcut.target_path(), exe)

    def test_macos_points_at_bundle_not_binary(self):
        """Finder가 앱으로 다루는 단위는 실행 파일이 아니라 .app 번들이다."""
        binary = Path("/Applications/EmotionDiary.app/Contents/MacOS/"
                      "EmotionDiary")
        with mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.object(sys, "executable", str(binary)), \
                mock.patch.object(config, "is_macos", return_value=True), \
                mock.patch.object(Path, "resolve", lambda self: self):
            self.assertEqual(shortcut.target_path(),
                             Path("/Applications/EmotionDiary.app"))


class DesktopDirTest(unittest.TestCase):
    def test_returns_existing_directory(self):
        """어느 환경에서든 경로 하나는 돌려준다 (없을 수는 있다)."""
        self.assertIsInstance(shortcut.desktop_dir(), Path)

    @unittest.skipUnless(os.name == "nt", "Windows 전용")
    def test_windows_desktop_is_real(self):
        """OneDrive로 옮겨진 바탕화면도 찾아내야 한다."""
        desktop = shortcut.desktop_dir()
        self.assertTrue(desktop.is_dir(), f"바탕화면을 못 찾음: {desktop}")

    @unittest.skipUnless(os.name == "nt", "Windows 전용")
    def test_falls_back_when_registry_unreadable(self):
        with mock.patch("winreg.OpenKey", side_effect=OSError):
            self.assertEqual(shortcut.desktop_dir(),
                             Path.home() / "Desktop")


class ShortcutPathTest(unittest.TestCase):
    def test_name_and_suffix(self):
        with mock.patch.object(shortcut, "desktop_dir",
                               return_value=Path("/desk")):
            path = shortcut.shortcut_path()
        self.assertEqual(path.stem, config.APP_NAME)
        self.assertEqual(path.suffix, ".lnk" if os.name == "nt" else "")


class CreateTest(unittest.TestCase):
    def test_refuses_when_not_frozen(self):
        with mock.patch.object(shortcut, "target_path", return_value=None):
            with self.assertRaises(shortcut.ShortcutError):
                shortcut.create()

    def test_refuses_without_desktop(self):
        missing = Path(tempfile.gettempdir()) / "없는-바탕화면-xyz"
        with mock.patch.object(shortcut, "target_path",
                               return_value=Path("/app")), \
                mock.patch.object(shortcut, "desktop_dir",
                                  return_value=missing):
            with self.assertRaises(shortcut.ShortcutError):
                shortcut.create()

    @unittest.skipUnless(os.name == "nt", "Windows 전용")
    def test_creates_real_lnk(self):
        """실제 .lnk가 만들어지는지 — 목이 아닌 진짜 파일."""
        with tempfile.TemporaryDirectory() as folder:
            desk = Path(folder)
            target = desk / "EmotionDiary.exe"
            target.write_bytes(b"stub")
            with mock.patch.object(shortcut, "target_path",
                                   return_value=target), \
                    mock.patch.object(shortcut, "desktop_dir",
                                      return_value=desk):
                path = shortcut.create()
                self.assertTrue(path.exists())
                self.assertEqual(path.suffix, ".lnk")
                # .lnk는 매직 넘버로 시작한다
                self.assertEqual(path.read_bytes()[:4], b"\x4c\x00\x00\x00")
                self.assertTrue(shortcut.exists())

    @unittest.skipUnless(os.name == "nt", "Windows 전용")
    def test_names_outside_system_codepage(self):
        """시스템 코드페이지에 없는 글자로도 만들어져야 한다.

        처음 쓰던 WScript.Shell은 ANSI 시절 컴포넌트라 코드페이지 밖 글자를
        다루지 못했다. 한국어 Windows에서는 '감정일기'가 cp949에 있어
        넘어갔지만 영문 Windows에서는 실패했다.

        여기서 이모지·그리스 문자를 쓰는 이유는 그것을 지원하려는 것이
        아니라, **한국어 Windows에서도 '코드페이지 밖'이라는 조건을 만들 수
        있는 유일한 방법**이기 때문이다. 이것이 통과하면 영문 Windows에서
        한글도 통과한다.
        """
        for name, folder in (("감정일기", "한글폴더"),
                             ("\U0001F642", "\U0001F600folder"),
                             ("Ωμέγα", "Ωfolder")):
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as root:
                    app_dir = Path(root) / folder
                    app_dir.mkdir()
                    target = app_dir / "App.exe"
                    target.write_bytes(b"stub")
                    desk = Path(root) / "Desktop"
                    desk.mkdir()
                    with mock.patch.object(config, "APP_NAME", name), \
                            mock.patch.object(shortcut, "target_path",
                                              return_value=target), \
                            mock.patch.object(shortcut, "desktop_dir",
                                              return_value=desk):
                        path = shortcut.create()
                    self.assertTrue(path.exists(), f"{name} 이 안 만들어짐")
                    self.assertEqual(path.stem, name)
                    self.assertEqual(path.read_bytes()[:4],
                                     b"\x4c\x00\x00\x00")

    @unittest.skipUnless(os.name == "nt", "Windows 전용")
    def test_does_not_spawn_powershell(self):
        """COM을 직접 부르므로 프로세스를 새로 띄우지 않는다.

        창 없는 앱에서 콘솔이 번쩍이지 않게 하려는 것이기도 하다.
        """
        import subprocess
        with tempfile.TemporaryDirectory() as folder:
            desk = Path(folder)
            target = desk / "EmotionDiary.exe"
            target.write_bytes(b"stub")
            with mock.patch.object(shortcut, "target_path",
                                   return_value=target), \
                    mock.patch.object(shortcut, "desktop_dir",
                                      return_value=desk), \
                    mock.patch.object(subprocess, "run") as run:
                shortcut.create()
            run.assert_not_called()

    @unittest.skipIf(os.name == "nt", "심볼릭 링크 경로 (macOS/Linux)")
    def test_creates_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            desk = Path(folder) / "Desktop"
            desk.mkdir()
            target = Path(folder) / "EmotionDiary.app"
            target.mkdir()
            with mock.patch.object(shortcut, "target_path",
                                   return_value=target), \
                    mock.patch.object(shortcut, "desktop_dir",
                                      return_value=desk):
                path = shortcut.create()
                self.assertTrue(path.is_symlink())
                self.assertEqual(path.resolve(), target.resolve())
                # 두 번 눌러도 덮어써질 뿐 실패하지 않는다
                shortcut.create()


if __name__ == "__main__":
    unittest.main()
