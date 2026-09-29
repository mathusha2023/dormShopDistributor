"""Пути к ресурсам и рабочей папке (учитывает сборку PyInstaller)."""

from __future__ import annotations

import sys
from pathlib import Path


def resource_root() -> Path:
    """Папка с ресурсами (в onefile — временный _MEIPASS)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def app_root() -> Path:
    """Папка рядом с приложением (для .settings и пользовательских файлов)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent
