# BiliNote Desktop Packaging

## Overview

这套流程分成两条：

- 本地 mac 打包：使用桌面脚本在当前机器上构建 `.dmg`，并自动复制到 `~/Downloads`
- 远端 CI 打包：提交并推送后，GitHub Actions 自动构建各平台桌面产物；需要时可用桌面脚本把最新的 Windows/mac 产物下载回 `~/Downloads`

## Desktop Script

桌面脚本位置：

- `/Users/linlu/Desktop/打包BiliNote.command`

默认双击行为：

- 执行本地 mac 打包
- 成功后把最新 `.dmg` 复制到 `~/Downloads`

也可以在终端里手动调用：

```bash
/Users/linlu/Desktop/打包BiliNote.command build-mac
/Users/linlu/Desktop/打包BiliNote.command download-ci --platform windows-latest
```

## Local mac Prerequisites

- `backend/.venv/bin/pyinstaller`
- `pnpm`
- Rust 工具链：`cargo`、`rustc`
- `ffmpeg`

脚本会优先把下面这些路径注入 PATH：

- `backend/.venv/bin`
- `~/.cargo/bin`
- `/opt/homebrew/bin`
- `/usr/local/bin`

## GitHub Actions

工作流文件：

- `.github/workflows/main.yml`

触发方式：

- push 到任意分支后自动构建
- push tag `v*` 时自动构建并创建 Release
- 手动 `workflow_dispatch`

默认会上传这些 artifact：

- `artifacts-macos-latest`
- `artifacts-windows-latest`
- `artifacts-ubuntu-22.04`

如果要把远端 Windows 产物下载到本机下载目录，需要先登录 GitHub CLI：

```bash
gh auth login
```
