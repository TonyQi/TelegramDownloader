import base64
import html
import os
import re
import subprocess
import time

from PySide6.QtCore import (
    QEvent,
    QEasingCurve,
    QObject,
    Qt,
    QSize,
    QTimer,
    Signal,
    QPropertyAnimation,
)
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGraphicsOpacityEffect,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QMenu,
    QPushButton,
    QSplitter,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QDialog,
)

from core.i18n import make_translator
from core.cache_store import cache_store
from ui.login_dialog import LoginDialog
from ui.settings_dialog import SettingsDialog

# ── Telegram macOS 风格全局样式表 ──────────────────────────────────────
TG_STYLE = """
/* 全局 */
QMainWindow, QWidget {
    background: #E6EBEE;
    color: #000000;
    font-family: "Segoe UI", "Helvetica Neue", "Apple SD Gothic Neo", sans-serif;
    font-size: 13px;
}

/* ── 工具栏 ── */
QToolBar {
    background: #FFFFFF;
    border-bottom: 1px solid #DADCE0;
    spacing: 4px;
    padding: 2px 6px;
}
QToolBar QToolButton {
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 6px 12px;
    color: #3390EC;
    font-weight: 500;
    font-size: 13px;
}
QToolBar QToolButton:hover {
    background: #F0F2F5;
}
QToolBar QToolButton:pressed {
    background: #E3E6EA;
}
QToolBar::separator {
    width: 1px;
    background: #DADCE0;
    margin: 4px 6px;
}

/* ── 输入框 ── */
QLineEdit {
    background: #F0F2F5;
    border: none;
    border-radius: 10px;
    padding: 8px 14px;
    color: #000000;
    font-size: 13px;
    selection-background-color: #A0D2FF;
}
QLineEdit:focus {
    background: #FFFFFF;
    border: 1.5px solid #3390EC;
}
QLineEdit::placeholder {
    color: #8E9BA7;
}

/* ── 按钮 ── */
QPushButton {
    background: #3390EC;
    color: #FFFFFF;
    border: none;
    border-radius: 10px;
    padding: 8px 18px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton:hover {
    background: #2B7FDB;
}
QPushButton:pressed {
    background: #2270C4;
}
QPushButton:disabled {
    background: #B0C4D8;
    color: #FFFFFF;
}

/* ── 次要按钮 (objectName 以 secondary 开头) ── */
QPushButton#secondary {
    background: transparent;
    color: #3390EC;
    border: 1.5px solid #3390EC;
}
QPushButton#secondary:hover {
    background: rgba(51, 144, 236, 0.08);
}
QPushButton#secondary:pressed {
    background: rgba(51, 144, 236, 0.14);
}

/* ── 列表 / 表格 ── */
QListWidget {
    background: #FFFFFF;
    border: none;
    outline: none;
    border-radius: 0px;
}
QListWidget::item {
    padding: 9px 14px;
    border-bottom: 1px solid #F0F2F5;
    border-radius: 0px;
    color: #000000;
}
QListWidget::item:selected {
    background: #3390EC;
    color: #FFFFFF;
}
QListWidget::item:hover:!selected {
    background: #F4F4F5;
}

QTableWidget {
    background: #FFFFFF;
    border: 1px solid #DADCE0;
    border-radius: 10px;
    gridline-color: #F0F2F5;
    selection-background-color: #D2E7FC;
    selection-color: #000000;
}
QTableWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #F0F2F5;
}
QTableWidget::item:selected {
    background: #D2E7FC;
}

QHeaderView::section {
    background: #F8F9FA;
    border: none;
    border-bottom: 1.5px solid #DADCE0;
    border-right: 1px solid #ECEEF0;
    padding: 8px 10px;
    font-weight: 600;
    font-size: 12px;
    color: #6B7B8D;
}
QHeaderView::section:last {
    border-right: none;
}

/* ── 滚动条 ── */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #C4C9CF;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #A8AEB6;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
    height: 0px;
}
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
}
QScrollBar::handle:horizontal {
    background: #C4C9CF;
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background: #A8AEB6;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
    width: 0px;
}

/* ── 分割器 ── */
QSplitter::handle {
    background: #DADCE0;
    width: 1px;
}
QSplitter::handle:hover {
    background: #3390EC;
}

/* ── 标签 ── */
QLabel#sectionTitle {
    font-size: 15px;
    font-weight: 700;
    color: #000000;
    padding: 6px 2px 4px 2px;
}
QLabel#metaText {
    color: #8E9BA7;
    font-size: 11px;
}
QLabel#messageText {
    background: transparent;
    color: #000000;
    font-size: 13px;
}
QLabel#thumb {
    background: #E8ECF0;
    border-radius: 10px;
}
QLabel#chatTitle {
    font-size: 16px;
    font-weight: 700;
    color: #000000;
    padding: 2px 0px;
}
QLabel#chatSubtitle {
    font-size: 12px;
    color: #8E9BA7;
}

/* ── 气泡 ── */
QFrame#bubbleIn {
    background: #FFFFFF;
    border: none;
    border-radius: 12px;
}
QFrame#bubbleOut {
    background: #EFFDDE;
    border: none;
    border-radius: 12px;
}

/* ── 面板 ── */
QFrame#panel {
    background: #FFFFFF;
    border: none;
}

/* ── 对话列表面板 (左侧) ── */
QFrame#sidebarPanel {
    background: #FFFFFF;
    border-right: 1px solid #DADCE0;
}

/* ── 聊天面板 (右侧) ── */
QFrame#chatPanel {
    background: #E6EBEE;
}

/* ── 下载面板 ── */
QFrame#downloadPanel {
    background: #E6EBEE;
}

/* ── 菜单 ── */
QMenu {
    background: #FFFFFF;
    border: 1px solid #DADCE0;
    border-radius: 10px;
    padding: 4px 0px;
}
QMenu::item {
    padding: 7px 24px;
    border-radius: 6px;
    margin: 2px 4px;
}
QMenu::item:selected {
    background: #3390EC;
    color: #FFFFFF;
}

/* ── 工具提示 ── */
QToolTip {
    background: #2C2C2E;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 12px;
}

QFrame#topHeader {
    background: #FFFFFF;
    border-bottom: 1px solid #D8DEE6;
}
QPushButton#iconButton {
    background: transparent;
    color: #253142;
    border: none;
    border-radius: 8px;
    padding: 4px 8px;
    font-size: 22px;
    font-weight: 400;
}
QPushButton#iconButton:hover {
    background: #F1F5F9;
}
QPushButton#navButton {
    background: transparent;
    color: #334155;
    border: none;
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 15px;
    font-weight: 500;
}
QPushButton#navButton:hover {
    background: #F1F5F9;
}
QPushButton#primaryAction {
    background: #2387DD;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 9px 22px;
    font-size: 14px;
    font-weight: 600;
}
QPushButton#primaryAction:hover {
    background: #1E78C8;
}
QPushButton#outlineAction {
    background: #FFFFFF;
    color: #1F2937;
    border: 1px solid #D6DEE8;
    border-radius: 7px;
    padding: 9px 16px;
    font-size: 13px;
    font-weight: 500;
}
QPushButton#outlineAction:hover {
    background: #F8FAFC;
}
QPushButton#dangerOutline {
    background: #FFFFFF;
    color: #DC2626;
    border: 1px solid #D6DEE8;
    border-radius: 7px;
    padding: 9px 16px;
    font-size: 13px;
    font-weight: 500;
}
QFrame#downloadCard {
    background: #FFFFFF;
    border: 1px solid #D7DEE8;
    border-radius: 10px;
}
QLabel#statValueBlue {
    color: #2387DD;
    font-size: 18px;
    font-weight: 700;
}
QLabel#statValueOrange {
    color: #F59E0B;
    font-size: 18px;
    font-weight: 700;
}
"""


def human_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    num = float(size)
    for unit in units:
        if num < 1024 or unit == units[-1]:
            return f"{num:.2f} {unit}"
        num /= 1024.0
    return f"{size} B"


URL_PATTERN = re.compile(r"(https?://[^\s<]+|www\.[^\s<]+|t\.me/[^\s<]+)")
URL_TRAILING_PUNCTUATION = ".,!?;:)]}，。！？；：）】"


def linkify_message_text(text: str) -> str:
    parts = []
    last = 0
    for match in URL_PATTERN.finditer(text):
        parts.append(html.escape(text[last:match.start()]))
        raw_url = match.group(0)
        stripped_url = raw_url.rstrip(URL_TRAILING_PUNCTUATION)
        trailing = raw_url[len(stripped_url):]
        href = stripped_url
        if href.startswith("www.") or href.startswith("t.me/"):
            href = f"https://{href}"
        label = html.escape(stripped_url)
        parts.append(f'<a href="{html.escape(href, quote=True)}">{label}</a>')
        parts.append(html.escape(trailing))
        last = match.end()
    parts.append(html.escape(text[last:]))
    return "".join(parts).replace("\n", "<br>")


def is_transient_network_error(exc) -> bool:
    text = str(exc).lower()
    markers = (
        "server closed the connection",
        "connection closed",
        "connection reset",
        "connection aborted",
        "incomplete",
        "read on a total",
        "timed out",
        "timeout",
    )
    return any(marker in text for marker in markers)


class MessageBridge(QObject):
    received = Signal(dict)


