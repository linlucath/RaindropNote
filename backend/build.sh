#!/usr/bin/env bash
set -e
# uncomment this for debugging
# set -x

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
TAURI_BIN_DIR="$REPO_ROOT/BillNote_frontend/src-tauri/bin"
BACKEND_BUNDLE_DIR="$TAURI_BIN_DIR/RaindropNoteBackend"
TEMP_ENV_CREATED=0

cd "$REPO_ROOT"
echo "当前工作目录：$(pwd)"

cleanup() {
  if [ "$TEMP_ENV_CREATED" -eq 1 ]; then
    echo "清理临时的 .env 文件..."
    rm -f "$BACKEND_DIR/.env"
  fi
}
trap cleanup EXIT

# 清理旧的构建
echo "清理旧的构建..."
rm -rf "$BACKEND_DIR/dist" "$BACKEND_DIR/build" "$TAURI_BIN_DIR"/*
echo "清理完成。"

TARGET_TRIPLE=$(rustc -Vv | grep host | cut -f2 -d' ')
echo "Detected target triple: $TARGET_TRIPLE"

# --- 核心修改部分开始 ---

# 步骤 1: 为了避免 PyInstaller 的解析歧义，我们先手动复制文件
echo "为打包准备 .env 文件..."
if [ ! -f "$BACKEND_DIR/.env" ]; then
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
  TEMP_ENV_CREATED=1
fi

# 步骤 2: PyInstaller 打包，直接添加已存在的 .env 文件
echo "开始 PyInstaller 打包..."
cd "$BACKEND_DIR"
pyinstaller \
  -y \
  --name RaindropNoteBackend \
  --paths "$BACKEND_DIR" \
  --distpath "$TAURI_BIN_DIR" \
  --workpath "$BACKEND_DIR/build" \
  --specpath "$BACKEND_DIR" \
  --hidden-import uvicorn \
  --hidden-import fastapi \
  --hidden-import starlette \
  --add-data "app/db/builtin_providers.json:." \
  --add-data ".env:." \
  "$BACKEND_DIR/main.py"

# --- 核心修改部分结束 ---


# 重命名主执行文件以包含目标平台信息
mv \
  "$BACKEND_BUNDLE_DIR/RaindropNoteBackend" \
  "$BACKEND_BUNDLE_DIR/RaindropNoteBackend-$TARGET_TRIPLE"

echo "PyInstaller 打包完成。"
echo "打包后的目录内容："
ls -l "$BACKEND_BUNDLE_DIR"

echo "请检查 src-tauri/bin/RaindropNoteBackend 目录，确认其中包含了名为 .env 的【文件】。"
