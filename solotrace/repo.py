"""
Repository access for SoloTrace: safe path resolution, reading source at a
commit or in the working tree, and small git helpers.

Everything SoloTrace reads on behalf of an AI verdict goes through
``SourceReader``, which refuses paths outside the repository.  An audit verdict
is untrusted input: it must never be able to make SoloTrace read (and later
publish) files such as ``/etc/hosts`` or ``../secrets.env``.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path, PurePosixPath

__all__ = [
    "UnsafePathError",
    "SourceReader",
    "repo_root",
    "head_commit",
    "is_dirty",
    "sha256_file",
    "relative_display",
]


class UnsafePathError(ValueError):
    """Raised when a path would escape the repository."""


def _git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout if result.returncode == 0 else None


def repo_root(start: Path | str = ".") -> Path:
    """The git top-level directory containing *start* (or *start* itself)."""
    start = Path(start).resolve()
    out = _git(start, "rev-parse", "--show-toplevel")
    return Path(out.strip()) if out else start


def head_commit(root: Path) -> str | None:
    out = _git(root, "rev-parse", "HEAD")
    return out.strip() if out else None


def is_dirty(root: Path) -> bool:
    out = _git(root, "status", "--porcelain", "--untracked-files=no")
    return bool(out and out.strip())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_display(path: Path, root: Path) -> str:
    """Repo-relative POSIX path for reports; never leaks absolute local paths."""
    try:
        return Path(path).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return Path(path).name


def _normalise_relpath(relpath: str) -> str:
    if not isinstance(relpath, str) or not relpath.strip():
        raise UnsafePathError("empty path")
    candidate = relpath.strip().replace("\\", "/")
    pure = PurePosixPath(candidate)
    if pure.is_absolute() or candidate.startswith("~") or (len(candidate) > 1 and candidate[1] == ":"):
        raise UnsafePathError(f"absolute paths are not allowed: {relpath!r}")
    if any(part == ".." for part in pure.parts):
        raise UnsafePathError(f"parent-directory segments are not allowed: {relpath!r}")
    return pure.as_posix()


class SourceReader:
    """Read repository files, either from the working tree or from a git commit.

    Paths are always interpreted relative to the repository root, and anything
    that would resolve outside it is rejected with ``UnsafePathError``.
    """

    def __init__(self, root: Path, commit: str | None = None) -> None:
        self.root = Path(root).resolve()
        self.commit = commit
        self._cache: dict[str, list[str] | None] = {}

    def check(self, relpath: str) -> str:
        """Validate *relpath*; return its normalised repo-relative form."""
        rel = _normalise_relpath(relpath)
        if self.commit is None:
            resolved = (self.root / rel).resolve()
            try:
                resolved.relative_to(self.root)
            except ValueError as exc:  # e.g. a symlink pointing outside the repo
                raise UnsafePathError(f"path escapes the repository: {relpath!r}") from exc
        return rel

    def text(self, relpath: str) -> str | None:
        rel = self.check(relpath)
        if self.commit is not None:
            return _git(self.root, "show", f"{self.commit}:{rel}")
        path = self.root / rel
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8", errors="replace")

    def lines(self, relpath: str) -> list[str] | None:
        """File contents as a list of lines (index 0 == line 1), or None if missing."""
        rel = self.check(relpath)
        if rel not in self._cache:
            text = self.text(rel)
            self._cache[rel] = None if text is None else text.splitlines()
        return self._cache[rel]

    def describe(self) -> dict:
        if self.commit is not None:
            return {"kind": "commit", "commit": self.commit}
        return {"kind": "working-tree", "commit": head_commit(self.root), "dirty": is_dirty(self.root)}
