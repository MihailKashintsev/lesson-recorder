"""Regression test: PyAudioWPatch (Windows-only WASAPI loopback, no macOS/Linux
wheels on PyPI) was shown as an installable package on every platform and
"Install missing" would auto-attempt it, always failing with a confusing
"No matching distribution found" error on macOS/Linux.
"""
from unittest.mock import patch

from ui.settings_widget import _packages_for_current_platform, PACKAGES_INFO


@patch("ui.settings_widget.sys.platform", "darwin")
def test_windows_only_package_excluded_on_macos():
    names = [p["pip_name"] for p in _packages_for_current_platform()]
    assert "PyAudioWPatch" not in names


@patch("ui.settings_widget.sys.platform", "win32")
def test_windows_only_package_included_on_windows():
    names = [p["pip_name"] for p in _packages_for_current_platform()]
    assert "PyAudioWPatch" in names


@patch("ui.settings_widget.sys.platform", "darwin")
def test_cross_platform_packages_still_included_on_macos():
    names = [p["pip_name"] for p in _packages_for_current_platform()]
    assert "faster-whisper" in names
    assert "openai-whisper" in names


def test_pyaudiowpatch_entry_is_tagged_windows_only():
    entry = next(p for p in PACKAGES_INFO if p["pip_name"] == "PyAudioWPatch")
    assert entry["platforms"] == ("win32",)
