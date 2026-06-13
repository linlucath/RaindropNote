from __future__ import annotations

import os
import json
import shutil
import stat
import struct
import subprocess
from pathlib import Path


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _read_png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as png_file:
        signature = png_file.read(8)
        if signature != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"{path} is not a PNG file")
        _chunk_size = png_file.read(4)
        chunk_type = png_file.read(4)
        if chunk_type != b"IHDR":
            raise ValueError(f"{path} is missing a PNG IHDR chunk")
        width, height = struct.unpack(">II", png_file.read(8))
    return width, height


def test_build_sh_runs_from_backend_directory_with_backend_relative_assets(tmp_path: Path):
    repo_root = tmp_path / "repo"
    backend_dir = repo_root / "backend"
    tauri_bin_dir = repo_root / "BillNote_frontend" / "src-tauri" / "bin"
    fake_bin_dir = tmp_path / "fake-bin"

    backend_dir.mkdir(parents=True)
    tauri_bin_dir.mkdir(parents=True)
    fake_bin_dir.mkdir(parents=True)
    (backend_dir / "app" / "db").mkdir(parents=True)
    (backend_dir / "app" / "db" / "builtin_providers.json").write_text("{}", encoding="utf-8")
    (backend_dir / ".env.example").write_text("BACKEND_PORT=8483\n", encoding="utf-8")
    (backend_dir / "main.py").write_text("print('backend')\n", encoding="utf-8")

    shutil.copyfile(Path(__file__).parents[1] / "build.sh", backend_dir / "build.sh")
    (backend_dir / "build.sh").chmod(0o755)

    _write_executable(
        fake_bin_dir / "rustc",
        "#!/usr/bin/env bash\n"
        "cat <<'EOF'\n"
        "rustc 1.0.0\n"
        "host: x86_64-test-platform\n"
        "EOF\n",
    )
    _write_executable(
        fake_bin_dir / "pyinstaller",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "distpath=''\n"
        "name=''\n"
        "windowed=0\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  case \"$1\" in\n"
        "    --distpath) distpath=\"$2\"; shift 2 ;;\n"
        "    --name) name=\"$2\"; shift 2 ;;\n"
        "    --windowed) windowed=1; shift ;;\n"
        "    --add-data)\n"
        "      source_path=\"${2%%:*}\"\n"
        "      test -f \"$source_path\"\n"
        "      shift 2 ;;\n"
        "    *) shift ;;\n"
        "  esac\n"
        "done\n"
        "if [ \"$windowed\" -eq 1 ]; then\n"
        "  app_dir=\"$distpath/$name.app/Contents\"\n"
        "  mkdir -p \"$app_dir/MacOS\" \"$app_dir/Resources\" \"$app_dir/_CodeSignature\"\n"
        "  touch \"$app_dir/MacOS/$name\" \"$app_dir/_CodeSignature/CodeResources\"\n"
        "else\n"
        "  mkdir -p \"$distpath/$name/_internal\"\n"
        "  touch \"$distpath/$name/$name\"\n"
        "fi\n",
    )
    _write_executable(
        fake_bin_dir / "codesign",
        "#!/usr/bin/env bash\n"
        "exit 0\n",
    )

    env = {
        **os.environ,
        "PATH": f"{fake_bin_dir}{os.pathsep}{os.environ['PATH']}",
    }

    result = subprocess.run(
        ["bash", "build.sh"],
        cwd=backend_dir,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert (
        tauri_bin_dir / "RaindropNoteBackend" / "RaindropNoteBackend-x86_64-test-platform"
    ).exists()
    assert (
        tauri_bin_dir / "RaindropNoteBackend.app" / "Contents" / "MacOS" / "RaindropNoteBackend"
    ).exists()
    assert not (backend_dir / ".env").exists()


def test_build_bat_uses_backend_relative_assets_from_repo_root():
    build_bat = (Path(__file__).parents[1] / "build.bat").read_text(encoding="utf-8")

    assert 'set "BACKEND_DIR=%REPO_ROOT%\\backend"' in build_bat
    assert 'pushd "%BACKEND_DIR%"' in build_bat
    assert '--add-data "app\\db\\builtin_providers.json;."' in build_bat
    assert '--add-data ".env;."' in build_bat
    assert "main.py" in build_bat


def test_tauri_sidecar_contract_matches_backend_build_scripts():
    repo_root = Path(__file__).parents[2]
    tauri_dir = repo_root / "BillNote_frontend" / "src-tauri"
    tauri_config = json.loads((tauri_dir / "tauri.conf.json").read_text(encoding="utf-8"))
    capabilities = json.loads(
        (tauri_dir / "capabilities" / "default.json").read_text(encoding="utf-8")
    )
    build_sh = (repo_root / "backend" / "build.sh").read_text(encoding="utf-8")
    build_bat = (repo_root / "backend" / "build.bat").read_text(encoding="utf-8")

    external_bins = tauri_config["bundle"]["externalBin"]
    shell_permissions = [
        permission
        for permission in capabilities["permissions"]
        if isinstance(permission, dict) and permission["identifier"] == "shell:allow-execute"
    ]

    assert external_bins == ["bin/RaindropNoteBackend/RaindropNoteBackend"]
    assert tauri_config["bundle"]["macOS"]["files"] == {
        "Resources/RaindropNoteBackend.app": "bin/RaindropNoteBackend.app"
    }
    assert shell_permissions[0]["allow"] == [
        {"name": "RaindropNoteBackend", "sidecar": True}
    ]
    assert "RaindropNoteBackend-$TARGET_TRIPLE" in build_sh
    assert "--windowed" in build_sh
    assert "RaindropNoteBackend.app" in build_sh
    assert 'codesign --verify --deep --strict --verbose=2 "$TAURI_BIN_DIR/RaindropNoteBackend.app"' in build_sh
    assert "RaindropNoteBackend-%TARGET_TRIPLE%.exe" in build_bat


def test_tauri_bundle_png_icons_are_square_for_linux_appimage():
    repo_root = Path(__file__).parents[2]
    tauri_dir = repo_root / "BillNote_frontend" / "src-tauri"
    tauri_config = json.loads((tauri_dir / "tauri.conf.json").read_text(encoding="utf-8"))

    png_icons = [Path(icon_path) for icon_path in tauri_config["bundle"]["icon"] if icon_path.endswith(".png")]

    assert png_icons, "Tauri bundle config should include at least one PNG icon"

    for relative_icon_path in png_icons:
        width, height = _read_png_dimensions(tauri_dir / relative_icon_path)
        assert width == height, (
            f"{relative_icon_path} is {width}x{height}; AppImage bundling requires a square PNG icon"
        )


def test_desktop_workflow_uses_host_targets_without_unused_matrix_target():
    repo_root = Path(__file__).parents[2]
    workflow = (repo_root / ".github" / "workflows" / "main.yml").read_text(encoding="utf-8")
    package_json = json.loads(
        (repo_root / "BillNote_frontend" / "package.json").read_text(encoding="utf-8")
    )

    assert "platform: macos-latest" in workflow
    assert "platform: ubuntu-22.04" in workflow
    assert "platform: windows-latest" in workflow
    assert "target:" not in workflow
    assert "pnpm tauri build --target" not in workflow
    assert package_json["scripts"]["desktop:build"] == "tauri build"
    assert package_json["scripts"]["desktop:build:ci"] == "tauri build --ci"
    assert package_json["scripts"]["desktop:build:ci:linux"] == "tauri build --ci --bundles deb,rpm"
    assert package_json["scripts"]["desktop:build:ci:windows"] == "tauri build --ci --bundles nsis"
    assert "pnpm install --frozen-lockfile" in workflow
    assert "Build Tauri App on Linux" in workflow
    assert "run: pnpm desktop:build:ci:linux" in workflow
    assert "Build Tauri App on Windows" in workflow
    assert "run: pnpm desktop:build:ci:windows" in workflow
    assert "Build Tauri App on macOS" in workflow
    assert "run: pnpm desktop:build:ci" in workflow


def test_desktop_workflow_uses_the_project_pnpm_version():
    repo_root = Path(__file__).parents[2]
    workflow = (repo_root / ".github" / "workflows" / "main.yml").read_text(encoding="utf-8")
    package_json = json.loads(
        (repo_root / "BillNote_frontend" / "package.json").read_text(encoding="utf-8")
    )

    assert package_json["packageManager"] == "pnpm@10.33.0"
    assert "version: 'latest'" not in workflow
    assert "version: '10.33.0'" in workflow


def test_desktop_workflow_fails_when_release_artifacts_are_missing():
    repo_root = Path(__file__).parents[2]
    workflow = (repo_root / ".github" / "workflows" / "main.yml").read_text(encoding="utf-8")

    assert 'ARTIFACT_PATTERNS=("*.dmg")' in workflow
    assert 'ARTIFACT_PATTERNS=("*.deb" "*.rpm")' in workflow
    assert 'ARTIFACT_PATTERNS=("nsis/*.exe")' in workflow
    assert '[[ "$FOUND_ARTIFACTS" -gt 0 ]]' in workflow
    assert 'No release artifacts found for $RUNNER_OS' in workflow
    assert "-exec cp {} release-artifacts/ \\; 2>/dev/null || true" not in workflow


def test_desktop_workflow_names_checksum_files_per_platform():
    repo_root = Path(__file__).parents[2]
    workflow = (repo_root / ".github" / "workflows" / "main.yml").read_text(encoding="utf-8")

    assert 'CHECKSUM_FILE="SHA256SUMS-${{ matrix.platform }}.txt"' in workflow
    assert 'cat "$CHECKSUM_FILE"' in workflow
    assert "> SHA256SUMS.txt" not in workflow
    assert "cat SHA256SUMS.txt" not in workflow


def test_desktop_workflow_selects_available_checksum_tool_per_runner():
    repo_root = Path(__file__).parents[2]
    workflow = (repo_root / ".github" / "workflows" / "main.yml").read_text(encoding="utf-8")

    assert "if command -v sha256sum >/dev/null 2>&1; then" in workflow
    assert "CHECKSUM_COMMAND=(sha256sum)" in workflow
    assert "CHECKSUM_COMMAND=(shasum -a 256)" in workflow
    assert '"${CHECKSUM_COMMAND[@]}" * > "$CHECKSUM_FILE"' in workflow
    assert 'sha256sum * > "$CHECKSUM_FILE" 2>/dev/null || shasum -a 256 * > "$CHECKSUM_FILE"' not in workflow


def test_release_job_verifies_all_platform_artifacts_before_publishing():
    repo_root = Path(__file__).parents[2]
    workflow = (repo_root / ".github" / "workflows" / "main.yml").read_text(encoding="utf-8")

    assert "Verify downloaded release artifacts" in workflow
    for platform in ["macos-latest", "ubuntu-22.04", "windows-latest"]:
        assert f"SHA256SUMS-{platform}.txt" in workflow
    assert "Missing checksum file:" in workflow
    assert "cd all-artifacts" in workflow
    assert 'sha256sum -c "$checksum"' in workflow


def test_local_packaging_helper_and_runbook_use_raindrop_names():
    repo_root = Path(__file__).parents[2]
    helper = (repo_root / "tools" / "package_bilinote.py").read_text(encoding="utf-8")
    runbook = (repo_root / "docs" / "runbooks" / "desktop-packaging.md").read_text(
        encoding="utf-8"
    )

    assert "[雨滴笔记助手]" in helper
    assert "RaindropNote-ci-" in helper
    assert "雨滴笔记助手 桌面端打包辅助脚本" in helper
    assert "[BiliNote]" not in helper
    assert "BiliNote-ci-" not in helper
    assert "BiliNote 桌面端打包辅助脚本" not in helper

    assert "# 雨滴笔记助手 Desktop Packaging" in runbook
    assert "打包雨滴笔记助手.command" in runbook
    assert "BiliNote" not in runbook


def test_docker_publish_workflow_uses_raindrop_names():
    repo_root = Path(__file__).parents[2]
    workflow = (repo_root / ".github" / "workflows" / "docker-build.yml").read_text(
        encoding="utf-8"
    )

    assert "raindrop-note-data:/app/backend/data" in workflow
    assert "--name raindrop-note" in workflow
    assert "bilinote" not in workflow.lower()


def test_complete_dockerfile_uses_frozen_frontend_lockfile():
    repo_root = Path(__file__).parents[2]
    dockerfile = (repo_root / "Dockerfile.complete").read_text(encoding="utf-8")

    assert "COPY ./BillNote_frontend/package.json ./BillNote_frontend/pnpm-lock.yaml ./" in dockerfile
    assert "RUN pnpm install --frozen-lockfile" in dockerfile


def test_dockerfiles_use_the_project_pnpm_version():
    repo_root = Path(__file__).parents[2]
    package_json = json.loads(
        (repo_root / "BillNote_frontend" / "package.json").read_text(encoding="utf-8")
    )

    package_manager = package_json["packageManager"]

    assert package_manager == "pnpm@10.33.0"
    for dockerfile_path in [
        repo_root / "Dockerfile.complete",
        repo_root / "BillNote_frontend" / "Dockerfile",
    ]:
        dockerfile = dockerfile_path.read_text(encoding="utf-8")
        assert f"corepack prepare {package_manager} --activate" in dockerfile
        assert "corepack prepare pnpm@latest --activate" not in dockerfile


def test_dockerfiles_use_node_20_for_tailwind_native_bindings():
    repo_root = Path(__file__).parents[2]

    for dockerfile_path in [
        repo_root / "Dockerfile.complete",
        repo_root / "BillNote_frontend" / "Dockerfile",
    ]:
        dockerfile = dockerfile_path.read_text(encoding="utf-8")
        assert "FROM node:20-alpine" in dockerfile
        assert "FROM node:18-alpine" not in dockerfile
