#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ -x ".venv/bin/python" ]]; then
  PYTHON=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
else
  echo "Не найден Python. Создай venv и установи зависимости:"
  echo "  python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

if ! "$PYTHON" -c "import PyInstaller" >/dev/null 2>&1; then
  echo "PyInstaller не установлен. Ставлю зависимости..."
  "$PYTHON" -m pip install -r requirements.txt
fi

if [[ ! -f "assets/checkbox_off.png" || ! -f "assets/checkbox_on.png" ]]; then
  echo "Генерирую иконки в assets/..."
  "$PYTHON" -c "from PyQt6.QtWidgets import QApplication; import sys; from main import ensure_checkbox_icons; app=QApplication(sys.argv); print(ensure_checkbox_icons())"
fi

echo "Сборка Distributor..."
"$PYTHON" -m PyInstaller --noconfirm --clean Distributor.spec

echo
echo "Готово: dist/Distributor"
if [[ "$(uname -s)" == "Darwin" ]]; then
  echo "Запуск: ./dist/Distributor"
else
  echo "Запуск: ./dist/Distributor"
fi
