"""Regression test: a user ran `brew install tesseract` — it works fine from
Terminal — but the app kept reporting Tesseract as missing. GUI apps launched
from Finder/Dock on macOS don't inherit the PATH .zshrc/.zprofile sets up for
Homebrew, so both the PATH lookup and the `which tesseract` subprocess call
in _find_tesseract_cmd_uncached() fail silently, with no Homebrew-specific
fallback path checked (unlike core/python_path.py, which already has one).
"""
from unittest.mock import patch

import core.tesseract_langs as tl


def _reset_cache():
    tl._tesseract_cmd_cache = False


@patch("core.tesseract_langs.sys.platform", "darwin")
@patch("core.tesseract_langs.shutil.which", return_value=None)
@patch("core.tesseract_langs.subprocess.run")
def test_finds_tesseract_at_homebrew_apple_silicon_path_when_path_lookup_fails(
    mock_run, mock_which
):
    _reset_cache()
    mock_run.return_value.returncode = 1  # `which tesseract` fails, as it does for GUI apps
    mock_run.return_value.stdout = ""

    with patch(
        "core.tesseract_langs.Path.exists",
        lambda self: str(self) == "/opt/homebrew/bin/tesseract",
    ):
        assert tl.find_tesseract_cmd() == "/opt/homebrew/bin/tesseract"


@patch("core.tesseract_langs.sys.platform", "darwin")
@patch("core.tesseract_langs.shutil.which", return_value=None)
@patch("core.tesseract_langs.subprocess.run")
def test_finds_tesseract_at_homebrew_intel_path(mock_run, mock_which):
    _reset_cache()
    mock_run.return_value.returncode = 1
    mock_run.return_value.stdout = ""

    with patch(
        "core.tesseract_langs.Path.exists",
        lambda self: str(self) == "/usr/local/bin/tesseract",
    ):
        assert tl.find_tesseract_cmd() == "/usr/local/bin/tesseract"


@patch("core.tesseract_langs.sys.platform", "win32")
@patch("core.tesseract_langs.shutil.which", return_value=None)
@patch("core.tesseract_langs.subprocess.run")
def test_windows_does_not_check_homebrew_paths(mock_run, mock_which):
    _reset_cache()
    mock_run.return_value.returncode = 1
    mock_run.return_value.stdout = ""

    with patch("core.tesseract_langs.Path.exists", return_value=False):
        assert tl.find_tesseract_cmd() is None
