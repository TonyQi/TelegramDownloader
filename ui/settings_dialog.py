from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from core.proxy import normalize_proxy_settings


class SettingsDialog(QDialog):
    def __init__(self, settings_manager, download_manager, telegram_service=None, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.download_manager = download_manager
        self.telegram_service = telegram_service
        self._proxy_test_future = None

        self.setWindowTitle("Settings")
        self.resize(520, 380)

        self.max_tasks = QSpinBox()
        self.max_tasks.setRange(1, 20)
        self.max_tasks.setValue(int(self.settings_manager.get("max_concurrent_tasks", 3)))

        self.chunk_concurrency = QSpinBox()
        self.chunk_concurrency.setRange(1, 16)
        self.chunk_concurrency.setValue(
            int(self.settings_manager.get("chunk_concurrency", 4))
        )

        self.download_dir = QLineEdit(self.settings_manager.get("download_dir"))

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_dir)

        dir_row = QHBoxLayout()
        dir_row.addWidget(self.download_dir)
        dir_row.addWidget(browse_btn)

        proxy = normalize_proxy_settings(self.settings_manager.get("proxy"))
        self.proxy_enabled = QCheckBox("Use proxy")
        self.proxy_enabled.setChecked(proxy["enabled"])

        self.proxy_scheme = QComboBox()
        self.proxy_scheme.addItems(["socks5", "http"])
        self.proxy_scheme.setCurrentText(proxy["scheme"])

        self.proxy_host = QLineEdit(proxy["host"])
        self.proxy_host.setPlaceholderText("127.0.0.1")

        self.proxy_port = QSpinBox()
        self.proxy_port.setRange(1, 65535)
        self.proxy_port.setValue(proxy["port"] if proxy["port"] > 0 else 7897)

        self.proxy_username = QLineEdit(proxy["username"])
        self.proxy_password = QLineEdit(proxy["password"])
        self.proxy_password.setEchoMode(QLineEdit.Password)

        self.proxy_test_status = QLabel("")
        self.test_proxy_btn = QPushButton("Test Telegram connection")
        self.test_proxy_btn.clicked.connect(self.test_proxy)

        proxy_test_row = QHBoxLayout()
        proxy_test_row.addWidget(self.test_proxy_btn)
        proxy_test_row.addWidget(self.proxy_test_status, 1)

        form = QFormLayout()
        form.addRow("Max concurrent tasks", self.max_tasks)
        form.addRow("Chunks per file", self.chunk_concurrency)
        form.addRow("Download folder", dir_row)
        form.addRow(self.proxy_enabled)
        form.addRow("Proxy type", self.proxy_scheme)
        form.addRow("Proxy host", self.proxy_host)
        form.addRow("Proxy port", self.proxy_port)
        form.addRow("Username", self.proxy_username)
        form.addRow("Password", self.proxy_password)
        form.addRow("Proxy test", proxy_test_row)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addStretch(1)
        root.addWidget(save_btn)

        self.proxy_enabled.toggled.connect(self.update_proxy_controls)
        self.update_proxy_controls()

    def proxy_settings(self):
        return {
            "enabled": self.proxy_enabled.isChecked(),
            "scheme": self.proxy_scheme.currentText(),
            "host": self.proxy_host.text().strip(),
            "port": int(self.proxy_port.value()),
            "username": self.proxy_username.text().strip(),
            "password": self.proxy_password.text(),
        }

    def update_proxy_controls(self):
        enabled = self.proxy_enabled.isChecked()
        for widget in (
            self.proxy_scheme,
            self.proxy_host,
            self.proxy_port,
            self.proxy_username,
            self.proxy_password,
            self.test_proxy_btn,
        ):
            widget.setEnabled(enabled)

        if not enabled:
            self.proxy_test_status.setText("Proxy disabled")
        elif not self.proxy_test_status.text():
            self.proxy_test_status.setText("Not tested")

    def browse_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Choose download folder",
            self.download_dir.text(),
        )
        if directory:
            self.download_dir.setText(directory)

    def test_proxy(self):
        if self.telegram_service is None:
            QMessageBox.warning(self, "Proxy test", "Telegram service is not available")
            return

        proxy = self.proxy_settings()
        if proxy["enabled"] and not proxy["host"]:
            QMessageBox.warning(self, "Proxy test", "Proxy host is required")
            return

        self.proxy_test_status.setText("Testing...")
        self.test_proxy_btn.setEnabled(False)
        self._proxy_test_future = self.telegram_service.test_proxy_async(proxy)
        self._poll_proxy_test()

    def _poll_proxy_test(self):
        if not self._proxy_test_future:
            self.test_proxy_btn.setEnabled(self.proxy_enabled.isChecked())
            return

        if not self._proxy_test_future.done():
            QTimer.singleShot(100, self._poll_proxy_test)
            return

        try:
            self._proxy_test_future.result()
        except Exception as exc:
            self.proxy_test_status.setText("Failed")
            QMessageBox.critical(self, "Proxy test failed", str(exc))
        else:
            self.proxy_test_status.setText("Connected to Telegram")
            QMessageBox.information(
                self,
                "Proxy test",
                "Proxy can connect to Telegram.",
            )
        finally:
            self._proxy_test_future = None
            self.test_proxy_btn.setEnabled(self.proxy_enabled.isChecked())

    def save(self):
        self.settings_manager.set("max_concurrent_tasks", int(self.max_tasks.value()))
        self.settings_manager.set("chunk_concurrency", int(self.chunk_concurrency.value()))
        self.settings_manager.set("download_dir", self.download_dir.text().strip())
        self.settings_manager.set("proxy", self.proxy_settings())
        self.download_manager.refresh_limits()
        QMessageBox.information(
            self,
            "Settings saved",
            "Proxy changes take effect after reconnecting or restarting the app.",
        )
        self.accept()
