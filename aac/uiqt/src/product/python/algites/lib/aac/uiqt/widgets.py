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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from algites.lib.aac.uiintf import (
    AIiAacUiController,
    AInUiFieldType,
    AIcUiChoice,
    AIcUiField,
    AIcUiFieldGroup,
    AIcUiForm,
    AIcUiObservationBinding,
    AIcUiObservationSelector,
    AIcUiRequirementEditor,
)


class AIcQtFormDialog(QDialog):
    def __init__(self, form: AIcUiForm, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.form = form
        self.setWindowTitle(form.title)
        self._editors: dict[str, QWidget] = {}
        layout = QVBoxLayout(self)
        if form.description:
            description = QLabel(form.description)
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
                label = QLabel(f"<b>{group.label}</b>")
                layout.addWidget(label)
            grid = QFormLayout()
            for field in group.fields:
                editor = self._create_editor(field)
                self._editors[field.id] = editor
                grid.addRow(field.label + (" *" if field.required else ""), editor)
                if field.description:
                    help_label = QLabel(field.description)
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
                widget.addItem(choice.label, choice.value)
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
            item = QListWidgetItem(choice.label)
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


class AIcAacAdministrationWidget(QWidget):
    """Reusable baseline AAC administration widget.

    Product code owns the QApplication/event loop.  This widget edits only Core-owned
    configuration/topology through AIiAacUiController.
    """

    def __init__(self, controller: AIiAacUiController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.components_table = self._table(("Component", "Version", "Providers", "Readiness", "Readiness detail"))
        self.catalog_table = self._table((
            "Name", "Component", "Version", "Artifact", "Publisher", "Provides", "Requires",
            "Entitlement", "State", "Source", "Entitlement info"
        ))
        product_id, technology_id = self.controller.catalog_defaults()
        self.catalog_product = QLineEdit(product_id or "")
        self.catalog_technology = QLineEdit(technology_id or "")
        self.catalog_search = QLineEdit()
        self.catalog_search.setPlaceholderText("Name, description, component id, category or tag")
        self.packages_table = self._table(("Component", "Version", "State", "Active scopes", "SHA-256", "Source"))
        self.packages_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.package_scope = QLineEdit("default")
        self.solver_solutions = QComboBox()
        self.solver_solutions.setEnabled(False)
        self._last_solver_result = None
        self.package_result = QTextEdit()
        self.package_result.setReadOnly(True)
        self.package_result.setPlaceholderText("Select one or more installed target packages and validate the complete target state.")
        self.instances_table = self._table(("Name", "Component", "Provider", "Capabilities", "Access", "State", "Readiness", "Readiness detail", "ID"))
        self.bindings_table = self._table(("Consumer", "Requirement", "Capability", "Cardinality", "Selected provider IDs"))
        self.observation_table = self._table(("Observer", "Selectors"))
        self.entitlement_table = self._table(("Component", "Capability", "Permission", "Scope", "Issuer", "Effective until"))
        self.tabs.addTab(self._components_tab(), "Components")
        self.tabs.addTab(self._packages_tab(), "Packages")
        self.tabs.addTab(self._instances_tab(), "Provider instances")
        self.tabs.addTab(self._bindings_tab(), "Bindings")
        self.tabs.addTab(self._observation_tab(), "Observation")
        self.tabs.addTab(self._entitlement_tab(), "Entitlement")
        self.refresh()

    @staticmethod
    def _table(headers: tuple[str, ...]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    def _components_tab(self) -> QWidget:
        widget = QWidget(); layout = QVBoxLayout(widget); layout.addWidget(self.components_table)
        refresh = QPushButton("Refresh"); refresh.clicked.connect(self.refresh); layout.addWidget(refresh)
        return widget

    def _packages_tab(self) -> QWidget:
        widget = QWidget(); layout = QVBoxLayout(widget)
        browse_label = QLabel("<b>Browse catalog</b>"); layout.addWidget(browse_label)
        query_row = QHBoxLayout()
        query_row.addWidget(QLabel("Product")); query_row.addWidget(self.catalog_product)
        query_row.addWidget(QLabel("Technology")); query_row.addWidget(self.catalog_technology)
        query_row.addWidget(QLabel("Search")); query_row.addWidget(self.catalog_search)
        search = QPushButton("Search"); search.clicked.connect(self._search_catalog); query_row.addWidget(search)
        layout.addLayout(query_row)
        layout.addWidget(self.catalog_table)
        catalog_buttons = QHBoxLayout()
        download = QPushButton("Download"); download.clicked.connect(self._download_catalog_package)
        install = QPushButton("Install"); install.clicked.connect(self._install_catalog_package)
        solve = QPushButton("Solve compatible target"); solve.clicked.connect(self._solve_catalog_target)
        catalog_buttons.addWidget(download); catalog_buttons.addWidget(install); catalog_buttons.addWidget(solve); catalog_buttons.addStretch(1)
        layout.addLayout(catalog_buttons)
        solver_row = QHBoxLayout()
        solver_row.addWidget(QLabel("Solver solution")); solver_row.addWidget(self.solver_solutions)
        apply_solution = QPushButton("Apply solver solution"); apply_solution.clicked.connect(self._apply_solver_solution)
        solver_row.addWidget(apply_solution); solver_row.addStretch(1)
        layout.addLayout(solver_row)

        stored_label = QLabel("<b>Stored packages</b>"); layout.addWidget(stored_label)
        note = QLabel(
            "Downloaded/installed artifacts are separate from activation. An upgrade is validated and committed as one "
            "target-state transaction; select every installed component version that must change together."
        )
        note.setWordWrap(True); layout.addWidget(note)
        layout.addWidget(self.packages_table)
        scope_row = QHBoxLayout(); scope_row.addWidget(QLabel("Application/workspace scope")); scope_row.addWidget(self.package_scope)
        layout.addLayout(scope_row)
        buttons = QHBoxLayout()
        restore = QPushButton("Restore obsolete"); restore.clicked.connect(self._restore_obsolete_package)
        validate = QPushButton("Validate selected replacement"); validate.clicked.connect(self._validate_package_upgrade)
        apply = QPushButton("Apply selected replacement"); apply.clicked.connect(self._apply_package_upgrade)
        refresh = QPushButton("Refresh"); refresh.clicked.connect(self.refresh)
        buttons.addWidget(restore); buttons.addWidget(validate); buttons.addWidget(apply); buttons.addWidget(refresh); buttons.addStretch(1)
        layout.addLayout(buttons); layout.addWidget(self.package_result)
        return widget

    def _instances_tab(self) -> QWidget:
        widget = QWidget(); layout = QVBoxLayout(widget); layout.addWidget(self.instances_table)
        row = QHBoxLayout()
        create = QPushButton("Create"); create.clicked.connect(self._create_instance)
        configure = QPushButton("Configure"); configure.clicked.connect(self._configure_instance)
        rename = QPushButton("Rename"); rename.clicked.connect(self._rename_instance)
        remove = QPushButton("Remove"); remove.clicked.connect(self._remove_instance)
        row.addWidget(create); row.addWidget(configure); row.addWidget(rename); row.addWidget(remove); row.addStretch(1)
        layout.addLayout(row); return widget

    def _bindings_tab(self) -> QWidget:
        widget = QWidget(); layout = QVBoxLayout(widget); layout.addWidget(self.bindings_table)
        edit = QPushButton("Edit selected requirement"); edit.clicked.connect(self._edit_binding)
        layout.addWidget(edit); return widget

    def _observation_tab(self) -> QWidget:
        widget = QWidget(); layout = QVBoxLayout(widget); layout.addWidget(self.observation_table)
        create = QPushButton("Configure observer"); create.clicked.connect(self._create_observation)
        edit = QPushButton("Edit"); edit.clicked.connect(self._edit_observation)
        delete = QPushButton("Delete"); delete.clicked.connect(self._delete_observation)
        row = QHBoxLayout(); row.addWidget(create); row.addWidget(edit); row.addWidget(delete); row.addStretch(1); layout.addLayout(row)
        return widget

    def _entitlement_tab(self) -> QWidget:
        widget = QWidget(); layout = QVBoxLayout(widget); layout.addWidget(self.entitlement_table)
        refresh = QPushButton("Refresh entitlement status"); refresh.clicked.connect(self.refresh); layout.addWidget(refresh)
        return widget

    def refresh(self) -> None:
        components = self.controller.components()
        self.components_table.setRowCount(len(components))
        for row, item in enumerate(components):
            self._set_row(self.components_table, row, (
                item.id, str(item.version), ", ".join(item.provider_definition_ids),
                item.readiness_state or "-", "; ".join(item.readiness_reasons),
            ))

        if self.catalog_product.text().strip() and self.catalog_technology.text().strip():
            try:
                self._populate_catalog(self.controller.catalog_packages(
                    self.catalog_product.text().strip(), self.catalog_technology.text().strip(),
                    self.catalog_search.text().strip() or None,
                ))
            except Exception as exc:
                self.catalog_table.setRowCount(0)
                self.package_result.setPlainText(f"Catalog refresh failed: {type(exc).__name__}: {exc}")

        packages = self.controller.package_artifacts()
        self.packages_table.setRowCount(len(packages))
        for row, item in enumerate(packages):
            self._set_row(self.packages_table, row, (
                item.component_id, str(item.component_version), item.state,
                ", ".join(item.selected_application_scope_ids), item.sha256, item.source_id or "",
            ), user_data=item.identity)

        instances = self.controller.provider_instances()
        self.instances_table.setRowCount(len(instances))
        for row, item in enumerate(instances):
            self._set_row(self.instances_table, row, (
                item.name, item.component_id, item.provider_definition_id, item.capabilities_text, item.access_mode, item.state,
                item.readiness_state or "-", "; ".join(item.readiness_reasons), item.id,
            ), user_data=item.id)

        requirements = self.controller.requirements()
        self.bindings_table.setRowCount(len(requirements))
        for row, item in enumerate(requirements):
            self._set_row(self.bindings_table, row, (
                item.consumer_instance_name + " [" + item.consumer_instance_id + "]", item.requirement_id,
                item.capability_id, item.cardinality, ", ".join(item.selected_provider_instance_ids),
            ), user_data=(item.consumer_instance_id, item.requirement_id))

        observations = self.controller.observation_bindings()
        self.observation_table.setRowCount(len(observations))
        for row, item in enumerate(observations):
            summary = "; ".join(
                f"{selector.capability} [{','.join(selector.phases)}]" for selector in item.selectors
            )
            self._set_row(self.observation_table, row, (item.observer_instance_id, summary), user_data=item.observer_instance_id)

        entitlement_rows = []
        for component in components:
            status = self.controller.entitlement_status(component.id)
            entitlement_rows.extend(status.permissions)
        self.entitlement_table.setRowCount(len(entitlement_rows))
        for row, item in enumerate(entitlement_rows):
            self._set_row(self.entitlement_table, row, (
                item.component_id, f"{item.capability_id}/{item.capability_version}", item.permission_id,
                item.licensing_scope or ("implicit" if item.implicit else ""), item.issuer_id or "", item.effective_until or "",
            ))

    @staticmethod
    def _set_row(table: QTableWidget, row: int, values: tuple[str, ...], user_data: object | None = None) -> None:
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            if column == 0 and user_data is not None:
                item.setData(Qt.ItemDataRole.UserRole, user_data)
            table.setItem(row, column, item)

    @staticmethod
    def _selected_data(table: QTableWidget) -> object | None:
        row = table.currentRow()
        if row < 0 or table.item(row, 0) is None:
            return None
        return table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def _create_instance(self) -> None:
        choices = []
        for component in self.controller.components():
            for provider_id in component.provider_definition_ids:
                choices.append(AIcUiChoice(f"{component.id}\n{provider_id}", f"{component.id} / {provider_id}"))
        form = AIcUiForm("create-instance", "Create provider instance", (
            AIcUiFieldGroup("main", "", (
                AIcUiField("provider", "Provider definition", AInUiFieldType.ENUM, choices[0].value if choices else None, True, choices=tuple(choices)),
                AIcUiField("name", "Name", AInUiFieldType.STRING, "default", True),
            )),
        ))
        if not choices:
            QMessageBox.information(self, "Provider instances", "No capability provider definitions are installed."); return
        dialog = AIcQtFormDialog(form, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            values = dialog.values(); component_id, provider_id = str(values["provider"]).split("\n", 1)
            self._guard(lambda: self.controller.create_provider_instance(component_id, provider_id, str(values["name"])))
            self.refresh()

    def _configure_instance(self) -> None:
        instance_id = self._selected_data(self.instances_table)
        if not instance_id: return
        dialog = AIcQtFormDialog(self.controller.provider_configuration_form(str(instance_id)), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            option = dialog.selected_configuration_provider_option()
            if option is None:
                self._guard(lambda: self.controller.update_provider_configuration(str(instance_id), dialog.values()))
            else:
                self._guard(lambda: self.controller.update_provider_scoped_configuration(
                    str(instance_id), option.configuration_scope.type, option.configuration_scope.id,
                    option.configuration_provider_id, dialog.values(), option.record_revision,
                ))
            self.refresh()

    def _rename_instance(self) -> None:
        instance_id = self._selected_data(self.instances_table)
        if not instance_id: return
        current = next(item for item in self.controller.provider_instances() if item.id == instance_id)
        form = AIcUiForm("rename", "Rename provider instance", (
            AIcUiFieldGroup("main", "", (AIcUiField("name", "Name", AInUiFieldType.STRING, current.name, True),)),
        ))
        dialog = AIcQtFormDialog(form, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._guard(lambda: self.controller.rename_provider_instance(str(instance_id), str(dialog.values()["name"])))
            self.refresh()

    def _remove_instance(self) -> None:
        instance_id = self._selected_data(self.instances_table)
        if not instance_id: return
        if QMessageBox.question(self, "Remove provider instance", f"Remove provider instance {instance_id}?") == QMessageBox.StandardButton.Yes:
            self._guard(lambda: self.controller.remove_provider_instance(str(instance_id)))
            self.refresh()

    def _edit_binding(self) -> None:
        data = self._selected_data(self.bindings_table)
        if not data:
            QMessageBox.information(self, "Bindings", "Select a requirement.")
            return
        consumer_id, requirement_id = data
        editor = self.controller.requirement_editor(str(consumer_id), str(requirement_id))
        dialog = AIcQtRequirementDialog(editor, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._guard(lambda: self.controller.set_requirement_providers(str(consumer_id), str(requirement_id), dialog.selected_provider_instance_ids()))
            self.refresh()

    def _populate_catalog(self, entries) -> None:
        self.catalog_table.setRowCount(len(entries))
        for row, item in enumerate(entries):
            state = "INSTALLED" if item.installed else ("DOWNLOADED" if item.downloaded else "AVAILABLE")
            self._set_row(self.catalog_table, row, (
                item.name or item.component_id, item.component_id, str(item.component_version), item.artifact_id,
                item.publisher or "", "; ".join(item.provides), "; ".join(item.requires),
                "; ".join(item.entitlement_summary) or "included/no declaration", state, item.source_id,
                item.entitlement_info_url or "",
            ), user_data=item.identity)

    def _search_catalog(self) -> None:
        product = self.catalog_product.text().strip()
        technology = self.catalog_technology.text().strip()
        if not product or not technology:
            QMessageBox.information(self, "AAC catalog", "Product and technology are mandatory catalog filters.")
            return
        try:
            entries = self.controller.catalog_packages(product, technology, self.catalog_search.text().strip() or None)
            self._populate_catalog(entries)
            self.package_result.setPlainText(f"Catalog query returned {len(entries)} artifact(s).")
        except Exception as exc:
            QMessageBox.critical(self, "AAC catalog", f"{type(exc).__name__}: {exc}")

    def _selected_catalog_identity(self):
        data = self._selected_data(self.catalog_table)
        if isinstance(data, tuple) and len(data) == 6:
            return (str(data[0]), str(data[1]), str(data[2]), str(data[3]), int(data[4]), str(data[5]))
        return None

    @staticmethod
    def _format_solver_solution(solution, label: str) -> str:
        lines = [label]
        requested = tuple(item for item in solution.selections if item.requested and item.direction.value != "UNCHANGED")
        automatic = tuple(item for item in solution.selections if not item.requested and item.direction.value != "UNCHANGED")
        unchanged = tuple(item for item in solution.selections if item.direction.value == "UNCHANGED")

        if requested:
            lines.append("Requested changes:")
            for item in requested:
                current = "not active" if item.current_version is None else str(item.current_version)
                lines.append(f"  {item.component_id}: {current} -> {item.target_version} [{item.direction.value}]")
        if automatic:
            lines.append("Automatically required changes:")
            for item in automatic:
                current = "not active" if item.current_version is None else str(item.current_version)
                suffix = "  DOWNGRADE" if item.direction.value == "DOWNGRADE" else ""
                lines.append(f"  {item.component_id}: {current} -> {item.target_version} [{item.direction.value}]{suffix}")
        if unchanged:
            lines.append("Unchanged:")
            lines.extend(f"  {item.component_id}/{item.target_version}" for item in unchanged)

        retrieval = tuple(item for item in solution.selections if item.download_required or item.install_required)
        if retrieval:
            lines.append("Package preparation:")
            for item in retrieval:
                actions = []
                if item.download_required:
                    actions.append("download")
                if item.install_required:
                    actions.append("install")
                lines.append(f"  {item.component_id}/{item.target_version}: {' + '.join(actions)}")

        if solution.explanations:
            lines.append("Explanations:")
            for item in solution.explanations:
                context = []
                if item.component_id:
                    context.append(item.component_id)
                if item.caused_by_component_id:
                    context.append(f"caused by {item.caused_by_component_id}")
                if item.capability_id:
                    context.append(f"capability {item.capability_id}")
                suffix = f" ({'; '.join(context)})" if context else ""
                lines.append(f"  [{item.code}] {item.message}{suffix}")

        missing_entitlements = tuple(item for item in solution.entitlement_diagnostics if not item.granted)
        if missing_entitlements:
            lines.append("Entitlement diagnostics (non-blocking):")
            for item in missing_entitlements:
                scopes = ", ".join(item.possible_licensing_scopes) or "external entitlement"
                detail = (
                    f"  {item.component_id}: {item.capability_id} v{item.capability_version} / "
                    f"{item.permission_id}; possible scopes: {scopes}"
                )
                if item.entitlement_info_url:
                    detail += f"; info: {item.entitlement_info_url}"
                lines.append(detail)

        if solution.readiness_diagnostics:
            lines.append("Predicted readiness diagnostics (non-blocking):")
            for item in solution.readiness_diagnostics:
                lines.append(f"  {item.component_id}: {item.state.value} — {item.message}")

        if solution.contains_downgrade:
            lines.append("WARNING: this alternative contains a downgrade and requires explicit confirmation.")
        return "\n".join(lines)

    @classmethod
    def _format_solver_result(cls, result) -> str:
        lines = []
        if result.primary is not None:
            lines.append(cls._format_solver_solution(result.primary, "Recommended solution"))
        else:
            lines.append("No recommended upgrade-only solution is available.")
        for index, solution in enumerate(result.alternatives, start=1):
            lines.append("")
            lines.append(cls._format_solver_solution(solution, f"Alternative {index}"))
        if result.diagnostics:
            lines.append("")
            lines.append("Solver diagnostics:")
            for item in result.diagnostics:
                context = []
                if item.component_id:
                    context.append(item.component_id)
                if item.capability_id:
                    context.append(f"capability {item.capability_id}")
                suffix = f" ({'; '.join(context)})" if context else ""
                lines.append(f"  [{item.code}] {item.message}{suffix}")
        return "\n".join(lines)

    def _solve_catalog_target(self) -> None:
        identity = self._selected_catalog_identity()
        if identity is None:
            QMessageBox.information(self, "Target-state solver", "Select one catalog artifact to request as the target release.")
            return
        scope = self.package_scope.text().strip()
        if not scope:
            QMessageBox.information(self, "Target-state solver", "Enter an application/workspace scope.")
            return
        try:
            result = self.controller.solve_catalog_target(scope, identity)
            self._last_solver_result = result
            self.solver_solutions.clear()
            if result.primary is not None:
                self.solver_solutions.addItem("Recommended", result.primary)
            for index, solution in enumerate(result.alternatives, start=1):
                suffix = " — DOWNGRADE" if solution.contains_downgrade else ""
                self.solver_solutions.addItem(f"Alternative {index}{suffix}", solution)
            self.solver_solutions.setEnabled(self.solver_solutions.count() > 0)
            self.package_result.setPlainText(self._format_solver_result(result))
        except Exception as exc:
            QMessageBox.critical(self, "Target-state solver", f"{type(exc).__name__}: {exc}")

    def _apply_solver_solution(self) -> None:
        solution = self.solver_solutions.currentData()
        if solution is None:
            QMessageBox.information(self, "Target-state solver", "Solve a target state and select one solution first.")
            return
        scope = self.package_scope.text().strip()
        if not scope:
            QMessageBox.information(self, "Target-state solver", "Enter an application/workspace scope.")
            return
        if solution.contains_downgrade:
            answer = QMessageBox.question(
                self,
                "Confirm downgrade alternative",
                "This solver alternative contains one or more downgrades. The solver offers downgrades only when "
                "persistent schema identities and write versions are unchanged. Apply this alternative?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            applied = self.controller.apply_target_state_solution(scope, solution)
            detail = self._format_solver_solution(applied, "Applied solver solution")
            self.refresh()
            self.package_result.setPlainText(detail + "\n\nReplacement transaction committed.")
        except Exception as exc:
            QMessageBox.critical(self, "Target-state solver", f"{type(exc).__name__}: {exc}")

    def _download_catalog_package(self) -> None:
        identity = self._selected_catalog_identity()
        if identity is None:
            QMessageBox.information(self, "AAC catalog", "Select one catalog artifact.")
            return
        try:
            package = self.controller.download_catalog_package(identity)
            self.package_result.setPlainText(
                f"Downloaded {package.component_id}/{package.component_version} sha256:{package.sha256}. "
                "Entitlement is not required merely to store/install an artifact."
            )
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "AAC catalog download", f"{type(exc).__name__}: {exc}")

    def _install_catalog_package(self) -> None:
        identity = self._selected_catalog_identity()
        if identity is None:
            QMessageBox.information(self, "AAC catalog", "Select one catalog artifact.")
            return
        try:
            package = self.controller.install_catalog_package(identity)
            self.package_result.setPlainText(
                f"Installed {package.component_id}/{package.component_version} sha256:{package.sha256}. "
                "Installation does not grant entitlement and does not by itself activate the component."
            )
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "AAC catalog install", f"{type(exc).__name__}: {exc}")

    def _restore_obsolete_package(self) -> None:
        identity = self._selected_data(self.packages_table)
        if not (isinstance(identity, tuple) and len(identity) == 3):
            QMessageBox.information(self, "Packages", "Select one obsolete stored package.")
            return
        try:
            package = self.controller.restore_obsolete_package((str(identity[0]), int(identity[1]), str(identity[2])))
            self.package_result.setPlainText(
                f"Restored {package.component_id}/{package.component_version} to installed candidates. "
                "Activation/downgrade still requires normal target-state validation."
            )
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Restore obsolete package", f"{type(exc).__name__}: {exc}")

    def _selected_package_identities(self) -> tuple[tuple[str, int, str], ...]:
        rows = sorted({index.row() for index in self.packages_table.selectionModel().selectedRows()})
        result = []
        for row in rows:
            item = self.packages_table.item(row, 0)
            identity = None if item is None else item.data(Qt.ItemDataRole.UserRole)
            if isinstance(identity, tuple) and len(identity) == 3:
                result.append((str(identity[0]), int(identity[1]), str(identity[2])))
        return tuple(result)

    @staticmethod
    def _format_upgrade_plan(plan) -> str:
        lines = [
            "Target state: " + ("COMPATIBLE" if plan.compatible else "INCOMPATIBLE"),
            f"Scope: {plan.application_scope_id}",
        ]
        if plan.replacements:
            lines.append("Replacements:")
            lines.extend(
                f"  {item.component_id}: {item.previous_version} -> {item.target_version}"
                for item in plan.replacements
            )
        if plan.diagnostics:
            lines.append("Diagnostics:")
            for item in plan.diagnostics:
                level = "BLOCKER" if item.blocking else "WARNING"
                detail = f"  {level} — {item.component_id}: {item.message}"
                if item.capability_id:
                    detail += f" [capability {item.capability_id}]"
                if item.code:
                    detail += f" [{item.code}]"
                lines.append(detail)
        return "\n".join(lines)

    def _validate_package_upgrade(self) -> None:
        identities = self._selected_package_identities()
        if not identities:
            QMessageBox.information(self, "Package upgrade", "Select one or more installed target package artifacts.")
            return
        scope = self.package_scope.text().strip()
        if not scope:
            QMessageBox.information(self, "Package upgrade", "Enter an application/workspace scope.")
            return
        try:
            plan = self.controller.plan_package_upgrades(scope, identities)
            self.package_result.setPlainText(self._format_upgrade_plan(plan))
        except Exception as exc:
            QMessageBox.critical(self, "Package upgrade", f"{type(exc).__name__}: {exc}")

    def _apply_package_upgrade(self) -> None:
        identities = self._selected_package_identities()
        if not identities:
            QMessageBox.information(self, "Package upgrade", "Select one or more installed target package artifacts.")
            return
        scope = self.package_scope.text().strip()
        if not scope:
            QMessageBox.information(self, "Package upgrade", "Enter an application/workspace scope.")
            return
        try:
            plan = self.controller.apply_package_upgrades(scope, identities)
            self.package_result.setPlainText(self._format_upgrade_plan(plan))
            if not plan.compatible:
                QMessageBox.warning(self, "Package upgrade", "The selected target state is incompatible; nothing was changed.")
                return
            self.refresh()
            self.package_result.setPlainText(self._format_upgrade_plan(plan) + "\n\nUpgrade committed.")
        except Exception as exc:
            QMessageBox.critical(self, "Package upgrade", f"{type(exc).__name__}: {exc}")

    def _create_observation(self) -> None:
        observers = [item for item in self.controller.provider_instances() if item.supports_capability("_AAC.capability.observation")]
        configured = {item.observer_instance_id for item in self.controller.observation_bindings()}
        available = [item for item in observers if item.id not in configured]
        if not available:
            QMessageBox.information(self, "Observation", "No unconfigured observation provider instance is available."); return
        choices = tuple(AIcUiChoice(item.id, f"{item.name} — {item.component_id} [{item.id}]") for item in available)
        form = AIcUiForm("observer", "Configure observer", (AIcUiFieldGroup("main", "", (
            AIcUiField("observer", "Observer instance", AInUiFieldType.ENUM, choices[0].value, True, choices=choices),
        )),))
        pick = AIcQtFormDialog(form, self)
        if pick.exec() != QDialog.DialogCode.Accepted: return
        binding = AIcUiObservationBinding(str(pick.values()["observer"]), (AIcUiObservationSelector(),))
        dialog = AIcQtObservationDialog(binding, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._guard(lambda: self.controller.put_observation_binding(dialog.value())); self.refresh()

    def _edit_observation(self) -> None:
        observer_id = self._selected_data(self.observation_table)
        if not observer_id: return
        binding = next(value for value in self.controller.observation_bindings() if value.observer_instance_id == observer_id)
        dialog = AIcQtObservationDialog(binding, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._guard(lambda: self.controller.put_observation_binding(dialog.value()))
            self.refresh()

    def _delete_observation(self) -> None:
        observer_id = self._selected_data(self.observation_table)
        if not observer_id: return
        self._guard(lambda: self.controller.delete_observation_binding(str(observer_id)))
        self.refresh()

    def _guard(self, operation) -> None:
        try:
            operation()
        except Exception as exc:
            QMessageBox.critical(self, "AAC configuration error", f"{type(exc).__name__}: {exc}")
