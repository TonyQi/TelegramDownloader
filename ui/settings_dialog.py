from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from core.i18n import LANGUAGES, make_translator
from core.proxy import normalize_proxy_settings

_SETTINGS_STYLE = """
QDialog {
    background: #FFFFFF;
}
QLabel#dialogTitle {
    font-size: 17px;
    font-weight: 700;
    color: #000000;
}
QLabel#sectionLabel {
    font-size: 13px;
    font-weight: 600;
    color: #3390EC;
    padding: 8px 0px 2px 0px;
}
QLabel#fieldLabel {
    font-size: 13px;
    color: #000000;
}
QLineEdit {
    background: #F0F2F5;
    border: none;
    border-radius: 8px;
    padding: 7px 12px;
    font-size: 13px;
    color: #000000;
}
QLineEdit:focus {
    background: #FFFFFF;
    border: 1.5px solid #3390EC;
}
QSpinBox {
    background: #F0F2F5;
    border: none;
    border-radius: 8px;
    padding: 7px 12px;
    font-size: 13px;
    color: #000000;
}
QSpinBox:focus {
    background: #FFFFFF;
    border: 1.5px solid #3390EC;
}
QComboBox {
    background: #F0F2F5;
    border: none;
    border-radius: 8px;
    padding: 7px 12px;
    font-size: 13px;
    color: #000000;
}
QComboBox:focus {
    background: #FFFFFF;
    border: 1.5px solid #3390EC;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QCheckBox {
    font-size: 13px;
    color: #000000;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #DADCE0;
    border-radius: 4px;
    background: #FFFFFF;
}
QCheckBox::indicator:checked {
    background: #3390EC;
    border-color: #3390EC;
}
QPushButton#saveBtn {
    background: #3390EC;
    color: #FFFFFF;
    border: none;
    border-radius: 10px;
    padding: 10px 28px;
    font-size: 14px;
    font-weight: 600;
}
QPushButton#saveBtn:hover {
    background: #2B7FDB;
}
QPushButton#saveBtn:pressed {
    background: #2270C4;
}
QPushButton#browseBtn {
    background: transparent;
    color: #3390EC;
    border: 1.5px solid #3390EC;
    border-radius: 8px;
    padding: 7px 14px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#browseBtn:hover {
    background: rgba(51, 144, 236, 0.08);
}
QPushButton#testBtn {
    background: transparent;
    color: #3390EC;
    border: 1.5px solid #DADCE0;
    border-radius: 8px;
    padding: 7px 14px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#testBtn:hover {
    background: #F4F4F5;
    border-color: #3390EC;
}
QLabel#testStatus {
    font-size: 12px;
    color: #8E9BA7;
}
QLabel#testStatusSuccess {
    font-size: 12px;
    color: #4CAF50;
    font-weight: 600;
}
QLabel#testStatusFail {
    font-size: 12px;
    color: #E53935;
}
QFrame#divider {
    background: #F0F2F5;
    max-height: 1px;
}
"""


