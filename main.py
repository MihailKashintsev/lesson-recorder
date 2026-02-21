import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

import core.database as db
from ui.main_window import MainWindow
from version import __version__, APP_NAME


def main():
    db.init_db()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(APP_NAME)

    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    # Проверяем обновления в фоне через 2 сек после запуска
    from core.updater import check_for_updates_async
    check_for_updates_async(parent=window)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
