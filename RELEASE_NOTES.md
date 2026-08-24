## What's new in v0.0.10

- **Fix (macOS):** the app could pick up the ancient Python 3.9 bundled with Xcode Command Line Tools instead of a real Python — pip installs then failed with "No matching distribution found". Now the found Python's version is actually checked.
- **Fix (macOS):** `PyAudioWPatch` (Windows-only) no longer shows up as an installable package on macOS/Linux.
- **Fix (macOS):** Tesseract OCR installed via Homebrew is now detected correctly — GUI apps don't inherit your Terminal's PATH, so the app was blind to `/opt/homebrew/bin/tesseract` even when it was installed and working.
