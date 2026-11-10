"""DbPorter — светлый десктопный интерфейс с Drag & Drop."""
from __future__ import annotations

import html
import json
import logging
import sys
from datetime import datetime

import pandas as pd
from PySide6.QtCore import QByteArray, QMimeData, QObject, Qt, QThread, Signal
from PySide6.QtGui import QColor, QDrag, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from dbporter import __version__
from dbporter.config import DbConfig
from dbporter.core.connection import create_db_engine
from dbporter.core.schema import list_tables
from dbporter.extractors.db_extractor import preview_table
from dbporter.pipeline import transfer_table

logger = logging.getLogger("dbporter.gui")

MIME_TYPE = "application/x-dbporter-table"

DEFAULT_PORTS = {
    "sqlite": "",
    "postgresql": "5432",
    "mysql": "3306",
    # У MSSQL порт по умолчанию не подставляем: для именованного экземпляра
    # (localhost\SQLEXPRESS01) порт определяется через SQL Browser.
    "mssql": "",
    "oracle": "1521",
}
DEFAULT_USERS = {
    "sqlite": "",
    "postgresql": "postgres",
    "mysql": "root",
    # Пусто = Windows-аутентификация для MS SQL.
    "mssql": "",
    "oracle": "system",
}
DB_TYPES = [
    ("SQLite", "sqlite"),
    ("PostgreSQL", "postgresql"),
    ("MySQL / MariaDB", "mysql"),
    ("MS SQL", "mssql"),
    ("Oracle", "oracle"),
]

