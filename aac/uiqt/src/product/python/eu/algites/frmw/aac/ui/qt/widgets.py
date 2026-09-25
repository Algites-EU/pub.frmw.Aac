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
from .aic_qt_panel_widget import AIcQtPanelWidget
from .aic_qt_form_dialog import AIcQtFormDialog
from .aic_qt_requirement_dialog import AIcQtRequirementDialog
from .aic_qt_observation_dialog import AIcQtObservationDialog
from .aic_aac_administration_widget import AIcAacAdministrationWidget

def _ui_text(value: AIcDisplayText | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, AIcDisplayText):
        return value.fallback
    return str(value)
