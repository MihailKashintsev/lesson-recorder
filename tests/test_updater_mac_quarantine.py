"""Regression tests for macOS update extraction (core.updater._install_unix).

Two real bugs a user hit while updating on an M1 Mac, back to back:

1. Gatekeeper quarantine blocking an unsigned app extracted from the update
   zip — fixed by stripping com.apple.quarantine from the extracted .app.

2. The bigger one: `zsh: permission denied` when actually trying to launch
   the "installed" update. zipfile.extractall() does NOT restore the Unix
   executable bit on extracted files (a well-known stdlib limitation) —
   Finder/Archive Utility use `ditto`/`unzip` under the hood, which do. The
   fix prefers `ditto -x -k` for extraction on macOS, and as a defense-in-
   depth fallback also explicitly chmod +x's everything under
   Contents/MacOS/ regardless of which extraction path ran.
"""
import os
import stat
import zipfile
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.updater import UpdateDialog


def _make_update_zip(tmp_path) -> str:
    zip_path = tmp_path / "LessonRecorder_v0.0.11_macOS_arm64.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        # zipfile.writestr() does not set the executable bit in external_attr —
        # this is exactly how a real update zip extracts with plain zipfile.
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
def test_ditto_unavailable_falls_back_to_zipfile_and_still_restores_exec_bit(
    mock_run, mock_popen, tmp_path
):
    zip_path = _make_update_zip(tmp_path)
    # Simulate no ditto on PATH / it failing — every subprocess.run() call
    # (ditto, then xattr) reports failure/no-op.
    mock_run.return_value = MagicMock(returncode=1)

    UpdateDialog._install_unix(_fake_self(), zip_path)

    binary = tmp_path / "LessonRecorder_update" / "LessonRecorder.app" / "Contents" / "MacOS" / "LessonRecorder"
    assert binary.is_file()
    mode = stat.S_IMODE(binary.stat().st_mode)
    assert mode & stat.S_IXUSR, "main executable must have the +x bit after extraction"


@patch("core.updater.sys.platform", "darwin")
@patch("core.updater.subprocess.Popen")
@patch("core.updater.subprocess.run")
def test_prefers_ditto_over_zipfile_when_available(mock_run, mock_popen, tmp_path):
    zip_path = _make_update_zip(tmp_path)
    mock_run.return_value = MagicMock(returncode=0)  # ditto "succeeds" (mocked — no real extraction happens)

    UpdateDialog._install_unix(_fake_self(), zip_path)

    # zipfile is imported locally inside _install_unix, so it can't be patched
    # from here — instead prove the fallback never ran the way its only
    # observable side effect would: the mocked ditto call did nothing, so if
    # zipfile.extractall() had ALSO run, the directory wouldn't be empty.
    extract_dir = tmp_path / "LessonRecorder_update"
    assert extract_dir.is_dir()
    assert list(extract_dir.iterdir()) == []

    calls = [c.args[0] for c in mock_run.call_args_list]
    assert calls[0][0] == "ditto"


@patch("core.updater.sys.platform", "darwin")
@patch("core.updater.subprocess.Popen")
@patch("core.updater.subprocess.run")
def test_extracted_app_gets_quarantine_stripped(mock_run, mock_popen, tmp_path):
    zip_path = _make_update_zip(tmp_path)
    mock_run.return_value = MagicMock(returncode=1)  # ditto fails -> zipfile fallback

    UpdateDialog._install_unix(_fake_self(), zip_path)

    extracted_app = tmp_path / "LessonRecorder_update" / "LessonRecorder.app"
    assert extracted_app.is_dir()
    xattr_calls = [c.args[0] for c in mock_run.call_args_list if c.args[0][0] == "xattr"]
    assert xattr_calls == [["xattr", "-cr", str(extracted_app)]]


@patch("core.updater.sys.platform", "linux")
@patch("core.updater.subprocess.Popen")
@patch("core.updater.subprocess.run")
def test_linux_does_not_call_ditto_or_xattr(mock_run, mock_popen, tmp_path):
    zip_path = _make_update_zip(tmp_path)

    UpdateDialog._install_unix(_fake_self(), zip_path)

    mock_run.assert_not_called()
