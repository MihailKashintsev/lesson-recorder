## What's new in v0.0.9

- **Fix (macOS, important):** the macOS build was never code-signed at all — not even ad-hoc. On Apple Silicon this means the app can't launch at all ("LessonRecorder is damaged and can't be opened"), and `xattr -cr` / right-click-Open don't fix it because the problem isn't quarantine, it's a missing signature. The build is now ad-hoc signed. If you're on v0.0.8 or earlier and can't open the app: delete it and install this version fresh (drag the new `.app` from the `.zip` straight to Applications).
- The in-app updater now strips the quarantine flag from the update it downloads automatically, instead of requiring the `xattr -cr` Terminal command by hand on every update.
