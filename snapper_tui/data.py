"""Snapshot data helpers powered by snapper."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


class SnapperError(RuntimeError):
    """Errors that occur when talking to the snapper command."""


@dataclass
class Snapshot:
    config: str
    subvolume: str
    number: int
    snapshot_type: str
    pre_number: int | None
    post_number: int | None
    date: str
    user: str
    cleanup: str | None
    description: str
    userdata: Mapping[str, str] | None
    used_space: int | None
    default: bool
    active: bool

    @classmethod
    def from_raw(cls, config: str, data: dict[str, Any]) -> Snapshot:
        return cls(
            config=data.get("config") or config or "",
            subvolume=data.get("subvolume", ""),
            number=_to_int(data.get("number")) or 0,
            snapshot_type=data.get("type", ""),
            pre_number=_to_int(data.get("pre-number")),
            post_number=_to_int(data.get("post-number")),
            date=data.get("date", ""),
            user=data.get("user", ""),
            cleanup=data.get("cleanup"),
            description=data.get("description", ""),
            userdata=_normalize_userdata(data.get("userdata")),
            used_space=_to_int(data.get("used-space")),
            default=bool(data.get("default", False)),
            active=bool(data.get("active", False)),
        )


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_userdata(value: Any) -> Mapping[str, str] | None:
    if isinstance(value, dict):
        return {k: str(v) for k, v in value.items()}
    return None


def _build_command(columns: Sequence[str]) -> list[str]:
    return [
        "snapper",
        "--jsonout",
        "list",
        "--columns",
        ",".join(columns),
    ]


def list_snapshots() -> list[Snapshot]:
    """Return a list of parsed snapshots from the default snapper config."""

    columns = [
        "config",
        "subvolume",
        "number",
        "type",
        "pre-number",
        "post-number",
        "date",
        "user",
        "cleanup",
        "description",
        "userdata",
        "used-space",
        "default",
        "active",
    ]
    command = _build_command(columns)
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise SnapperError("`snapper` executable not found in PATH") from exc
    except subprocess.CalledProcessError as exc:
        details = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise SnapperError(f"snapper list failed: {details}") from exc

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SnapperError("Unable to decode snapper JSON output") from exc

    snapshots: list[Snapshot] = []
    if isinstance(payload, dict):
        for config_name, entries in payload.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                snapshots.append(Snapshot.from_raw(config_name, entry))
    else:
        raise SnapperError("Unexpected snapper output structure")
    return snapshots
