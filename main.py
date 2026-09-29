#!/usr/bin/env python3
"""Распределение покупок из кассового чека между жильцами общежития."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import PEOPLE
from csv_report import ensure_settings, load_report_dir, save_report_dir, write_report_csv

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
CHECKBOX_SIZE = 20


def _draw_checkbox_frame(painter: QPainter, size: int, border: QColor) -> None:
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(border, 2))
    painter.setBrush(QColor("#1a212b"))
    margin = 1
    painter.drawRoundedRect(margin, margin, size - 2 * margin, size - 2 * margin, 4, 4)


def _make_checkbox_icon(checked: bool) -> QPixmap:
    size = CHECKBOX_SIZE * 2
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    border = QColor("#4aa07f" if checked else "#6b7a8d")
    _draw_checkbox_frame(painter, size, border)

    if checked:
        pen = QPen(QColor("#ffffff"))
        pen.setWidth(3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(QPointF(size * 0.22, size * 0.52), QPointF(size * 0.42, size * 0.72))
        painter.drawLine(QPointF(size * 0.42, size * 0.72), QPointF(size * 0.78, size * 0.30))

    painter.end()
    return pixmap


def ensure_checkbox_icons() -> tuple[str, str]:
    ASSETS_DIR.mkdir(exist_ok=True)
    unchecked_path = ASSETS_DIR / "checkbox_off.png"
    checked_path = ASSETS_DIR / "checkbox_on.png"
    if not unchecked_path.exists():
        _make_checkbox_icon(False).save(str(unchecked_path), "PNG")
    if not checked_path.exists():
        _make_checkbox_icon(True).save(str(checked_path), "PNG")
    return unchecked_path.as_posix(), checked_path.as_posix()


def build_stylesheet(unchecked_icon: str, checked_icon: str) -> str:
    return f"""
