from __future__ import annotations

from eu.algites.frmw.aac.core.authentication.aiig_security_bootstrap_1 import AIigSecurityBootstrap_1
from eu.algites.frmw.aac.core.authentication.aiig_security_bootstrap_security_bootstrap_1 import AIigSecurityBootstrapSecurityBootstrap_1
from eu.algites.frmw.aac.core.authentication.aiig_security_bootstrap_security_bootstrap_authentication_profiles_items_1 import AIigSecurityBootstrapSecurityBootstrapAuthenticationProfilesItems_1
from eu.algites.frmw.aac.core.authentication.aiig_security_bootstrap_security_bootstrap_authentication_profiles_items_parameters_additional_properties_one_of_1_1 import AIigSecurityBootstrapSecurityBootstrapAuthenticationProfilesItemsParametersAdditionalPropertiesOneOf1_1
from eu.algites.frmw.aac.core.authentication.aiig_security_bootstrap_security_bootstrap_authentication_profiles_items_parameters_additional_properties_one_of_1_secret_reference_1 import AIigSecurityBootstrapSecurityBootstrapAuthenticationProfilesItemsParametersAdditionalPropertiesOneOf1SecretReference_1
from eu.algites.frmw.aac.core.authentication.aiig_security_bootstrap_security_bootstrap_secret_providers_items_1 import AIigSecurityBootstrapSecurityBootstrapSecretProvidersItems_1
from eu.algites.frmw.aac.core.schemas.resources import read_core_schema
import json
from importlib import resources
from pathlib import Path
from typing import Any, Mapping
import yaml
from jsonschema import Draft202012Validator
from eu.algites.frmw.aac.core.authentication.api import (
    AIcAuthenticationParameter, AIcAuthenticationProfile, AIcSecretProviderRegistration, AIcSecretReference, AIcSecurityBootstrap,
)
from eu.algites.frmw.aac.core.configuration.api import (
    AInWorkspaceConfigurationProfilePolicy,
    AIcConfigurationBootstrap,
    AIcConfigurationProfile,
    AIcConfigurationProfileSourceRegistration,
    AIcConfigurationProviderBinding,
    AIcConfigurationProviderRegistration,
    AIcConfigurationScopeDefinition,
    AIcConfigurationScopeResolverRegistration,
)
from eu.algites.frmw.aac.core.errors import AIxDescriptorError
from eu.algites.frmw.aac.core.presentation.api import normalize_display_text

