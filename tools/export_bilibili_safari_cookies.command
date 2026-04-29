#!/bin/zsh
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Exporting Safari cookies for BiliNote..."
echo "Cookie values will not be printed."

.venv/bin/python -m yt_dlp \
  --cookies-from-browser safari \
  --cookies backend/cookies.txt \
  --skip-download \
  --no-warnings \
  --quiet \
  https://www.bilibili.com/video/BV1fCdUBkEst

python3 - <<'PY'
from pathlib import Path

p = Path("backend/cookies.txt")
text = p.read_text(errors="ignore").splitlines() if p.exists() else []
bili = [line for line in text if line and not line.startswith("#") and "bilibili" in line]
names = []
for line in bili:
    parts = line.split("\t")
    if len(parts) >= 7:
        names.append(parts[5])

login_names = {"SESSDATA", "DedeUserID", "bili_jct"}
present = sorted(login_names.intersection(names))

print(f"cookies file: {p.resolve()}")
print(f"bilibili cookie count: {len(bili)}")
print(f"login cookies present: {'yes' if present else 'no'}")
if present:
    print("login cookie names present:", ", ".join(present))
else:
    print("No Bilibili login cookies were found.")
PY

echo "Done."