STYLESHEET = """
QWidget {
    background-color: #EAF7F3;
    color: #1E3A37;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}
QMainWindow, QWidget#root {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0.35,
        stop:0 #F6FCFA, stop:0.55 #E4F6F1, stop:1 #D9F0EA);
}
QLabel {
    color: #5C837D;
    background: transparent;
}
QLabel#appTitle {
    color: #1E3A37;
    font-size: 22px;
    font-weight: 800;
}
QLabel#appSubtitle {
    color: #7C9A95;
    font-size: 11px;
}
QLabel#eyebrow {
    color: #E27D60;
    font-size: 9px;
    font-weight: 700;
}
QLabel#version {
    color: #C38D9E;
    font-size: 11px;
    font-weight: 600;
}
QLabel#panelTitle {
    color: #1E3A37;
    font-size: 16px;
    font-weight: 700;
}
QLabel#sectionTitle {
    color: #3E8F84;
    font-size: 13px;
    font-weight: 700;
}
QLabel#hint {
    color: #7C9A95;
    font-size: 11px;
}
QLabel#statusBadge {
    background-color: #E7F2EF;
    color: #6F928C;
    border-radius: 10px;
    padding: 4px 11px;
    font-size: 11px;
    font-weight: 700;
}
QLabel#statusBadge[state="connected"] {
    background-color: rgba(65, 179, 163, 0.18);
    color: #2E8B7F;
}
QLabel#statusBadge[state="busy"] {
    background-color: rgba(232, 168, 124, 0.28);
    color: #A96B3B;
}
QFrame#card {
    background-color: #FFFFFF;
    border: 1px solid rgba(65, 179, 163, 0.18);
    border-radius: 16px;
}
QFrame#panel {
    background: transparent;
    border: none;
}
QLineEdit, QComboBox {
    background-color: #F8FCFB;
    border: 1px solid rgba(65, 179, 163, 0.24);
    border-radius: 9px;
    padding: 6px 10px;
    min-height: 18px;
    color: #1E3A37;
    selection-background-color: #E27D60;
    selection-color: #FFFFFF;
}
QComboBox {
    padding-right: 28px;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #41B3A3;
    background-color: #FFFFFF;
}
QLineEdit:disabled, QComboBox:disabled {
    color: #A7C2BD;
    background-color: #EEF7F4;
}
QComboBox::drop-down {
    border: none;
    width: 26px;
}
QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    border: 1px solid rgba(65, 179, 163, 0.24);
    selection-background-color: rgba(226, 125, 96, 0.18);
    selection-color: #1E3A37;
    padding: 4px;
}
QComboBox QAbstractItemView::item {
    min-height: 26px;
    padding-left: 8px;
}
QPushButton {
    background-color: #E27D60;
    color: #FFFFFF;
    border: none;
    border-radius: 9px;
    padding: 7px 14px;
    min-height: 18px;
    font-weight: 700;
}
QPushButton:hover {
    background-color: #EA9076;
}
QPushButton:pressed {
    background-color: #CC6A4E;
}
QPushButton:disabled {
    background-color: #DCEFE9;
    color: #93B3AD;
}
QPushButton#ghost {
    background-color: #FFFFFF;
    color: #3E6E67;
    border: 1px solid rgba(65, 179, 163, 0.30);
    padding: 6px 11px;
    font-size: 12px;
}
QPushButton#ghost:hover {
    background-color: rgba(65, 179, 163, 0.12);
    color: #1E3A37;
}
QPushButton#ghost:disabled {
    color: #A7C2BD;
    background-color: #F4FAF8;
    border: 1px solid rgba(65, 179, 163, 0.16);
}
QPushButton#transfer {
    background-color: #E27D60;
    color: #FFFFFF;
    border-radius: 10px;
    padding: 9px 16px;
    font-size: 13px;
}
QPushButton#transfer:hover {
    background-color: #EA9076;
}
QPushButton#transfer:disabled {
    background-color: #DCEFE9;
    color: #93B3AD;
}
QListWidget, QTableWidget {
    background-color: #FFFFFF;
    border: 1px solid rgba(65, 179, 163, 0.18);
    border-radius: 12px;
    alternate-background-color: #F4FBF9;
    selection-background-color: rgba(226, 125, 96, 0.18);
    selection-color: #1E3A37;
}
QListWidget::item {
    padding: 6px 9px;
    border-radius: 7px;
}
QListWidget::item:hover {
    background-color: rgba(65, 179, 163, 0.08);
}
QListWidget::item:selected {
    background-color: rgba(226, 125, 96, 0.18);
    color: #1E3A37;
}
QTableWidget {
    gridline-color: rgba(65, 179, 163, 0.12);
}
QTableWidget::item {
    padding: 4px 6px;
}
QHeaderView::section {
    background-color: #E9F6F2;
    color: #4A756F;
    border: none;
    border-bottom: 1px solid rgba(65, 179, 163, 0.22);
    padding: 6px 8px;
    font-weight: 700;
}
QTextEdit#log {
    background-color: #F8FCFB;
    border: 1px solid rgba(65, 179, 163, 0.18);
    border-radius: 10px;
    color: #3F6E67;
    font-family: Consolas, "Cascadia Mono", monospace;
    font-size: 12px;
    padding: 8px;
    selection-background-color: rgba(226, 125, 96, 0.25);
}
QProgressBar {
    background-color: #DCEFE9;
    border: none;
    border-radius: 3px;
    height: 6px;
    max-height: 6px;
}
QProgressBar::chunk {
    background-color: #E27D60;
    border-radius: 3px;
}
QSplitter::handle {
    background: transparent;
}
QSplitter::handle:horizontal {
    width: 12px;
}
QSplitter::handle:vertical {
    height: 12px;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #B7D9D2;
    border-radius: 4px;
    min-height: 28px;
}
QScrollBar::handle:vertical:hover {
    background: #8FC5BB;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background: #B7D9D2;
    border-radius: 4px;
    min-width: 28px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QStatusBar {
    background-color: #EAF7F3;
    color: #7C9A95;
    border-top: 1px solid rgba(65, 179, 163, 0.18);
    font-size: 11px;
}
QToolTip {
    background-color: #FFFFFF;
    color: #1E3A37;
    border: 1px solid rgba(65, 179, 163, 0.30);
    padding: 6px;
}
QMessageBox {
    background-color: #FFFFFF;
}
QMessageBox QLabel {
    color: #1E3A37;
}
"""


def _plural(count: int, forms: tuple[str, str, str]) -> str:
    one, few, many = forms
    if count % 10 == 1 and count % 100 != 11:
        return one
    if 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
        return few
    return many


class LogBridge(QObject):
    """Потокобезопасный мост для логов из QThread в GUI-поток."""

    message = Signal(str, str)


