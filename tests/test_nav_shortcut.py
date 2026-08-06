"""사이드바의 '바탕화면 바로가기' 버튼.

가리킬 실행 파일이 없는 소스 실행에서는 버튼이 아예 없어야 하고,
배포본에서는 '가이드' 바로 아래에 있어야 한다.
"""
import os
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.services import shortcut  # noqa: E402
from app.ui_qt.widgets import nav_bar as nav_bar_module  # noqa: E402

_app = QApplication.instance() or QApplication([])


class _FakeApp:
    """NavBar가 부르는 것만 갖춘 최소 대역."""

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


def _build(supported: bool, exists: bool = False):
    with mock.patch.object(nav_bar_module.shortcut, "is_supported",
                           return_value=supported), \
            mock.patch.object(nav_bar_module.shortcut, "exists",
                              return_value=exists), \
            mock.patch.object(nav_bar_module.shortcut, "shortcut_path",
                              return_value=Path("/desk/감정일기.lnk")):
        return nav_bar_module.NavBar(_FakeApp())


class NavShortcutButtonTest(unittest.TestCase):
    def test_hidden_when_running_from_source(self):
        bar = _build(supported=False)
        self.assertIsNone(bar.shortcut_button)
        labels = [b.text() for _key, b in bar._items]
        self.assertNotIn("바탕화면 바로가기", labels)

    def test_sits_right_below_guide(self):
        bar = _build(supported=True)
        labels = [b.text() for _key, b in bar._items]
        self.assertEqual(labels[labels.index("가이드") + 1],
                         "바탕화면 바로가기")

    def test_label_changes_when_already_made(self):
        bar = _build(supported=True, exists=True)
        self.assertEqual(bar.shortcut_button.text(), "바로가기 다시 만들기")
        self.assertIn("감정일기.lnk", bar.shortcut_button.toolTip())

    def test_styled_as_action_not_navigation(self):
        """초록 볼드 — QSS가 kind로 칠하므로 테마를 바꿔도 따라온다."""
        from app import theme
        from app.ui_qt.style import build_qss
        bar = _build(supported=True)
        self.assertEqual(bar.shortcut_button.property("kind"), "navAction")
        import re
        qss = build_qss()
        blocks = re.findall(r'QPushButton\[kind="navAction"\][^{]*\{([^}]*)\}',
                            qss)
        self.assertTrue(blocks, "navAction 규칙이 QSS에 없다")
        styled = [b for b in blocks
                  if theme.PRIMARY in b and "font-weight: bold" in b]
        self.assertTrue(styled, f"초록 볼드 규칙이 없다: {blocks}")

    def test_separated_from_guide(self):
        """가이드와 사이에 구분선이 있어야 한다 (위 항목들처럼)."""
        bar = _build(supported=True)
        # 구분선은 메뉴 항목 사이마다 하나씩 — 바로가기가 붙으면 하나 는다
        plain = _build(supported=False)
        self.assertEqual(len(bar._separators), len(plain._separators) + 1)

    def test_not_checkable(self):
        """화면 전환 항목이 아니므로 눌린 채로 남지 않아야 한다."""
        bar = _build(supported=True)
        self.assertFalse(bar.shortcut_button.isCheckable())
        bar.set_active("home")
        self.assertFalse(bar.shortcut_button.isChecked())

    def test_hidden_when_collapsed(self):
        bar = _build(supported=True)
        bar._apply(False)
        self.assertFalse(bar.shortcut_button.isVisible())
        bar._apply(True)


class GuideNoLongerHasCardTest(unittest.TestCase):
    def test_card_moved_out_of_guide(self):
        from app.ui_qt.widgets import guide_popup
        self.assertFalse(hasattr(guide_popup.GuideDialog, "_shortcut_card"))
        # 가이드는 사이드바 버튼을 글로 안내한다
        usage = " ".join(text for _name, text in guide_popup._USAGE)
        self.assertIn("바탕화면 바로가기", usage)


class ServiceStillWorksTest(unittest.TestCase):
    def test_shortcut_service_untouched(self):
        self.assertTrue(callable(shortcut.create))
        self.assertTrue(callable(shortcut.is_supported))


if __name__ == "__main__":
    unittest.main()
