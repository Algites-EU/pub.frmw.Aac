"""Verify the deterministic module name of the public matcher interface."""

from eu.algites.frmw.aac.core.bindings.aii_capability_profile_matcher import AIiCapabilityProfileMatcher
from eu.algites.frmw.aac.core.bindings.api import AIiCapabilityProfileMatcher as AIiPublicMatcher


def test_matcher_interface_has_its_own_deterministic_module() -> None:
    assert AIiCapabilityProfileMatcher.__module__ == (
        "eu.algites.frmw.aac.core.bindings.aii_capability_profile_matcher"
    )
    assert AIiPublicMatcher is AIiCapabilityProfileMatcher
