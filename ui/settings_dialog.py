from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)


class SettingsDialog(QDialog):
    def __init__(self, settings_manager, download_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.download_manager = download_manager
        self.setWindowTitle("设置")
        self.resize(420, 220)

        self.max_tasks = QSpinBox()
        self.max_tasks.setRange(1, 20)
        self.max_tasks.setValue(int(self.settings_manager.get("max_concurrent_tasks", 3)))

        self.chunk_concurrency = QSpinBox()
        self.chunk_concurrency.setRange(1, 16)
        self.chunk_concurrency.setValue(int(self.settings_manager.get("chunk_concurrency", 4)))

        self.download_dir = QLineEdit(self.settings_manager.get("download_dir"))

        browse_btn = QPushButton("选择目录")
        browse_btn.clicked.connect(self.browse_dir)

        dir_row = QHBoxLayout()
        dir_row.addWidget(self.download_dir)
        dir_row.addWidget(browse_btn)

        form = QFormLayout()
        form.addRow("同时下载任务数", self.max_tasks)
        form.addRow("单文件分块并发数", self.chunk_concurrency)
        form.addRow("下载目录", dir_row)

        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.save)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addStretch(1)
        root.addWidget(save_btn)

    def browse_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "选择下载目录", self.download_dir.text())
        if directory:
            self.download_dir.setText(directory)

    def save(self):
        self.settings_manager.set("max_concurrent_tasks", int(self.max_tasks.value()))
        self.settings_manager.set("chunk_concurrency", int(self.chunk_concurrency.value()))
        self.settings_manager.set("download_dir", self.download_dir.text().strip())
        self.download_manager.refresh_limits()
        self.accept()
