import pytest

from algites.lib.aac.coreintf.authentication import (
    AIcAuthenticationParameter,
    AIcAuthenticationProfile,
    AIcSecretReference,
    AIcSecurityBootstrap,
    AIcSecretProviderRegistration,
)


def test_authentication_profile_accepts_extensible_mechanism_and_secret_reference():
    ref = AIcSecretReference("env", "TOKEN")
    profile = AIcAuthenticationProfile("remote", "CUSTOM_MECHANISM", {"token": AIcAuthenticationParameter(secret_reference=ref)})
    assert profile.mechanism == "CUSTOM_MECHANISM"
    assert profile.parameters["token"].secret_reference == ref


def test_authentication_parameter_cannot_mix_plain_and_secret_value():
    with pytest.raises(ValueError):
        AIcAuthenticationParameter("plain", AIcSecretReference("env", "TOKEN"))


def test_security_bootstrap_requires_unique_ids():
    with pytest.raises(ValueError):
        AIcSecurityBootstrap(1, (
            AIcSecretProviderRegistration("env", "ENVIRONMENT", bootstrap_safe=True),
            AIcSecretProviderRegistration("env", "ENVIRONMENT", bootstrap_safe=True),
        ))
