import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QDialog

from config import APP_ICON_FILE, APP_NAME
from core.settings_manager import settings_manager
from downloader.download_manager import DownloadManager
from telegram.service import TelegramService
from ui.login_dialog import LoginDialog
from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app_icon = QIcon(str(APP_ICON_FILE))
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    telegram_service = TelegramService(settings_manager)
    telegram_service.start()

    download_manager = DownloadManager(telegram_service, settings_manager)

    try:
        if not telegram_service.is_authorized(timeout=20):
            dlg = LoginDialog(telegram_service, settings_manager)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                telegram_service.stop()
                return 0

        window = MainWindow(telegram_service, download_manager, settings_manager)
        if not app_icon.isNull():
            window.setWindowIcon(app_icon)
        window.show()
        exit_code = app.exec()
    finally:
        download_manager.shutdown()
        telegram_service.stop()

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
