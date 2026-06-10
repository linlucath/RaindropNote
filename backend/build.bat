@echo off
setlocal enabledelayedexpansion
set "TEMP_ENV_CREATED=0"
set "REPO_ROOT=%~dp0.."
set "BACKEND_DIR=%REPO_ROOT%\backend"
set "TAURI_BIN_DIR=%REPO_ROOT%\BillNote_frontend\src-tauri\bin"

REM 切换到脚本所在目录的上级，也就是项目根目录
cd /d "%REPO_ROOT%"
echo 当前工作目录：%cd%

REM 清理旧的构建
echo 清理旧的构建...
if exist backend\dist rmdir /s /q backend\dist
if exist backend\build rmdir /s /q backend\build
if exist "%TAURI_BIN_DIR%" rmdir /s /q "%TAURI_BIN_DIR%"
echo 清理完成。

REM 重新创建 Tauri 需要的目录结构
mkdir "%TAURI_BIN_DIR%"

REM 获取 Rust 的 target triple（适配 Tauri 对应平台）
for /f "tokens=2 delims=:" %%A in ('rustc -Vv ^| findstr "host"') do (
    set "TARGET_TRIPLE=%%A"
)
set "TARGET_TRIPLE=%TARGET_TRIPLE: =%"
echo Detected target triple: %TARGET_TRIPLE%


REM --- 核心修改部分开始 ---

REM 步骤 1: 为了避免 PyInstaller 的解析歧义，我们先手动复制文件
echo 为打包准备 .env 文件...
if not exist "%BACKEND_DIR%\.env" (
  copy "%BACKEND_DIR%\.env.example" "%BACKEND_DIR%\.env"
  set "TEMP_ENV_CREATED=1"
)

REM 步骤 2: 执行 PyInstaller 打包，直接添加已存在的 .env 文件
echo 开始 PyInstaller 打包...
pushd "%BACKEND_DIR%"
pyinstaller ^
  -y ^
  --name RaindropNoteBackend ^
  --paths "%BACKEND_DIR%" ^
  --distpath "%TAURI_BIN_DIR%" ^
  --workpath "%BACKEND_DIR%\build" ^
  --specpath "%BACKEND_DIR%" ^
  --hidden-import uvicorn ^
  --hidden-import fastapi ^
  --hidden-import starlette ^
  --add-data "app\db\builtin_providers.json;." ^
  --add-data ".env;." ^
  main.py
set "PYINSTALLER_EXIT=%ERRORLEVEL%"
popd
if not "%PYINSTALLER_EXIT%"=="0" exit /b %PYINSTALLER_EXIT%

REM 步骤 3: 清理在项目根目录创建的临时 .env 文件
if "%TEMP_ENV_CREATED%"=="1" (
  echo 清理临时的 .env 文件...
  if exist "%BACKEND_DIR%\.env" del "%BACKEND_DIR%\.env"
)

REM --- 核心修改部分结束 ---


REM 重命名生成的可执行文件为符合 Tauri 要求的名称
move /Y "%TAURI_BIN_DIR%\RaindropNoteBackend\RaindropNoteBackend.exe" "%TAURI_BIN_DIR%\RaindropNoteBackend\RaindropNoteBackend-%TARGET_TRIPLE%.exe"

echo PyInstaller 打包完成：
dir "%TAURI_BIN_DIR%\RaindropNoteBackend"

echo 请检查 BillNote_frontend\src-tauri\bin\RaindropNoteBackend 目录，确认其中包含了名为 .env 的【文件】。

endlocal
