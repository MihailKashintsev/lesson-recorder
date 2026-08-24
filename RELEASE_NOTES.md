## What's new in v0.0.11

- **Fix (macOS, the real "can't be opened" cause):** every update installed through the app's own updater silently produced a binary with no executable permission at all ("zsh: permission denied" if you tried to launch it from Terminal). Python's zip extraction doesn't restore Unix file permissions the way Finder does — the updater now uses `ditto` (the same tool Finder uses) to extract, with a permission-repair fallback either way.
- If you're updating from v0.0.10 or earlier and the app currently won't open at all: the in-app updater can't fix this one either, since it can't run. Delete the app and install fresh from this release's `.zip` instead.