class AIcSecurityBootstrapLoader:
    """Load the product-supplied fixed-schema security bootstrap.

    The source itself is an external trust boundary. This loader validates structure; a
    product/installation decides which source path/bytes are trusted before calling it.
    """

    @staticmethod
    def load_file(path: str | Path) -> AIcSecurityBootstrap:
        path = Path(path)
        return AIcSecurityBootstrapLoader.load_text(path.read_text(encoding="utf-8"), source=str(path))

    @staticmethod
    def load_text(text: str, source: str = "<memory>") -> AIcSecurityBootstrap:
        try:
            raw = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise AIxDescriptorError(f"invalid YAML in security bootstrap {source}: {exc}") from exc
        if not isinstance(raw, Mapping):
            raise AIxDescriptorError(f"{source}: security bootstrap root must be a mapping")
        schema_text = read_core_schema("security-bootstrap_1.jsondef.schema.json")
        schema = json.loads(schema_text)
        errors = sorted(Draft202012Validator(schema).iter_errors(raw), key=lambda error: list(error.absolute_path))
        if errors:
            rendered = []
            for error in errors:
                path = "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in error.absolute_path)
                rendered.append(f"{path}: {error.message}")
            raise AIxDescriptorError(f"{source}: security bootstrap schema validation failed: " + "; ".join(rendered))
        try:
            body = raw[AIigSecurityBootstrap_1.SCHEMA_FIELD_NAME__SECURITY_BOOTSTRAP]
            secret_providers = tuple(AIcSecretProviderRegistration(
                id=str(item[AIigSecurityBootstrapSecurityBootstrapSecretProvidersItems_1.SCHEMA_FIELD_NAME__ID]), type=str(item[AIigSecurityBootstrapSecurityBootstrapSecretProvidersItems_1.SCHEMA_FIELD_NAME__TYPE]),
                name=normalize_display_text(item.get(AIigSecurityBootstrapSecurityBootstrapSecretProvidersItems_1.SCHEMA_FIELD_NAME__NAME)), description=normalize_display_text(item.get(AIigSecurityBootstrapSecurityBootstrapSecretProvidersItems_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
                settings=dict(item.get(AIigSecurityBootstrapSecurityBootstrapSecretProvidersItems_1.SCHEMA_FIELD_NAME__SETTINGS, {})), bootstrap_safe=bool(item.get(AIigSecurityBootstrapSecurityBootstrapSecretProvidersItems_1.SCHEMA_FIELD_NAME__BOOTSTRAP_SAFE, False))
            ) for item in body.get(AIigSecurityBootstrapSecurityBootstrap_1.SCHEMA_FIELD_NAME__SECRET_PROVIDERS, ()))
            profiles = []
            for item in body.get(AIigSecurityBootstrapSecurityBootstrap_1.SCHEMA_FIELD_NAME__AUTHENTICATION_PROFILES, ()):
                parameters = {}
                for key, value in dict(item.get(AIigSecurityBootstrapSecurityBootstrapAuthenticationProfilesItems_1.SCHEMA_FIELD_NAME__PARAMETERS, {})).items():
                    if isinstance(value, Mapping) and "SecretReference" in value:
                        ref = value[AIigSecurityBootstrapSecurityBootstrapAuthenticationProfilesItemsParametersAdditionalPropertiesOneOf1_1.SCHEMA_FIELD_NAME__SECRET_REFERENCE]
                        parameters[str(key)] = AIcAuthenticationParameter(secret_reference=AIcSecretReference(
                            str(ref[AIigSecurityBootstrapSecurityBootstrapAuthenticationProfilesItemsParametersAdditionalPropertiesOneOf1SecretReference_1.SCHEMA_FIELD_NAME__SECRET_PROVIDER_ID]), str(ref[AIigSecurityBootstrapSecurityBootstrapAuthenticationProfilesItemsParametersAdditionalPropertiesOneOf1SecretReference_1.SCHEMA_FIELD_NAME__KEY]),
                            str(ref[AIigSecurityBootstrapSecurityBootstrapAuthenticationProfilesItemsParametersAdditionalPropertiesOneOf1SecretReference_1.SCHEMA_FIELD_NAME__VERSION]) if ref.get(AIigSecurityBootstrapSecurityBootstrapAuthenticationProfilesItemsParametersAdditionalPropertiesOneOf1SecretReference_1.SCHEMA_FIELD_NAME__VERSION) is not None else None,
                            dict(ref.get(AIigSecurityBootstrapSecurityBootstrapAuthenticationProfilesItemsParametersAdditionalPropertiesOneOf1SecretReference_1.SCHEMA_FIELD_NAME__METADATA, {})),
                        ))
                    else:
                        parameters[str(key)] = AIcAuthenticationParameter(value=value)
                profiles.append(AIcAuthenticationProfile(
                    id=str(item[AIigSecurityBootstrapSecurityBootstrapAuthenticationProfilesItems_1.SCHEMA_FIELD_NAME__ID]), mechanism=str(item[AIigSecurityBootstrapSecurityBootstrapAuthenticationProfilesItems_1.SCHEMA_FIELD_NAME__MECHANISM]),
                    name=normalize_display_text(item.get(AIigSecurityBootstrapSecurityBootstrapAuthenticationProfilesItems_1.SCHEMA_FIELD_NAME__NAME)), description=normalize_display_text(item.get(AIigSecurityBootstrapSecurityBootstrapAuthenticationProfilesItems_1.SCHEMA_FIELD_NAME__DESCRIPTION)),
                    parameters=parameters, metadata=dict(item.get(AIigSecurityBootstrapSecurityBootstrapAuthenticationProfilesItems_1.SCHEMA_FIELD_NAME__METADATA, {}))
                ))
            return AIcSecurityBootstrap(
                int(body[AIigSecurityBootstrapSecurityBootstrap_1.SCHEMA_FIELD_NAME__SCHEMA_VERSION]), secret_providers, tuple(profiles), dict(body.get(AIigSecurityBootstrapSecurityBootstrap_1.SCHEMA_FIELD_NAME__METADATA, {}))
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AIxDescriptorError(f"{source}: invalid security bootstrap: {exc}") from exc