class MainWindow(QMainWindow):
    def __init__(self, telegram_service, download_manager, settings_manager):
        super().__init__()
        self.telegram_service = telegram_service
        self.download_manager = download_manager
        self.settings_manager = settings_manager
        self.t = make_translator(settings_manager)
        self.current_chat_id = None
        self._loading_dialogs = False
        self._loading_messages = False
        self._dialog_future = None
        self._message_future = None
        self._newer_message_future = None
        self._send_future = None
        self._message_load_chat_id = None
        self._newer_message_load_chat_id = None
        self._message_load_started_at = 0.0
        self._message_load_mode = "replace"
        self._sync_newer_until_latest = False
        self._message_used_cached_result = False
        self._loading_older_messages = False
        self._loading_newer_messages = False
        self._has_more_messages = True
        self._confirmed_latest = None
        self._newest_seen_id = 0
        self._preserving_message_scroll = False
        self._scroll_position_save_pending = False
        self._thumbnail_queue = []
        self._thumbnail_futures = {}
        self._thumbnail_chat_id = None
        self._max_thumbnail_concurrency = 16
        self._resize_layout_refresh_pending = False
        self.message_bridge = MessageBridge()
        self.message_bridge.received.connect(self.on_realtime_message)
        self.telegram_service.add_message_handler(self.message_bridge.received.emit)

        self.setWindowTitle(self.t("app.title"))
        self.resize(1360, 780)
        self.setStyleSheet(TG_STYLE)

        self._build_toolbar()
        self._build_layout()
        self.retranslate_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_download_table)
        self.timer.start(int(self.settings_manager.get("refresh_interval_ms", 700)))

        self.load_dialogs()
        self.refresh_download_table()

    def _build_toolbar(self):
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setFixedHeight(0)
        toolbar.hide()
        self.addToolBar(toolbar)

        self.app_title_label = QLabel()
        self.app_title_label.setStyleSheet(
            "QLabel { color: #111827; font-size: 15px; font-weight: 700; "
            "padding-left: 8px; }"
        )
        toolbar.addWidget(self.app_title_label)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        spacer.setMinimumWidth(24)
        toolbar.addWidget(spacer)

        self.chats_action = QAction(self)
        self.chats_action.triggered.connect(self.show_chat_page)
        toolbar.addAction(self.chats_action)

        self.downloads_action = QAction(self)
        self.downloads_action.triggered.connect(self.show_downloads_page)
        toolbar.addAction(self.downloads_action)

        toolbar.addSeparator()

        self.refresh_action = QAction(self)
        self.refresh_action.triggered.connect(self.load_dialogs)
        toolbar.addAction(self.refresh_action)

        self.settings_action = QAction(self)
        self.settings_action.triggered.connect(self.open_settings)
        toolbar.addAction(self.settings_action)

        self.relogin_action = QAction(self)
        self.relogin_action.triggered.connect(self.relogin)
        toolbar.addAction(self.relogin_action)

    def _build_layout(self):
        self.pages = QStackedWidget()
        self.setCentralWidget(self.pages)

        # ── 聊天页 ──
        chat_page = QWidget()
        chat_page.setStyleSheet("background: #F4F8FB;")
        root = QSplitter(Qt.Horizontal, chat_page)
        root.setHandleWidth(1)
        chat_page_layout = QVBoxLayout(chat_page)
        chat_page_layout.setContentsMargins(0, 0, 0, 0)
        chat_page_layout.addWidget(root)

        # 左侧会话列表
        dialogs_panel = QFrame()
        dialogs_panel.setObjectName("sidebarPanel")
        dialogs_panel.setMinimumWidth(330)
        dialogs_panel.setMaximumWidth(430)
        dialogs_layout = QVBoxLayout(dialogs_panel)
        dialogs_layout.setContentsMargins(0, 0, 0, 0)
        dialogs_layout.setSpacing(0)

        # 会话列表标题栏
        header_bar = QFrame()
        header_bar.setObjectName("topHeader")
        header_bar.setFixedHeight(54)
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(18, 0, 18, 0)
        self.sidebar_menu_button = QPushButton("☰")
        self.sidebar_menu_button.setObjectName("iconButton")
        self.sidebar_menu_button.setFixedSize(32, 32)
        header_layout.addWidget(self.sidebar_menu_button)
        self.dialogs_title_label = QLabel()
        self.dialogs_title_label.setObjectName("chatTitle")
        self.dialogs_title_label.hide()
        header_layout.addStretch()
        dialogs_layout.addWidget(header_bar)

        # 搜索框容器
        search_container = QFrame()
        search_container.setStyleSheet("background: #FFFFFF; border-bottom: 1px solid #E3E9F0;")
        search_container.setFixedHeight(66)
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(18, 10, 18, 10)
        self.dialog_search = QLineEdit()
        self.dialog_search.setFixedHeight(42)
        self.dialog_search.setStyleSheet(
            "QLineEdit { background: #FFFFFF; border: 1px solid #D7DEE8; border-radius: 8px; "
            "padding: 0px 14px; font-size: 13px; color: #111827; }"
            "QLineEdit:focus { border: 1.5px solid #2387DD; }"
        )
        self.dialog_search.textChanged.connect(self.filter_dialogs)
        search_layout.addWidget(self.dialog_search)
        dialogs_layout.addWidget(search_container)

        # 会话列表
        self.dialog_list = QListWidget()
        self.dialog_list.setStyleSheet(
            "QListWidget { background: #FFFFFF; border: none; outline: none; }"
            "QListWidget::item { padding: 0px; border: none; }"
            "QListWidget::item:selected { background: transparent; }"
            "QListWidget::item:hover:!selected { background: transparent; }"
        )
        self.dialog_list.itemSelectionChanged.connect(self.on_dialog_selected)
        self.dialog_list.itemSelectionChanged.connect(self.update_dialog_item_styles)
        dialogs_layout.addWidget(self.dialog_list, 1)

        # 右侧聊天面板
        chat_panel = QFrame()
        chat_panel.setObjectName("chatPanel")
        chat_layout = QVBoxLayout(chat_panel)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)

        # 聊天顶栏
        chat_header = QFrame()
        chat_header.setObjectName("topHeader")
        chat_header.setFixedHeight(68)
        chat_header_layout = QHBoxLayout(chat_header)
        chat_header_layout.setContentsMargins(18, 0, 20, 0)
        chat_header_layout.setSpacing(14)
        self.chat_avatar = QLabel()
        self.chat_avatar.setFixedSize(50, 50)
        self.chat_avatar.setAlignment(Qt.AlignCenter)
        self.chat_avatar.setStyleSheet(
            "QLabel { background: #5F9BE8; color: #FFFFFF; border-radius: 25px; "
            "font-size: 18px; font-weight: 700; }"
        )
        chat_header_layout.addWidget(self.chat_avatar)

        chat_title_block = QVBoxLayout()
        chat_title_block.setContentsMargins(0, 0, 0, 0)
        chat_title_block.setSpacing(1)
        self.chat_title = QLabel()
        self.chat_title.setObjectName("chatTitle")
        self.chat_subtitle = QLabel()
        self.chat_subtitle.setObjectName("chatSubtitle")
        chat_title_block.addWidget(self.chat_title)
        chat_title_block.addWidget(self.chat_subtitle)
        chat_header_layout.addLayout(chat_title_block)
        chat_header_layout.addStretch()

        self.reload_messages_button = QPushButton("⌕")
        self.reload_messages_button.setObjectName("iconButton")
        self.reload_messages_button.setFixedSize(40, 40)
        self.reload_messages_button.clicked.connect(self.reload_current_messages)
        chat_header_layout.addWidget(self.reload_messages_button)
        self.chat_downloads_button = QPushButton()
        self.chat_downloads_button.setObjectName("navButton")
        self.chat_downloads_button.clicked.connect(self.show_downloads_page)
        chat_header_layout.addWidget(self.chat_downloads_button)
        self.chat_settings_button = QPushButton()
        self.chat_settings_button.setObjectName("navButton")
        self.chat_settings_button.clicked.connect(self.open_settings)
        chat_header_layout.addWidget(self.chat_settings_button)
        chat_layout.addWidget(chat_header)

        # 消息列表
        self.message_list = QListWidget()
        self.message_list.setStyleSheet(
            "QListWidget { background: #EEF6FC; border: none; outline: none; padding: 12px 22px; }"
            "QListWidget::item { background: transparent; border: none; padding: 0px; }"
            "QListWidget::item:selected { background: transparent; }"
        )
        self.message_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.message_list.setResizeMode(QListWidget.Adjust)
        self.message_list.setWordWrap(True)
        self.message_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.message_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.message_list.setSpacing(4)
        self.message_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.message_list.customContextMenuRequested.connect(self.open_message_menu)
        self.message_list.verticalScrollBar().valueChanged.connect(self.on_message_scroll)
        chat_layout.addWidget(self.message_list, 1)

        self.jump_latest_button = QPushButton(self.message_list.viewport())
        self.jump_latest_button.setFixedSize(44, 44)
        self.jump_latest_button.setToolTip(self.t("chat.jump_latest"))
        self.jump_latest_button.setText("↓")
        self.jump_latest_button.setStyleSheet(
            "QPushButton { background: #FFFFFF; color: #3390EC; border: 1px solid #DADCE0; "
            "border-radius: 22px; font-size: 22px; font-weight: 700; padding: 0px; }"
            "QPushButton:hover { background: #F0F7FF; border-color: #3390EC; }"
        )
        self.jump_latest_button.clicked.connect(self.jump_to_latest_message)
        self.jump_latest_button.hide()
        self.message_list.viewport().installEventFilter(self)

        # 消息输入栏
        input_bar = QFrame()
        input_bar.setStyleSheet("background: #FFFFFF; border-top: 1px solid #D7DEE8;")
        input_bar.setFixedHeight(78)
        send_row = QHBoxLayout(input_bar)
        send_row.setContentsMargins(24, 14, 28, 14)
        send_row.setSpacing(14)

        self.attach_button = QPushButton("🔗")
        self.attach_button.setObjectName("iconButton")
        self.attach_button.setFixedSize(34, 34)
        send_row.addWidget(self.attach_button)

        self.message_input = QLineEdit()
        self.message_input.setFixedHeight(46)
        self.message_input.setStyleSheet(
            "QLineEdit { background: #FFFFFF; border: 1px solid #CCD6E2; border-radius: 8px; "
            "padding: 0px 18px; font-size: 13px; color: #111827; }"
            "QLineEdit:focus { border: 1.5px solid #2387DD; }"
        )
        self.message_input.returnPressed.connect(self.send_current_message)

        self.send_button = QPushButton()
        self.send_button.setObjectName("primaryAction")
        self.send_button.setFixedHeight(46)
        self.send_button.setFixedWidth(92)
        self.send_button.setStyleSheet(
            "QPushButton { background: #2387DD; color: #FFF; border: none; "
            "border-radius: 8px; font-weight: 600; font-size: 13px; }"
            "QPushButton:hover { background: #1E78C8; }"
        )
        self.send_button.clicked.connect(self.send_current_message)

        send_row.addWidget(self.message_input, 1)
        send_row.addWidget(self.send_button)
        chat_layout.addWidget(input_bar)

        # ── 下载页 ──
        downloads_page = QWidget()
        downloads_page.setStyleSheet("background: #F4F8FB;")
        downloads_page_layout = QVBoxLayout(downloads_page)
        downloads_page_layout.setContentsMargins(0, 0, 0, 0)
        downloads_page_layout.setSpacing(24)

        downloads_header = QFrame()
        downloads_header.setObjectName("topHeader")
        downloads_header.setFixedHeight(78)
        downloads_header_layout = QHBoxLayout(downloads_header)
        downloads_header_layout.setContentsMargins(32, 0, 32, 0)
        self.downloads_back_button = QPushButton("←  Chats")
        self.downloads_back_button.setObjectName("navButton")
        self.downloads_back_button.setFixedHeight(44)
        self.downloads_back_button.clicked.connect(self.show_chat_page)
        downloads_header_layout.addWidget(self.downloads_back_button)
        divider = QFrame()
        divider.setFixedSize(1, 48)
        divider.setStyleSheet("background: #D7DEE8;")
        downloads_header_layout.addWidget(divider)
        self.downloads_page_title_label = QLabel()
        self.downloads_page_title_label.setStyleSheet(
            "QLabel { color: #111827; font-size: 24px; font-weight: 700; padding-left: 20px; }"
        )
        downloads_header_layout.addWidget(self.downloads_page_title_label)
        downloads_header_layout.addStretch()
        self.downloads_settings_button = QPushButton("⚙  Settings")
        self.downloads_settings_button.setObjectName("navButton")
        self.downloads_settings_button.clicked.connect(self.open_settings)
        downloads_header_layout.addWidget(self.downloads_settings_button)
        downloads_page_layout.addWidget(downloads_header)

        downloads_panel = QFrame()
        downloads_panel.setObjectName("downloadPanel")
        downloads_panel.setStyleSheet("QFrame#downloadPanel { background: #F4F8FB; border: none; }")
        downloads_layout = QVBoxLayout(downloads_panel)
        downloads_layout.setContentsMargins(32, 12, 32, 28)
        downloads_layout.setSpacing(24)

        # 下载页标题
        dl_title_row = QHBoxLayout()
        self.downloads_title_label = QLabel()
        self.downloads_title_label.setObjectName("sectionTitle")
        self.downloads_title_label.hide()
        dl_title_row.addWidget(self.downloads_title_label)
        dl_title_row.addStretch()
        self.downloads_summary_label = QLabel()
        self.downloads_summary_label.setStyleSheet(
            "QLabel { color: #6B7280; font-size: 12px; background: #F8FAFC; "
            "border: 1px solid #E5E7EB; border-radius: 8px; padding: 5px 10px; }"
        )
        self.downloads_summary_label.hide()
        dl_title_row.addWidget(self.downloads_summary_label)
        downloads_layout.addLayout(dl_title_row)

        # 链接输入行
        top_controls = QHBoxLayout()
        top_controls.setSpacing(18)
        controls_card = QFrame()
        controls_card.setObjectName("downloadCard")
        controls_layout = QHBoxLayout(controls_card)
        controls_layout.setContentsMargins(16, 14, 16, 14)
        controls_layout.setSpacing(8)
        link_row = QHBoxLayout()
        link_row.setSpacing(10)
        self.url_input = QLineEdit()
        self.url_input.setFixedHeight(42)
        self.url_input.setMinimumWidth(340)
        self.url_input.setStyleSheet(
            "QLineEdit { background: #FFFFFF; border: 1px solid #D7DEE8; border-radius: 7px; "
            "padding: 0px 16px; font-size: 13px; color: #111827; }"
            "QLineEdit:focus { border: 1.5px solid #2387DD; }"
        )
        self.add_button = QPushButton()
        self.add_button.setObjectName("primaryAction")
        self.add_button.setFixedHeight(42)
        self.add_button.setFixedWidth(82)
        link_row.addWidget(self.url_input, 1)
        link_row.addWidget(self.add_button)
        controls_layout.addLayout(link_row, 1)
        top_controls.addWidget(controls_card, 1)

        stats_card = QFrame()
        stats_card.setObjectName("downloadCard")
        stats_card.setFixedWidth(340)
        stats_layout = QHBoxLayout(stats_card)
        stats_layout.setContentsMargins(20, 12, 20, 12)
        stats_layout.setSpacing(18)
        self.active_stat_label = QLabel()
        self.queued_stat_label = QLabel()
        self.speed_stat_label = QLabel()
        for stat_label in (self.active_stat_label, self.queued_stat_label, self.speed_stat_label):
            stat_label.setAlignment(Qt.AlignCenter)
            stat_label.setStyleSheet("QLabel { color: #334155; font-size: 12px; }")
            stats_layout.addWidget(stat_label, 1)
        top_controls.addWidget(stats_card)
        downloads_layout.addLayout(top_controls)

        # 下载表格
        self.table = QTableWidget(0, 7)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_download_task_menu)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setStyleSheet(
            "QTableWidget { border: 1px solid #D7DEE8; border-radius: 10px; "
            "background: #FFFFFF; gridline-color: transparent; }"
            "QTableWidget::item { padding: 16px 18px; border-bottom: 1px solid #E5EAF0; font-size: 13px; }"
            "QTableWidget::item:selected { background: #D2E7FC; }"
            "QHeaderView::section { background: #FFFFFF; border: none; "
            "border-bottom: 1px solid #D7DEE8; "
            "padding: 13px 18px; font-weight: 600; font-size: 13px; color: #64748B; }"
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setFixedHeight(44)
        self.table.verticalHeader().setDefaultSectionSize(72)
        downloads_layout.addWidget(self.table, 1)

        # 操作按钮行
        queue_actions = QHBoxLayout()
        queue_actions.setSpacing(6)

        btn_style_primary = (
            "QPushButton { background: #FFFFFF; color: #1F2937; border: 1px solid #D6DEE8; "
            "border-radius: 7px; padding: 9px 16px; font-weight: 500; font-size: 13px; }"
            "QPushButton:hover { background: #F8FAFC; }"
        )
        btn_style_secondary = (
            "QPushButton { background: #FFFFFF; color: #6B7280; "
            "border: 1px solid #D6DEE8; border-radius: 7px; "
            "padding: 9px 16px; font-weight: 500; font-size: 13px; }"
            "QPushButton:hover { background: #F8FAFC; }"
        )
        btn_style_danger = (
            "QPushButton { background: #FFFFFF; color: #DC2626; "
            "border: 1px solid #D6DEE8; border-radius: 7px; "
            "padding: 9px 16px; font-weight: 500; font-size: 13px; }"
            "QPushButton:hover { background: #FEF2F2; }"
        )
        btn_style_ghost = (
            "QPushButton { background: #FFFFFF; color: #1F2937; "
            "border: 1px solid #D6DEE8; border-radius: 7px; "
            "padding: 9px 16px; font-weight: 500; font-size: 13px; }"
            "QPushButton:hover { background: #F8FAFC; }"
        )

        self.start_button = QPushButton()
        self.start_button.setStyleSheet(btn_style_primary)
        self.pause_button = QPushButton()
        self.pause_button.setStyleSheet(btn_style_secondary)
        self.resume_button = QPushButton()
        self.resume_button.setStyleSheet(btn_style_secondary)
        self.cancel_button = QPushButton()
        self.cancel_button.setStyleSheet(btn_style_danger)
        self.open_dir_button = QPushButton()
        self.open_dir_button.setStyleSheet(btn_style_ghost)

        self.start_button.clicked.connect(self.start_selected)
        self.pause_button.clicked.connect(self.pause_selected)
        self.resume_button.clicked.connect(self.resume_selected)
        self.cancel_button.clicked.connect(self.cancel_selected)
        self.open_dir_button.clicked.connect(self.open_download_dir)

        controls_layout.addWidget(self.start_button)
        controls_layout.addWidget(self.pause_button)
        controls_layout.addWidget(self.resume_button)
        controls_layout.addWidget(self.cancel_button)
        controls_layout.addWidget(self.open_dir_button)
        downloads_page_layout.addWidget(downloads_panel)

        # ── 组装页面 ──
        root.addWidget(dialogs_panel)
        root.addWidget(chat_panel)
        root.setSizes([300, 1060])

        self.pages.addWidget(chat_page)
        self.pages.addWidget(downloads_page)
        self.pages.setCurrentIndex(0)

    def eventFilter(self, source, event):
        if (
            hasattr(self, "message_list")
            and source is self.message_list.viewport()
            and event.type() == QEvent.Resize
        ):
            self._position_jump_latest_button()
        return super().eventFilter(source, event)

    @staticmethod
    def _panel():
        panel = QFrame()
        panel.setObjectName("panel")
        return panel

    @staticmethod
    def _title(text):
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        return label

    @staticmethod
    def _pixmap_from_base64(encoded):
        if not encoded:
            return None
        try:
            raw = base64.b64decode(encoded)
        except Exception:
            return None

        pixmap = QPixmap()
        if not pixmap.loadFromData(raw):
            return None
        return pixmap

    def _dialog_item_widget(self, dialog, selected=False):
        widget = QFrame()
        widget.setProperty("dialog_id", dialog["id"])
        widget.setFixedHeight(84)
        widget.setStyleSheet(
            "QFrame { background: %s; border-bottom: 1px solid #E5EAF0; border-left: none; }"
            % ("#D7ECFA" if selected else "#FFFFFF")
        )

        layout = QHBoxLayout(widget)
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(14)

        avatar = QLabel((dialog["title"] or "?")[:1].upper())
        avatar.setFixedSize(56, 56)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(
            "QLabel { background: #6FA4EA; color: #FFFFFF; border-radius: 28px; "
            "font-size: 18px; font-weight: 700; }"
        )
        avatar_pixmap = self._pixmap_from_base64(dialog.get("avatar_base64", ""))
        if avatar_pixmap:
            avatar.setText("")
            avatar.setPixmap(
                avatar_pixmap.scaled(56, 56, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            )
        layout.addWidget(avatar)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(3)
        title = QLabel(dialog["title"])
        title.setStyleSheet(
            "QLabel { color: #111827; font-size: 14px; font-weight: 700; "
            "background: transparent; }"
        )
        title.setMinimumWidth(80)
        preview_text = self.t("chat.peer")
        if dialog.get("pinned"):
            preview_text = self.t("chat.pinned")
        preview = QLabel(preview_text)
        preview.setStyleSheet(
            "QLabel { color: #5F6B7A; font-size: 12px; background: transparent; }"
        )
        text_col.addWidget(title)
        text_col.addWidget(preview)
        layout.addLayout(text_col, 1)

        side_col = QVBoxLayout()
        side_col.setContentsMargins(0, 0, 0, 0)
        side_col.setSpacing(5)
        time_label = QLabel("")
        time_label.setStyleSheet(
            "QLabel { color: #9CA3AF; font-size: 11px; background: transparent; }"
        )
        side_col.addWidget(time_label, alignment=Qt.AlignRight)
        unread = int(dialog.get("unread_count") or 0)
        unread_label = QLabel(str(unread) if unread else "")
        unread_label.setFixedHeight(22)
        unread_label.setMinimumWidth(22)
        unread_label.setAlignment(Qt.AlignCenter)
        unread_label.setStyleSheet(
            "QLabel { background: %s; color: #FFFFFF; border-radius: 11px; "
            "font-size: 11px; font-weight: 700; padding: 0px 6px; }"
            % ("#2387DD" if unread else "transparent")
        )
        side_col.addWidget(unread_label, alignment=Qt.AlignRight)
        layout.addLayout(side_col)
        return widget

    def update_dialog_item_styles(self):
        for index in range(self.dialog_list.count()):
            item = self.dialog_list.item(index)
            widget = self.dialog_list.itemWidget(item)
            if widget is None:
                continue
            bg_color = "#D7ECFA" if item.isSelected() else "#FFFFFF"
            widget.setStyleSheet(
                f"QFrame {{ background: {bg_color}; border-bottom: 1px solid #E5EAF0; border-left: none; }}"
            )

    def _set_chat_avatar(self, dialog):
        pixmap = self._pixmap_from_base64(dialog.get("avatar_base64", ""))
        if pixmap:
            self.chat_avatar.setText("")
            self.chat_avatar.setPixmap(
                pixmap.scaled(50, 50, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            )
            return

        self.chat_avatar.setPixmap(QPixmap())
        self.chat_avatar.setText((dialog["title"] or "?")[:1].upper())

    def retranslate_ui(self):
        self.t = make_translator(self.settings_manager)
        self.setWindowTitle(self.t("app.title"))
        self.refresh_action.setText(self.t("nav.refresh"))
        self.settings_action.setText(self.t("nav.settings"))
        self.relogin_action.setText(self.t("nav.relogin"))
        self.chats_action.setText(self.t("nav.chats"))
        self.downloads_action.setText(self.t("nav.downloads"))

        self.dialogs_title_label.setText(self.t("chat.title"))
        self.app_title_label.setText(self.t("app.title"))
        self.dialog_search.setPlaceholderText(self.t("chat.search"))
        if not self.current_chat_id:
            self.chat_title.setText(self.t("chat.select"))
            self.chat_avatar.setText("")
            self.chat_subtitle.setText("")
        self.reload_messages_button.setText(self.t("chat.refresh"))
        self.reload_messages_button.setText("⌕")
        self.chat_downloads_button.setText(self.t("nav.downloads"))
        self.chat_settings_button.setText("⚙  " + self.t("nav.settings"))
        self.jump_latest_button.setToolTip(self.t("chat.jump_latest"))
        self.message_input.setPlaceholderText(self.t("chat.input"))
        self.send_button.setText(self.t("chat.send"))

        self.downloads_title_label.setText(self.t("downloads.title"))
        self.downloads_page_title_label.setText(self.t("downloads.title"))
        self.downloads_back_button.setText("←  " + self.t("nav.chats"))
        self.downloads_settings_button.setText("⚙  " + self.t("nav.settings"))
        self.url_input.setPlaceholderText(self.t("downloads.link_placeholder"))
        self.add_button.setText(self.t("downloads.add"))
        self.table.setHorizontalHeaderLabels(
            [
                self.t("downloads.file"),
                self.t("downloads.status"),
                self.t("downloads.progress"),
                self.t("downloads.speed"),
                self.t("downloads.size"),
                self.t("downloads.error"),
                "",
            ]
        )
        self.start_button.setText(self.t("downloads.start"))
        self.pause_button.setText(self.t("downloads.pause"))
        self.resume_button.setText(self.t("downloads.resume"))
        self.cancel_button.setText(self.t("downloads.cancel"))
        self.start_button.setText("▶  " + self.t("downloads.start"))
        self.pause_button.setText("Ⅱ  " + self.t("downloads.pause"))
        self.resume_button.setText("▷  " + self.t("downloads.resume"))
        self.cancel_button.setText("×  " + self.t("downloads.cancel"))
        self.open_dir_button.setText("▣  " + self.t("downloads.open_folder"))
        self.update_downloads_badge()

        self._refresh_message_widgets()

    def show_chat_page(self):
        self.switch_page(0)

    def show_downloads_page(self):
        self.refresh_download_table()
        self.switch_page(1)

    def update_downloads_badge(self):
        tasks = self.download_manager.list_tasks()
        active = sum(1 for task in tasks if task.status == "downloading")
        queued = sum(1 for task in tasks if task.status == "queued")
        speed = sum(task.speed for task in tasks if task.status == "downloading")
        speed_text = f"{speed / 1024 / 1024:.1f} MB/s" if speed > 0 else "0 MB/s"
        total_pending = active + queued
        label = self.t("nav.downloads")
        if total_pending:
            label = f"{label} ({total_pending})"
        self.downloads_action.setText(label)
        if hasattr(self, "chat_downloads_button"):
            badge = f"  {total_pending}" if total_pending else ""
            self.chat_downloads_button.setText(f"⇩  {self.t('nav.downloads')}{badge}")
        if hasattr(self, "active_stat_label"):
            self.active_stat_label.setText(
                f'Active<br><span style="color:#2387DD;font-size:20px;font-weight:700;">{active}</span>'
            )
            self.queued_stat_label.setText(
                f'Queued<br><span style="color:#F59E0B;font-size:20px;font-weight:700;">{queued}</span>'
            )
            self.speed_stat_label.setText(
                f'Speed<br><span style="color:#2387DD;font-size:20px;font-weight:700;">{speed_text}</span>'
            )
        self.downloads_summary_label.setText(
            self.t(
                "downloads.summary",
                active=active,
                queued=queued,
                speed=speed_text,
            )
        )

    def switch_page(self, index):
        if self.pages.currentIndex() == index:
            return

        self.pages.setCurrentIndex(index)
        effect = QGraphicsOpacityEffect(self.pages.currentWidget())
        self.pages.currentWidget().setGraphicsEffect(effect)
        self._page_animation = QPropertyAnimation(effect, b"opacity", self)
        self._page_animation.setDuration(180)
        self._page_animation.setStartValue(0.0)
        self._page_animation.setEndValue(1.0)
        self._page_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._page_animation.finished.connect(
            lambda: self.pages.currentWidget().setGraphicsEffect(None)
        )
        self._page_animation.start()

    def open_message_menu(self, position):
        item = self.message_list.itemAt(position)
        if not item:
            return

        message = item.data(Qt.UserRole)
        if not isinstance(message, dict) or not message.get("has_document"):
            return

        menu = QMenu(self)
        download_action = menu.addAction(self.t("menu.download"))
        menu.addAction(self.t("menu.copy_text"))
        menu.addAction(self.t("menu.copy_link"))
        selected_action = menu.exec(self.message_list.mapToGlobal(position))
        if selected_action == download_action:
            self.download_message_file(message)

    def load_dialogs(self):
        if self._loading_dialogs:
            return

        cached_dialogs = self.telegram_service.list_dialogs_cached()
        if cached_dialogs:
            self._render_dialogs(cached_dialogs)

        self._loading_dialogs = True
        self._dialog_future = self.telegram_service.list_dialogs_async(limit=100)
        self._poll_dialog_future()

    def _poll_dialog_future(self):
        if not self._dialog_future:
            self._loading_dialogs = False
            return

        if not self._dialog_future.done():
            QTimer.singleShot(80, self._poll_dialog_future)
            return

        try:
            dialogs = self._dialog_future.result()
        except Exception as exc:
            self._dialog_future = None
            self._loading_dialogs = False
            QMessageBox.critical(self, self.t("dialog.failed_load_chats"), str(exc))
            return

        self._dialog_future = None
        self._loading_dialogs = False

        self._render_dialogs(dialogs)

    def _render_dialogs(self, dialogs):
        selected_chat_id = self.current_chat_id
        self.dialog_list.clear()
        for dialog in dialogs:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, dialog)
            item.setSizeHint(QSize(330, 84))
            self.dialog_list.addItem(item)
            self.dialog_list.setItemWidget(
                item,
                self._dialog_item_widget(
                    dialog,
                    bool(selected_chat_id and dialog["id"] == selected_chat_id),
                ),
            )
            if selected_chat_id and dialog["id"] == selected_chat_id:
                item.setSelected(True)
                self.dialog_list.setCurrentItem(item)
        self.filter_dialogs(self.dialog_search.text())

    def filter_dialogs(self, text):
        keyword = text.strip().lower()
        for index in range(self.dialog_list.count()):
            item = self.dialog_list.item(index)
            dialog = item.data(Qt.UserRole)
            item.setHidden(keyword not in dialog["title"].lower())

    def on_dialog_selected(self):
        item = self.dialog_list.currentItem()
        if not item:
            return
        dialog = item.data(Qt.UserRole)
        old_chat_id = self.current_chat_id
        if old_chat_id:
            self._save_chat_position(old_chat_id)
        self.current_chat_id = dialog["id"]
        self._confirmed_latest = None
        self._newest_seen_id = 0
        self._has_more_messages = True
        self.chat_title.setText(dialog["title"])
        self._set_chat_avatar(dialog)
        self.chat_subtitle.setText(self.t("chat.online"))
        self.jump_latest_button.hide()
        # 切换聊天时清理旧聊天的原始消息缓存，释放内存
        if old_chat_id and str(old_chat_id) != str(dialog["id"]):
            self.telegram_service.purge_raw_message_cache(old_chat_id)
        self.load_messages(dialog["id"])

    def reload_current_messages(self):
        if self.current_chat_id:
            self.load_messages(self.current_chat_id, show_loading=False)

    def on_message_scroll(self, value):
        self._update_jump_latest_button()
        if self._preserving_message_scroll:
            return
        self._schedule_save_current_chat_position()

        scrollbar = self.message_list.verticalScrollBar()
        if self._is_at_latest_message():
            # 到达底部：清除未读，加载可能漏掉的新消息
            self._mark_current_dialog_read()
            self.load_newer_messages(sync_until_latest=True)
            return

        # 不在底部：根据视口下方消息数更新未读
        self._update_unread_from_scroll_position()

        if value > scrollbar.minimum() + 20:
            return
        if (
            not self.current_chat_id
            or self._loading_messages
            or self._loading_older_messages
            or self._loading_newer_messages
        ):
            return
        if not self._has_more_messages or self.message_list.count() == 0:
            return
        self.load_older_messages()

    def _is_at_latest_message(self):
        scrollbar = self.message_list.verticalScrollBar()
        return scrollbar.maximum() <= 0 or scrollbar.value() >= scrollbar.maximum() - 24

    def _position_jump_latest_button(self):
        if not hasattr(self, "jump_latest_button"):
            return
        viewport = self.message_list.viewport()
        margin = 18
        x = max(margin, viewport.width() - self.jump_latest_button.width() - margin)
        y = max(margin, viewport.height() - self.jump_latest_button.height() - margin)
        self.jump_latest_button.move(x, y)

    def _update_jump_latest_button(self):
        if not hasattr(self, "jump_latest_button"):
            return
        self._position_jump_latest_button()
        should_show = (
            bool(self.current_chat_id)
            and self.message_list.count() > 0
            and not self._is_at_latest_message()
        )
        self.jump_latest_button.setVisible(should_show)
        if should_show:
            self.jump_latest_button.raise_()

    def jump_to_latest_message(self):
        self.message_list.scrollToBottom()
        self._confirmed_latest = None
        self.load_newer_messages(sync_until_latest=True)
        QTimer.singleShot(0, self._update_jump_latest_button)

    def _restore_message_scroll_value(self, value):
        scrollbar = self.message_list.verticalScrollBar()
        previous_preserving = self._preserving_message_scroll
        self._preserving_message_scroll = True
        try:
            scrollbar.setValue(max(scrollbar.minimum(), min(int(value), scrollbar.maximum())))
        finally:
            self._preserving_message_scroll = previous_preserving
        self._update_jump_latest_button()

    def _restore_message_scroll_value_later(self, value):
        QTimer.singleShot(0, lambda v=value: self._restore_message_scroll_value(v))
        QTimer.singleShot(40, lambda v=value: self._restore_message_scroll_value(v))

    def _restore_visible_anchor_snapshot(self, snapshot):
        if not snapshot:
            return
        scrollbar = self.message_list.verticalScrollBar()
        previous_preserving = self._preserving_message_scroll
        self._preserving_message_scroll = True
        try:
            item = self._find_message_item(snapshot.get("anchor_message_id"))
            if item is not None:
                current_rect = self.message_list.visualItemRect(item)
                target_value = (
                    scrollbar.value()
                    + current_rect.top()
                    - int(snapshot.get("anchor_offset") or 0)
                )
            else:
                target_value = int(snapshot.get("scroll_value") or scrollbar.value())
            scrollbar.setValue(
                max(scrollbar.minimum(), min(int(target_value), scrollbar.maximum()))
            )
        finally:
            self._preserving_message_scroll = previous_preserving
        self._update_jump_latest_button()

    def _restore_visible_anchor_snapshot_later(self, snapshot):
        if not snapshot:
            return
        QTimer.singleShot(0, lambda s=dict(snapshot): self._restore_visible_anchor_snapshot(s))
        QTimer.singleShot(40, lambda s=dict(snapshot): self._restore_visible_anchor_snapshot(s))
        QTimer.singleShot(120, lambda s=dict(snapshot): self._restore_visible_anchor_snapshot(s))

    def _visible_anchor_snapshot(self):
        scrollbar = self.message_list.verticalScrollBar()
        snapshot = {
            "scroll_value": int(scrollbar.value()),
            "newest_seen_id": int(self._newest_seen_id or 0),
        }

        viewport_height = self.message_list.viewport().height()
        for y in range(0, max(1, viewport_height), 8):
            item = self.message_list.itemAt(8, y)
            if item is None:
                continue
            message = item.data(Qt.UserRole)
            if not isinstance(message, dict):
                continue
            message_id = int(message.get("id", 0) or 0)
            if message_id <= 0:
                continue
            rect = self.message_list.visualItemRect(item)
            snapshot["anchor_message_id"] = message_id
            snapshot["anchor_offset"] = int(rect.top())
            break
        return snapshot

    def _save_chat_position(self, chat_id=None):
        chat_id = str(chat_id or self.current_chat_id or "")
        if self.current_chat_id and chat_id != str(self.current_chat_id):
            self._scroll_position_save_pending = False
            return
        if not chat_id or self.message_list.count() == 0:
            self._scroll_position_save_pending = False
            return
        cache_store.save_chat_position(chat_id, self._visible_anchor_snapshot())
        self._scroll_position_save_pending = False

    def _schedule_save_current_chat_position(self):
        if not self.current_chat_id or self._scroll_position_save_pending:
            return
        chat_id = str(self.current_chat_id)
        self._scroll_position_save_pending = True
        QTimer.singleShot(250, lambda c=chat_id: self._save_chat_position(c))

    def _find_message_item(self, message_id):
        target_id = int(message_id or 0)
        if target_id <= 0:
            return None
        for index in range(self.message_list.count()):
            item = self.message_list.item(index)
            message = item.data(Qt.UserRole)
            if isinstance(message, dict) and int(message.get("id", 0) or 0) == target_id:
                return item
        return None

    def _restore_chat_position(self, chat_id):
        position = cache_store.load_chat_position(chat_id)
        if not position:
            self._update_jump_latest_button()
            return

        self._newest_seen_id = max(
            int(self._newest_seen_id or 0),
            int(position.get("newest_seen_id") or 0),
        )
        scrollbar = self.message_list.verticalScrollBar()
        self._preserving_message_scroll = True
        try:
            item = self._find_message_item(position.get("anchor_message_id"))
            if item is not None:
                self.message_list.scrollToItem(item, QAbstractItemView.PositionAtTop)
                anchor_offset = int(position.get("anchor_offset") or 0)
                target_value = scrollbar.value() - anchor_offset
            else:
                target_value = int(position.get("scroll_value") or 0)
            scrollbar.setValue(
                max(scrollbar.minimum(), min(int(target_value), scrollbar.maximum()))
            )
        finally:
            self._preserving_message_scroll = False
        self._update_jump_latest_button()

    def _restore_chat_position_later(self, chat_id):
        QTimer.singleShot(0, lambda c=str(chat_id): self._restore_chat_position(c))
        QTimer.singleShot(80, lambda c=str(chat_id): self._restore_chat_position(c))

    def _mark_current_dialog_read(self):
        if not self.current_chat_id:
            return

        # 更新 _newest_seen_id 为当前最新消息，确保未读计数归零
        newest = self.newest_message_id()
        if newest:
            self._newest_seen_id = max(self._newest_seen_id, newest)

        self._clear_dialog_unread_count(self.current_chat_id)
        try:
            self.telegram_service.mark_chat_read_async(self.current_chat_id)
        except Exception:
            pass

    def _update_unread_from_scroll_position(self):
        """根据当前视口位置计算未读数：滚动时找到视口内最新消息，
        更新 _newest_seen_id，未读数 = 比它更新的消息总数。"""
        if not self.current_chat_id:
            return
        count = self.message_list.count()
        if count == 0:
            return

        viewport_height = self.message_list.viewport().height()
        newest_visible_id = 0
        for index in range(count):
            item = self.message_list.item(index)
            model_index = self.message_list.indexFromItem(item)
            rect = self.message_list.visualRect(model_index)
            if rect.top() < viewport_height:
                msg = item.data(Qt.UserRole)
                if isinstance(msg, dict):
                    msg_id = int(msg.get("id", 0))
                    if msg_id > newest_visible_id:
                        newest_visible_id = msg_id

        if newest_visible_id > 0 and newest_visible_id > self._newest_seen_id:
            self._newest_seen_id = newest_visible_id

        if self._newest_seen_id <= 0:
            return

        below = 0
        for index in range(count):
            item = self.message_list.item(index)
            msg = item.data(Qt.UserRole)
            if isinstance(msg, dict) and int(msg.get("id", 0)) > self._newest_seen_id:
                below += 1

        self._set_dialog_unread_count(self.current_chat_id, below)

    def _update_dialog_unread_count(self, delta):
        """将当前会话的未读数增加 delta（可为负数），不低于 0。"""
        if not self.current_chat_id:
            return
        for index in range(self.dialog_list.count()):
            item = self.dialog_list.item(index)
            dialog = item.data(Qt.UserRole)
            if not isinstance(dialog, dict) or str(dialog.get("id")) != str(self.current_chat_id):
                continue
            current = int(dialog.get("unread_count") or 0)
            self._set_dialog_unread_count(self.current_chat_id, max(0, current + delta))
            return

    def _set_dialog_unread_count(self, chat_id, count):
        """直接设置指定会话的未读数。"""
        for index in range(self.dialog_list.count()):
            item = self.dialog_list.item(index)
            dialog = item.data(Qt.UserRole)
            if not isinstance(dialog, dict) or str(dialog.get("id")) != str(chat_id):
                continue

            current = int(dialog.get("unread_count") or 0)
            if current == count:
                return

            updated_dialog = dict(dialog)
            updated_dialog["unread_count"] = count
            item.setData(Qt.UserRole, updated_dialog)
            self.dialog_list.setItemWidget(
                item,
                self._dialog_item_widget(updated_dialog, item.isSelected()),
            )
            return

    def _clear_dialog_unread_count(self, chat_id):
        for index in range(self.dialog_list.count()):
            item = self.dialog_list.item(index)
            dialog = item.data(Qt.UserRole)
            if not isinstance(dialog, dict) or str(dialog.get("id")) != str(chat_id):
                continue

            if int(dialog.get("unread_count") or 0) == 0:
                return

            updated_dialog = dict(dialog)
            updated_dialog["unread_count"] = 0
            item.setData(Qt.UserRole, updated_dialog)
            self.dialog_list.setItemWidget(
                item,
                self._dialog_item_widget(updated_dialog, item.isSelected()),
            )
            return

    def oldest_message_id(self):
        oldest_id = None
        for index in range(self.message_list.count()):
            item = self.message_list.item(index)
            message = item.data(Qt.UserRole)
            if not isinstance(message, dict):
                continue
            message_id = int(message.get("id", 0))
            if message_id <= 0:
                continue
            if oldest_id is None or message_id < oldest_id:
                oldest_id = message_id
        return oldest_id

    def newest_message_id(self):
        newest_id = None
        for index in range(self.message_list.count()):
            item = self.message_list.item(index)
            message = item.data(Qt.UserRole)
            if not isinstance(message, dict):
                continue
            message_id = int(message.get("id", 0))
            if message_id <= 0:
                continue
            if newest_id is None or message_id > newest_id:
                newest_id = message_id
        return newest_id

    def load_older_messages(self):
        oldest_id = self.oldest_message_id()
        if not oldest_id:
            return

        self._loading_older_messages = True
        self.load_messages(
            self.current_chat_id,
            show_loading=False,
            offset_id=oldest_id,
            mode="prepend",
        )

    def load_newer_messages(self, sync_until_latest=False):
        if (
            not self.current_chat_id
            or self._loading_messages
            or self._loading_older_messages
            or self._loading_newer_messages
        ):
            return

        newest_id = self.newest_message_id()
        if not newest_id:
            return

        latest_marker = (str(self.current_chat_id), int(newest_id))
        if self._confirmed_latest == latest_marker:
            self._mark_current_dialog_read()
            return

        self._loading_newer_messages = True
        self._newer_message_load_chat_id = str(self.current_chat_id)
        self._sync_newer_until_latest = bool(sync_until_latest)
        self._newer_message_future = self.telegram_service.list_newer_messages_async(
            self.current_chat_id,
            min_id=newest_id,
            limit=50,
            include_thumbnails=False,
        )
        self._poll_newer_message_future()

    def _poll_newer_message_future(self):
        if not self._newer_message_future:
            self._loading_newer_messages = False
            return

        if not self._newer_message_future.done():
            QTimer.singleShot(80, self._poll_newer_message_future)
            return

        fetch_failed = False
        try:
            messages = self._newer_message_future.result()
        except Exception:
            messages = []
            fetch_failed = True

        loaded_chat_id = self._newer_message_load_chat_id
        sync_until_latest = self._sync_newer_until_latest
        self._newer_message_future = None
        self._newer_message_load_chat_id = None
        self._loading_newer_messages = False
        self._sync_newer_until_latest = False

        if loaded_chat_id != str(self.current_chat_id):
            return

        if fetch_failed:
            QTimer.singleShot(0, self._update_jump_latest_button)
            return

        if not messages:
            newest_id = self.newest_message_id()
            if newest_id:
                self._confirmed_latest = (str(self.current_chat_id), int(newest_id))
            if self._is_at_latest_message():
                self._mark_current_dialog_read()
            QTimer.singleShot(0, self._update_jump_latest_button)
            return

        appended_count = self._append_newer_messages(messages, keep_scroll_position=True)
        self._confirmed_latest = None
        if appended_count == 0:
            QTimer.singleShot(0, self._update_jump_latest_button)
            return
        if sync_until_latest:
            QTimer.singleShot(0, lambda: self.load_newer_messages(sync_until_latest=True))

    def _append_newer_messages(
        self,
        messages,
        scroll_to_bottom=False,
        keep_scroll_position=False,
    ):
        appended = []
        scrollbar = self.message_list.verticalScrollBar()
        old_value = scrollbar.value()
        anchor_snapshot = self._visible_anchor_snapshot()
        self._preserving_message_scroll = True
        try:
            for message in messages:
                if self._has_message(message["id"]):
                    continue
                self._add_message_widget(message)
                appended.append(message)

            if scroll_to_bottom:
                self.message_list.scrollToBottom()
            elif keep_scroll_position:
                scrollbar.setValue(old_value)
        finally:
            self._preserving_message_scroll = False
        if keep_scroll_position:
            if anchor_snapshot.get("anchor_message_id"):
                self._restore_visible_anchor_snapshot_later(anchor_snapshot)
            else:
                self._restore_message_scroll_value_later(old_value)
        if appended:
            self._queue_thumbnail_loading(appended, append=True)
        QTimer.singleShot(0, self._update_jump_latest_button)
        return len(appended)

    def on_realtime_message(self, message):
        chat_id = str(message.get("chat_id", ""))
        if chat_id != str(self.current_chat_id):
            return

        if self._has_message(message["id"]):
            return

        at_bottom = self._is_at_latest_message()
        old_value = self.message_list.verticalScrollBar().value()
        if self.message_list.count() == 1:
            only_item = self.message_list.item(0)
            if only_item and only_item.flags() == Qt.NoItemFlags:
                self.message_list.clear()

        self._preserving_message_scroll = True
        try:
            self._add_message_widget(message)
        finally:
            self._preserving_message_scroll = False

        if at_bottom:
            # 用户正在看最新消息：自动滚动到新消息，标记已读
            self.message_list.scrollToBottom()
            self._newest_seen_id = max(self._newest_seen_id, int(message.get("id", 0)))
            self._mark_current_dialog_read()
        elif self.message_list.count() > 1:
            # 用户在浏览历史消息：不改变视口，未读数 +1
            self._restore_message_scroll_value(old_value)
            self._update_dialog_unread_count(1)

        self._confirmed_latest = None
        QTimer.singleShot(0, self._update_jump_latest_button)
        if message.get("media_kind") in ("photo", "video") and not message.get("thumbnail_base64"):
            self._thumbnail_queue.append(message["id"])
            if not self._thumbnail_chat_id:
                self._thumbnail_chat_id = str(self.current_chat_id)
            self._start_next_thumbnail()

    def _has_message(self, message_id):
        for index in range(self.message_list.count()):
            item = self.message_list.item(index)
            message = item.data(Qt.UserRole)
            if isinstance(message, dict) and message.get("id") == message_id:
                return True
        return False

    def send_current_message(self):
        if not self.current_chat_id:
            QMessageBox.information(
                self, self.t("dialog.tip"), self.t("dialog.select_chat_first")
            )
            return

        text = self.message_input.text().strip()
        if not text:
            return

        self.send_button.setEnabled(False)
        self._send_future = self.telegram_service.send_message_async(
            self.current_chat_id,
            text,
        )
        self._poll_send_future()

    def _poll_send_future(self):
        if not self._send_future:
            self.send_button.setEnabled(True)
            return

        if not self._send_future.done():
            QTimer.singleShot(80, self._poll_send_future)
            return

        try:
            message = self._send_future.result()
            self.message_input.clear()
            if not self._has_message(message["id"]):
                self._add_message_widget(message)
                self.message_list.scrollToBottom()
                QTimer.singleShot(0, self._update_jump_latest_button)
        except Exception as exc:
            QMessageBox.critical(self, self.t("dialog.failed_send_message"), str(exc))
        finally:
            self._send_future = None
            self.send_button.setEnabled(True)

    def load_messages(self, chat_id, show_loading=True, offset_id=0, mode="replace"):
        if self._loading_messages:
            if self._message_future and not self._message_future.done():
                self._message_future.cancel()
            self._message_future = None
            self._loading_messages = False

        if mode == "replace":
            self._reset_thumbnail_loading()
            self._confirmed_latest = None
            self._has_more_messages = True
        self._loading_messages = True
        self._message_load_chat_id = str(chat_id)
        self._message_load_started_at = time.monotonic()
        self._message_load_mode = mode
        self._message_used_cached_result = False

        used_cached_messages = False
        if mode == "replace" and not offset_id:
            cached_messages = self.telegram_service.list_messages_cached(chat_id, limit=500)
            if cached_messages:
                self._render_messages(cached_messages, mode="replace", scroll_to_bottom=False)
                self._restore_chat_position_later(chat_id)
                used_cached_messages = True
                self._message_used_cached_result = True
                self._loading_messages = False
                self._message_load_chat_id = None
                self._message_future = None
                QTimer.singleShot(
                    0,
                    lambda c=str(chat_id): (
                        self.load_newer_messages(sync_until_latest=True)
                        if str(self.current_chat_id) == c
                        else None
                    ),
                )
                return

        if show_loading:
            if not used_cached_messages:
                self.message_list.clear()
                placeholder = QListWidgetItem(self.t("chat.loading_messages"))
                placeholder.setFlags(Qt.NoItemFlags)
                self.message_list.addItem(placeholder)

        self._message_future = self.telegram_service.list_messages_async(
            chat_id,
            limit=50,
            include_thumbnails=False,
            offset_id=offset_id,
        )
        self._poll_message_future(show_loading)

    def _poll_message_future(self, show_loading):
        if not self._message_future:
            self._loading_messages = False
            return

        if not self._message_future.done():
            if time.monotonic() - self._message_load_started_at > 45:
                self._message_future.cancel()
                self._message_future = None
                self._message_load_chat_id = None
                self._loading_messages = False
                self._loading_older_messages = False
                if show_loading:
                    self.message_list.clear()
                    self.jump_latest_button.hide()
                    item = QListWidgetItem(
                        self.t("chat.load_timeout")
                    )
                    item.setFlags(Qt.NoItemFlags)
                    self.message_list.addItem(item)
                return
            QTimer.singleShot(80, lambda: self._poll_message_future(show_loading))
            return

        try:
            messages = self._message_future.result()
        except Exception as exc:
            used_cached_result = self._message_used_cached_result
            if show_loading and not self._message_used_cached_result:
                self.message_list.clear()
            self._message_future = None
            self._message_load_chat_id = None
            self._loading_messages = False
            self._loading_older_messages = False
            self._message_used_cached_result = False
            if used_cached_result and is_transient_network_error(exc):
                QTimer.singleShot(0, self._update_jump_latest_button)
                return
            QMessageBox.critical(self, self.t("dialog.failed_load_messages"), str(exc))
            return

        loaded_chat_id = self._message_load_chat_id
        load_mode = self._message_load_mode
        used_cached_result = self._message_used_cached_result
        self._message_future = None
        self._message_load_chat_id = None
        self._loading_messages = False
        self._loading_older_messages = False
        self._message_used_cached_result = False

        if loaded_chat_id != str(self.current_chat_id):
            return

        if load_mode == "replace" and not messages and used_cached_result:
            return

        current_newest = self.newest_message_id() or 0
        if load_mode == "replace" and current_newest > 0:
            newer_messages = [
                message
                for message in messages
                if int(message.get("id", 0) or 0) > current_newest
            ]
            if newer_messages:
                self._append_newer_messages(newer_messages, keep_scroll_position=True)
                self._confirmed_latest = None
                QTimer.singleShot(
                    0,
                    lambda: self.load_newer_messages(sync_until_latest=True),
                )
            else:
                QTimer.singleShot(0, self._update_jump_latest_button)
            return

        self._render_messages(
            messages,
            mode=load_mode,
            show_empty=show_loading,
            scroll_to_bottom=False,
        )
        if load_mode == "replace":
            self._restore_chat_position_later(loaded_chat_id)

    def _render_messages(
        self,
        messages,
        mode="replace",
        show_empty=True,
        scroll_to_bottom=False,
    ):
        if mode == "prepend":
            self._prepend_messages(messages)
            return

        self.message_list.clear()
        if not messages:
            self.jump_latest_button.hide()
            if show_empty:
                item = QListWidgetItem(self.t("chat.no_messages"))
                item.setFlags(Qt.NoItemFlags)
                self.message_list.addItem(item)
            return

        for message in messages:
            self._add_message_widget(message)
        if scroll_to_bottom:
            self.message_list.scrollToBottom()
            if messages:
                self._newest_seen_id = max(
                    self._newest_seen_id,
                    max(int(m.get("id", 0)) for m in messages),
                )
        QTimer.singleShot(0, self._update_jump_latest_button)
        self._queue_thumbnail_loading(messages)

    def _add_message_widget(self, message):
        item = QListWidgetItem()
        item.setData(Qt.UserRole, message)
        widget = self._message_widget(message)
        self.message_list.addItem(item)
        self.message_list.setItemWidget(item, widget)
        self._update_message_item_size(item, widget)

    def _replace_message_widget(self, item, message):
        scrollbar = self.message_list.verticalScrollBar()
        old_value = scrollbar.value()
        anchor_snapshot = self._visible_anchor_snapshot()

        self._preserving_message_scroll = True
        try:
            item.setData(Qt.UserRole, message)
            widget = self._message_widget(message)
            self.message_list.setItemWidget(item, widget)
            self._update_message_item_size(item, widget)
            scrollbar.setValue(old_value)
        finally:
            self._preserving_message_scroll = False
        if anchor_snapshot.get("anchor_message_id"):
            self._restore_visible_anchor_snapshot_later(anchor_snapshot)
        else:
            self._restore_message_scroll_value_later(old_value)
        QTimer.singleShot(0, self._update_jump_latest_button)

    def _prepend_messages(self, messages):
        if not messages:
            self._has_more_messages = False
            self._loading_older_messages = False
            return

        scrollbar = self.message_list.verticalScrollBar()
        anchor_snapshot = self._visible_anchor_snapshot()

        scrollbar.blockSignals(True)
        self._preserving_message_scroll = True
        try:
            for message in reversed(messages):
                if self._has_message(message["id"]):
                    continue
                item = QListWidgetItem()
                item.setData(Qt.UserRole, message)
                widget = self._message_widget(message)
                self.message_list.insertItem(0, item)
                self.message_list.setItemWidget(item, widget)
                self._update_message_item_size(item, widget)
            self._restore_visible_anchor_snapshot(anchor_snapshot)
        finally:
            self._preserving_message_scroll = False
            scrollbar.blockSignals(False)

        self._loading_older_messages = False
        self._restore_visible_anchor_snapshot_later(anchor_snapshot)
        QTimer.singleShot(0, self._update_jump_latest_button)
        self._queue_thumbnail_loading(messages, append=True)

    def _update_message_item_size(self, item, widget):
        widget.ensurePolished()
        layout = widget.layout()
        if layout is not None:
            layout.activate()
        widget.adjustSize()
        hint = widget.sizeHint()
        item.setSizeHint(QSize(hint.width(), max(44, hint.height() + 14)))

    def _refresh_message_widgets(self):
        self._resize_layout_refresh_pending = False
        for index in range(self.message_list.count()):
            item = self.message_list.item(index)
            message = item.data(Qt.UserRole)
            if not isinstance(message, dict):
                continue
            self._replace_message_widget(item, message)

    def _message_widget(self, message):
        outer = QWidget()
        outer.setStyleSheet("background: transparent;")
        outer_layout = QHBoxLayout(outer)
        outer_layout.setContentsMargins(0, 5, 0, 5)
        outer_layout.setSpacing(0)

        viewport_width = self.message_list.viewport().width() or 620
        bubble_width = max(320, min(560, int(viewport_width * 0.55)))
        content_width = max(260, bubble_width - 30)

        is_out = message["out"]

        if is_out:
            outer_layout.addStretch(2)

        bubble = QFrame()
        bubble.setObjectName("bubbleOut" if is_out else "bubbleIn")
        bubble.setMaximumWidth(bubble_width)

        if is_out:
            bubble.setStyleSheet(
                "QFrame#bubbleOut { background: #DDF0FF; border: 1px solid #B9DCF7; border-radius: 10px; }"
            )
        else:
            bubble.setStyleSheet(
                "QFrame#bubbleIn { background: #FFFFFF; border: 1px solid #DDE5EE; border-radius: 10px; }"
            )

        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(12, 9, 12, 9)
        bubble_layout.setSpacing(6)

        # 消息元数据（发送者 + 时间）
        sender_text = self.t("chat.me") if is_out else self.t("chat.peer")
        time_str = message['date'].split(' ')[-1] if ' ' in message['date'] else message['date']
        meta = QLabel(f"{sender_text}, {time_str}")
        meta.setObjectName("metaText")
        meta.setMaximumWidth(content_width)
        meta.setStyleSheet(
            f"color: {'#5DB74C' if is_out else '#3390EC'}; font-size: 11px; font-weight: 500; "
            "background: transparent;"
        )
        bubble_layout.addWidget(meta)

        # 缩略图
        thumb = self._thumbnail_label(message, max_width=content_width)
        if thumb:
            bubble_layout.addWidget(thumb)
        elif message.get("media_items"):
            bubble_layout.addLayout(self._album_layout(message, content_width))
        elif message.get("media_kind") in ("photo", "video"):
            bubble_layout.addWidget(
                self._thumbnail_placeholder(message, max_width=content_width)
            )

        # 文本内容
        text = message["text"].strip()
        if text:
            text_label = QLabel(linkify_message_text(text))
            text_label.setObjectName("messageText")
            text_label.setTextFormat(Qt.RichText)
            text_label.setWordWrap(True)
            text_label.setMaximumWidth(content_width)
            text_label.setOpenExternalLinks(True)
            text_label.setTextInteractionFlags(
                Qt.TextBrowserInteraction | Qt.TextSelectableByMouse
            )
            text_label.setStyleSheet(
                "QLabel { background: transparent; color: #000000; font-size: 13px; "
                "line-height: 1.35; }"
                "QLabel a { color: #168ACD; text-decoration: none; }"
            )
            bubble_layout.addWidget(text_label)

        # 文件信息
        if message.get("file"):
            file_info = message["file"]
            kind = message.get("media_kind") or "file"
            icons = {"photo": "\U0001F5BC", "video": "\U0001F3AC", "file": "\U0001F4C4"}
            icon = icons.get(kind, "\U0001F4C4")
            file_label = QLabel(f"{icon}  {file_info['name']}")
            file_label.setObjectName("metaText")
            file_label.setWordWrap(True)
            file_label.setMaximumWidth(content_width)
            file_label.setStyleSheet(
                "QLabel { background: transparent; color: #3390EC; font-size: 12px; "
                "padding: 2px 0px; }"
            )
            bubble_layout.addWidget(file_label)

            size_label = QLabel(human_bytes(file_info['size']))
            size_label.setObjectName("metaText")
            size_label.setStyleSheet(
                "QLabel { background: transparent; color: #8E9BA7; font-size: 11px; }"
            )
            bubble_layout.addWidget(size_label)

        outer_layout.addWidget(bubble)
        if not is_out:
            outer_layout.addStretch(2)
        return outer

    def _thumbnail_label(self, message, max_width=360, max_height=220):
        encoded = message.get("thumbnail_base64") or ""
        if not encoded:
            return None

        try:
            raw = base64.b64decode(encoded)
        except Exception:
            return None

        pixmap = QPixmap()
        if not pixmap.loadFromData(raw):
            return None

        label = QLabel()
        label.setObjectName("thumb")
        label.setAlignment(Qt.AlignCenter)
        width = max(160, min(360, int(max_width)))
        height = max(110, min(max_height, int(width * 0.62)))
        label.setMinimumSize(min(220, width), min(120, height))
        label.setMaximumSize(width, height)
        label.setStyleSheet("QLabel#thumb { background: #E8ECF0; border-radius: 10px; }")
        label.setPixmap(
            pixmap.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

        if message.get("media_kind") == "video":
            label.setToolTip("Video preview")

        return label

    def _album_layout(self, message, max_width):
        album_layout = QVBoxLayout()
        album_layout.setSpacing(4)
        current_row = None
        cell_width = max(140, int((max_width - 8) / 2))
        cell_height = max(100, int(cell_width * 0.68))

        for index, media in enumerate(message.get("media_items") or []):
            if index % 2 == 0:
                current_row = QHBoxLayout()
                current_row.setSpacing(4)
                album_layout.addLayout(current_row)

            preview_message = {
                "media_kind": media.get("media_kind", ""),
                "thumbnail_base64": media.get("thumbnail_base64", ""),
            }
            thumb = self._thumbnail_label(
                preview_message,
                max_width=cell_width,
                max_height=cell_height,
            )
            if thumb is None:
                thumb = self._thumbnail_placeholder(
                    preview_message,
                    max_width=cell_width,
                    max_height=cell_height,
                )
            thumb.setMinimumSize(cell_width, cell_height)
            thumb.setMaximumSize(cell_width, cell_height)
            current_row.addWidget(thumb)

        return album_layout

    def _thumbnail_placeholder(self, message, max_width=360, max_height=220):
        label = QLabel(self.t("chat.loading_preview"))
        label.setObjectName("thumb")
        label.setAlignment(Qt.AlignCenter)
        width = max(160, min(360, int(max_width)))
        height = max(110, min(max_height, int(width * 0.62)))
        label.setMinimumSize(min(220, width), min(120, height))
        label.setMaximumSize(width, height)
        label.setStyleSheet(
            "QLabel#thumb { background: #E8ECF0; border-radius: 10px; "
            "color: #8E9BA7; font-size: 12px; }"
        )
        label.setToolTip(f"{message.get('media_kind', 'media').title()} preview")
        return label

    def _reset_thumbnail_loading(self):
        for future in self._thumbnail_futures.values():
            if not future.done():
                future.cancel()
        self._thumbnail_queue = []
        self._thumbnail_futures = {}
        self._thumbnail_chat_id = None

    def _queue_thumbnail_loading(self, messages, append=False):
        if not append:
            self._thumbnail_queue = []
            self._thumbnail_chat_id = str(self.current_chat_id) if self.current_chat_id else None

        queued = []
        for message in messages:
            if message.get("media_items"):
                queued.extend(
                    media["id"]
                    for media in message["media_items"]
                    if media.get("media_kind") in ("photo", "video")
                    and not media.get("thumbnail_base64")
                )
                continue

            if (
                message.get("media_kind") in ("photo", "video")
                and not message.get("thumbnail_base64")
            ):
                queued.append(message["id"])

        existing = set(self._thumbnail_queue) | set(self._thumbnail_futures.keys())
        self._thumbnail_queue.extend(
            message_id for message_id in queued if message_id not in existing
        )
        if not self._thumbnail_chat_id:
            self._thumbnail_chat_id = str(self.current_chat_id) if self.current_chat_id else None
        self._start_next_thumbnail()

    def _start_next_thumbnail(self):
        if not self._thumbnail_chat_id:
            return

        while (
            self._thumbnail_queue
            and len(self._thumbnail_futures) < self._max_thumbnail_concurrency
        ):
            message_id = self._thumbnail_queue.pop(0)
            if message_id in self._thumbnail_futures:
                continue
            self._thumbnail_futures[message_id] = self.telegram_service.message_thumbnail_async(
                self._thumbnail_chat_id,
                message_id,
            )

        if self._thumbnail_futures:
            self._poll_thumbnail_futures()

    def _poll_thumbnail_futures(self):
        if not self._thumbnail_futures:
            return

        completed = [
            message_id
            for message_id, future in self._thumbnail_futures.items()
            if future.done()
        ]

        if not completed:
            QTimer.singleShot(50, self._poll_thumbnail_futures)
            return

        chat_id = self._thumbnail_chat_id
        for message_id in completed:
            future = self._thumbnail_futures.pop(message_id, None)
            if future is None:
                continue

            try:
                thumbnail = future.result()
            except Exception:
                thumbnail = ""

            if chat_id == str(self.current_chat_id) and thumbnail:
                self._apply_thumbnail(message_id, thumbnail)

        self._start_next_thumbnail()

    def _apply_thumbnail(self, message_id, thumbnail):
        for index in range(self.message_list.count()):
            item = self.message_list.item(index)
            message = item.data(Qt.UserRole)
            if not isinstance(message, dict):
                continue

            if message.get("id") == message_id:
                message = dict(message)
                message["thumbnail_base64"] = thumbnail
                self._replace_message_widget(item, message)
                return

            media_items = message.get("media_items") or []
            for media in media_items:
                if media.get("id") != message_id:
                    continue

                message = dict(message)
                message["media_items"] = [dict(media_item) for media_item in media_items]
                for media_item in message["media_items"]:
                    if media_item.get("id") == message_id:
                        media_item["thumbnail_base64"] = thumbnail
                        break
                self._replace_message_widget(item, message)
                return

    def download_selected_message_file(self):
        item = self.message_list.currentItem()
        if not item or not self.current_chat_id:
            QMessageBox.information(
                self, self.t("dialog.tip"), self.t("dialog.select_file_message")
            )
            return

        message = item.data(Qt.UserRole)
        self.download_message_file(message)

    def download_message_file(self, message):
        if not message or not message.get("has_document"):
            QMessageBox.information(
                self, self.t("dialog.tip"), self.t("dialog.no_downloadable_file")
            )
            return

        try:
            media_items = message.get("media_items") or []
            downloadable_ids = [
                media["id"]
                for media in media_items
                if media.get("has_document")
            ]
            if not downloadable_ids:
                downloadable_ids = [message["id"]]

            for message_id in downloadable_ids:
                self.download_manager.add_message_task(self.current_chat_id, message_id)
            self.refresh_download_table()
            self.show_downloads_page()
        except Exception as exc:
            QMessageBox.critical(self, self.t("dialog.failed_add_download"), str(exc))

    def selected_task_id(self):
        selected = self.table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def task_for_table_row(self, row):
        if row < 0:
            return None
        item = self.table.item(row, 0)
        task_id = item.data(Qt.UserRole) if item else None
        return self.download_manager.get_task(task_id) if task_id else None

    def open_download_task_menu(self, position):
        row = self.table.rowAt(position.y())
        task = self.task_for_table_row(row)
        if not task or task.status != "finished":
            return

        self.table.selectRow(row)
        menu = QMenu(self)
        open_folder_action = menu.addAction(self.t("downloads.open_containing_folder"))
        selected_action = menu.exec(self.table.viewport().mapToGlobal(position))
        if selected_action == open_folder_action:
            self.open_task_file_location(task)

    def resolve_task_file_path(self, task):
        candidates = []
        if task.file_path:
            candidates.append(os.path.abspath(task.file_path))

        if task.name:
            download_dir = os.path.abspath(self.settings_manager.ensure_download_dir())
            candidates.append(os.path.join(download_dir, task.name))

            if os.path.isdir(download_dir):
                for root, _, files in os.walk(download_dir):
                    if task.name in files:
                        candidates.append(os.path.join(root, task.name))
                        break

        seen = set()
        for candidate in candidates:
            normalized = os.path.normcase(os.path.abspath(candidate))
            if normalized in seen:
                continue
            seen.add(normalized)
            if os.path.isfile(candidate):
                return candidate
        return ""

    def open_task_file_location(self, task):
        file_path = self.resolve_task_file_path(task)
        if not file_path:
            QMessageBox.information(
                self,
                self.t("dialog.tip"),
                self.t("dialog.file_not_found"),
            )
            return

        file_path = os.path.abspath(file_path)
        if os.name == "nt":
            subprocess.Popen(["explorer.exe", f'/select,"{file_path}"'])
        else:
            QMessageBox.information(
                self,
                self.t("dialog.download_folder"),
                os.path.dirname(file_path),
            )

    def add_download(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(
                self, self.t("dialog.tip"), self.t("dialog.enter_message_link")
            )
            return
        try:
            self.download_manager.add_task(url)
            self.url_input.clear()
            self.refresh_download_table()
        except Exception as exc:
            QMessageBox.critical(self, self.t("dialog.failed_add_download"), str(exc))

    def pause_selected(self):
        task_id = self.selected_task_id()
        if task_id:
            self.download_manager.pause_task(task_id)
            self.refresh_download_table()

    def start_selected(self):
        task_id = self.selected_task_id()
        if task_id:
            self.download_manager.resume_task(task_id)
            self.refresh_download_table()

    def resume_selected(self):
        task_id = self.selected_task_id()
        if task_id:
            self.download_manager.resume_task(task_id)
            self.refresh_download_table()

    def cancel_selected(self):
        task_id = self.selected_task_id()
        if task_id:
            self.download_manager.cancel_task(task_id)
            self.refresh_download_table()

    def open_settings(self):
        dlg = SettingsDialog(
            self.settings_manager,
            self.download_manager,
            self.telegram_service,
            self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.retranslate_ui()

    def relogin(self):
        try:
            self.telegram_service.logout()
        except Exception:
            pass
        dlg = LoginDialog(self.telegram_service, self.settings_manager, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_dialogs()

    def open_download_dir(self):
        path = os.path.abspath(self.settings_manager.get("download_dir"))
        if os.name == "nt":
            os.startfile(path)
        else:
            QMessageBox.information(self, self.t("dialog.download_folder"), path)

    def closeEvent(self, event):
        self._save_chat_position()
        self.telegram_service.remove_message_handler(self.message_bridge.received.emit)
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._resize_layout_refresh_pending:
            return
        self._resize_layout_refresh_pending = True
        QTimer.singleShot(120, self._refresh_message_widgets)

    def refresh_download_table(self):
        tasks = sorted(
            self.download_manager.list_tasks(),
            key=lambda x: x.created_at,
            reverse=True,
        )
        self.update_downloads_badge()
        self.table.setRowCount(len(tasks))

        status_icons = {
            "queued": "\u23f3",
            "downloading": "\u2b07\ufe0f",
            "finished": "\u2705",
            "paused": "\u23f8\ufe0f",
            "failed": "\u274c",
            "cancelled": "\u26d4\ufe0f",
        }

        for row, task in enumerate(tasks):
            icon = status_icons.get(task.status, "")
            status_text = f"{icon} {task.status.title()}"
            name = task.name or task.url
            lower_name = name.lower()
            if lower_name.endswith((".mp4", ".mov", ".mkv", ".avi")):
                file_prefix = "▶  "
            elif lower_name.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
                file_prefix = "▧  "
            elif lower_name.endswith((".zip", ".rar", ".7z")):
                file_prefix = "▣  "
            elif lower_name.endswith((".pdf", ".doc", ".docx")):
                file_prefix = "▤  "
            else:
                file_prefix = "▰  "

            values = [
                file_prefix + name,
                status_text,
                f"{task.progress:.1f}%",
                f"{task.speed / 1024 / 1024:.2f} MB/s" if task.speed > 0 else "\u2014",
                f"{human_bytes(task.downloaded_size)} / {human_bytes(task.total_size)}" if task.total_size > 0 else "\u2014",
                task.error or "\u2014",
                "⋮",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, task.task_id)
                if col in (1, 2, 3, 4, 6):
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, col, item)
