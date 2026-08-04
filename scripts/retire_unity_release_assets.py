#!/usr/bin/env python3
"""Archive and retire old Unity release assets without rebuilding their bytes.

The script wraps the original asset in a new AES-encrypted 7z archive together
with its SHA-256 and optional old archive password. It verifies the archive
locally and again after upload before deleting the old public asset.

Dry-run is the default. Use --apply only after reviewing the printed plan.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any

DEFAULT_REPO = "Atm4x/NeuroMita"
# Пароль защищает архив от случайного скачивания и запуска, а не от целенаправленного вскрытия.
DEFAULT_ARCHIVE_PASSWORD = "VinerX"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], *, capture: bool = False) -> str:
    completed = subprocess.run(
        command,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE if capture else None,
    )
    return completed.stdout if capture else ""


def require_binary(name: str, candidates: list[str]) -> str:
    for candidate in candidates:
        if shutil.which(candidate):
            return candidate
    raise RuntimeError(f"{name} was not found. Tried: {', '.join(candidates)}")


def read_release(repo: str, tag: str) -> dict[str, Any]:
    raw = run(["gh", "api", f"repos/{repo}/releases/tags/{tag}"], capture=True)
    release = json.loads(raw)
    if not isinstance(release, dict):
        raise RuntimeError(f"GitHub returned an invalid release for {tag}")
    if release.get("immutable") or release.get("isImmutable"):
        raise RuntimeError(f"Release {tag} is immutable; its assets cannot be replaced")
    return release


def unity_asset_name(release: dict[str, Any], requested: str | None) -> str | None:
    """Имя устанавливаемого Unity-ассета либо None, если релиз уже заархивирован."""
    names = [str(asset.get("name") or "") for asset in release.get("assets") or []]
    if requested:
        if requested not in names:
            raise RuntimeError(f"Asset {requested!r} is not present in release {release.get('tag_name')}")
        return requested
    candidates = [
        name
        for name in names
        if "unitybuild" in name.casefold()
        and name.casefold().endswith((".zip", ".7z"))
        and "-retired" not in name.casefold()
    ]
    if not candidates:
        if any("-retired" in name.casefold() for name in names):
            return None
        raise RuntimeError("Release has no installable Unity asset")
    if len(candidates) > 1:
        raise RuntimeError(
            "Expected exactly one installable Unity asset; use --asset-name to choose one. "
            f"Found: {candidates}"
        )
    return candidates[0]


def retired_name(asset_name: str) -> str:
    source = Path(asset_name)
    return f"{source.stem}-retired.7z"


def make_archive(
    seven_zip: str,
    *,
    source_asset: Path,
    destination: Path,
    archive_password: str,
    metadata: dict[str, Any],
    old_password: str | None,
) -> None:
    package = destination.parent / "archive-content"
    package.mkdir()
    wrapped_asset = package / source_asset.name
    shutil.copy2(source_asset, wrapped_asset)
    (package / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if old_password:
        (package / "access.json").write_text(
            json.dumps({"original_archive_password": old_password}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    run([
        seven_zip,
        "a",
        "-t7z",
        "-mx=0",
        "-mhe=on",
        f"-p{archive_password}",
        str(destination),
        str(package / "*"),
    ])
    run([seven_zip, "t", f"-p{archive_password}", str(destination)])


def verify_archive(
    seven_zip: str,
    archive: Path,
    password: str,
    asset_name: str,
    expected_sha256: str,
    work_dir: str | None = None,
) -> None:
    with tempfile.TemporaryDirectory(prefix="neuromita-retired-verify-", dir=work_dir) as raw_dir:
        output = Path(raw_dir)
        run([seven_zip, "x", "-y", f"-p{password}", f"-o{output}", str(archive)])
        wrapped_asset = output / asset_name
        if not wrapped_asset.is_file():
            raise RuntimeError(f"Verification failed: {asset_name} is missing from {archive.name}")
        actual = sha256(wrapped_asset)
        if actual != expected_sha256:
            raise RuntimeError(
                f"Verification failed: original asset hash changed ({actual} != {expected_sha256})"
            )


def append_retired_note(existing: str, *, tag: str, asset_name: str, digest: str) -> str:
    marker = f"Archived Unity asset: {asset_name}"
    if marker in existing:
        return existing
    note = (
        "\n\n---\n"
        "Status: retired test build; not installable by the launcher.\n"
        f"{marker}\n"
        f"Original SHA-256: {digest}\n"
        f"Release tag: {tag}\n"
    )
    return existing.rstrip() + note


def archive_release(
    *,
    args: argparse.Namespace,
    seven_zip: str,
    archive_password: str,
    old_password: str | None,
    tag: str,
) -> None:
    release = read_release(args.repo, tag)
    asset_name = unity_asset_name(release, args.asset_name)
    if asset_name is None:
        print(f"{tag}: already retired, skipping")
        return
    new_name = retired_name(asset_name)
    print(f"{tag}: {asset_name} -> {new_name}")
    if not args.apply:
        print("  dry-run: no files or GitHub release assets will be changed")
        return

    with tempfile.TemporaryDirectory(prefix="neuromita-retire-", dir=args.work_dir) as raw_dir:
        work = Path(raw_dir)
        download_dir = work / "download"
        download_dir.mkdir()
        run([
            "gh", "release", "download", tag, "--repo", args.repo,
            "--pattern", asset_name, "--dir", str(download_dir),
        ])
        original = download_dir / asset_name
        if not original.is_file():
            raise RuntimeError(f"GitHub download did not create {asset_name}")
        original_hash = sha256(original)
        metadata = {
            "schema": 1,
            "status": "retired",
            "source_repository": args.repo,
            "release_tag": tag,
            "original_asset_name": asset_name,
            "original_asset_sha256": original_hash,
            "original_asset_size": original.stat().st_size,
            "old_password_included": bool(old_password),
        }
        retired = work / new_name
        make_archive(
            seven_zip,
            source_asset=original,
            destination=retired,
            archive_password=archive_password,
            metadata=metadata,
            old_password=old_password,
        )
        verify_archive(seven_zip, retired, archive_password, asset_name, original_hash, work_dir=args.work_dir)

        run([
            "gh", "release", "upload", tag, str(retired), "--repo", args.repo, "--clobber",
        ])
        remote_dir = work / "remote-verify"
        remote_dir.mkdir()
        run([
            "gh", "release", "download", tag, "--repo", args.repo,
            "--pattern", new_name, "--dir", str(remote_dir),
        ])
        remote_archive = remote_dir / new_name
        verify_archive(seven_zip, remote_archive, archive_password, asset_name, original_hash, work_dir=args.work_dir)

        # Deletion is deliberately last: until this point GitHub still has the
        # original asset and the newly uploaded archive has been independently verified.
        run(["gh", "release", "delete-asset", tag, asset_name, "--repo", args.repo, "--yes"])
        notes = append_retired_note(
            str(release.get("body") or ""),
            tag=tag,
            asset_name=asset_name,
            digest=original_hash,
        )
        notes_path = work / "release-notes.md"
        notes_path.write_text(notes, encoding="utf-8")
        run(["gh", "release", "edit", tag, "--repo", args.repo, "--notes-file", str(notes_path)])
        print(f"  archived and retired: {new_name}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"GitHub repository (default: {DEFAULT_REPO})")
    parser.add_argument("--tag", action="append", required=True, help="Release tag to archive; repeat for multiple releases")
    parser.add_argument("--asset-name", help="Exact Unity asset name; required only when a release has several Unity assets")
    parser.add_argument("--archive-password", help="New archive password; overrides --archive-password-env")
    parser.add_argument("--archive-password-env", default="NEUROMITA_RETIRED_ARCHIVE_PASSWORD", help="Environment variable containing the new archive password")
    parser.add_argument("--old-password", help="Old asset password to keep inside the encrypted wrapper; overrides --old-password-env")
    parser.add_argument("--old-password-env", help="Optional environment variable containing the old asset password to keep inside the encrypted wrapper")
    parser.add_argument("--seven-zip", help="Path to 7z executable; autodetected when omitted")
    parser.add_argument("--work-dir", help="Directory for temporary files; defaults to the system temp drive (needs ~4x the asset size)")
    parser.add_argument("--apply", action="store_true", help="Actually upload the wrapper and delete the original asset")
    return parser.parse_args()


def resolve_archive_password(args: argparse.Namespace) -> str:
    return args.archive_password or os.environ.get(args.archive_password_env, "") or DEFAULT_ARCHIVE_PASSWORD


def resolve_old_password(args: argparse.Namespace) -> str | None:
    if args.old_password:
        return args.old_password
    if args.old_password_env:
        return os.environ.get(args.old_password_env, "") or None
    return None


def main() -> int:
    args = parse_args()
    archive_password = resolve_archive_password(args)
    old_password = resolve_old_password(args)
    failures: list[str] = []
    try:
        require_binary("GitHub CLI", ["gh"])
        seven_zip = args.seven_zip or (require_binary("7-Zip", ["7z.exe", "7z", "7zz"]) if args.apply else "")
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    for tag in args.tag:
        try:
            archive_release(
                args=args,
                seven_zip=seven_zip,
                archive_password=archive_password,
                old_password=old_password,
                tag=tag,
            )
        except (RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
            # Один сломанный релиз не должен обрывать остальные: исходный ассет удаляется последним шагом.
            print(f"ERROR [{tag}]: {error}", file=sys.stderr)
            failures.append(tag)

    if failures:
        print(f"Failed tags: {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())