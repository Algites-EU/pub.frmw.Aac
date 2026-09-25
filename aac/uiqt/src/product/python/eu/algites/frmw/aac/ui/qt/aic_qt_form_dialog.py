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

class AIcQtFormDialog(QDialog):
    def __init__(self, form: AIcUiForm, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.form = form
        self.setWindowTitle(_ui_text(form.title))
        self._editors: dict[str, QWidget] = {}
        layout = QVBoxLayout(self)
        if form.description:
            description = QLabel(_ui_text(form.description))
            description.setWordWrap(True)
            layout.addWidget(description)
        self._provider_selector = None
        if form.configuration_provider_options:
            selector_row = QWidget()
            selector_layout = QFormLayout(selector_row)
            self._provider_selector = QComboBox()
            preferred = -1
            for index, option in enumerate(form.configuration_provider_options):
                mode = "RW" if option.can_write_value else "RO"
                record_revision = f" rev={option.record_revision}" if option.record_revision is not None else ""
                label = f"{option.configuration_scope.key} / {option.configuration_provider_id} [{mode}{record_revision}]"
                self._provider_selector.addItem(label, index)
                if preferred < 0 and option.can_write_value:
                    preferred = index
            if preferred >= 0:
                self._provider_selector.setCurrentIndex(preferred)
            selector_layout.addRow("Edit target", self._provider_selector)
            layout.addWidget(selector_row)
        for group in form.groups:
            if group.label:
                label = QLabel(f"<b>{_ui_text(group.label)}</b>")
                layout.addWidget(label)
            grid = QFormLayout()
            for field in group.fields:
                editor = self._create_editor(field)
                self._editors[field.id] = editor
                grid.addRow(_ui_text(field.label) + (" *" if field.required else ""), editor)
                if field.description:
                    help_label = QLabel(_ui_text(field.description))
                    help_label.setWordWrap(True)
                    help_label.setStyleSheet("font-size: 90%;")
                    grid.addRow("", help_label)
            layout.addLayout(grid)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self._buttons = buttons
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if self._provider_selector is not None:
            self._provider_selector.currentIndexChanged.connect(self._sync_write_access)
            self._sync_write_access()

    def _create_editor(self, field: AIcUiField) -> QWidget:
        value = field.value
        if field.field_type is AInUiFieldType.BOOLEAN:
            widget = QCheckBox()
            widget.setChecked(bool(value))
        elif field.field_type is AInUiFieldType.INTEGER:
            widget = QSpinBox()
            widget.setRange(-2_147_483_648, 2_147_483_647)
            widget.setValue(int(value or 0))
        elif field.field_type is AInUiFieldType.NUMBER:
            widget = QDoubleSpinBox()
            widget.setRange(-1e100, 1e100)
            widget.setDecimals(8)
            widget.setValue(float(value or 0.0))
        elif field.field_type is AInUiFieldType.ENUM:
            widget = QComboBox()
            for choice in field.choices:
                widget.addItem(_ui_text(choice.label), choice.value)
            index = widget.findData(value)
            if index >= 0:
                widget.setCurrentIndex(index)
        elif field.field_type in (AInUiFieldType.JSON, AInUiFieldType.MULTILINE):
            widget = QTextEdit()
            if field.field_type is AInUiFieldType.JSON:
                widget.setPlainText(json.dumps(value if value is not None else {}, indent=2, ensure_ascii=False))
            else:
                widget.setPlainText(str(value or ""))
        else:
            widget = QLineEdit(str(value or ""))
            if field.secret:
                widget.setEchoMode(QLineEdit.EchoMode.Password)
        widget.setEnabled(not field.read_only)
        return widget

    def selected_configuration_provider_option(self):
        if self._provider_selector is None:
            return None
        index = self._provider_selector.currentData()
        if index is None:
            return None
        return self.form.configuration_provider_options[int(index)]

    def _sync_write_access(self) -> None:
        option = self.selected_configuration_provider_option()
        writable = option is None or option.can_write_value
        for field_id, widget in self._editors.items():
            field = next(field for field in self.form.fields if field.id == field_id)
            widget.setEnabled(writable and not field.read_only)
        ok = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setEnabled(writable)

    def values(self) -> dict[str, object]:
        result: dict[str, object] = {}
        by_id = {field.id: field for field in self.form.fields}
        for field_id, widget in self._editors.items():
            field = by_id[field_id]
            if isinstance(widget, QCheckBox):
                value: object = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                value = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                value = widget.value()
            elif isinstance(widget, QComboBox):
                value = widget.currentData()
            elif isinstance(widget, QTextEdit):
                text = widget.toPlainText()
                value = json.loads(text) if field.field_type is AInUiFieldType.JSON else text
            elif isinstance(widget, QLineEdit):
                value = widget.text()
            else:
                raise TypeError(type(widget).__name__)
            result[field_id] = value
        return result
