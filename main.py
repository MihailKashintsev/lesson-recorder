import sys
import traceback


def main():
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from PyQt6.QtGui import QFont, QIcon
        from PyQt6.QtCore import QTimer
    except ImportError:
        print("ОШИБКА: PyQt6 не установлен.")
        print("Выполни: pip install -r requirements.txt")
        input("Нажми Enter для выхода...")
        sys.exit(1)

    app = QApplication(sys.argv)

    # Глобальный перехват исключений
    def handle_exception(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        error_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        print("КРИТИЧЕСКАЯ ОШИБКА:\n", error_text)
        try:
            msg = QMessageBox()
            msg.setWindowTitle("LessonRecorder — Ошибка")
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setText("Произошла ошибка. Скопируй текст ниже для отладки:")
            msg.setDetailedText(error_text)
            msg.exec()
        except Exception:
            pass

    sys.excepthook = handle_exception

    try:
        import core.database as db
        db.init_db()
    except Exception as e:
        QMessageBox.critical(None, "Ошибка БД", f"Не удалось инициализировать базу данных:\n{e}")
        sys.exit(1)

    try:
        from version import __version__, APP_NAME
    except ImportError:
        __version__ = "dev"
        APP_NAME = "LessonRecorder"

    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(APP_NAME)

    # Попытка загрузить иконку приложения
    try:
        import os
        from pathlib import Path
        icon_path = Path(__file__).parent / "app_icon.ico"
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
    except Exception:
        pass

    try:
        from ui.main_window import MainWindow
        window = MainWindow()
        window.show()
    except Exception as e:
        error_text = traceback.format_exc()
        QMessageBox.critical(None, "Ошибка запуска",
            f"Не удалось открыть главное окно:\n\n{e}\n\n{error_text}")
        sys.exit(1)

    # ✅ ИСПРАВЛЕНО: Проверка обновлений через QTimer — только в главном потоке
    # Раньше вызов из фонового потока мог открывать дополнительное окно
    def _start_update_check():
        try:
            from core.updater import check_for_updates_async
            check_for_updates_async(parent=window)
        except Exception:
            pass

    QTimer.singleShot(3000, _start_update_check)  # через 3 секунды после запуска

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
