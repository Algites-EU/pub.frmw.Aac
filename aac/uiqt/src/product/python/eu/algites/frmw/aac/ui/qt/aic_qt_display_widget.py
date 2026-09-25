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

class AIcQtDisplayWidget(QWidget):
    """Baseline Qt renderer for toolkit-neutral AAC display content."""

    def __init__(self, display: AIcUiDisplay, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if display.title is not None:
            title = QLabel(f"<b>{_ui_text(display.title)}</b>")
            title.setWordWrap(True)
            layout.addWidget(title)
        browser = QTextBrowser()
        content = display.content
        if content.format is AInDisplayContentFormat.MARKDOWN:
            browser.setMarkdown(content.fallback)
        elif content.format is AInDisplayContentFormat.HTML:
            browser.setHtml(content.fallback)
        else:
            browser.setPlainText(content.fallback)
        browser.setOpenExternalLinks(False)
        layout.addWidget(browser)
