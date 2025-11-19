"""Utility helpers for Snapper TUI."""

from __future__ import annotations

import shutil
from collections.abc import Mapping


def human_readable_bytes(size: int | None, precision: int = 1) -> str:
    """Format bytes into human-readable format."""
    if size is None:
        return "n/a"
    if size < 0:
        return "-"
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"]
    value = float(size)
    unit_index = 0
    while value >= 1024 and unit_index < len(units) - 1:
        value /= 1024
        unit_index += 1
    return f"{value:.{precision}f} {units[unit_index]}"


def flatten_user_data(userdata: Mapping[str, str] | None) -> str:
    """Flatten user data mapping into a string."""
    if not userdata:
        return ""
    entries = [f"{key}={value}" for key, value in userdata.items()]
    return " ".join(entries)


def free_space_for_path(path: str = "/") -> int | None:
    """Get free disk space for a given path."""
    try:
        usage = shutil.disk_usage(path)
        return usage.free
    except OSError:
        return None
