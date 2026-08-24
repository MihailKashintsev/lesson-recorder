## What's new in v0.0.7

- **Fix:** the Windows installer had stopped actually installing Python — a previous change removed the install steps but left the wizard text promising an automatic download. Restored.
- **macOS:** Python now installs automatically, both from `mac_setup.sh` and with a one-click "Установить автоматически" button right in the app's Settings screen (installs Homebrew first if it's missing, then Python through it).
- Added engineering documentation and a small test suite.