class GuiLogHandler(logging.Handler):
    def __init__(self, bridge: LogBridge):
        super().__init__()
        self._bridge = bridge

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno >= logging.ERROR:
            level = "error"
        elif record.levelno >= logging.WARNING:
            level = "warn"
        else:
            level = "info"
        try:
            self._bridge.message.emit(record.getMessage(), level)
        except Exception:  # noqa: BLE001 — logging не должен падать из-за GUI
            self.handleError(record)


class TaskWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            self.succeeded.emit(self._fn())
        except Exception as exc:
            logger.debug("Фоновая задача завершилась ошибкой", exc_info=True)
            self.failed.emit(str(exc) or exc.__class__.__name__)


class StatusBadge(QLabel):
    def __init__(self):
        super().__init__()
        self.setObjectName("statusBadge")
        self.setAlignment(Qt.AlignCenter)
        self.set_state("Не подключено", "idle")

    def set_state(self, text: str, state: str) -> None:
        self.setText(text)
        self.setProperty("state", state)
        self.style().unpolish(self)
        self.style().polish(self)


class ChevronComboBox(QComboBox):
    """QComboBox с аккуратным шевроном вместо системной стрелки."""

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#5C837D"), 1.6)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        x = self.width() - 18
        y = self.height() // 2 - 2
        painter.drawLine(x, y, x + 4, y + 4)
        painter.drawLine(x + 4, y + 4, x + 8, y)
        painter.end()