QMainWindow, QDialog, QMessageBox {{
    background-color: #12161c;
    color: #f5f7fa;
}}
QLabel {{
    color: #f5f7fa;
}}
QLabel#titleLabel {{
    color: #ffffff;
    font-size: 22px;
    font-weight: 700;
}}
QLabel#subtitleLabel {{
    color: #a8b3c2;
    font-size: 13px;
}}
QLabel#dialogTitle {{
    color: #ffffff;
    font-size: 18px;
    font-weight: 700;
}}
QTextEdit {{
    background: #1a212b;
    color: #ffffff;
    border: 1px solid #2c3645;
    border-radius: 10px;
    padding: 10px;
    font-size: 13px;
    selection-background-color: #3d8b6e;
    selection-color: #ffffff;
}}
QTableWidget {{
    background: #171d26;
    color: #ffffff;
    alternate-background-color: #1d2530;
    border: 1px solid #2c3645;
    border-radius: 10px;
    gridline-color: #2c3645;
    font-size: 14px;
    selection-background-color: #2a4a3d;
    selection-color: #ffffff;
    outline: none;
}}
QHeaderView::section {{
    background-color: #24352f;
    color: #ffffff;
    padding: 12px 8px;
    border: none;
    border-right: 1px solid #314840;
    border-bottom: 1px solid #314840;
    font-size: 15px;
    font-weight: 700;
}}
QTableWidget::item {{
    padding: 6px;
    color: #ffffff;
}}
QPushButton {{
    background-color: #3d8b6e;
    color: #ffffff;
    border: none;
    border-radius: 10px;
    padding: 12px 20px;
    font-size: 15px;
    font-weight: 700;
}}
QPushButton:hover {{
    background-color: #4aa07f;
}}
QPushButton:pressed {{
    background-color: #31775c;
}}
QPushButton#secondaryButton {{
    background-color: transparent;
    color: #ffffff;
    border: 2px solid #4aa07f;
}}
QPushButton#secondaryButton:hover {{
    background-color: #24352f;
    border-color: #6bc49a;
}}
QCheckBox {{
    spacing: 0px;
    color: #ffffff;
    background: transparent;
}}
QCheckBox::indicator {{
    width: {CHECKBOX_SIZE}px;
    height: {CHECKBOX_SIZE}px;
    border: none;
    background: transparent;
}}
QCheckBox::indicator:unchecked {{
    image: url("{unchecked_icon}");
}}
QCheckBox::indicator:checked {{
    image: url("{checked_icon}");
}}
QFrame#footerBar {{
    background: #1a212b;
    border: 1px solid #2c3645;
    border-radius: 12px;
}}
QDialogButtonBox QPushButton {{
    min-width: 90px;
}}
QScrollBar:vertical {{
    background: #171d26;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #3a4658;
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: #4f5f75;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""


@dataclass(frozen=True)
class Item:
    name: str
    price: float


def parse_money(value: str) -> float:
    return float(value.replace(" ", "").replace(",", "."))


def format_money(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def parse_receipt(text: str) -> tuple[list[Item], float]:
    """Извлекает позиции и итог из текста кассового чека."""
    total_match = re.search(r"Итог:\s*([\d\s]+[,\.]\d{2})", text)
    if not total_match:
        raise ValueError("В чеке не найден итог (строка «Итог:»).")
    receipt_total = parse_money(total_match.group(1))

    item_header = re.compile(r"^(\d+)\.\s+(.+)$", re.MULTILINE)
    price_line = re.compile(
        r"Цена\s*\*\s*Кол\s*\n\s*([\d\s]+[,\.]\d{2})\s*\*\s*([\d\s]+[,\.]?\d*)\s*(шт\.|кг)",
        re.IGNORECASE,
    )
    sum_line = re.compile(r"Сумма\s*\n\s*([\d\s]+[,\.]\d{2})")

    headers = list(item_header.finditer(text))
    if not headers:
        raise ValueError("В чеке не найдены позиции товаров.")

    items: list[Item] = []
    for index, header in enumerate(headers):
        start = header.end()
        end = headers[index + 1].start() if index + 1 < len(headers) else total_match.start()
        block = text[start:end]
        name = header.group(2).strip()

        price_match = price_line.search(block)
        sum_match = sum_line.search(block)
        if not price_match or not sum_match:
            raise ValueError(f"Не удалось разобрать позицию: {name}")

        unit_price = parse_money(price_match.group(1))
        qty = parse_money(price_match.group(2))
        unit = price_match.group(3).lower()
        line_sum = parse_money(sum_match.group(1))

        if unit.startswith("шт") and qty == int(qty) and int(qty) > 1:
            count = int(qty)
            for _ in range(count):
                items.append(Item(name=name, price=unit_price))
        else:
            items.append(Item(name=name, price=line_sum))

    parsed_total = round(sum(item.price for item in items), 2)
    if abs(parsed_total - receipt_total) > 0.01:
        raise ValueError(
            "Сумма позиций не совпадает с итогом чека:\n"
            f"распарсено {format_money(parsed_total)}, в чеке {format_money(receipt_total)}"
        )

    return items, receipt_total


def centered_checkbox() -> tuple[QWidget, QCheckBox]:
    box = QCheckBox()
    box.setText("")
    box.setFixedSize(CHECKBOX_SIZE + 4, CHECKBOX_SIZE + 4)
    box.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    cell = QWidget()
    cell.setStyleSheet("background: transparent;")
    layout = QHBoxLayout(cell)
    layout.addWidget(box)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.setContentsMargins(0, 0, 0, 0)
    return cell, box


class ReceiptInputDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Вставьте чек")
        self.resize(680, 760)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("Новый чек")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        hint = QLabel("Вставьте текст кассового чека целиком и нажмите «ОК».")
        hint.setObjectName("subtitleLabel")
        layout.addWidget(hint)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText('ООО "Агроторг"\n...\nИтог:\n3556,78')
        layout.addWidget(self.text_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def receipt_text(self) -> str:
        return self.text_edit.toPlainText().strip()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[Item] = []
        self.receipt_total = 0.0
        self.person_boxes: list[dict[str, QCheckBox]] = []
        self.common_boxes: list[QCheckBox] = []
        self._syncing = False

        self.setWindowTitle("Распределение покупок")
        self.resize(980, 760)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        header = QVBoxLayout()
        header.setSpacing(4)
        title = QLabel("Распределение покупок")
        title.setObjectName("titleLabel")
        self.subtitle = QLabel("Отметьте, кто берёт товар, или включите «Общак».")
        self.subtitle.setObjectName("subtitleLabel")
        header.addWidget(title)
        header.addWidget(self.subtitle)
        root.addLayout(header)

        self.table = QTableWidget(0, 3 + len(PEOPLE))
        self.table.setHorizontalHeaderLabels(["Название", "Цена", "Общак", *PEOPLE])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.verticalHeader().setDefaultSectionSize(38)

        header_view = self.table.horizontalHeader()
        header_view.setHighlightSections(False)
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        for col in range(3, 3 + len(PEOPLE)):
            header_view.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

        root.addWidget(self.table)

        footer = QFrame()
        footer.setObjectName("footerBar")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(14, 12, 14, 12)
        footer_layout.setSpacing(12)

        self.total_label = QLabel("Итого: —")
        total_font = QFont()
        total_font.setPointSize(15)
        total_font.setBold(True)
        self.total_label.setFont(total_font)

        new_receipt_btn = QPushButton("Новый чек")
        new_receipt_btn.setObjectName("secondaryButton")
        new_receipt_btn.setMinimumHeight(44)
        new_receipt_btn.clicked.connect(self.load_new_receipt)

        path_btn = QPushButton("Путь CSV")
        path_btn.setObjectName("secondaryButton")
        path_btn.setMinimumHeight(44)
        path_btn.clicked.connect(self.choose_report_path)

        calc_button = QPushButton("Посчитать")
        calc_button.setMinimumHeight(44)
        calc_button.clicked.connect(self.calculate)

        footer_layout.addWidget(self.total_label)
        footer_layout.addStretch(1)
        footer_layout.addWidget(path_btn)
        footer_layout.addWidget(new_receipt_btn)
        footer_layout.addWidget(calc_button)
        root.addWidget(footer)

    def load_items(self, items: list[Item], receipt_total: float) -> None:
        self.items = items
        self.receipt_total = receipt_total
        self.person_boxes = []
        self.common_boxes = []
        self._syncing = False

        self.table.clearContents()
        self.table.setRowCount(len(items) + 1)
        self.subtitle.setText(
            f"Позиций: {len(items)}  ·  отметьте владельцев или включите «Общак»"
        )
        self.total_label.setText(f"Итого: {format_money(receipt_total)} ₽")

        bold = QFont()
        bold.setBold(True)
        bold.setPointSize(13)

        text_color = QColor("#ffffff")
        row_bg = QColor("#171d26")
        alt_bg = QColor("#1d2530")
        total_bg = QColor("#24352f")

        for row, item in enumerate(items):
            bg = alt_bg if row % 2 else row_bg

            name_item = QTableWidgetItem(item.name)
            name_item.setFont(QFont("", 13))
            name_item.setForeground(text_color)
            name_item.setBackground(bg)

            price_item = QTableWidgetItem(format_money(item.price))
            price_item.setFont(QFont("", 13))
            price_item.setForeground(text_color)
            price_item.setBackground(bg)
            price_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, price_item)

            for col in range(2, 3 + len(PEOPLE)):
                placeholder = QTableWidgetItem("")
                placeholder.setBackground(bg)
                self.table.setItem(row, col, placeholder)

            common_cell, common_box = centered_checkbox()
            self.table.setCellWidget(row, 2, common_cell)
            self.common_boxes.append(common_box)

            row_boxes: dict[str, QCheckBox] = {}
            for col, person in enumerate(PEOPLE, start=3):
                cell, box = centered_checkbox()
                self.table.setCellWidget(row, col, cell)
                row_boxes[person] = box
                box.stateChanged.connect(
                    lambda _state, r=row: self._on_person_changed(r)
                )
            self.person_boxes.append(row_boxes)

            common_box.stateChanged.connect(
                lambda state, r=row: self._on_common_changed(r, state)
            )

        total_row = len(items)
        total_name = QTableWidgetItem("Итого")
        total_name.setFont(bold)
        total_name.setForeground(text_color)
        total_name.setBackground(total_bg)

        total_value = QTableWidgetItem(format_money(receipt_total))
        total_value.setFont(bold)
        total_value.setForeground(text_color)
        total_value.setBackground(total_bg)
        total_value.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        self.table.setItem(total_row, 0, total_name)
        self.table.setItem(total_row, 1, total_value)
        for col in range(2, 3 + len(PEOPLE)):
            filler = QTableWidgetItem("")
            filler.setBackground(total_bg)
            self.table.setItem(total_row, col, filler)

    def _on_common_changed(self, row: int, state: int) -> None:
        if self._syncing:
            return
        self._syncing = True
        checked = state == Qt.CheckState.Checked.value
        for box in self.person_boxes[row].values():
            box.setChecked(checked)
        self._syncing = False

    def _on_person_changed(self, row: int) -> None:
        if self._syncing:
            return
        self._syncing = True
        all_checked = all(box.isChecked() for box in self.person_boxes[row].values())
        self.common_boxes[row].setChecked(all_checked)
        self._syncing = False

    def load_new_receipt(self) -> None:
        parsed = ask_receipt(self)
        if parsed is None:
            return
        items, receipt_total = parsed
        self.load_items(items, receipt_total)

    def choose_report_path(self) -> None:
        current = str(load_report_dir())
        path = QFileDialog.getExistingDirectory(
            self,
            "Папка для сохранения CSV",
            current,
        )
        if not path:
            return
        save_report_dir(path)
        QMessageBox.information(
            self,
            "Путь сохранён",
            f"Отчёты будут сохраняться в папку:\n{path}",
        )

    def calculate(self) -> None:
        if not self.items:
            QMessageBox.information(self, "Пусто", "Сначала загрузите чек.")
            return

        shares = {person: 0.0 for person in PEOPLE}
        unassigned: list[str] = []
        rows: list[dict[str, str]] = []

        for item, boxes, common_box in zip(
            self.items, self.person_boxes, self.common_boxes
        ):
            selected = [person for person, box in boxes.items() if box.isChecked()]
            row = {
                "Название": item.name,
                "Цена": format_money(item.price),
                "Общак": "да" if common_box.isChecked() else "нет",
            }
            for person in PEOPLE:
                row[person] = ""

            if not selected:
                unassigned.append(f"{item.name} ({format_money(item.price)})")
            else:
                share = item.price / len(selected)
                for person in selected:
                    shares[person] += share
                    row[person] = format_money(share)

            rows.append(row)

        total_row = {
            "Название": "Итого",
            "Цена": format_money(self.receipt_total),
            "Общак": "",
        }
        for person in PEOPLE:
            total_row[person] = format_money(shares[person])
        rows.append(total_row)

        lines = [f"{person}: {format_money(amount)} ₽" for person, amount in shares.items()]
        lines.append("")
        lines.append(f"Сумма долей: {format_money(sum(shares.values()))} ₽")
        lines.append(f"Итог чека: {format_money(self.receipt_total)} ₽")

        if unassigned:
            lines.append("")
            lines.append("Без владельца:")
            lines.extend(f"• {name}" for name in unassigned)

        try:
            csv_path = write_report_csv(rows, PEOPLE)
        except OSError as exc:
            QMessageBox.critical(self, "Ошибка сохранения", str(exc))
            return

        lines.append("")
        lines.append(f"CSV сохранён: {csv_path}")
        QMessageBox.information(self, "Результат", "\n".join(lines))


def ask_receipt(parent: QWidget | None = None) -> tuple[list[Item], float] | None:
    """Показывает диалог ввода чека, пока не будет валидный текст или отмена."""
    draft = ""
    while True:
        dialog = ReceiptInputDialog(parent)
        if draft:
            dialog.text_edit.setPlainText(draft)
            cursor = dialog.text_edit.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            dialog.text_edit.setTextCursor(cursor)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None

        text = dialog.receipt_text()
        if not text:
            QMessageBox.critical(parent, "Ошибка", "Чек пустой. Вставьте текст чека и попробуйте снова.")
            continue

        try:
            return parse_receipt(text)
        except ValueError as exc:
            QMessageBox.critical(parent, "Ошибка парсинга", f"{exc}\n\nИсправьте чек и попробуйте снова.")
            draft = text


def main() -> None:
    if not PEOPLE:
        print("В config.py список PEOPLE пуст — добавьте хотя бы одного участника.")
        sys.exit(1)

    ensure_settings()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    unchecked_icon, checked_icon = ensure_checkbox_icons()
    app.setStyleSheet(build_stylesheet(unchecked_icon, checked_icon))

    window = MainWindow()
    parsed = ask_receipt(window)
    if parsed is None:
        sys.exit(0)

    items, receipt_total = parsed
    window.load_items(items, receipt_total)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
