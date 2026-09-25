from __future__ import annotations
import json
from typing import Mapping
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from eu.algites.frmw.aac.core.presentation.api import AInDisplayContentFormat, AIcDisplayText
from eu.algites.frmw.aac.ui.api import (
    AIiAacUiController,
    AInUiFieldType,
    AIcUiChoice,
    AIcUiField,
    AIcUiFieldGroup,
    AIcUiForm,
    AIcUiDisplay,
    AIcUiPanel,
    AIcUiObservationBinding,
    AIcUiObservationSelector,
    AIcUiRequirementEditor,
)

def _ui_text(value: AIcDisplayText | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, AIcDisplayText):
        return value.fallback
    return str(value)

class AIcQtRequirementDialog(QDialog):
    def __init__(self, editor: AIcUiRequirementEditor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.editor = editor
        self.setWindowTitle(f"Binding: {editor.requirement_id}")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"Capability: {editor.capability_id} | versions: {', '.join(map(str, editor.versions))} | {editor.cardinality}"
        ))
        self.list = QListWidget()
        self.list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
            if editor.cardinality == "SINGLE" else QAbstractItemView.SelectionMode.MultiSelection
        )
        selected = set(editor.selected_provider_instance_ids)
        for choice in editor.provider_choices:
            item = QListWidgetItem(_ui_text(choice.label))
            item.setData(Qt.ItemDataRole.UserRole, choice.value)
            self.list.addItem(item)
            if choice.value in selected:
                item.setSelected(True)
        layout.addWidget(self.list)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_provider_instance_ids(self) -> tuple[str, ...]:
        return tuple(str(item.data(Qt.ItemDataRole.UserRole)) for item in self.list.selectedItems())
