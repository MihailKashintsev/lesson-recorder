"""Regression test: a user updated on macOS, dragged the new .app to
Applications exactly as instructed, and got "can't be opened" — Gatekeeper
blocking an unsigned app extracted from the update zip. _install_unix must
strip the quarantine attribute from the extracted .app itself, the same
fix the in-app instructions already tell users to run by hand.

Calls the method unbound against a minimal fake `self` (SimpleNamespace with
mock progress_bar/status_label) rather than constructing a real QDialog —
see tests/test_pip_thread_lifetime.py for why real widget construction is
avoided under pytest + PyQt6 + QT_QPA_PLATFORM=offscreen on this machine.
"""
import os
import zipfile
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.updater import UpdateDialog


def _make_update_zip(tmp_path) -> str:
    zip_path = tmp_path / "LessonRecorder_v0.0.9_macOS_arm64.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("LessonRecorder.app/Contents/MacOS/LessonRecorder", "fake binary")
        z.writestr("LessonRecorder.app/Contents/Info.plist", "<plist/>")
    return str(zip_path)


def _fake_self():
    return SimpleNamespace(
        progress_bar=MagicMock(), status_label=MagicMock(), skip_btn=MagicMock()
    )


@patch("core.updater.sys.platform", "darwin")
@patch("core.updater.subprocess.Popen")
@patch("core.updater.subprocess.run")
def test_extracted_app_gets_quarantine_stripped_on_macos(mock_run, mock_popen, tmp_path):
    zip_path = _make_update_zip(tmp_path)

    UpdateDialog._install_unix(_fake_self(), zip_path)

    extracted_app = tmp_path / "LessonRecorder_update" / "LessonRecorder.app"
    assert extracted_app.is_dir()
    mock_run.assert_called_once_with(["xattr", "-cr", str(extracted_app)], check=False)


@patch("core.updater.sys.platform", "linux")
@patch("core.updater.subprocess.Popen")
@patch("core.updater.subprocess.run")
def test_linux_does_not_call_xattr(mock_run, mock_popen, tmp_path):
    zip_path = _make_update_zip(tmp_path)

    UpdateDialog._install_unix(_fake_self(), zip_path)

    mock_run.assert_not_called()
