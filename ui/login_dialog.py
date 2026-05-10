import base64

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout


class LoginDialog(QDialog):
    def __init__(self, telegram_service, parent=None):
        super().__init__(parent)
        self.telegram_service = telegram_service
        self.setWindowTitle("Telegram 二维码登录")
        self.resize(380, 460)

        self.status_label = QLabel("正在生成二维码...")
        self.status_label.setAlignment(Qt.AlignCenter)

        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignCenter)

        self.refresh_button = QPushButton("刷新二维码")
        self.refresh_button.clicked.connect(self.load_qr)

        layout = QVBoxLayout(self)
        layout.addWidget(self.status_label)
        layout.addWidget(self.qr_label, 1)
        layout.addWidget(self.refresh_button)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_login)
        self.timer.start(1500)

        self.load_qr()

    def load_qr(self):
        try:
            data = self.telegram_service.generate_qr()
            if data["status"] == "authorized":
                self.accept()
                return
            raw = base64.b64decode(data["image_base64"])
            pixmap = QPixmap()
            pixmap.loadFromData(raw, "PNG")
            self.qr_label.setPixmap(
                pixmap.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            self.status_label.setText("请用 Telegram 手机客户端扫码登录")
        except Exception as exc:
            self.status_label.setText(f"二维码生成失败: {exc}")

    def check_login(self):
        try:
            if self.telegram_service.is_authorized(timeout=10):
                self.status_label.setText("登录成功")
                self.accept()
        except Exception:
            pass
