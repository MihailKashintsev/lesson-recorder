"""
core/transcriber.py restarts transcription without faster-whisper when the
worker subprocess exits with a code in NATIVE_CRASH_CODES (the fallback
branch is `rc in NATIVE_CRASH_CODES or (rc is not None and rc < 0)` inside
Transcriber.run()). That branch itself is entangled with QThread + a real
subprocess.Popen and isn't worth faking an integration test around, but the
crash-code table it depends on is plain module-level data we can check
directly — a typo'd hex constant here would silently break the fallback for
that specific crash.
"""
from core.transcriber import NATIVE_CRASH_CODES


def test_known_windows_crash_codes_are_present():
    # ACCESS_VIOLATION (0xC0000005) and DLL init failure (0xC0000142) are the
    # two crash codes users have actually hit with faster-whisper/ctranslate2.
    assert 0xC0000005 in NATIVE_CRASH_CODES
    assert 0xC0000142 in NATIVE_CRASH_CODES


def test_crash_codes_are_unsigned_32bit_values():
    # These are Windows exit codes as reported by subprocess (unsigned),
    # so every entry must fit in 32 bits and be non-negative.
    for code in NATIVE_CRASH_CODES:
        assert 0 <= code <= 0xFFFFFFFF
