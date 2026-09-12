#!/usr/bin/env python3
"""Shared helpers for loading example configuration from .env files."""
import os

from log_util import log


def load_dotenv():
    """Load KEY=VALUE lines from nearby .env files into os.environ.

    Search order:
    - current working directory
    - examples/ (this file's directory)
    - repo python/ root (parent of examples/)

    Existing environment variables win over .env values.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    seen = set()
    for directory in (os.getcwd(), here, os.path.dirname(here)):
        path = os.path.join(directory, ".env")
        if path in seen or not os.path.isfile(path):
            continue
        seen.add(path)
        try:
            with open(path, encoding="utf-8") as handle:
                for raw in handle:
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    if line.lower().startswith("export "):
                        line = line[len("export "):]
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))
            log(f"Đã nạp .env từ {path}")
        except OSError:
            pass
