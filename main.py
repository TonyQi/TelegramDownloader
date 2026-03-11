import sys

from PySide6.QtWidgets import QApplication
##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
from config import APP_NAME
from core.settings_manager import settings_manager
from downloader.download_manager import DownloadManager
from telegram.service import TelegramService
from ui.login_dialog import LoginDialog
from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    telegram_service = TelegramService()
    telegram_service.start()

    download_manager = DownloadManager(telegram_service, settings_manager)

    try:
        if not telegram_service.is_authorized(timeout=20):
            dlg = LoginDialog(telegram_service)
            if dlg.exec() != dlg.Accepted:
                telegram_service.stop()
                return 0

        window = MainWindow(telegram_service, download_manager, settings_manager)
        window.show()
        exit_code = app.exec()
    finally:
        download_manager.shutdown()
        telegram_service.stop()

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