class TableList(QListWidget):
    """Список таблиц с переносом через Drag & Drop между панелями."""

    table_dropped = Signal(str, str)  # (ключ панели-источника, имя таблицы)

    def __init__(self, panel_key: str):
        super().__init__()
        self.panel_key = panel_key
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.CopyAction)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setUniformItemSizes(True)
        self.setSpacing(2)
        self.setToolTip("Перетащите таблицу в соседнюю панель")

    def startDrag(self, supported_actions) -> None:
        item = self.currentItem()
        if item is None:
            return

        payload = json.dumps({"panel": self.panel_key, "table": item.text()}).encode("utf-8")
        mime = QMimeData()
        mime.setData(MIME_TYPE, QByteArray(payload))
        mime.setText(item.text())

        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.CopyAction)

    def _can_accept(self, event) -> bool:
        return event.mimeData().hasFormat(MIME_TYPE)

    def dragEnterEvent(self, event) -> None:
        if self._can_accept(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if self._can_accept(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        if not self._can_accept(event):
            event.ignore()
            return

        try:
            raw = bytes(event.mimeData().data(MIME_TYPE)).decode("utf-8")
            payload = json.loads(raw)
            source_key = str(payload["panel"])
            table_name = str(payload["table"])
        except (KeyError, TypeError, ValueError, UnicodeDecodeError):
            event.ignore()
            return

        if not table_name or source_key == self.panel_key:
            event.ignore()
            return

        event.acceptProposedAction()
        self.table_dropped.emit(source_key, table_name)


class DatabasePanel(QFrame):
    def __init__(self, key: str, title: str, hint: str, is_left: bool, main_window: MainWindow):
        super().__init__()
        self.key = key
        self.title = title
        self.is_left = is_left
        self.main_window = main_window
        self.engine = None
        self.current_df: pd.DataFrame | None = None
        self.current_table: str | None = None
        self._last_type = ""

        self.setObjectName("panel")
        self.setMinimumWidth(360)
        self._build_ui(title, hint)
        self.on_type_changed(self.cb_type.currentText())

    # ── построение интерфейса ───────────────────────────────────

    def _build_ui(self, title: str, hint: str) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        header = QHBoxLayout()
        self.title_label = QLabel(title)
        self.title_label.setObjectName("panelTitle")
        self.title_label.setToolTip(hint)
        self.badge = StatusBadge()

        header.addWidget(self.title_label)
        header.addStretch(1)
        header.addWidget(self.badge, 0, Qt.AlignVCenter)
        root.addLayout(header)

        conn_card, conn_layout = self._make_card()
        self.conn_title = QLabel("Подключение")
        self.conn_title.setObjectName("sectionTitle")
        conn_layout.addWidget(self.conn_title)

        self.cb_type = ChevronComboBox()
        for label, key in DB_TYPES:
            self.cb_type.addItem(label, key)
        self.ed_host = QLineEdit("localhost")
        self.ed_port = QLineEdit()
        self.ed_db = QLineEdit("source.db" if self.is_left else "target.db")
        self.ed_user = QLineEdit()
        self.ed_pass = QLineEdit()
        self.ed_pass.setEchoMode(QLineEdit.Password)
        self.ed_pass.setPlaceholderText("••••••")

        # Две компактные колонки вместо длинного списка полей:
        # для SQLite остаётся одна строка «тип + база», для серверных СУБД —
        # по три строки в каждой колонке.
        forms = QHBoxLayout()
        forms.setContentsMargins(0, 0, 0, 0)
        forms.setSpacing(12)

        left_form = QFormLayout()
        left_form.setContentsMargins(0, 0, 0, 0)
        left_form.setHorizontalSpacing(8)
        left_form.setVerticalSpacing(5)
        left_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        left_form.addRow("Тип БД", self.cb_type)
        left_form.addRow("Хост", self.ed_host)
        left_form.addRow("Пользователь", self.ed_user)

        right_form = QFormLayout()
        right_form.setContentsMargins(0, 0, 0, 0)
        right_form.setHorizontalSpacing(8)
        right_form.setVerticalSpacing(5)
        right_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        right_form.addRow("База данных", self.ed_db)
        right_form.addRow("Порт", self.ed_port)
        right_form.addRow("Пароль", self.ed_pass)

        self._left_form = left_form
        self._right_form = right_form

        self.conn_fields = QWidget()
        fields_layout = QVBoxLayout(self.conn_fields)
        fields_layout.setContentsMargins(0, 0, 0, 0)
        fields_layout.setSpacing(0)
        forms.addLayout(left_form, 1)
        forms.addLayout(right_form, 1)
        fields_layout.addLayout(forms)
        conn_layout.addWidget(self.conn_fields)

        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        self.btn_connect = QPushButton("Подключиться")
        self.btn_disconnect = QPushButton("Отключиться")
        self.btn_disconnect.setObjectName("ghost")
        self.btn_disconnect.setVisible(False)
        buttons.addWidget(self.btn_connect, 1)
        buttons.addWidget(self.btn_disconnect, 1)
        conn_layout.addLayout(buttons)
        root.addWidget(conn_card)

        tables_card, tables_layout = self._make_card()
        tables_head = QHBoxLayout()
        tables_label = QLabel("Таблицы")
        tables_label.setObjectName("sectionTitle")
        self.tables_hint = QLabel("0 таблиц")
        self.tables_hint.setObjectName("hint")
        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.setObjectName("ghost")
        self.btn_refresh.setEnabled(False)
        tables_head.addWidget(tables_label)
        tables_head.addWidget(self.tables_hint)
        tables_head.addStretch(1)
        tables_head.addWidget(self.btn_refresh)
        tables_layout.addLayout(tables_head)

        self.table_list = TableList(self.key)
        self.table_list.setMinimumHeight(90)
        tables_layout.addWidget(self.table_list, 1)

        preview_card, preview_layout = self._make_card()
        preview_head = QHBoxLayout()
        preview_label = QLabel("Предпросмотр")
        preview_label.setObjectName("sectionTitle")
        self.preview_info = QLabel("Выберите таблицу")
        self.preview_info.setObjectName("hint")
        preview_head.addWidget(preview_label)
        preview_head.addStretch(1)
        preview_head.addWidget(self.preview_info)
        preview_layout.addLayout(preview_head)

        self.data_table = QTableWidget()
        self.data_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.data_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.data_table.setAlternatingRowColors(True)
        self.data_table.verticalHeader().setVisible(False)
        self.data_table.horizontalHeader().setStretchLastSection(True)
        self.data_table.horizontalHeader().setDefaultSectionSize(120)
        self.data_table.setMinimumHeight(110)
        preview_layout.addWidget(self.data_table, 1)

        content = QSplitter(Qt.Vertical)
        content.setChildrenCollapsible(False)
        content.setHandleWidth(6)
        content.addWidget(tables_card)
        content.addWidget(preview_card)
        content.setSizes([260, 340])
        root.addWidget(content, 1)

        arrow = "→" if self.is_left else "←"
        self.btn_transfer = QPushButton(f"{arrow}  Перенести в соседнюю базу")
        self.btn_transfer.setObjectName("transfer")
        self.btn_transfer.setEnabled(False)
        root.addWidget(self.btn_transfer)

        self.cb_type.currentTextChanged.connect(self.on_type_changed)
        self.btn_connect.clicked.connect(self.connect)
        self.btn_disconnect.clicked.connect(self.disconnect)
        self.btn_refresh.clicked.connect(self.refresh_tables)
        self.btn_transfer.clicked.connect(self.copy_all)
        self.table_list.itemClicked.connect(self.load_preview)
        self.table_list.table_dropped.connect(
            lambda source_key, table: self.main_window.handle_drop(source_key, table, self)
        )

    @staticmethod
    def _make_card() -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 9, 12, 11)
        layout.setSpacing(6)
        return card, layout

    # ── состояние и подключение ─────────────────────────────────

    def set_status(self, text: str, state: str) -> None:
        self.badge.set_state(text, state)

    def set_busy(self, busy: bool) -> None:
        self.btn_connect.setEnabled(not busy)
        self.btn_disconnect.setEnabled(not busy)
        self.btn_refresh.setEnabled(not busy and self.engine is not None)
        self.conn_fields.setEnabled(not busy)
        self.table_list.setEnabled(not busy)
        self.update_transfer_state()

    def update_transfer_state(self) -> None:
        target = self.main_window.other_panel(self)
        enabled = bool(
            not self.main_window.busy
            and self.engine is not None
            and self.current_table
            and target.engine is not None
        )
        self.btn_transfer.setEnabled(enabled)
        arrow = "→" if self.is_left else "←"
        if self.current_table:
            self.btn_transfer.setText(f"{arrow}  Перенести «{self.current_table}»")
        else:
            self.btn_transfer.setText(f"{arrow}  Перенести в соседнюю базу")

    def on_type_changed(self, _label: str | None = None) -> None:
        db_type = self.cb_type.currentData() or "sqlite"
        is_sqlite = db_type == "sqlite"
        self._left_form.setRowVisible(self.ed_host, not is_sqlite)
        self._left_form.setRowVisible(self.ed_user, not is_sqlite)
        self._right_form.setRowVisible(self.ed_port, not is_sqlite)
        self._right_form.setRowVisible(self.ed_pass, not is_sqlite)

        old_port = DEFAULT_PORTS.get(self._last_type, "")
        if not self.ed_port.text() or self.ed_port.text() == old_port:
            self.ed_port.setText(DEFAULT_PORTS.get(db_type, ""))

        old_user = DEFAULT_USERS.get(self._last_type, "")
        if not self.ed_user.text() or self.ed_user.text() == old_user:
            self.ed_user.setText(DEFAULT_USERS.get(db_type, ""))

        host_hint = r"localhost\SQLEXPRESS01" if db_type == "mssql" else "localhost"
        self.ed_host.setPlaceholderText(host_hint)
        user_hint = "пусто = Windows-аутентификация" if db_type == "mssql" else ""
        self.ed_user.setPlaceholderText(user_hint)
        self.ed_port.setPlaceholderText(
            "необязательно" if db_type == "mssql" else ""
        )

        self.ed_db.setPlaceholderText(
            "путь к файлу .db" if is_sqlite else "имя базы данных"
        )
        self._last_type = db_type

    def get_config(self) -> DbConfig:
        db_type = self.cb_type.currentData() or "sqlite"
        port_text = self.ed_port.text().strip()
        port: int | None = None
        if db_type != "sqlite" and port_text:
            if not port_text.isdigit():
                raise ValueError("Порт должен быть числом")
            port = int(port_text)

        return DbConfig(
            db_type=db_type,
            host=None if db_type == "sqlite" else self.ed_host.text().strip() or None,
            port=port,
            database=self.ed_db.text().strip(),
            username=None if db_type == "sqlite" else self.ed_user.text().strip() or None,
            password=None if db_type == "sqlite" else self.ed_pass.text() or None,
        )

    def connect(self) -> None:
        if self.main_window.busy:
            return
        try:
            cfg = self.get_config()
        except Exception as exc:  # noqa: BLE001 — pydantic/парсер порта
            QMessageBox.warning(self, "Проверьте параметры", str(exc))
            return

        self.set_status("Подключение…", "busy")
        self.main_window.log(f"Подключение: {cfg.db_type} · {cfg.database}", "info")

        def job():
            engine = create_db_engine(cfg)
            try:
                tables = list_tables(engine)
            except Exception:
                engine.dispose()
                raise
            return engine, tables

        self.main_window.run_task(
            job,
            self._on_connected,
            self._on_connect_error,
            "Подключение к базе…",
        )

    def _on_connected(self, result) -> None:
        engine, tables = result
        if self.engine is not None:
            self.engine.dispose()
        self.engine = engine
        self.current_table = None
        self.current_df = None
        self._clear_preview()
        self._fill_tables(tables)
        self._set_connected_controls(True)
        self.set_status("Подключено", "connected")
        self.main_window.log(
            f"Подключено: {len(tables)} {_plural(len(tables), ('таблица', 'таблицы', 'таблиц'))}",
            "success",
        )
        self.main_window.refresh_transfer_state()

    def _on_connect_error(self, message: str) -> None:
        connected = self.engine is not None
        self.set_status(
            "Подключено" if connected else "Не подключено",
            "connected" if connected else "idle",
        )
        self.main_window.log(f"Ошибка подключения: {message}", "error")
        QMessageBox.critical(self, "Ошибка подключения", message)

    def disconnect(self) -> None:
        if self.main_window.busy:
            return
        if self.engine is not None:
            self.engine.dispose()
        self.engine = None
        self.current_table = None
        self.current_df = None
        self.table_list.clear()
        self._clear_preview()
        self.tables_hint.setText("0 таблиц")
        self._set_connected_controls(False)
        self.set_status("Не подключено", "idle")
        self.main_window.log(f"{self.title}: отключено", "info")
        self.main_window.refresh_transfer_state()

    def _set_connected_controls(self, connected: bool) -> None:
        # При успешном подключении прячем всю форму — остаётся только
        # кнопка «Отключиться», а таблицы и предпросмотр получают больше места.
        self.conn_title.setVisible(not connected)
        self.conn_fields.setVisible(not connected)
        self.btn_connect.setVisible(not connected)
        self.btn_disconnect.setVisible(connected)
        self.btn_connect.setText("Подключиться")
        self.btn_refresh.setEnabled(connected)

    def _fill_tables(self, tables: list[str]) -> None:
        selected = self.current_table
        self.table_list.clear()
        self.table_list.addItems(tables)
        self.tables_hint.setText(
            f"{len(tables)} {_plural(len(tables), ('таблица', 'таблицы', 'таблиц'))}"
        )
        if selected:
            matches = self.table_list.findItems(selected, Qt.MatchExactly)
            if matches:
                self.table_list.setCurrentItem(matches[0])
        self.main_window.refresh_transfer_state()

    def refresh_tables(self) -> None:
        if self.engine is None or self.main_window.busy:
            return
        engine = self.engine
        self.main_window.run_task(
            lambda: list_tables(engine),
            self._fill_tables,
            lambda message: self.main_window.log(f"Ошибка списка таблиц: {message}", "error"),
            "Обновление списка таблиц…",
        )

    # ── превью и перенос ────────────────────────────────────────

    def _clear_preview(self) -> None:
        self.data_table.clear()
        self.data_table.setRowCount(0)
        self.data_table.setColumnCount(0)
        self.preview_info.setText("Выберите таблицу")

    def load_preview(self, item) -> None:
        if self.engine is None or self.main_window.busy:
            return
        table = item.text()
        self.current_table = table
        self.preview_info.setText(f"{table} · первые 100 строк")
        engine = self.engine
        self.main_window.run_task(
            lambda: preview_table(engine, table, limit=100),
            lambda df: self._on_preview(table, df),
            lambda message: self._on_preview_error(table, message),
            f"Загрузка «{table}»…",
        )

    def _on_preview(self, table: str, df: pd.DataFrame) -> None:
        if self.current_table != table:
            return
        self.current_df = df
        self._populate_preview(df)
        self.preview_info.setText(
            f"{table} · {len(df)} {_plural(len(df), ('строка', 'строки', 'строк'))}"
        )
        self.main_window.refresh_transfer_state()

    def _on_preview_error(self, table: str, message: str) -> None:
        self.preview_info.setText("Ошибка загрузки")
        self.main_window.log(f"Ошибка превью «{table}»: {message}", "error")

    def _populate_preview(self, df: pd.DataFrame) -> None:
        self.data_table.clear()
        self.data_table.setRowCount(len(df))
        self.data_table.setColumnCount(len(df.columns))
        self.data_table.setHorizontalHeaderLabels([str(c) for c in df.columns])

        for row in range(len(df)):
            for col, _name in enumerate(df.columns):
                value = df.iat[row, col]
                try:
                    missing = bool(pd.isna(value))
                except (TypeError, ValueError):
                    missing = False
                cell = QTableWidgetItem("—" if missing else str(value))
                if missing:
                    cell.setForeground(QColor("#9FBDB7"))
                self.data_table.setItem(row, col, cell)

        self.data_table.resizeColumnsToContents()
        for col in range(self.data_table.columnCount()):
            if self.data_table.columnWidth(col) > 280:
                self.data_table.setColumnWidth(col, 280)

    def copy_all(self) -> None:
        if self.main_window.busy:
            return
        if self.engine is None or not self.current_table:
            QMessageBox.warning(
                self,
                "Нет таблицы",
                "Сначала подключитесь и выберите таблицу в списке.",
            )
            return
        target = self.main_window.other_panel(self)
        target.accept_transfer(self, self.current_table)

    def accept_transfer(self, source: DatabasePanel, table_name: str) -> None:
        if self.main_window.busy or source is self:
            return
        if source.engine is None:
            QMessageBox.warning(self, "Нет подключения", "База-источник не подключена.")
            return
        if self.engine is None:
            QMessageBox.warning(self, "Нет подключения", "Подключите базу-приёмник.")
            return

        self.set_status("Перенос…", "busy")
        self.main_window.log(f"Перенос «{table_name}»: {source.title} → {self.title}", "info")

        def job():
            return transfer_table(source.engine, self.engine, table_name)

        def ok(rows: int) -> None:
            self.set_status("Подключено", "connected")
            self.main_window.log(
                f"Готово: {rows} {_plural(rows, ('строка', 'строки', 'строк'))} → «{table_name}»",
                "success",
            )
            self.refresh_tables()

        def error(message: str) -> None:
            self.set_status("Подключено", "connected")
            self.main_window.log(f"Ошибка переноса: {message}", "error")
            QMessageBox.critical(self, "Ошибка переноса", message)

        self.main_window.run_task(job, ok, error, f"Перенос «{table_name}»…")

    def shutdown(self) -> None:
        if self.engine is not None:
            self.engine.dispose()
            self.engine = None


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._busy = False
        self._worker: TaskWorker | None = None
        self._cursor_set = False

        self.setWindowTitle("DbPorter — перенос данных между базами")
        self.resize(1320, 860)
        self.setMinimumSize(1060, 700)

        central = QWidget()
        central.setObjectName("root")
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(10)
        root.addLayout(self._build_header())

        panels = QSplitter(Qt.Horizontal)
        panels.setChildrenCollapsible(False)
        panels.setHandleWidth(6)
        self.left_panel = DatabasePanel(
            "left", "База А", "Источник или приёмник — без ограничений", True, self
        )
        self.right_panel = DatabasePanel(
            "right", "База Б", "Источник или приёмник — без ограничений", False, self
        )
        panels.addWidget(self.left_panel)
        panels.addWidget(self.right_panel)
        panels.setSizes([680, 680])

        outer = QSplitter(Qt.Vertical)
        outer.setChildrenCollapsible(False)
        outer.setHandleWidth(6)
        outer.addWidget(panels)
        outer.addWidget(self._build_log_card())
        outer.setSizes([720, 170])

        root.addWidget(outer, 1)
        self.setCentralWidget(central)
        self.statusBar().showMessage("Готов к работе")

        self.log_bridge = LogBridge(self)
        self.log_bridge.message.connect(self.log)
        self._log_handler = GuiLogHandler(self.log_bridge)
        self._log_handler.setLevel(logging.INFO)
        db_logger = logging.getLogger("dbporter")
        self._old_propagate = db_logger.propagate
        db_logger.addHandler(self._log_handler)
        db_logger.setLevel(logging.INFO)
        db_logger.propagate = False

        self.log(f"DbPorter v{__version__} готов к работе", "info")

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setSpacing(10)

        titles = QVBoxLayout()
        titles.setSpacing(1)
        eyebrow = QLabel("ANY-TO-ANY DATA PORTER")
        eyebrow.setObjectName("eyebrow")
        title = QLabel("DbPorter")
        title.setObjectName("appTitle")
        subtitle = QLabel("Перенос таблиц между PostgreSQL, MySQL, MSSQL, Oracle и SQLite")
        subtitle.setObjectName("appSubtitle")
        titles.addWidget(eyebrow)
        titles.addWidget(title)
        titles.addWidget(subtitle)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedWidth(150)
        self.progress.setVisible(False)

        version = QLabel(f"v{__version__}")
        version.setObjectName("version")

        header.addLayout(titles)
        header.addStretch(1)
        header.addWidget(self.progress, 0, Qt.AlignVCenter)
        header.addWidget(version, 0, Qt.AlignTop)
        return header

    def _build_log_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(6)

        head = QHBoxLayout()
        title = QLabel("Журнал событий")
        title.setObjectName("sectionTitle")
        clear = QPushButton("Очистить")
        clear.setObjectName("ghost")
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(clear)

        self.log_output = QTextEdit()
        self.log_output.setObjectName("log")
        self.log_output.setReadOnly(True)
        self.log_output.setAcceptRichText(True)
        self.log_output.document().setMaximumBlockCount(2000)
        self.log_output.setMinimumHeight(60)

        layout.addLayout(head)
        layout.addWidget(self.log_output, 1)
        clear.clicked.connect(self.log_output.clear)
        return card

    @property
    def busy(self) -> bool:
        return self._busy

    def other_panel(self, panel: DatabasePanel) -> DatabasePanel:
        return self.right_panel if panel is self.left_panel else self.left_panel

    def refresh_transfer_state(self) -> None:
        self.left_panel.update_transfer_state()
        self.right_panel.update_transfer_state()

    def run_task(self, fn, on_success, on_error, message: str = "Выполняется…") -> bool:
        if self._busy:
            return False

        self._set_busy(True, message)
        worker = TaskWorker(fn, self)
        self._worker = worker

        def succeeded(result) -> None:
            self._worker = None
            self._set_busy(False)
            on_success(result)

        def failed(error_message: str) -> None:
            self._worker = None
            self._set_busy(False)
            on_error(error_message)

        worker.succeeded.connect(succeeded)
        worker.failed.connect(failed)
        worker.finished.connect(worker.deleteLater)
        worker.start()
        return True

    def _set_busy(self, busy: bool, message: str = "Выполняется…") -> None:
        self._busy = busy
        self.progress.setVisible(busy)
        self.statusBar().showMessage(message if busy else "Готов к работе")

        if busy and not self._cursor_set:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self._cursor_set = True
        elif not busy and self._cursor_set:
            QApplication.restoreOverrideCursor()
            self._cursor_set = False

        for panel in (self.left_panel, self.right_panel):
            panel.set_busy(busy)

    def log(self, text: str, level: str = "info") -> None:
        colors = {
            "info": "#5C837D",
            "success": "#2E8B7F",
            "warn": "#B4754A",
            "error": "#C2554B",
        }
        color = colors.get(level, colors["info"])
        message = html.escape(str(text)).replace("\n", "<br>")
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_output.append(
            f'<span style="color:#A5C3BD">{stamp}</span>'
            f'&nbsp;&nbsp;<span style="color:{color}">{message}</span>'
        )
        scroll = self.log_output.verticalScrollBar()
        scroll.setValue(scroll.maximum())

    def handle_drop(self, source_key: str, table_name: str, target: DatabasePanel) -> None:
        if self._busy:
            return
        source = {"left": self.left_panel, "right": self.right_panel}.get(source_key)
        if source is None or source is target:
            return
        target.accept_transfer(source, table_name)

    def closeEvent(self, event) -> None:
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(
                self,
                "Операция выполняется",
                "Дождитесь завершения текущего подключения или переноса.",
            )
            event.ignore()
            return
        self.left_panel.shutdown()
        self.right_panel.shutdown()
        db_logger = logging.getLogger("dbporter")
        db_logger.removeHandler(self._log_handler)
        db_logger.propagate = self._old_propagate
        super().closeEvent(event)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("DbPorter")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
