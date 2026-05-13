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
import re

p = Path("backend/cookies.txt")
text = p.read_text(errors="ignore").splitlines() if p.exists() else []
bili = [line for line in text if line and not line.startswith("#") and "bilibili" in line]
names = []
cookie_pairs = []
for line in bili:
    parts = line.split("\t")
    if len(parts) >= 7:
        names.append(parts[5])
        cookie_pairs.append((parts[5], parts[6]))

login_names = {"SESSDATA", "DedeUserID", "bili_jct"}
present = sorted(login_names.intersection(names))

preferred_keys = [
    "SESSDATA",
    "bili_jct",
    "DedeUserID",
    "DedeUserID__ckMd5",
    "sid",
    "buvid3",
    "buvid4",
    "buvid_fp",
    "_uuid",
    "b_nut",
    "bili_ticket",
    "bili_ticket_expires",
    "CURRENT_FNVAL",
    "PVID",
]
selected = []
seen = set()
for key in preferred_keys:
    for name, value in cookie_pairs:
        if name == key and name not in seen:
            selected.append(f"{name}={value}")
            seen.add(name)

cookie_string = "; ".join(selected)
env_path = Path(".env")
env_text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
pattern = re.compile(r"^BILIBILI_COOKIE=.*$", re.MULTILINE)
replacement = f"BILIBILI_COOKIE={cookie_string}"
if pattern.search(env_text):
    env_text = pattern.sub(replacement, env_text)
else:
    env_text = env_text.rstrip() + ("\n" if env_text else "") + replacement + "\n"
env_path.write_text(env_text, encoding="utf-8")

print(f"cookies file: {p.resolve()}")
print(f"bilibili cookie count: {len(bili)}")
print(f"login cookies present: {'yes' if present else 'no'}")
if present:
    print("login cookie names present:", ", ".join(present))
else:
    print("No Bilibili login cookies were found.")
print(f".env updated: {env_path.resolve()}")
PY

echo "Done."
