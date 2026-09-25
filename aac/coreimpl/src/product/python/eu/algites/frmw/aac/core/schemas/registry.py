from __future__ import annotations
import copy
import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Mapping
from jsonschema import Draft202012Validator, validators
from eu.algites.frmw.aac.core.implementation.errors import AIxSchemaValidationError

from .aic_registered_schema import AIcRegisteredSchema
from .aic_schema_registry import AIcSchemaRegistry

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

def _format_validation_error(error) -> str:
    path = "$"
    for element in error.absolute_path:
        path += f"[{element}]" if isinstance(element, int) else f".{element}"
    return f"{path}: {error.message}"
