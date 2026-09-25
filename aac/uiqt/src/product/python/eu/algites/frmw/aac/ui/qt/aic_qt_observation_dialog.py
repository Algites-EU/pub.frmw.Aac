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

class AIcQtObservationDialog(QDialog):
    def __init__(self, binding: AIcUiObservationBinding, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.binding = binding
        self.setWindowTitle("Observation binding")
        selector = binding.selectors[0] if binding.selectors else AIcUiObservationSelector()
        layout = QFormLayout(self)
        self.capability = QLineEdit(selector.capability)
        self.versions = QLineEdit(",".join(str(value) for value in selector.versions))
        self.operations = QLineEdit(",".join(selector.operations))
        self.pre = QCheckBox("PRE")
        self.post = QCheckBox("POST")
        self.pre.setChecked("PRE" in selector.phases)
        self.post.setChecked("POST" in selector.phases)
        phase_row = QWidget()
        phase_layout = QHBoxLayout(phase_row)
        phase_layout.setContentsMargins(0, 0, 0, 0)
        phase_layout.addWidget(self.pre)
        phase_layout.addWidget(self.post)
        layout.addRow("Capability", self.capability)
        layout.addRow("Versions", self.versions)
        layout.addRow("Operations", self.operations)
        layout.addRow("Phases", phase_row)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def value(self) -> AIcUiObservationBinding:
        versions = tuple(int(value.strip()) for value in self.versions.text().split(",") if value.strip())
        operations = tuple(value.strip() for value in self.operations.text().split(",") if value.strip())
        phases = tuple(value for value, widget in (("PRE", self.pre), ("POST", self.post)) if widget.isChecked())
        return AIcUiObservationBinding(
            self.binding.observer_instance_id,
            (AIcUiObservationSelector(self.capability.text().strip() or "*", versions, operations, phases),),
        )
