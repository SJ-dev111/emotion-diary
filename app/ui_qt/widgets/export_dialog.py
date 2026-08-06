"""내보내기 팝업 — 백업(JSON)과 공유용(HTML·PDF) 두 탭.

차트는 분석 화면과 같은 위젯을 화면 밖에서 그려 PNG로 담는다. 그래서
내보낸 문서의 그림이 앱에서 보던 것과 정확히 같다.
"""
import base64
from datetime import date

from PySide6.QtCore import QBuffer, QDate, Qt
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QDateEdit, QDialog, QFileDialog, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QRadioButton, QTabWidget, QVBoxLayout,
    QWidget)

from app import config, theme
from app.services import backup, report
from app.ui_qt.widgets.charts import MoodGauge, PieChart
from app.ui_qt.widgets.common import confirm, sub_label


def _widget_to_data_uri(widget) -> str:
    """위젯을 그려 PNG data URI로. 실패하면 빈 문자열(그림 없이 진행)."""
    image = widget.grab().toImage()
    # QBuffer에 QByteArray를 넘기면 그 객체의 수명을 관리해 주지 않는다.
    # 임시 객체를 넘기면 파괴된 메모리를 가리키므로 내부 버퍼를 쓴다.
    buffer = QBuffer()
    if not buffer.open(QBuffer.WriteOnly):
        return ""
    if not image.save(buffer, "PNG"):
        return ""
    encoded = base64.b64encode(bytes(buffer.data())).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _render_charts(report_data) -> tuple:
    """파이 차트·기분 게이지를 화면 밖에서 그려 data URI 두 개로.

    내보낸 문서는 앱 테마와 무관하게 늘 라이트다. 그런데 차트는 HTML이
    아니라 위젯을 그려서 담기 때문에, 앱이 다크면 어두운 배경·흐린 글자로
    찍힌다. 그리는 동안만 팔레트를 라이트로 돌려 놓았다가 되돌린다.
    grab()은 이벤트 루프를 돌리지 않아 그 사이 다른 화면이 다시 그려질
    일은 없다.
    """
    saved_theme = theme.current_theme
    theme.set_theme("light")
    try:
        ordered = sorted(report_data["category_counts"].items(),
                         key=lambda kv: kv[1], reverse=True)
        # 문서의 카드가 흰 바탕이라 위젯 배경도 흰색으로 맞춰 그린다
        white = f"background-color: {theme.CARD};"
        pie = PieChart()
        pie.set_data([(name, value, theme.category_color(name, i))
                      for i, (name, value) in enumerate(ordered)])
        pie.setStyleSheet(white)
        pie.resize(220, 220)
        gauge = MoodGauge()
        gauge.set_value(report_data["average"])
        gauge.setStyleSheet(white)
        gauge.resize(460, 90)
        try:
            return _widget_to_data_uri(pie), _widget_to_data_uri(gauge)
        finally:
            pie.deleteLater()
            gauge.deleteLater()
    finally:
        theme.set_theme(saved_theme)


