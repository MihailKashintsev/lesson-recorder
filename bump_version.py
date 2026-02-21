"""
Обновляет версию в version.py и installer/version_info.txt
Использование: python bump_version.py 1.1.0
"""
import sys
import re

if len(sys.argv) < 2:
    print("Usage: python bump_version.py 1.1.0")
    sys.exit(1)

version = sys.argv[1]
parts = version.split(".")
win_ver = f"{parts[0]}, {parts[1]}, {parts[2]}, 0"

# version.py
with open("version.py", "r", encoding="utf-8") as f:
    content = f.read()
content = re.sub(r'__version__ = "[^"]*"', f'__version__ = "{version}"', content)
with open("version.py", "w", encoding="utf-8") as f:
    f.write(content)
print(f"version.py -> {version}")

# version_info.txt
with open("installer/version_info.txt", "r", encoding="utf-8") as f:
    info = f.read()
info = re.sub(r"filevers=\([^)]*\)", f"filevers=({win_ver})", info)
info = re.sub(r"prodvers=\([^)]*\)", f"prodvers=({win_ver})", info)
info = re.sub(r"u'FileVersion', u'[^']*'", f"u'FileVersion', u'{version}.0'", info)
info = re.sub(r"u'ProductVersion', u'[^']*'", f"u'ProductVersion', u'{version}.0'", info)
with open("installer/version_info.txt", "w", encoding="utf-8") as f:
    f.write(info)
print(f"version_info.txt -> {version}")

print("OK")
