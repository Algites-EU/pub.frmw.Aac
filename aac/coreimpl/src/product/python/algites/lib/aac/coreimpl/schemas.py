from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Mapping

from jsonschema import Draft202012Validator, validators

from .errors import AIxSchemaValidationError

AAC_SCHEMA_ID_KEY = "x-aac-schema-id"
AAC_SCHEMA_VERSION_KEY = "x-aac-schema-version"
AAC_DATA_ENTITY_REFERENCE_KEY = "x-aac-data-entity-reference"


def schema_identity(schema: Mapping[str, object]) -> tuple[str, int]:
    schema_id = schema.get(AAC_SCHEMA_ID_KEY)
    schema_version = schema.get(AAC_SCHEMA_VERSION_KEY)
    if not isinstance(schema_id, str) or not schema_id.strip():
        raise ValueError(f"JSON schema must declare non-empty {AAC_SCHEMA_ID_KEY!r}")
    if not isinstance(schema_version, int) or isinstance(schema_version, bool) or schema_version < 1:
        raise ValueError(f"JSON schema must declare integer {AAC_SCHEMA_VERSION_KEY!r} >= 1")
    return schema_id.strip(), schema_version


def _data_entity_reference_targets(schema: object, path: tuple[str, ...] = ()):
    if isinstance(schema, Mapping):
        annotation = schema.get(AAC_DATA_ENTITY_REFERENCE_KEY)
        if annotation is not None:
            if not isinstance(annotation, Mapping):
                raise ValueError(f"{AAC_DATA_ENTITY_REFERENCE_KEY!r} at {'.'.join(path) or '$'} must be an object")
            unknown = set(annotation) - {"schema_id"}
            if unknown:
                raise ValueError(
                    f"{AAC_DATA_ENTITY_REFERENCE_KEY!r} at {'.'.join(path) or '$'} contains unsupported keys {sorted(unknown)!r}"
                )
            target = annotation.get("schema_id")
            if not isinstance(target, str) or not target.strip():
                raise ValueError(
                    f"{AAC_DATA_ENTITY_REFERENCE_KEY!r} at {'.'.join(path) or '$'} requires non-empty schema_id"
                )
            yield path, target.strip()
        for key, value in schema.items():
            if key == AAC_DATA_ENTITY_REFERENCE_KEY:
                continue
            yield from _data_entity_reference_targets(value, path + (str(key),))
    elif isinstance(schema, list):
        for index, value in enumerate(schema):
            yield from _data_entity_reference_targets(value, path + (str(index),))


def _extend_with_default(validator_class):
    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema):
        if isinstance(instance, dict):
            for property_name, subschema in properties.items():
                if "default" in subschema and property_name not in instance:
                    instance[property_name] = copy.deepcopy(subschema["default"])
        yield from validate_properties(validator, properties, instance, schema)

    return validators.extend(validator_class, {"properties": set_defaults})


DefaultingDraft202012Validator = _extend_with_default(Draft202012Validator)


@dataclass(frozen=True, slots=True)
class AIcRegisteredSchema:
    id: str
    version: int
    resource_name: str
    schema: Mapping[str, object]
    source: str

    @property
    def key(self) -> str:
        return self.resource_name


