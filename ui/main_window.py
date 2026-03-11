import os

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
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


class MainWindow(QMainWindow):
    def __init__(self, telegram_service, download_manager, settings_manager):
        super().__init__()
        self.telegram_service = telegram_service
        self.download_manager = download_manager
        self.settings_manager = settings_manager
        self.setWindowTitle("Telegram Desktop Downloader")
        self.resize(1200, 700)

        toolbar = QToolBar()
        self.addToolBar(toolbar)

        settings_action = QAction("设置", self)
        settings_action.triggered.connect(self.open_settings)
        toolbar.addAction(settings_action)

        relogin_action = QAction("重新登录", self)
        relogin_action.triggered.connect(self.relogin)
        toolbar.addAction(relogin_action)

        central = QWidget()
        self.setCentralWidget(central)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("输入 Telegram 消息链接，例如 https://t.me/channel/123")

        self.add_button = QPushButton("添加下载")
        self.add_button.clicked.connect(self.add_download)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("消息链接"))
        top_row.addWidget(self.url_input, 1)
        top_row.addWidget(self.add_button)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["任务ID", "文件名", "状态", "进度", "速度", "已下载 / 总大小", "错误", "文件路径"]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)

        self.pause_button = QPushButton("暂停")
        self.pause_button.clicked.connect(self.pause_selected)
        self.resume_button = QPushButton("继续")
        self.resume_button.clicked.connect(self.resume_selected)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.cancel_selected)
        self.open_dir_button = QPushButton("打开下载目录")
        self.open_dir_button.clicked.connect(self.open_download_dir)

        bottom_row = QHBoxLayout()
        bottom_row.addWidget(self.pause_button)
        bottom_row.addWidget(self.resume_button)
        bottom_row.addWidget(self.cancel_button)
        bottom_row.addStretch(1)
        bottom_row.addWidget(self.open_dir_button)

        layout = QVBoxLayout(central)
        layout.addLayout(top_row)
        layout.addWidget(self.table, 1)
        layout.addLayout(bottom_row)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_table)
        self.timer.start(int(self.settings_manager.get("refresh_interval_ms", 700)))

        self.refresh_table()

    def selected_task_id(self):
        selected = self.table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        item = self.table.item(row, 0)
        return item.text() if item else None

    def add_download(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "提示", "请输入 Telegram 消息链接")
            return
        try:
            self.download_manager.add_task(url)
            self.url_input.clear()
            self.refresh_table()
        except Exception as exc:
            QMessageBox.critical(self, "错误", str(exc))

    def pause_selected(self):
        task_id = self.selected_task_id()
        if task_id:
            self.download_manager.pause_task(task_id)

    def resume_selected(self):
        task_id = self.selected_task_id()
        if task_id:
            self.download_manager.resume_task(task_id)

    def cancel_selected(self):
        task_id = self.selected_task_id()
        if task_id:
            self.download_manager.cancel_task(task_id)

    def open_settings(self):
        dlg = SettingsDialog(self.settings_manager, self.download_manager, self)
        dlg.exec()

    def relogin(self):
        try:
            self.telegram_service.logout()
        except Exception:
            pass
        dlg = LoginDialog(self.telegram_service, self)
        dlg.exec()

    def open_download_dir(self):
        path = os.path.abspath(self.settings_manager.get("download_dir"))
        if os.name == "nt":
            os.startfile(path)
        else:
            QMessageBox.information(self, "下载目录", path)

    def refresh_table(self):
        tasks = sorted(self.download_manager.list_tasks(), key=lambda x: x.created_at, reverse=True)
        self.table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            values = [
                task.task_id,
                task.name or "",
                task.status,
                f"{task.progress:.2f}%",
                f"{task.speed / 1024 / 1024:.2f} MB/s",
                f"{human_bytes(task.downloaded_size)} / {human_bytes(task.total_size)}",
                task.error,
                task.file_path,
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))
