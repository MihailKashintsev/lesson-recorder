## What's new in v0.0.8

- **Fix (crash):** installing or checking a package in Settings could crash the app on exit from that action ("QThread: Destroyed while thread is still running"). A background thread's last reference was released a moment too early — fixed by waiting for it to actually finish first.
- macOS crash reports will now show the real app version instead of a hardcoded "1.0.0".
