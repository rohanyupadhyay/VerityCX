"""Read only contained regular document files, rejecting links and filesystem changes."""

import os
import stat
from pathlib import Path, PurePosixPath


class SourceError(ValueError):
    """Expose a safe source-policy category without paths or document bodies."""


def path_chain(root: Path, relative: str) -> tuple[Path, list[os.stat_result]]:
    """Inspect lexical containment and every path component without following links."""
    parsed = PurePosixPath(relative)
    if (
        not relative
        or parsed.is_absolute()
        or "\\" in relative
        or ":" in relative
        or any(part in {"", ".", ".."} for part in relative.split("/"))
        or parsed.suffix != ".json"
    ):
        raise SourceError("forbidden_source")
    absolute = root.absolute()
    paths = [*reversed(absolute.parents), absolute]
    current = absolute
    for part in parsed.parts:
        current = current / part
        paths.append(current)
    snapshots: list[os.stat_result] = []
    try:
        for index, path in enumerate(paths):
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise SourceError("forbidden_source")
            expected = stat.S_ISREG if index == len(paths) - 1 else stat.S_ISDIR
            if not expected(info.st_mode):
                raise SourceError("forbidden_source")
            snapshots.append(info)
    except OSError:
        raise SourceError("corpus_changed") from None
    return current, snapshots


def verified_bytes(root: Path, relative: str) -> bytes:
    """Read at most one MiB and require stable file/directory identity across the read."""
    path, before = path_chain(root, relative)
    if before[-1].st_size > 1024 * 1024:
        raise SourceError("invalid_document")
    try:
        descriptor = os.open(
            path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        )
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino) != (before[-1].st_dev, before[-1].st_ino):
                raise SourceError("corpus_changed")
            raw = stream.read(1024 * 1024 + 1)
            finished = os.fstat(stream.fileno())
        _, after = path_chain(root, relative)

        def identity(item: os.stat_result) -> tuple[int, int, int, int]:
            """Compare filesystem identity and mutation metadata before/after opening."""
            # Unrelated directory children may change; only directory identity matters.
            if stat.S_ISDIR(item.st_mode):
                return item.st_dev, item.st_ino, 0, 0
            return item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns

        if len(raw) > 1024 * 1024 or identity(opened) != identity(finished):
            raise SourceError("corpus_changed")
        if [identity(item) for item in before] != [identity(item) for item in after]:
            raise SourceError("corpus_changed")
        return raw
    except OSError:
        raise SourceError("corpus_changed") from None