class SettingsDialog(QDialog):
    def __init__(self, settings_manager, download_manager, telegram_service=None, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.download_manager = download_manager
        self.telegram_service = telegram_service
        self.t = make_translator(settings_manager)
        self._proxy_test_future = None

        self.setWindowTitle(self.t("settings.title"))
        self.resize(500, 640)
        self.setStyleSheet(_SETTINGS_STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(0)

        # 标题
        title = QLabel(self.t("settings.title"))
        title.setObjectName("dialogTitle")
        root.addWidget(title)
        root.addSpacing(20)

        # ── 下载设置 ──
        section0 = QLabel(self.t("settings.section.general"))
        section0.setObjectName("sectionLabel")
        root.addWidget(section0)
        root.addSpacing(6)

        form0 = QFormLayout()
        form0.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form0.setSpacing(10)

        self.language_combo = QComboBox()
        for code, label in LANGUAGES.items():
            self.language_combo.addItem(label, code)
        current_language = self.settings_manager.get("language", "en")
        language_index = self.language_combo.findData(current_language)
        self.language_combo.setCurrentIndex(max(language_index, 0))
        self.language_combo.setFixedHeight(34)
        form0.addRow(self.t("settings.language"), self.language_combo)
        root.addLayout(form0)

        divider0 = QFrame()
        divider0.setObjectName("divider")
        divider0.setFixedHeight(1)
        root.addSpacing(16)
        root.addWidget(divider0)
        root.addSpacing(16)

        section1 = QLabel(self.t("settings.section.download"))
        section1.setObjectName("sectionLabel")
        root.addWidget(section1)
        root.addSpacing(6)

        form1 = QFormLayout()
        form1.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form1.setSpacing(10)

        self.max_tasks = QSpinBox()
        self.max_tasks.setRange(1, 20)
        self.max_tasks.setValue(int(self.settings_manager.get("max_concurrent_tasks", 3)))
        self.max_tasks.setFixedHeight(34)
        form1.addRow(self.t("settings.max_tasks"), self.max_tasks)

        self.chunk_concurrency = QSpinBox()
        self.chunk_concurrency.setRange(1, 16)
        self.chunk_concurrency.setValue(
            int(self.settings_manager.get("chunk_concurrency", 4))
        )
        self.chunk_concurrency.setFixedHeight(34)
        form1.addRow(self.t("settings.chunks_per_file"), self.chunk_concurrency)

        dir_row = QHBoxLayout()
        dir_row.setSpacing(6)
        self.download_dir = QLineEdit(self.settings_manager.get("download_dir"))
        self.download_dir.setFixedHeight(34)

        browse_btn = QPushButton(self.t("settings.browse"))
        browse_btn.setObjectName("browseBtn")
        browse_btn.setFixedHeight(34)
        browse_btn.setCursor(Qt.PointingHandCursor)
        browse_btn.clicked.connect(self.browse_dir)
        dir_row.addWidget(self.download_dir, 1)
        dir_row.addWidget(browse_btn)
        form1.addRow(self.t("settings.download_folder"), dir_row)

        root.addLayout(form1)

        # 分割线
        divider1 = QFrame()
        divider1.setObjectName("divider")
        divider1.setFixedHeight(1)
        root.addSpacing(16)
        root.addWidget(divider1)
        root.addSpacing(16)

        # ── 代理设置 ──
        section2 = QLabel(self.t("settings.section.proxy"))
        section2.setObjectName("sectionLabel")
        root.addWidget(section2)
        root.addSpacing(6)

        proxy = normalize_proxy_settings(self.settings_manager.get("proxy"))

        self.proxy_enabled = QCheckBox(self.t("settings.use_proxy"))
        self.proxy_enabled.setChecked(proxy["enabled"])
        self.proxy_enabled.setCursor(Qt.PointingHandCursor)
        root.addWidget(self.proxy_enabled)
        root.addSpacing(8)

        form2 = QFormLayout()
        form2.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form2.setSpacing(10)

        self.proxy_scheme = QComboBox()
        self.proxy_scheme.addItems(["socks5", "http"])
        self.proxy_scheme.setCurrentText(proxy["scheme"])
        self.proxy_scheme.setFixedHeight(34)
        form2.addRow(self.t("settings.proxy_type"), self.proxy_scheme)

        self.proxy_host = QLineEdit(proxy["host"])
        self.proxy_host.setPlaceholderText("127.0.0.1")
        self.proxy_host.setFixedHeight(34)
        form2.addRow(self.t("settings.host"), self.proxy_host)

        self.proxy_port = QSpinBox()
        self.proxy_port.setRange(1, 65535)
        self.proxy_port.setValue(proxy["port"] if proxy["port"] > 0 else 7897)
        self.proxy_port.setFixedHeight(34)
        form2.addRow(self.t("settings.port"), self.proxy_port)

        self.proxy_username = QLineEdit(proxy["username"])
        self.proxy_username.setFixedHeight(34)
        form2.addRow(self.t("settings.username"), self.proxy_username)

        self.proxy_password = QLineEdit(proxy["password"])
        self.proxy_password.setEchoMode(QLineEdit.Password)
        self.proxy_password.setFixedHeight(34)
        form2.addRow(self.t("settings.password"), self.proxy_password)

        root.addLayout(form2)
        root.addSpacing(8)

        # 测试连接
        test_row = QHBoxLayout()
        test_row.setSpacing(8)
        self.test_proxy_btn = QPushButton(self.t("settings.test_connection"))
        self.test_proxy_btn.setObjectName("testBtn")
        self.test_proxy_btn.setFixedHeight(34)
        self.test_proxy_btn.setCursor(Qt.PointingHandCursor)
        self.test_proxy_btn.clicked.connect(self.test_proxy)

        self.proxy_test_status = QLabel(self.t("settings.not_tested"))
        self.proxy_test_status.setObjectName("testStatus")
        test_row.addWidget(self.test_proxy_btn)
        test_row.addWidget(self.proxy_test_status, 1)
        root.addLayout(test_row)

        self.proxy_enabled.toggled.connect(self.update_proxy_controls)
        self.update_proxy_controls()

        root.addStretch()

        # 底部保存按钮
        save_row = QHBoxLayout()
        save_row.addStretch()
        save_btn = QPushButton(self.t("settings.save"))
        save_btn.setObjectName("saveBtn")
        save_btn.setFixedHeight(40)
        save_btn.setMinimumWidth(120)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self.save)
        save_row.addWidget(save_btn)
        root.addSpacing(8)
        root.addLayout(save_row)

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
            self.proxy_test_status.setText(self.t("settings.proxy_disabled"))
            self.proxy_test_status.setObjectName("testStatus")
        elif self.proxy_test_status.text() in (
            self.t("settings.proxy_disabled"),
            self.t("settings.not_tested"),
        ):
            self.proxy_test_status.setText(self.t("settings.not_tested"))
            self.proxy_test_status.setObjectName("testStatus")

        self.proxy_test_status.style().unpolish(self.proxy_test_status)
        self.proxy_test_status.style().polish(self.proxy_test_status)

    def browse_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            self.t("settings.choose_folder"),
            self.download_dir.text(),
        )
        if directory:
            self.download_dir.setText(directory)

    def test_proxy(self):
        if self.telegram_service is None:
            QMessageBox.warning(
                self,
                self.t("settings.proxy_test"),
                self.t("settings.service_unavailable"),
            )
            return

        proxy = self.proxy_settings()
        if proxy["enabled"] and not proxy["host"]:
            QMessageBox.warning(
                self,
                self.t("settings.proxy_test"),
                self.t("settings.proxy_host_required"),
            )
            return

        self.proxy_test_status.setText(self.t("settings.testing"))
        self.proxy_test_status.setObjectName("testStatus")
        self.proxy_test_status.style().unpolish(self.proxy_test_status)
        self.proxy_test_status.style().polish(self.proxy_test_status)
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
            self.proxy_test_status.setText(self.t("settings.connection_failed"))
            self.proxy_test_status.setObjectName("testStatusFail")
            self.proxy_test_status.style().unpolish(self.proxy_test_status)
            self.proxy_test_status.style().polish(self.proxy_test_status)
            QMessageBox.critical(self, self.t("settings.proxy_test_failed"), str(exc))
        else:
            self.proxy_test_status.setText(self.t("settings.connected"))
            self.proxy_test_status.setObjectName("testStatusSuccess")
            self.proxy_test_status.style().unpolish(self.proxy_test_status)
            self.proxy_test_status.style().polish(self.proxy_test_status)
        finally:
            self._proxy_test_future = None
            self.test_proxy_btn.setEnabled(self.proxy_enabled.isChecked())

    def save(self):
        self.settings_manager.set("max_concurrent_tasks", int(self.max_tasks.value()))
        self.settings_manager.set("chunk_concurrency", int(self.chunk_concurrency.value()))
        self.settings_manager.set("download_dir", self.download_dir.text().strip())
        self.settings_manager.set("language", self.language_combo.currentData())
        self.settings_manager.set("proxy", self.proxy_settings())
        self.t = make_translator(self.settings_manager)
        self.download_manager.refresh_limits()
        QMessageBox.information(
            self,
            self.t("settings.saved_title"),
            self.t("settings.saved_message"),
        )
        self.accept()
