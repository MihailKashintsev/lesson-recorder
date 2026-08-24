"""Тесты для PythonInstallThread (ui/settings_widget.py) — автоустановка
Homebrew+Python на macOS из работающего приложения. Мокаем subprocess/shutil,
реальный Homebrew/Python на машине, где гоняются тесты, не трогаем.
"""
import os
import sys
from unittest.mock import patch, MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6")

from ui.settings_widget import PythonInstallThread


def _run_thread(thread: PythonInstallThread):
    result = {}
    thread.done.connect(lambda ok, msg: result.update(success=ok, message=msg))
    thread.run()  # вызываем run() напрямую — без event loop, синхронно
    return result


@patch("ui.settings_widget.shutil.which", return_value="/opt/homebrew/bin/brew")
@patch("ui.settings_widget.subprocess.run")
def test_brew_already_present_installs_python_directly(mock_run, mock_which):
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    result = _run_thread(PythonInstallThread())
    assert result["success"] is True
    # Homebrew не переустанавливался — сразу brew install python@...
    assert mock_run.call_count == 1
    args = mock_run.call_args[0][0]
    assert args[0] == "/opt/homebrew/bin/brew"
    assert args[1] == "install"
    assert "python@" in args[2]


@patch("ui.settings_widget.Path")
@patch("ui.settings_widget.shutil.which", return_value=None)
@patch("ui.settings_widget.subprocess.run")
def test_brew_missing_bootstraps_homebrew_then_python(mock_run, mock_which, mock_path_cls):
    # Первый subprocess.run — установка Homebrew (успех), второй — brew install python
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout="", stderr=""),
        MagicMock(returncode=0, stdout="", stderr=""),
    ]
    mock_path_cls.return_value.exists.return_value = True
    result = _run_thread(PythonInstallThread())
    assert result["success"] is True
    assert mock_run.call_count == 2


@patch("ui.settings_widget.shutil.which", return_value=None)
@patch("ui.settings_widget.subprocess.run")
def test_homebrew_install_failure_reported_not_crashed(mock_run, mock_which):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="curl failed")
    result = _run_thread(PythonInstallThread())
    assert result["success"] is False
    assert "Homebrew" in result["message"]


@patch("ui.settings_widget.shutil.which", return_value="/opt/homebrew/bin/brew")
@patch("ui.settings_widget.subprocess.run")
def test_brew_install_python_failure_reported_not_crashed(mock_run, mock_which):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="no bottle available")
    result = _run_thread(PythonInstallThread())
    assert result["success"] is False
    assert "Python" in result["message"]
