#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = REPO_ROOT / "BillNote_frontend"
BACKEND_DIR = REPO_ROOT / "backend"
DOWNLOADS_DIR = Path.home() / "Downloads"
WORKFLOW_NAME = "main.yml"


class PackagingError(RuntimeError):
    pass


def info(message: str) -> None:
    print(f"[BiliNote] {message}")


def run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    printable = " ".join(cmd)
    info(f"运行命令: {printable}")
    subprocess.run(cmd, cwd=cwd or REPO_ROOT, env=env, check=True)


def run_capture(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> str:
    completed = subprocess.run(
        cmd,
        cwd=cwd or REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )
    return completed.stdout.strip()


def prepend_path(parts: list[Path]) -> dict[str, str]:
    env = os.environ.copy()
    current = env.get("PATH", "")
    prefixes = [str(path) for path in parts if path.exists()]
    env["PATH"] = os.pathsep.join(prefixes + [current]) if current else os.pathsep.join(prefixes)
    return env


def resolve_python() -> Path:
    preferred = BACKEND_DIR / ".venv" / "bin" / "python"
    if preferred.exists():
        return preferred

    python_bin = shutil.which("python3")
    if python_bin:
        return Path(python_bin)

    raise PackagingError("未找到可用的 Python 解释器，请先安装 Python 3。")


def resolve_build_env() -> dict[str, str]:
    cargo_bin = Path.home() / ".cargo" / "bin"
    venv_bin = BACKEND_DIR / ".venv" / "bin"
    return prepend_path([venv_bin, cargo_bin, Path("/opt/homebrew/bin"), Path("/usr/local/bin")])


def require_command(name: str, env: dict[str, str]) -> None:
    if shutil.which(name, path=env.get("PATH")):
        return
    raise PackagingError(f"缺少命令 `{name}`，请先安装后再重试。")


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def sanitize_name(value: str) -> str:
    return value.replace("/", "-").replace("\\", "-").replace(" ", "_")


def copy_artifact(source: Path, target_dir: Path) -> Path:
    ensure_directory(target_dir)
    destination = target_dir / source.name
    if destination.exists():
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        destination = target_dir / f"{source.stem}-{timestamp}{source.suffix}"
    shutil.copy2(source, destination)
    return destination


def latest_matching_artifact(pattern: str) -> Path:
    matches = sorted(FRONTEND_DIR.glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)
    if not matches:
        raise PackagingError(f"没有找到匹配 `{pattern}` 的打包产物。")
    return matches[0]


def build_mac(args: argparse.Namespace) -> int:
    if platform.system() != "Darwin":
        raise PackagingError("mac 打包只能在 macOS 上执行。")

    env = resolve_build_env()
    require_command("pnpm", env)
    require_command("rustc", env)
    require_command("cargo", env)
    require_command("hdiutil", env)

    pyinstaller_path = BACKEND_DIR / ".venv" / "bin" / "pyinstaller"
    if not pyinstaller_path.exists():
        raise PackagingError("未找到 backend/.venv/bin/pyinstaller，请先在 backend 虚拟环境中安装依赖。")

    if not args.skip_install:
        run(["pnpm", "install", "--frozen-lockfile"], cwd=FRONTEND_DIR, env=env)

    run(["bash", "./backend/build.sh"], cwd=REPO_ROOT, env=env)
    run(["pnpm", "tauri", "build"], cwd=FRONTEND_DIR, env=env)

    artifact = latest_matching_artifact("src-tauri/target/release/bundle/**/*.dmg")
    copied = copy_artifact(artifact, DOWNLOADS_DIR)
    info(f"mac 安装包已复制到: {copied}")
    return 0


def assert_gh_ready(env: dict[str, str]) -> None:
    require_command("gh", env)
    auth = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, env=env)
    if auth.returncode != 0:
        raise PackagingError("GitHub CLI 尚未登录，请先运行 `gh auth login`。")


def select_latest_run(branch: str, env: dict[str, str]) -> dict[str, object]:
    output = run_capture(
        [
            "gh",
            "run",
            "list",
            "--workflow",
            WORKFLOW_NAME,
            "--branch",
            branch,
            "--limit",
            "20",
            "--json",
            "databaseId,status,conclusion,displayTitle,headBranch,createdAt",
        ],
        cwd=REPO_ROOT,
        env=env,
    )
    runs = json.loads(output)
    if not runs:
        raise PackagingError(f"分支 `{branch}` 上还没有 `{WORKFLOW_NAME}` 的运行记录。")
    return runs[0]


def download_ci(args: argparse.Namespace) -> int:
    env = resolve_build_env()
    assert_gh_ready(env)

    branch = args.branch or run_capture(["git", "branch", "--show-current"], cwd=REPO_ROOT, env=env)
    run_meta = select_latest_run(branch, env)
    run_id = str(run_meta["databaseId"])
    status = str(run_meta["status"])
    conclusion = str(run_meta["conclusion"])

    if status != "completed" and args.wait:
        run(["gh", "run", "watch", run_id], cwd=REPO_ROOT, env=env)
        run_meta = select_latest_run(branch, env)
        status = str(run_meta["status"])
        conclusion = str(run_meta["conclusion"])

    if status != "completed":
        raise PackagingError(f"工作流仍在 `{status}`，可稍后重试，或加上 `--wait`。")
    if conclusion != "success":
        raise PackagingError(f"工作流已完成，但结果为 `{conclusion}`，请先检查 GitHub Actions 日志。")

    artifact_name = f"artifacts-{args.platform}"
    target_dir = DOWNLOADS_DIR / f"BiliNote-ci-{sanitize_name(branch)}-{run_id}"
    if target_dir.exists():
        shutil.rmtree(target_dir)
    ensure_directory(target_dir)

    run(
        ["gh", "run", "download", run_id, "--name", artifact_name, "--dir", str(target_dir)],
        cwd=REPO_ROOT,
        env=env,
    )
    info(f"CI 产物已下载到: {target_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BiliNote 桌面端打包辅助脚本")
    subparsers = parser.add_subparsers(dest="command", required=True)

    mac_parser = subparsers.add_parser("build-mac", help="在当前 mac 上构建 dmg 并复制到下载目录")
    mac_parser.add_argument("--skip-install", action="store_true", help="跳过 pnpm install")
    mac_parser.set_defaults(handler=build_mac)

    ci_parser = subparsers.add_parser(
        "download-ci",
        help="下载最近一次 GitHub Actions 桌面构建产物到下载目录",
    )
    ci_parser.add_argument(
        "--platform",
        default="windows-latest",
        choices=["windows-latest", "macos-latest", "ubuntu-22.04"],
        help="要下载的产物平台",
    )
    ci_parser.add_argument("--branch", help="指定分支名，默认取当前 git 分支")
    ci_parser.add_argument(
        "--wait",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="如果工作流仍在运行，是否等待其结束",
    )
    ci_parser.set_defaults(handler=download_ci)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.handler(args)
    except PackagingError as exc:
        info(f"打包失败: {exc}")
        return 1
    except subprocess.CalledProcessError as exc:
        info(f"命令执行失败，退出码 {exc.returncode}")
        return exc.returncode or 1


if __name__ == "__main__":
    sys.exit(main())
