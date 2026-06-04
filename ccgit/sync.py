"""Filesystem sync and manifest generation."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
import hashlib
import os
from pathlib import Path
import shutil
from typing import Dict, Iterable, List, Sequence, Set


DEFAULT_EXCLUDES = [
    ".git/",
    ".ccgit/",
    "__pycache__/",
    "*.pyc",
]


@dataclass(frozen=True)
class FileRecord:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class SyncSummary:
    copied: int
    removed: int
    unchanged: int
    skipped: List[str]


def normalize_path(path: Path) -> str:
    text = path.as_posix()
    return text[2:] if text.startswith("./") else text


def is_excluded(relative_path: str, patterns: Sequence[str]) -> bool:
    rel = relative_path.strip("/")
    for pattern in patterns:
        pattern = pattern.strip()
        if not pattern:
            continue
        directory_pattern = pattern.endswith("/")
        pattern = pattern.rstrip("/")
        if directory_pattern and (rel == pattern or rel.startswith(pattern + "/")):
            return True
        if fnmatch(rel, pattern) or fnmatch(Path(rel).name, pattern):
            return True
    return False


def iter_files(root: Path, excludes: Sequence[str]) -> Iterable[Path]:
    root = root.resolve()
    patterns = list(DEFAULT_EXCLUDES) + list(excludes)
    for current_root, dirnames, filenames in os.walk(root):
        current = Path(current_root)
        kept_dirs = []
        for dirname in dirnames:
            rel = normalize_path((current / dirname).relative_to(root))
            if not is_excluded(rel + "/", patterns):
                kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in filenames:
            file_path = current / filename
            rel = normalize_path(file_path.relative_to(root))
            if not is_excluded(rel, patterns):
                yield file_path


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(root: Path, excludes: Sequence[str]) -> List[FileRecord]:
    root = root.resolve()
    records = []
    for file_path in iter_files(root, excludes):
        stat = file_path.stat()
        records.append(
            FileRecord(
                path=normalize_path(file_path.relative_to(root)),
                size=stat.st_size,
                sha256=file_hash(file_path),
            )
        )
    return sorted(records, key=lambda item: item.path)


def sync_tree(source: Path, destination: Path, excludes: Sequence[str]) -> SyncSummary:
    """Mirror source into destination while preserving destination's .git directory."""

    source = source.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    destination = destination.resolve()
    protected_patterns = list(DEFAULT_EXCLUDES)
    desired: Set[str] = set()
    copied = 0
    unchanged = 0
    skipped: List[str] = []

    for source_file in iter_files(source, excludes):
        rel = normalize_path(source_file.relative_to(source))
        desired.add(rel)
        dest_file = destination / rel
        dest_file.parent.mkdir(parents=True, exist_ok=True)

        if dest_file.exists() and dest_file.is_file():
            if source_file.stat().st_size == dest_file.stat().st_size:
                if file_hash(source_file) == file_hash(dest_file):
                    unchanged += 1
                    continue

        shutil.copy2(source_file, dest_file)
        copied += 1

    removed = 0
    for dest_file in list(iter_files(destination, [])):
        rel = normalize_path(dest_file.relative_to(destination))
        if is_excluded(rel, protected_patterns):
            skipped.append(rel)
            continue
        if rel not in desired:
            dest_file.unlink()
            removed += 1

    remove_empty_dirs(destination)
    return SyncSummary(copied=copied, removed=removed, unchanged=unchanged, skipped=sorted(skipped))


def remove_empty_dirs(root: Path) -> None:
    for current_root, dirnames, _ in os.walk(root, topdown=False):
        current = Path(current_root)
        if current == root:
            continue
        if ".git" in current.parts:
            continue
        try:
            current.rmdir()
        except OSError:
            pass


def manifest_to_dict(records: Sequence[FileRecord]) -> List[Dict[str, object]]:
    return [{"path": item.path, "size": item.size, "sha256": item.sha256} for item in records]
