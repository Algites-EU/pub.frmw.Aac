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

from .aic_qt_display_widget import AIcQtDisplayWidget

def _ui_text(value: AIcDisplayText | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, AIcDisplayText):
        return value.fallback
    return str(value)

class AIcQtPanelWidget(QGroupBox):
    """Baseline recursive Qt renderer for AAC panels/display blocks."""

    def __init__(self, panel: AIcUiPanel, parent: QWidget | None = None) -> None:
        super().__init__(_ui_text(panel.title), parent)
        layout = QVBoxLayout(self)
        if panel.description is not None:
            description = QLabel(_ui_text(panel.description))
            description.setWordWrap(True)
            layout.addWidget(description)
        for display in panel.displays:
            layout.addWidget(AIcQtDisplayWidget(display, self))
        for child in panel.panels:
            layout.addWidget(AIcQtPanelWidget(child, self))
