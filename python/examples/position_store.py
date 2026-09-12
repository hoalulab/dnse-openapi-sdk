#!/usr/bin/env python3
"""Persist the current open position to disk so it survives app restarts.

When an entry fills, the position (side/qty/entry/SL/TP) is saved. On the next
start the app reloads it and keeps managing the TP/SL exit instead of opening a
new trade. When the position closes, the file is cleared.

The file (default: examples/.position.json, override with DNSE_POSITION_STORE)
is written 0600 and is gitignored.
"""
import json
import os
import time


def _path():
    return os.environ.get(
        "DNSE_POSITION_STORE",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".position.json"),
    )


def save_position(pos: dict):
    """Persist an open position (dict). Stamps opened_at if absent."""
    data = dict(pos)
    data.setdefault("opened_at", time.time())
    path = _path()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    return path


def load_position():
    """Return the persisted position dict, or None if none/unreadable."""
    try:
        with open(_path(), encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def clear_position():
    """Delete the persisted position (call when it is closed)."""
    try:
        os.remove(_path())
    except OSError:
        pass