class AIcSchemaRegistry:
    def __init__(self) -> None:
        self._by_resource: dict[str, AIcRegisteredSchema] = {}
        self._by_identity: dict[tuple[str, int], AIcRegisteredSchema] = {}

    def register(self, resource_name: str, schema: Mapping[str, object], *, source: str = "<memory>") -> AIcRegisteredSchema:
        schema_id, version = schema_identity(schema)
        resource_key = Path(resource_name).name
        registered = AIcRegisteredSchema(schema_id, version, resource_key, copy.deepcopy(dict(schema)), source)
        existing = self._by_identity.get((schema_id, version))
        if existing is not None and dict(existing.schema) != dict(registered.schema):
            raise ValueError(f"conflicting schema definition for {schema_id}/{version}")
        resource_existing = self._by_resource.get(resource_key)
        if resource_existing is not None and (resource_existing.id, resource_existing.version) != (schema_id, version):
            raise ValueError(
                f"schema resource {resource_key!r} is already registered as "
                f"{resource_existing.id}/{resource_existing.version}"
            )
        canonical = existing or registered
        self._by_identity[(schema_id, version)] = canonical
        self._by_resource[resource_key] = canonical
        return canonical

    def register_text(self, resource_name: str, text: str, *, source: str = "<memory>") -> AIcRegisteredSchema:
        raw = json.loads(text)
        if not isinstance(raw, Mapping):
            raise ValueError("JSON schema root must be an object")
        Draft202012Validator.check_schema(raw)
        tuple(_data_entity_reference_targets(raw))
        return self.register(resource_name, raw, source=source)

    def register_file(self, path: str | Path) -> AIcRegisteredSchema:
        path = Path(path)
        return self.register_text(path.name, path.read_text(encoding="utf-8"), source=str(path))

    def register_package_resource(self, package: str, resource_name: str) -> AIcRegisteredSchema:
        try:
            text = resources.files(package).joinpath(resource_name).read_text(encoding="utf-8")
        except (ModuleNotFoundError, FileNotFoundError) as exc:
            raise FileNotFoundError(f"cannot load schema {resource_name!r} from package {package!r}") from exc
        return self.register_text(Path(resource_name).name, text, source=f"{package}:{resource_name}")

    def get(self, resource_name: str) -> AIcRegisteredSchema:
        return self._by_resource[Path(resource_name).name]

    def get_identity(self, schema_id: str, version: int) -> AIcRegisteredSchema:
        return self._by_identity[(schema_id, version)]

    def contains_identity(self, schema_id: str, version: int) -> bool:
        return (schema_id, version) in self._by_identity

    def versions(self, schema_id: str) -> tuple[int, ...]:
        return tuple(sorted(version for (candidate_id, version) in self._by_identity if candidate_id == schema_id))

    def data_entity_references(self, schema_id: str, version: int):
        from algites.lib.aac.coreintf.dataentity import AIcDataEntityReferenceDefinition

        registered = self.get_identity(schema_id, version)
        return tuple(
            AIcDataEntityReferenceDefinition(schema_id, version, path, target_schema_id)
            for path, target_schema_id in _data_entity_reference_targets(registered.schema)
        )

    def normalize(self, resource_name: str, value: Mapping[str, object] | None, *, apply_defaults: bool = True) -> dict[str, object]:
        registered = self.get(resource_name)
        normalized: dict[str, object] = copy.deepcopy(dict(value or {}))
        validator_class = DefaultingDraft202012Validator if apply_defaults else Draft202012Validator
        validator = validator_class(registered.schema)
        errors = sorted(validator.iter_errors(normalized), key=lambda error: list(error.absolute_path))
        if errors:
            diagnostics = tuple(_format_validation_error(error) for error in errors)
            raise AIxSchemaValidationError(registered.resource_name, diagnostics)
        return normalized


    def normalize_value(self, resource_name: str, value: object, *, apply_defaults: bool = True) -> object:
        registered = self.get(resource_name)
        normalized = copy.deepcopy(value)
        validator_class = DefaultingDraft202012Validator if apply_defaults else Draft202012Validator
        validator = validator_class(registered.schema)
        errors = sorted(validator.iter_errors(normalized), key=lambda error: list(error.absolute_path))
        if errors:
            diagnostics = tuple(_format_validation_error(error) for error in errors)
            raise AIxSchemaValidationError(registered.resource_name, diagnostics)
        return normalized



    def validate_resolved_configuration(self, resource_name: str, value: Mapping[str, object] | None) -> tuple[str, ...]:
        """Validate a resolved runtime configuration without treating top-level ``required`` as availability.

        AAC multi-provider resolution may legitimately yield missing/UNDEFINED top-level values.
        ``required`` remains meaningful inside concrete nested structures that are present, but
        runtime availability/readiness is not inferred from top-level JSON Schema requiredness.
        """
        registered = self.get(resource_name)
        schema = copy.deepcopy(dict(registered.schema))
        schema.pop("required", None)
        normalized: dict[str, object] = copy.deepcopy(dict(value or {}))
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(normalized), key=lambda error: list(error.absolute_path))
        return tuple(_format_validation_error(error) for error in errors)

    def configuration_property_metadata(self, resource_name: str) -> tuple[tuple[str, ...], dict[str, tuple[str, ...]], dict[str, object]]:
        registered = self.get(resource_name)
        properties = registered.schema.get("properties", {}) if isinstance(registered.schema, Mapping) else {}
        property_ids: list[str] = []
        accepted: dict[str, tuple[str, ...]] = {}
        defaults: dict[str, object] = {}
        if isinstance(properties, Mapping):
            for property_id, raw in properties.items():
                if not isinstance(raw, Mapping):
                    continue
                key = str(property_id)
                property_ids.append(key)
                scopes = raw.get("x-aac-configuration-scopes", ())
                if isinstance(scopes, list):
                    accepted[key] = tuple(str(value) for value in scopes)
                if "default" in raw:
                    defaults[key] = copy.deepcopy(raw["default"])
        return tuple(property_ids), accepted, defaults


    def snapshot(self):
        return (copy.deepcopy(self._by_resource), copy.deepcopy(self._by_identity))

    def restore(self, snapshot) -> None:
        self._by_resource, self._by_identity = copy.deepcopy(snapshot[0]), copy.deepcopy(snapshot[1])

    def validate(self, resource_name: str, value: Mapping[str, object] | None) -> tuple[str, ...]:
        try:
            self.normalize(resource_name, value, apply_defaults=False)
            return ()
        except AIxSchemaValidationError as exc:
            return exc.diagnostics


def _format_validation_error(error) -> str:
    path = "$"
    for element in error.absolute_path:
        path += f"[{element}]" if isinstance(element, int) else f".{element}"
    return f"{path}: {error.message}"
