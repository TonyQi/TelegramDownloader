import base64
import os
import time

from PySide6.QtCore import QEasingCurve, QObject, Qt, QSize, QTimer, Signal, QPropertyAnimation
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
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
)

from ui.login_dialog import LoginDialog
from ui.settings_dialog import SettingsDialog


def human_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    num = float(size)
    for unit in units:
        if num < 1024 or unit == units[-1]:
            return f"{num:.2f} {unit}"
        num /= 1024.0
    return f"{size} B"


class MessageBridge(QObject):
    received = Signal(dict)


class MainWindow(QMainWindow):
    def __init__(self, telegram_service, download_manager, settings_manager):
        super().__init__()
        self.telegram_service = telegram_service
        self.download_manager = download_manager
        self.settings_manager = settings_manager
        self.current_chat_id = None
        self._loading_dialogs = False
        self._loading_messages = False
        self._dialog_future = None
        self._message_future = None
        self._send_future = None
        self._message_load_chat_id = None
        self._message_load_started_at = 0.0
        self._message_load_mode = "replace"
        self._loading_older_messages = False
        self._has_more_messages = True
        self._thumbnail_queue = []
        self._thumbnail_futures = {}
        self._thumbnail_chat_id = None
        self._max_thumbnail_concurrency = 4
        self._resize_layout_refresh_pending = False
        self.message_bridge = MessageBridge()
        self.message_bridge.received.connect(self.on_realtime_message)
        self.telegram_service.add_message_handler(self.message_bridge.received.emit)

        self.setWindowTitle("Telegram Downloader")
        self.resize(1360, 780)
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #f5f7fb; color: #111827; }
            QToolBar { background: #ffffff; border-bottom: 1px solid #dfe5ee; spacing: 8px; }
            QLineEdit {
                background: #ffffff; border: 1px solid #d6deea; border-radius: 8px;
                padding: 8px 10px;
            }
            QPushButton {
                background: #229ed9; color: #ffffff; border: 0; border-radius: 8px;
                padding: 8px 14px; font-weight: 600;
            }
            QPushButton:hover { background: #168ac0; }
            QListWidget, QTableWidget {
                background: #ffffff; border: 1px solid #dfe5ee; border-radius: 8px;
                selection-background-color: #d9effc; selection-color: #111827;
            }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #edf1f6; }
            QListWidget::item:selected { background: #d9effc; }
            QHeaderView::section {
                background: #f8fafc; border: 0; border-bottom: 1px solid #dfe5ee;
                padding: 8px; font-weight: 600;
            }
            QLabel#sectionTitle { font-size: 16px; font-weight: 700; padding: 4px 2px; }
            QLabel#metaText { color: #64748b; font-size: 12px; }
            QLabel#messageText { background: transparent; }
            QLabel#thumb { background: #e5edf5; border-radius: 8px; }
            QFrame#panel { background: #f5f7fb; border: 0; }
            QFrame#bubbleIn { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; }
            QFrame#bubbleOut { background: #e0f2fe; border: 1px solid #bae6fd; border-radius: 8px; }
            """
        )

        self._build_toolbar()
        self._build_layout()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_download_table)
        self.timer.start(int(self.settings_manager.get("refresh_interval_ms", 700)))

        self.load_dialogs()
        self.refresh_download_table()

    def _build_toolbar(self):
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        refresh_action = QAction("Refresh chats", self)
        refresh_action.triggered.connect(self.load_dialogs)
        toolbar.addAction(refresh_action)

        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.open_settings)
        toolbar.addAction(settings_action)

        relogin_action = QAction("Re-login", self)
        relogin_action.triggered.connect(self.relogin)
        toolbar.addAction(relogin_action)

        toolbar.addSeparator()

        chats_action = QAction("Chats", self)
        chats_action.triggered.connect(self.show_chat_page)
        toolbar.addAction(chats_action)

        downloads_action = QAction("Downloads", self)
        downloads_action.triggered.connect(self.show_downloads_page)
        toolbar.addAction(downloads_action)

    def _build_layout(self):
        self.pages = QStackedWidget()
        self.setCentralWidget(self.pages)

        chat_page = QWidget()
        root = QSplitter(Qt.Horizontal, chat_page)
        chat_page_layout = QVBoxLayout(chat_page)
        chat_page_layout.setContentsMargins(0, 0, 0, 0)
        chat_page_layout.addWidget(root)

        dialogs_panel = self._panel()
        dialogs_layout = QVBoxLayout(dialogs_panel)
        dialogs_layout.addWidget(self._title("Telegram"))
        self.dialog_search = QLineEdit()
        self.dialog_search.setPlaceholderText("Search chats")
        self.dialog_search.textChanged.connect(self.filter_dialogs)
        dialogs_layout.addWidget(self.dialog_search)
        self.dialog_list = QListWidget()
        self.dialog_list.itemSelectionChanged.connect(self.on_dialog_selected)
        dialogs_layout.addWidget(self.dialog_list, 1)

        chat_panel = self._panel()
        chat_layout = QVBoxLayout(chat_panel)
        self.chat_title = self._title("Select a chat")
        chat_layout.addWidget(self.chat_title)
        self.message_list = QListWidget()
        self.message_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.message_list.setResizeMode(QListWidget.Adjust)
        self.message_list.setWordWrap(True)
        self.message_list.setSpacing(6)
        self.message_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.message_list.customContextMenuRequested.connect(self.open_message_menu)
        self.message_list.verticalScrollBar().valueChanged.connect(
            self.on_message_scroll
        )
        chat_layout.addWidget(self.message_list, 1)
        message_actions = QHBoxLayout()
        self.reload_messages_button = QPushButton("Refresh messages")
        self.reload_messages_button.clicked.connect(self.reload_current_messages)
        message_actions.addWidget(self.reload_messages_button)
        message_actions.addStretch(1)
        chat_layout.addLayout(message_actions)

        send_row = QHBoxLayout()
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Write a message")
        self.message_input.returnPressed.connect(self.send_current_message)
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_current_message)
        send_row.addWidget(self.message_input, 1)
        send_row.addWidget(self.send_button)
        chat_layout.addLayout(send_row)

        downloads_page = QWidget()
        downloads_page_layout = QVBoxLayout(downloads_page)
        downloads_page_layout.setContentsMargins(8, 8, 8, 8)

        downloads_panel = self._panel()
        downloads_layout = QVBoxLayout(downloads_panel)
        downloads_layout.addWidget(self._title("Download queue"))
        link_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste a Telegram message link")
        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.add_download)
        link_row.addWidget(self.url_input, 1)
        link_row.addWidget(self.add_button)
        downloads_layout.addLayout(link_row)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["File", "Status", "Progress", "Speed", "Size", "Error"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        downloads_layout.addWidget(self.table, 1)

        queue_actions = QHBoxLayout()
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_selected)
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.pause_selected)
        self.resume_button = QPushButton("Resume")
        self.resume_button.clicked.connect(self.resume_selected)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_selected)
        self.open_dir_button = QPushButton("Open folder")
        self.open_dir_button.clicked.connect(self.open_download_dir)
        queue_actions.addWidget(self.start_button)
        queue_actions.addWidget(self.pause_button)
        queue_actions.addWidget(self.resume_button)
        queue_actions.addWidget(self.cancel_button)
        queue_actions.addStretch(1)
        queue_actions.addWidget(self.open_dir_button)
        downloads_layout.addLayout(queue_actions)
        downloads_page_layout.addWidget(downloads_panel)

        root.addWidget(dialogs_panel)
        root.addWidget(chat_panel)
        root.setSizes([320, 900])

        self.pages.addWidget(chat_page)
        self.pages.addWidget(downloads_page)
        self.pages.setCurrentIndex(0)

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

    def show_chat_page(self):
        self.switch_page(0)

    def show_downloads_page(self):
        self.refresh_download_table()
        self.switch_page(1)

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
        download_action = menu.addAction("Download")
        selected_action = menu.exec(self.message_list.mapToGlobal(position))
        if selected_action == download_action:
            self.download_message_file(message)

    def load_dialogs(self):
        if self._loading_dialogs:
            return

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
            QMessageBox.critical(self, "Failed to load chats", str(exc))
            return

        self._dialog_future = None
        self._loading_dialogs = False

        selected_chat_id = self.current_chat_id
        self.dialog_list.clear()
        for dialog in dialogs:
            title = dialog["title"]
            unread = f"  ({dialog['unread_count']})" if dialog["unread_count"] else ""
            item = QListWidgetItem(f"{title}{unread}")
            item.setData(Qt.UserRole, dialog)
            self.dialog_list.addItem(item)
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
        self.current_chat_id = dialog["id"]
        self._has_more_messages = True
        self.chat_title.setText(dialog["title"])
        self.load_messages(dialog["id"])

    def reload_current_messages(self):
        if self.current_chat_id:
            self.load_messages(self.current_chat_id, show_loading=False)

    def on_message_scroll(self, value):
        scrollbar = self.message_list.verticalScrollBar()
        if value > scrollbar.minimum() + 20:
            return
        if not self.current_chat_id or self._loading_messages or self._loading_older_messages:
            return
        if not self._has_more_messages or self.message_list.count() == 0:
            return
        self.load_older_messages()

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

    def on_realtime_message(self, message):
        chat_id = str(message.get("chat_id", ""))
        if chat_id != str(self.current_chat_id):
            return

        if self._has_message(message["id"]):
            return

        if self.message_list.count() == 1:
            only_item = self.message_list.item(0)
            if only_item and only_item.flags() == Qt.NoItemFlags:
                self.message_list.clear()

        self._add_message_widget(message)
        self.message_list.scrollToBottom()
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
            QMessageBox.information(self, "Tip", "Select a chat first")
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
        except Exception as exc:
            QMessageBox.critical(self, "Failed to send message", str(exc))
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
            self._has_more_messages = True
        self._loading_messages = True
        self._message_load_chat_id = str(chat_id)
        self._message_load_started_at = time.monotonic()
        self._message_load_mode = mode
        if show_loading:
            self.message_list.clear()
            placeholder = QListWidgetItem("Loading messages...")
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
                    item = QListWidgetItem(
                        "Message loading timed out. Check proxy and try Refresh messages."
                    )
                    item.setFlags(Qt.NoItemFlags)
                    self.message_list.addItem(item)
                return
            QTimer.singleShot(80, lambda: self._poll_message_future(show_loading))
            return

        try:
            messages = self._message_future.result()
        except Exception as exc:
            if show_loading:
                self.message_list.clear()
            self._message_future = None
            self._message_load_chat_id = None
            self._loading_messages = False
            QMessageBox.critical(self, "Failed to load messages", str(exc))
            return

        loaded_chat_id = self._message_load_chat_id
        load_mode = self._message_load_mode
        self._message_future = None
        self._message_load_chat_id = None
        self._loading_messages = False
        self._loading_older_messages = False

        if loaded_chat_id != str(self.current_chat_id):
            return

        if load_mode == "prepend":
            self._prepend_messages(messages)
            return

        self.message_list.clear()
        if not messages:
            item = QListWidgetItem("No messages")
            item.setFlags(Qt.NoItemFlags)
            self.message_list.addItem(item)
            return

        for message in messages:
            self._add_message_widget(message)
        self.message_list.scrollToBottom()
        self._queue_thumbnail_loading(messages)

    def _add_message_widget(self, message):
        item = QListWidgetItem()
        item.setData(Qt.UserRole, message)
        widget = self._message_widget(message)
        self.message_list.addItem(item)
        self.message_list.setItemWidget(item, widget)
        self._update_message_item_size(item, widget)

    def _replace_message_widget(self, item, message):
        item.setData(Qt.UserRole, message)
        widget = self._message_widget(message)
        self.message_list.setItemWidget(item, widget)
        self._update_message_item_size(item, widget)

    def _prepend_messages(self, messages):
        if not messages:
            self._has_more_messages = False
            return

        scrollbar = self.message_list.verticalScrollBar()
        old_max = scrollbar.maximum()

        for message in reversed(messages):
            if self._has_message(message["id"]):
                continue
            item = QListWidgetItem()
            item.setData(Qt.UserRole, message)
            widget = self._message_widget(message)
            self.message_list.insertItem(0, item)
            self.message_list.setItemWidget(item, widget)
            self._update_message_item_size(item, widget)

        new_max = scrollbar.maximum()
        scrollbar.setValue(new_max - old_max)
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
        outer_layout = QHBoxLayout(outer)
        outer_layout.setContentsMargins(4, 2, 4, 2)
        outer_layout.setSpacing(8)

        viewport_width = self.message_list.viewport().width() or 620
        bubble_width = max(280, min(520, int(viewport_width * 0.72)))
        content_width = max(220, bubble_width - 32)

        if message["out"]:
            outer_layout.addStretch(1)

        bubble = QFrame()
        bubble.setObjectName("bubbleOut" if message["out"] else "bubbleIn")
        bubble.setMaximumWidth(bubble_width)
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(10, 8, 10, 8)
        bubble_layout.setSpacing(6)

        meta = QLabel(("Me" if message["out"] else "Chat") + f" · {message['date']}")
        meta.setObjectName("metaText")
        meta.setMaximumWidth(content_width)
        bubble_layout.addWidget(meta)

        thumb = self._thumbnail_label(message, max_width=content_width)
        if thumb:
            bubble_layout.addWidget(thumb)
        elif message.get("media_items"):
            bubble_layout.addLayout(self._album_layout(message, content_width))
        elif message.get("media_kind") in ("photo", "video"):
            bubble_layout.addWidget(
                self._thumbnail_placeholder(message, max_width=content_width)
            )

        text = message["text"].strip()
        if text:
            text_label = QLabel(text)
            text_label.setObjectName("messageText")
            text_label.setWordWrap(True)
            text_label.setMaximumWidth(content_width)
            text_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            bubble_layout.addWidget(text_label)

        if message.get("file"):
            file_info = message["file"]
            kind = message.get("media_kind") or "file"
            file_label = QLabel(
                f"{kind.title()}: {file_info['name']} · {human_bytes(file_info['size'])}"
            )
            file_label.setObjectName("metaText")
            file_label.setWordWrap(True)
            file_label.setMaximumWidth(content_width)
            bubble_layout.addWidget(file_label)

        outer_layout.addWidget(bubble)
        if not message["out"]:
            outer_layout.addStretch(1)
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
        label.setPixmap(
            pixmap.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

        if message.get("media_kind") == "video":
            label.setToolTip("Video preview")

        return label

    def _album_layout(self, message, max_width):
        album_layout = QVBoxLayout()
        album_layout.setSpacing(6)
        current_row = None
        cell_width = max(130, int((max_width - 8) / 2))
        cell_height = max(100, int(cell_width * 0.68))

        for index, media in enumerate(message.get("media_items") or []):
            if index % 2 == 0:
                current_row = QHBoxLayout()
                current_row.setSpacing(6)
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
        label = QLabel("Loading preview...")
        label.setObjectName("thumb")
        label.setAlignment(Qt.AlignCenter)
        width = max(160, min(360, int(max_width)))
        height = max(110, min(max_height, int(width * 0.62)))
        label.setMinimumSize(min(220, width), min(120, height))
        label.setMaximumSize(width, height)
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
            QTimer.singleShot(100, self._poll_thumbnail_futures)
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
            QMessageBox.information(self, "Tip", "Select a file message first")
            return

        message = item.data(Qt.UserRole)
        self.download_message_file(message)

    def download_message_file(self, message):
        if not message or not message.get("has_document"):
            QMessageBox.information(self, "Tip", "This message has no downloadable file")
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
            QMessageBox.critical(self, "Failed to add download", str(exc))

    def selected_task_id(self):
        selected = self.table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def add_download(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Tip", "Enter a Telegram message link")
            return
        try:
            self.download_manager.add_task(url)
            self.url_input.clear()
            self.refresh_download_table()
        except Exception as exc:
            QMessageBox.critical(self, "Failed to add download", str(exc))

    def pause_selected(self):
        task_id = self.selected_task_id()
        if task_id:
            self.download_manager.pause_task(task_id)

    def start_selected(self):
        task_id = self.selected_task_id()
        if task_id:
            self.download_manager.resume_task(task_id)

    def resume_selected(self):
        task_id = self.selected_task_id()
        if task_id:
            self.download_manager.resume_task(task_id)

    def cancel_selected(self):
        task_id = self.selected_task_id()
        if task_id:
            self.download_manager.cancel_task(task_id)

    def open_settings(self):
        dlg = SettingsDialog(
            self.settings_manager,
            self.download_manager,
            self.telegram_service,
            self,
        )
        dlg.exec()

    def relogin(self):
        try:
            self.telegram_service.logout()
        except Exception:
            pass
        dlg = LoginDialog(self.telegram_service, self)
        if dlg.exec() == dlg.Accepted:
            self.load_dialogs()

    def open_download_dir(self):
        path = os.path.abspath(self.settings_manager.get("download_dir"))
        if os.name == "nt":
            os.startfile(path)
        else:
            QMessageBox.information(self, "Download folder", path)

    def closeEvent(self, event):
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
        self.table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            values = [
                task.name or task.url,
                task.status,
                f"{task.progress:.2f}%",
                f"{task.speed / 1024 / 1024:.2f} MB/s",
                f"{human_bytes(task.downloaded_size)} / {human_bytes(task.total_size)}",
                task.error,
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, task.task_id)
                self.table.setItem(row, col, item)