class ExportDialog(QDialog):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.setWindowTitle("내보내기")
        self.setMinimumWidth(520)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        tabs = QTabWidget()
        tabs.addTab(self._share_tab(), "보기·공유용")
        tabs.addTab(self._backup_tab(), "백업")
        root.addWidget(tabs)

        close = QPushButton("닫기")
        close.clicked.connect(self.accept)
        bottom = QHBoxLayout()
        bottom.addStretch()
        bottom.addWidget(close)
        root.addLayout(bottom)

    # ── 공유용 탭 ─────────────────────────────────────────────

    def _share_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 12, 4, 4)
        layout.setSpacing(10)

        layout.addWidget(sub_label(
            "앱에서 보던 모습 그대로 문서를 만들어요."
            " 다른 사람에게 보여주거나 인쇄할 때 쓰세요.", 13))

        scope_row = QHBoxLayout()
        scope_row.addWidget(QLabel("범위"))
        self.scope_combo = QComboBox()
        self.scope_combo.addItems(["전체", "기간 지정", "즐겨찾기만"])
        self.scope_combo.setMinimumHeight(36)
        self.scope_combo.setStyleSheet("font-size: 14px;")
        self.scope_combo.currentTextChanged.connect(self._on_scope_change)
        scope_row.addWidget(self.scope_combo)
        scope_row.addStretch()
        layout.addLayout(scope_row)

        self.period_row = QWidget()
        period = QHBoxLayout(self.period_row)
        period.setContentsMargins(0, 0, 0, 0)
        period.addWidget(QLabel("기간"))
        self.start_edit = self._date_edit(
            QDate.currentDate().addMonths(-1))
        period.addWidget(self.start_edit)
        period.addWidget(QLabel("~"))
        self.end_edit = self._date_edit(QDate.currentDate())
        period.addWidget(self.end_edit)
        period.addStretch()
        layout.addWidget(self.period_row)
        self.period_row.setVisible(False)

        format_row = QHBoxLayout()
        format_row.addWidget(QLabel("형식"))
        self.html_radio = QRadioButton("HTML")
        self.html_radio.setChecked(True)
        self.pdf_radio = QRadioButton("PDF")
        self._format_group = QButtonGroup(self)
        self._format_group.addButton(self.html_radio)
        self._format_group.addButton(self.pdf_radio)
        format_row.addWidget(self.html_radio)
        format_row.addWidget(self.pdf_radio)
        format_row.addStretch()
        layout.addLayout(format_row)

        layout.addWidget(sub_label(
            "HTML은 왼쪽 목록으로 넘겨 보는 형태예요 — 1쪽은 분석,"
            " 그 뒤로 일기 한 편씩 담겨요. PDF는 인쇄·제출에 편하도록"
            " 전체를 이어서 담습니다.", 12))

        self.share_button = QPushButton("문서로 내보내기")
        self.share_button.setMinimumHeight(40)
        self.share_button.clicked.connect(self._export_report)
        layout.addWidget(self.share_button)
        layout.addStretch()
        return page

    def _date_edit(self, initial: QDate) -> QDateEdit:
        edit = QDateEdit(initial)
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("yyyy-MM-dd")
        edit.setMinimumHeight(38)
        edit.setFixedWidth(160)
        edit.lineEdit().setReadOnly(True)
        edit.setFocusPolicy(Qt.NoFocus)
        return edit

    def _on_scope_change(self, text):
        self.period_row.setVisible(text == "기간 지정")

    def _export_report(self):
        scope = self.scope_combo.currentText()
        start = end = None
        if scope == "기간 지정":
            start = self.start_edit.date().toString("yyyy-MM-dd")
            end = self.end_edit.date().toString("yyyy-MM-dd")
            if start > end:
                QMessageBox.warning(self, "기간 확인",
                                    "시작 날짜가 끝 날짜보다 늦어요.")
                return

        data = report.gather(
            self.app.diary_repo, self.app.tag_repo,
            start=start, end=end,
            favorites_only=(scope == "즐겨찾기만"),
            scope_label=scope)
        if data["count"] == 0:
            QMessageBox.information(self, "내보낼 일기 없음",
                                    "이 범위에 적은 일기가 없어요.")
            return

        as_pdf = self.pdf_radio.isChecked()
        extension = "pdf" if as_pdf else "html"
        filter_text = ("PDF 문서 (*.pdf)" if as_pdf
                       else "HTML 문서 (*.html)")
        path, _ = QFileDialog.getSaveFileName(
            self, "저장 위치 선택",
            str(config.export_dir() / report.default_filename(data, extension)),
            filter_text)
        if not path:
            return

        pie_uri, gauge_uri = _render_charts(data)
        try:
            if as_pdf:
                # PDF는 1쪽에 분석 + 목차, 그 뒤로 한 쪽에 일기 하나
                report.write_pdf(path, data, pie_uri, gauge_uri)
            else:
                # HTML은 브라우저에서 보므로 사이드바가 있는 페이지형으로
                report.write_html(
                    path, report.build_paged_html(data, pie_uri, gauge_uri))
        except OSError as exc:
            QMessageBox.critical(self, "저장 실패", f"파일을 쓰지 못했어요.\n{exc}")
            return
        QMessageBox.information(
            self, "내보내기 완료",
            f"일기 {data['count']}개를 저장했어요.\n{path}")

    # ── 백업 탭 ──────────────────────────────────────────────

    def _backup_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 12, 4, 4)
        layout.setSpacing(10)

        layout.addWidget(sub_label(
            "일기와 감정 기록, 직접 추가한 감정 단어를 파일 하나로"
            " 저장해요. PC를 바꾸거나 앱을 다시 설치할 때 그대로"
            " 되돌릴 수 있어요.", 13))

        export_button = QPushButton("백업 파일 저장")
        export_button.setMinimumHeight(40)
        export_button.clicked.connect(self._export_backup)
        layout.addWidget(export_button)
        self.backup_button = export_button

        line = QLabel()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: {theme.BORDER};")
        layout.addWidget(line)

        layout.addWidget(QLabel("백업 되돌리기"))
        self.overwrite_radio = QRadioButton(
            "덮어쓰기 — 지금 데이터를 지우고 백업 시점으로 되돌려요")
        self.merge_radio = QRadioButton(
            "병합 — 지금 데이터를 두고 백업에만 있는 일기를 더해요")
        self.merge_radio.setChecked(True)
        for radio in (self.overwrite_radio, self.merge_radio):
            radio.setStyleSheet("font-size: 13px;")
            layout.addWidget(radio)
        self._restore_group = QButtonGroup(self)
        self._restore_group.addButton(self.overwrite_radio)
        self._restore_group.addButton(self.merge_radio)

        # 되돌리기는 데이터를 바꾸는 동작이라 저장보다 눈에 덜 띄게 둔다
        restore_button = QPushButton("백업 파일 불러오기")
        restore_button.setProperty("kind", "flat")
        restore_button.setMinimumHeight(40)
        restore_button.clicked.connect(self._restore_backup)
        layout.addWidget(restore_button)
        self.restore_button = restore_button
        layout.addStretch()
        return page

    def _export_backup(self):
        default = config.export_dir() / (
            f"{config.APP_NAME}_백업_{date.today().isoformat()}.json")
        path, _ = QFileDialog.getSaveFileName(
            self, "백업 저장 위치", str(default), "백업 파일 (*.json)")
        if not path:
            return
        try:
            counts = backup.export_backup(self.app.conn, path)
        except OSError as exc:
            QMessageBox.critical(self, "저장 실패", f"파일을 쓰지 못했어요.\n{exc}")
            return
        QMessageBox.information(
            self, "백업 완료",
            f"일기 {counts['entries']}개, 추가한 감정 단어"
            f" {counts['words']}개를 저장했어요.\n{path}")

    def _restore_backup(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "백업 파일 선택", str(config.export_dir()),
            "백업 파일 (*.json)")
        if not path:
            return
        try:
            data = backup.load_backup(path)
        except backup.BackupError as exc:
            QMessageBox.critical(self, "불러오기 실패", str(exc))
            return

        mode = "overwrite" if self.overwrite_radio.isChecked() else "merge"
        counts = backup.summarize(data)
        if mode == "overwrite":
            question = (
                f"지금 있는 일기를 모두 지우고 백업의 일기"
                f" {counts['entries']}개로 되돌릴까요?\n"
                "이 동작은 되돌릴 수 없어요.")
        else:
            question = (f"백업의 일기 {counts['entries']}개 중"
                        " 지금 없는 것만 더할까요?")
        if not confirm(self, "백업 되돌리기", question,
                       yes="되돌리기", no="취소"):
            return

        try:
            added = backup.restore_backup(self.app.conn, data, mode)
        except backup.BackupError as exc:
            QMessageBox.critical(self, "복원 실패", str(exc))
            return

        skipped = (f"\n이미 있던 일기 {added['skipped']}개는 건너뛰었어요."
                   if added["skipped"] else "")
        QMessageBox.information(
            self, "복원 완료",
            f"일기 {added['entries']}개, 감정 단어 {added['words']}개를"
            f" 불러왔어요.{skipped}")
        # 복원된 내용이 바로 보이도록 화면과 어휘를 새로 읽는다
        self.app.editor.reload_vocab()
        self.app.show_home()
