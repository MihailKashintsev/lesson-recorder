"""Regression test for a real crash: PyQt aborts with SIGABRT
("QThread: Destroyed while thread is still running") if the last Python
reference to a QThread is dropped from a slot connected to a signal the
thread emits from inside its own run() — Qt may not have marked it
finished yet. _on_pip_done / _after_recheck must wait() on the thread
before letting the dict pop() release the last reference.

Calls the methods unbound against a minimal fake `self` rather than a
real SettingsWidget — constructing an actual QWidget crashes natively
under pytest + PyQt6 + QT_QPA_PLATFORM=offscreen on this machine (verified
harmless outside pytest, in a plain `python3 -c` run), and the methods
under test only touch self._pip_threads / self._pkg_rows anyway.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from ui.settings_widget import SettingsWidget


def test_on_pip_done_waits_on_thread_before_releasing_reference():
    fake_thread = MagicMock()
    fake_self = SimpleNamespace(
        _pip_threads={"faster-whisper": fake_thread},
        _pkg_rows={},
    )

    SettingsWidget._on_pip_done(fake_self, "faster-whisper", True, "")

    fake_thread.wait.assert_called_once()
    assert "faster-whisper" not in fake_self._pip_threads


def test_after_recheck_waits_on_thread_before_releasing_reference():
    fake_thread = MagicMock()
    fake_self = SimpleNamespace(
        _pip_threads={"__recheck_faster-whisper": fake_thread},
        _pkg_rows={},
    )

    SettingsWidget._after_recheck(fake_self, "faster-whisper")

    fake_thread.wait.assert_called_once()
    assert "__recheck_faster-whisper" not in fake_self._pip_threads


def test_on_pip_done_handles_missing_thread_gracefully():
    fake_self = SimpleNamespace(_pip_threads={}, _pkg_rows={})
    SettingsWidget._on_pip_done(fake_self, "nonexistent-package", False, "some error")
