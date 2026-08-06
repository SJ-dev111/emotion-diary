"""감정 단어 실시간 하이라이트 — QSyntaxHighlighter 기반.

Qt가 변경된 줄(블록)만 다시 검사해 주므로 별도 디바운스가 필요 없다.
인식 규칙은 emotion_detector(자모 어간 매칭 + 부정 감지)를 그대로 쓴다.
"""
from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat

from app import theme
from app.services import emotion_detector


class EmotionHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self._vocab = []

    def set_vocab(self, vocab) -> None:
        """단어집 갱신 후 전체 재하이라이트."""
        self._vocab = vocab
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        if not text or not self._vocab:
            return
        for match in emotion_detector.detect(text, self._vocab):
            fmt = QTextCharFormat()
            # 배경만 칠하면 다크에서 본문 글자색(밝음)이 밝은 파스텔에
            # 묻힌다. 배경과 짝이 맞는 글자색을 함께 지정한다.
            fmt.setBackground(QColor(theme.category_chip(match.category)))
            fmt.setForeground(
                QColor(theme.category_chip_text(match.category)))
            self.setFormat(match.start, match.end - match.start, fmt)
