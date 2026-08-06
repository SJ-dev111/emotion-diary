"""확인 창의 버튼이 한국어로 나오는지.

PySide6에는 Qt 표준 버튼('Yes'/'No')의 한국어 번역이 들어 있지 않다.
그대로 두면 한국어 앱에 영어 버튼이 섞이므로, 글자를 직접 넣는
common.confirm()을 쓴다. 이 테스트는 그것이 유지되는지 지킨다.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from app.ui_qt.widgets.common import confirm  # noqa: E402

_app = QApplication.instance() or QApplication([])


class ConfirmButtonTest(unittest.TestCase):
    def _build(self, **kwargs):
        """창을 띄우지 않고 만들어진 QMessageBox만 붙잡는다."""
        boxes = []
        original = QMessageBox.exec

        def capture(box):
            boxes.append(box)
            return 0

        QMessageBox.exec = capture
        try:
            confirm(None, "제목", "본문", **kwargs)
        finally:
            QMessageBox.exec = original
        return boxes[0]

    def test_buttons_are_korean(self):
        box = self._build()
        labels = [b.text() for b in box.buttons()]
        self.assertEqual(labels, ["예", "아니오"])

    def test_custom_labels(self):
        box = self._build(yes="삭제", no="취소")
        self.assertEqual([b.text() for b in box.buttons()], ["삭제", "취소"])

    def test_no_english_anywhere(self):
        for kwargs in ({}, {"yes": "삭제", "no": "취소"},
                       {"yes": "만들기", "no": "아니요"}):
            box = self._build(**kwargs)
            for button in box.buttons():
                self.assertNotIn(button.text().lower(), ("yes", "no", "ok",
                                                         "cancel"))

    def test_default_is_no_unless_asked(self):
        """되돌릴 수 없는 동작이 Enter 한 번에 실행되지 않게."""
        box = self._build(yes="삭제", no="취소")
        self.assertEqual(box.defaultButton().text(), "취소")
        self.assertEqual(box.escapeButton().text(), "취소")

    def test_default_yes_when_asked(self):
        box = self._build(yes="만들기", no="아니요", default_yes=True)
        self.assertEqual(box.defaultButton().text(), "만들기")
        # Esc는 그래도 '아니요'
        self.assertEqual(box.escapeButton().text(), "아니요")


class NoRawQuestionTest(unittest.TestCase):
    def test_screens_do_not_use_qmessagebox_question(self):
        """새 코드가 실수로 영어 버튼 창을 되살리지 않도록."""
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent / "app"
        offenders = []
        for path in root.rglob("*.py"):
            if path.name == "common.py":
                continue      # 헬퍼 자신은 설명 주석에서 언급한다
            text = path.read_text(encoding="utf-8")
            if "QMessageBox.question" in text:
                offenders.append(str(path.relative_to(root)))
        self.assertEqual(offenders, [],
                         f"common.confirm()을 쓰세요: {offenders}")


if __name__ == "__main__":
    unittest.main()
