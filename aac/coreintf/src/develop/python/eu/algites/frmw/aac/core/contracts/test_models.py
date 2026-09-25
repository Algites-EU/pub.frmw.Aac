import pytest

from eu.algites.frmw.aac.core.capability.api import AIcCapabilityContract, AIcCapabilityOperation, AIcCapabilityRef


def test_contract_operation_ids_are_unique():
    op = AIcCapabilityOperation("run")
    with pytest.raises(ValueError):
        AIcCapabilityContract(AIcCapabilityRef("x", 1), "test.group", (op, op))


def test_capability_version_starts_at_one():
    with pytest.raises(ValueError):
        AIcCapabilityRef("x", 0)

from eu.algites.frmw.aac.core.capability.api import (
    AIcAuthorizationPermissionDescriptor, AIcOperationAuthorizationRequirement,
)
from eu.algites.frmw.aac.core.presentation.api import AIcDisplayText


def test_operation_authorization_references_declared_permission_vocabulary():
    contract = AIcCapabilityContract(
        AIcCapabilityRef("x.secured", 1),
        "_AAC.runtime",
        (AIcCapabilityOperation("edit", authorization=AIcOperationAuthorizationRequirement(all_of=("EDIT",))),),
        authorization_permissions=(AIcAuthorizationPermissionDescriptor("EDIT", AIcDisplayText(text="Edit")),),
    )
    assert contract.operation("edit").authorization.is_satisfied_by({"EDIT"})
    with pytest.raises(ValueError):
        AIcCapabilityContract(
            AIcCapabilityRef("x.bad", 1),
            "_AAC.runtime",
        (AIcCapabilityOperation("edit", authorization=AIcOperationAuthorizationRequirement(any_of=("UNKNOWN",))),),
        )


def test_display_text_accepts_resource_key_without_localization_engine():
    text = AIcDisplayText(resource_key="vendor.site.edit.name")
    assert text.fallback == "vendor.site.edit.name"


def test_operation_authorization_combines_all_of_and_any_of_without_expression_language():
    requirement = AIcOperationAuthorizationRequirement(all_of=("EDIT",), any_of=("STANDARD", "ADVANCED"))
    assert requirement.is_satisfied_by({"EDIT", "STANDARD"})
    assert requirement.is_satisfied_by({"EDIT", "ADVANCED"})
    assert not requirement.is_satisfied_by({"EDIT"})
    assert not requirement.is_satisfied_by({"STANDARD", "ADVANCED"})


def test_display_text_prefers_direct_text_as_fallback_when_resource_key_is_also_present():
    text = AIcDisplayText(text="Edit sites", resource_key="vendor.site.edit.name")
    assert text.fallback == "Edit sites"
