#!/usr/bin/env python3
"""Small atomic filesystem writes shared by runtime commands."""

from __future__ import annotations

import os
import secrets
import stat
from pathlib import Path


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_mode = (
        stat.S_IMODE(path.stat().st_mode)
        if path.exists()
        else None
    )
    temporary_path: Path | None = None
    try:
        creation_mode = existing_mode if existing_mode is not None else 0o666
        for _ in range(100):
            candidate = path.parent / (
                f".{path.name}.{secrets.token_hex(8)}.tmp"
            )
            try:
                descriptor = os.open(
                    candidate,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    creation_mode,
                )
            except FileExistsError:
                continue
            temporary_path = candidate
            break
        else:
            raise FileExistsError(
                f"could not allocate a temporary file beside {path}"
            )
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        if existing_mode is not None:
            temporary_path.chmod(existing_mode)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
