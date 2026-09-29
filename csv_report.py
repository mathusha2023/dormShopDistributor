"""Сохранение CSV-отчётов и путь из файла .settings."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from config import DEFAULT_REPORT_DIR

SETTINGS_FILE = Path(__file__).resolve().parent / ".settings"


def ensure_settings(default_dir: str = DEFAULT_REPORT_DIR) -> Path:
    """Создаёт .settings с папкой по умолчанию, если файла ещё нет."""
    if not SETTINGS_FILE.exists():
        save_report_dir(default_dir)
    return SETTINGS_FILE


def load_report_dir(default_dir: str = DEFAULT_REPORT_DIR) -> Path:
    """Читает папку сохранения отчётов из .settings."""
    ensure_settings(default_dir)
    path_text = SETTINGS_FILE.read_text(encoding="utf-8").strip()
    if not path_text:
        path_text = default_dir
        save_report_dir(path_text)

    directory = Path(path_text).expanduser()
    # На случай, если в .settings раньше лежал путь к файлу.
    if directory.suffix.lower() == ".csv":
        directory = directory.parent
    return directory


def save_report_dir(path: str | Path) -> None:
    """Записывает папку сохранения отчётов в .settings."""
    directory = Path(path).expanduser()
    if directory.suffix.lower() == ".csv":
        directory = directory.parent
    SETTINGS_FILE.write_text(f"{directory}\n", encoding="utf-8")


def build_report_filename() -> str:
    return f"otchet_{datetime.now():%Y%m%d_%H%M%S}.csv"


def write_report_csv(
    rows: list[dict[str, str]],
    people: list[str],
    directory: Path | None = None,
) -> Path:
    """Пишет отчёт в CSV в сохранённую или переданную папку."""
    folder = Path(directory) if directory is not None else load_report_dir()
    folder.mkdir(parents=True, exist_ok=True)

    target = folder / build_report_filename()
    fieldnames = ["Название", "Цена", "Общак", *people]
    with target.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    return target.resolve()
