"""Regression test: a real user's Mac had /usr/bin/python3 on PATH pointing
at the Xcode Command Line Tools' bundled Python 3.9 (a read-only framework
install, below MIN_PYTHON = 3.10). find_python_exe()'s PATH step used to
return whatever `shutil.which("python3")` found with zero version check, so
the app happily used that 3.9 for pip installs — which then failed with
"no matching distribution" for packages that dropped 3.9 support, instead
of showing the "Python not found" banner and offering to install a real one.
"""
from unittest.mock import patch, MagicMock

from core.python_path import _check_exe, _version_at_least


def _fake_run(version: str):
    def run(cmd, **kwargs):
        return MagicMock(returncode=0, stdout=f"{version}\n", stderr="")
    return run


@patch("subprocess.run")
def test_version_at_least_rejects_old_python(mock_run):
    mock_run.side_effect = _fake_run("3.9")
    assert _version_at_least("/usr/bin/python3", (3, 10)) is False


@patch("subprocess.run")
def test_version_at_least_accepts_new_enough_python(mock_run):
    mock_run.side_effect = _fake_run("3.13")
    assert _version_at_least("/opt/homebrew/bin/python3", (3, 10)) is True


@patch("core.python_path.Path.exists", return_value=True)
@patch("subprocess.run")
def test_check_exe_rejects_xcode_python_3_9(mock_run, mock_exists):
    mock_run.side_effect = _fake_run("3.9")
    xcode_python = (
        "/Applications/Xcode.app/Contents/Developer/Library/Frameworks/"
        "Python3.framework/Versions/3.9/bin/python3"
    )
    assert _check_exe(xcode_python) is None


@patch("core.python_path.Path.exists", return_value=True)
@patch("subprocess.run")
def test_check_exe_accepts_modern_python(mock_run, mock_exists):
    mock_run.side_effect = _fake_run("3.13")
    assert _check_exe("/opt/homebrew/bin/python3") == "/opt/homebrew/bin/python3"
