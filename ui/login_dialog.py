import base64

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFrame

from core.i18n import make_translator

class LoginDialog(QDialog):
    def __init__(self, telegram_service, settings_manager=None, parent=None):
        super().__init__(parent)
        self.telegram_service = telegram_service
        self.t = make_translator(settings_manager)
        self.setWindowTitle(self.t("login.title"))
        self.resize(380, 480)
        self.setStyleSheet("""
            QDialog {
                background: #FFFFFF;
            }
            QLabel#titleLabel {
                font-size: 20px;
                font-weight: 700;
                color: #000000;
            }
            QLabel#subtitleLabel {
                font-size: 13px;
                color: #8E9BA7;
                line-height: 1.4;
            }
            QLabel#statusLabel {
                font-size: 13px;
                color: #8E9BA7;
            }
            QLabel#statusLabelSuccess {
                font-size: 13px;
                color: #4CAF50;
                font-weight: 600;
            }
            QLabel#statusLabelError {
                font-size: 13px;
                color: #E53935;
            }
            QPushButton#refreshBtn {
                background: #3390EC;
                color: #FFFFFF;
                border: none;
                border-radius: 10px;
                padding: 10px 24px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton#refreshBtn:hover {
                background: #2B7FDB;
            }
            QPushButton#refreshBtn:pressed {
                background: #2270C4;
            }
            QFrame#qrContainer {
                background: #FFFFFF;
                border: 2px solid #E8ECF0;
                border-radius: 16px;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(0)

        # 标题
        title = QLabel(self.t("login.heading"))
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)
        root.addSpacing(8)

        subtitle = QLabel(self.t("login.subtitle"))
        subtitle.setObjectName("subtitleLabel")
        subtitle.setAlignment(Qt.AlignCenter)
        root.addWidget(subtitle)
        root.addSpacing(24)

        # QR 容器
        qr_container = QFrame()
        qr_container.setObjectName("qrContainer")
        qr_container.setFixedSize(260, 260)
        qr_layout = QVBoxLayout(qr_container)
        qr_layout.setContentsMargins(16, 16, 16, 16)

        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setFixedSize(228, 228)
        qr_layout.addWidget(self.qr_label, alignment=Qt.AlignCenter)
        root.addWidget(qr_container, alignment=Qt.AlignCenter)
        root.addSpacing(18)

        # 状态文字
        self.status_label = QLabel(self.t("login.generating"))
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self.status_label)
        root.addSpacing(16)

        # 刷新按钮
        self.refresh_button = QPushButton(self.t("login.refresh"))
        self.refresh_button.setObjectName("refreshBtn")
        self.refresh_button.setFixedHeight(42)
        self.refresh_button.setCursor(Qt.PointingHandCursor)
        self.refresh_button.clicked.connect(self.load_qr)
        root.addWidget(self.refresh_button, alignment=Qt.AlignCenter)

        root.addStretch()

        # 底部提示
        hint = QLabel(self.t("login.hint"))
        hint.setObjectName("subtitleLabel")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("font-size: 11px; color: #B0B8C0;")
        root.addWidget(hint)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_login)
        self.timer.start(1500)

        self.load_qr()

    def load_qr(self):
        try:
            data = self.telegram_service.generate_qr()
            if data["status"] == "authorized":
                self.status_label.setText(self.t("login.success"))
                self.status_label.setObjectName("statusLabelSuccess")
                self.status_label.style().unpolish(self.status_label)
                self.status_label.style().polish(self.status_label)
                self.accept()
                return
            raw = base64.b64decode(data["image_base64"])
            pixmap = QPixmap()
            pixmap.loadFromData(raw, "PNG")
            self.qr_label.setPixmap(
                pixmap.scaled(224, 224, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            self.status_label.setText(self.t("login.waiting"))
            self.status_label.setObjectName("statusLabel")
            self.status_label.style().unpolish(self.status_label)
            self.status_label.style().polish(self.status_label)
        except Exception as exc:
            self.status_label.setText(self.t("login.qr_error", error=exc))
            self.status_label.setObjectName("statusLabelError")
            self.status_label.style().unpolish(self.status_label)
            self.status_label.style().polish(self.status_label)

    def check_login(self):
        try:
            if self.telegram_service.is_authorized(timeout=10):
                self.status_label.setText(self.t("login.success"))
                self.status_label.setObjectName("statusLabelSuccess")
                self.status_label.style().unpolish(self.status_label)
                self.status_label.style().polish(self.status_label)
                self.accept()
        except Exception:
            pass
