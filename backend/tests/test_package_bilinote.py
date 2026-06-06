from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parents[2]
PACKAGE_SCRIPT = REPO_ROOT / "tools" / "package_bilinote.py"


def load_package_module():
    spec = importlib.util.spec_from_file_location("package_bilinote", PACKAGE_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_checksum(target_dir: Path, platform: str, artifact_name: str, digest: str) -> None:
    (target_dir / f"SHA256SUMS-{platform}.txt").write_text(
        f"{digest}  {artifact_name}\n",
        encoding="utf-8",
    )


def test_verify_downloaded_artifacts_accepts_matching_platform_checksums(tmp_path: Path):
    package = load_package_module()
    artifact = tmp_path / "RaindropNote.dmg"
    artifact.write_bytes(b"desktop artifact")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    write_checksum(tmp_path, "macos-latest", artifact.name, digest)

    package.verify_downloaded_artifacts(tmp_path, "macos-latest")


def test_verify_downloaded_artifacts_rejects_missing_checksum(tmp_path: Path):
    package = load_package_module()

    with pytest.raises(package.PackagingError, match="缺少校验和文件"):
        package.verify_downloaded_artifacts(tmp_path, "windows-latest")


def test_verify_downloaded_artifacts_rejects_checksum_mismatch(tmp_path: Path):
    package = load_package_module()
    artifact = tmp_path / "RaindropNote.msi"
    artifact.write_bytes(b"desktop artifact")
    write_checksum(tmp_path, "windows-latest", artifact.name, "0" * 64)

    with pytest.raises(package.PackagingError, match="校验失败"):
        package.verify_downloaded_artifacts(tmp_path, "windows-latest")


def test_verify_downloaded_artifacts_rejects_checksum_paths_outside_target_dir(
    tmp_path: Path,
):
    package = load_package_module()
    outside_artifact = tmp_path.parent / "RaindropNote.dmg"
    outside_artifact.write_bytes(b"outside artifact")
    digest = hashlib.sha256(outside_artifact.read_bytes()).hexdigest()
    write_checksum(tmp_path, "macos-latest", f"../{outside_artifact.name}", digest)

    with pytest.raises(package.PackagingError, match="校验文件路径无效"):
        package.verify_downloaded_artifacts(tmp_path, "macos-latest")


def test_verify_downloaded_artifacts_rejects_absolute_checksum_paths(tmp_path: Path):
    package = load_package_module()
    outside_artifact = tmp_path.parent / "RaindropNote.msi"
    outside_artifact.write_bytes(b"outside artifact")
    digest = hashlib.sha256(outside_artifact.read_bytes()).hexdigest()
    write_checksum(tmp_path, "windows-latest", str(outside_artifact), digest)

    with pytest.raises(package.PackagingError, match="校验文件路径无效"):
        package.verify_downloaded_artifacts(tmp_path, "windows-latest")


def test_build_mac_uses_the_shared_desktop_build_script():
    source = PACKAGE_SCRIPT.read_text(encoding="utf-8")

    assert 'run(["pnpm", "desktop:build"], cwd=FRONTEND_DIR, env=env)' in source
    assert 'run(["pnpm", "tauri", "build"], cwd=FRONTEND_DIR, env=env)' not in source
